#!/usr/bin/env python3
"""Fetch missing player height/weight from Elite Prospects (+ DPH fallback) and sync rankings."""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from draft_config import DEFAULT_DRAFT_YEAR, paths_for_year
from generate_draft_board import parse_players
from name_utils import canonical_key
from photo_fetch import (
    _get_html,
    _parse_ep_player,
    load_ep_draft_players,
    resolve_ep_id,
)
from player_sizes import (
    is_missing_size,
    normalize_height,
    normalize_weight_lbs,
    size_from_dph_report,
    size_from_ep_player,
)

EP_DELAY = 0.85
EP_WORKERS = 4

_rate_lock = threading.Lock()
_last_fetch = 0.0


def log(msg: str) -> None:
    print(msg, flush=True)


def rate_limit(delay: float = EP_DELAY) -> None:
    global _last_fetch
    with _rate_lock:
        now = time.monotonic()
        wait = delay - (now - _last_fetch)
        if wait > 0:
            time.sleep(wait)
        _last_fetch = time.monotonic()


def load_json(path: Path, default: dict | list | None = None):
    if not path.exists():
        return default if default is not None else {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def count_missing(rankings: list[dict]) -> int:
    return sum(
        1
        for p in rankings
        if is_missing_size(p.get("Taille")) or is_missing_size(p.get("Poids_lbs"))
    )


def _compact_last(name: str) -> str:
    parts = name.replace("-", " ").split()
    return re.sub(r"[^a-z0-9]+", "", parts[-1].lower()) if parts else ""


def _compact_first(name: str) -> str:
    parts = name.replace("-", " ").split()
    return re.sub(r"[^a-z0-9]+", "", parts[0].lower()) if parts else ""


def _edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[-1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def _first_name_match(ours: str, theirs: str) -> bool:
    if not ours or not theirs:
        return False
    if ours == theirs or ours.startswith(theirs) or theirs.startswith(ours):
        return True
    return len(ours) >= 2 and len(theirs) >= 2 and ours[:2] == theirs[:2]


NAME_VARIANTS: dict[str, list[str]] = {
    "Joseph Erickson": ["Joe Erickson"],
    "John Galanek": ["Jack Galanek"],
    "James Rieber": ["Jimmy Rieber"],
    "Elisei Ryabykin": ["Yelisei Ryabykin"],
    "Kent Sauer": ["KJ Sauer"],
    "Theodore Lechner": ["Teddy Lechner"],
    "Lukas Zajic": ["Lucas Zajic"],
    "Tsimafei Tuzin": ["Tim Tuzin"],
    "Casper Juustovaara": ["Casper Juustovaara Karlsson"],
    "Giorgos Pantellas": ["Giorgos Pantelas"],
    "Oleg Kulebiakin": ["Oleg Kulebyakin"],
    "Andrei Molgachev": ["Andrei Molgachyov"],
    "Nikita Voiaga": ["Nikita Voyaga"],
    "Kirill Buzaev": ["Kirill Buzayev"],
    "Thomas Bleyl": ["Tommy Bleyl"],
}


def resolve_ep_id_for_player(
    name: str,
    birth: str | None,
    draft_players,
    ep_index: dict[str, int],
    ep_by_name: dict[str, int],
) -> int | None:
    key = canonical_key(name)
    if key in ep_index:
        return ep_index[key]

    for variant in NAME_VARIANTS.get(name, []):
        vkey = canonical_key(variant)
        if vkey in ep_index:
            return ep_index[vkey]
        if variant in ep_by_name:
            return ep_by_name[variant]

    resolved = resolve_ep_id(name, birth, draft_players=draft_players)
    if resolved:
        return resolved

    ours_last = _compact_last(name)
    ours_first = _compact_first(name)
    best: tuple[int, int, int] | None = None
    for ep_name, ep_id in ep_by_name.items():
        ep_last = _compact_last(ep_name)
        if _edit_distance(ours_last, ep_last) > 2:
            continue
        ep_first = _compact_first(ep_name)
        if not _first_name_match(ours_first, ep_first):
            continue
        dist = _edit_distance(ours_last, ep_last)
        score = dist * 10 + abs(len(ep_name) - len(name))
        if best is None or score < best[0]:
            best = (score, ep_id, len(ep_name))
    return best[1] if best else None


def fetch_ep_size(
    name: str,
    birth: str | None,
    ep_id: int,
) -> tuple[str | None, int | None, dict]:
    rate_limit()
    html = _get_html(f"https://www.eliteprospects.com/player/{ep_id}")
    if not html:
        return None, None, {}
    player = _parse_ep_player(html)
    if not player:
        return None, None, {}
    height, weight = size_from_ep_player(player)
    return height, weight, player


def fetch_one(
    player: dict,
    *,
    draft_players,
    ep_index: dict[str, int],
    ep_by_name: dict[str, int],
    scouting: dict,
    ep_cache: dict,
    meta: dict,
) -> tuple[str, dict]:
    name = player["Nom"]
    key = canonical_key(name)
    birth = (player.get("Date_Naissance") or "").strip() or None

    existing = meta.get(key, {})
    if (
        not is_missing_size(existing.get("height"))
        and not is_missing_size(existing.get("weight"))
    ):
        return key, existing

    height: str | None = None
    weight: int | None = None
    source = existing.get("source")

    # DPH scouting reports (fast, no network if cached)
    report = scouting.get(key, {})
    if report:
        dh, dw = size_from_dph_report(report)
        if dh and dw:
            height, weight, source = dh, dw, "dph"

    # EP cache
    if height is None or weight is None:
        cached = ep_cache.get(key, {})
        parsed = cached.get("parsed") or {}
        bio = parsed.get("bio") or {}
        if bio.get("height") or bio.get("weight"):
            eh = normalize_height(bio.get("height"))
            ew = normalize_weight_lbs(bio.get("weight"))
            height = height or eh
            weight = weight or ew
            if eh or ew:
                source = source or "ep_cache"

    # EP player page
    if height is None or weight is None:
        ep_id = resolve_ep_id_for_player(name, birth, draft_players, ep_index, ep_by_name)
        if ep_id:
            eh, ew, ep_player = fetch_ep_size(name, birth, ep_id)
            if ep_player:
                ep_cache[key] = {
                    **ep_cache.get(key, {}),
                    "ep_id": str(ep_id),
                    "parsed": {
                        "bio": {
                            "height": ep_player.get("height"),
                            "weight": ep_player.get("weight"),
                            "position": ep_player.get("position"),
                        },
                        "ep_id": str(ep_id),
                    },
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }
            height = height or eh
            weight = weight or ew
            if eh or ew:
                source = "eliteprospects"

    entry = {
        "name": name,
        "height": height,
        "weight": weight,
        "source": source,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if height and weight:
        meta[key] = entry
    elif key not in meta:
        meta[key] = entry
    return key, entry


def apply_sizes_to_rankings(rankings: list[dict], meta: dict) -> int:
    updated = 0
    for p in rankings:
        key = canonical_key(p["Nom"])
        m = meta.get(key, {})
        if is_missing_size(p.get("Taille")) and not is_missing_size(m.get("height")):
            p["Taille"] = m["height"]
            updated += 1
        if is_missing_size(p.get("Poids_lbs")) and not is_missing_size(m.get("weight")):
            p["Poids_lbs"] = str(int(m["weight"]))
            updated += 1
    return updated


def apply_sizes_to_tsv(tsv_path: Path, meta: dict) -> int:
    if not tsv_path.exists():
        return 0
    players = parse_players(tsv_path.read_text(encoding="utf-8"))
    updated = 0
    lines: list[str] = []
    for p in players:
        m = meta.get(p.key, {})
        h, w = p.height, p.weight
        if is_missing_size(h) and not is_missing_size(m.get("height")):
            h = m["height"]
            updated += 1
        if is_missing_size(w) and not is_missing_size(m.get("weight")):
            w = str(int(m["weight"]))
            updated += 1
        dob_s = p.birth_date.isoformat() if p.birth_date else ""
        lines.append(
            f"{p.last}, {p.first}\t{p.pos}\t{h}\t{w}\t{p.shoots}\t{p.country}\t{dob_s}"
        )
    tsv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch missing player sizes")
    parser.add_argument("--year", type=int, default=DEFAULT_DRAFT_YEAR)
    parser.add_argument("--workers", type=int, default=EP_WORKERS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    paths = paths_for_year(args.year)
    data_dir = paths["data_dir"]
    rankings_path = paths["rankings"]
    tsv_path = paths["eligible_tsv"]
    meta_path = data_dir / "player_meta.json"
    ep_cache_path = data_dir / "ep_cache.json"
    ep_index_path = data_dir / "ep_draft_index.json"
    scouting_path = data_dir / "scouting_reports.json"

    rankings = load_json(rankings_path, [])
    meta = load_json(meta_path, {})
    ep_cache = load_json(ep_cache_path, {})
    scouting = load_json(scouting_path, {})
    ep_index_raw = load_json(ep_index_path, {})
    ep_index = {
        canonical_key(p["name"]): int(p["id"])
        for p in ep_index_raw.get("players", [])
    }
    ep_by_name = {p["name"]: int(p["id"]) for p in ep_index_raw.get("players", [])}

    before = count_missing(rankings)
    log(f"Before: {before}/{len(rankings)} players missing height or weight")

    draft_players = load_ep_draft_players(cache_path=ep_index_path)
    pending = [
        p
        for p in rankings
        if is_missing_size(p.get("Taille")) or is_missing_size(p.get("Poids_lbs"))
    ]
    log(f"Fetching sizes for {len(pending)} players ({args.workers} workers)...")

    fetched = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                fetch_one,
                p,
                draft_players=draft_players,
                ep_index=ep_index,
                ep_by_name=ep_by_name,
                scouting=scouting,
                ep_cache=ep_cache,
                meta=meta,
            ): p["Nom"]
            for p in pending
        }
        for i, fut in enumerate(as_completed(futures), 1):
            name = futures[fut]
            try:
                key, entry = fut.result()
                if entry.get("height") and entry.get("weight"):
                    fetched += 1
                if i % 25 == 0 or i == len(futures):
                    log(f"  progress: {i}/{len(futures)} ({fetched} resolved)")
            except Exception as e:
                log(f"  WARN {name}: {e}")

    if not args.dry_run:
        save_json(meta_path, meta)
        save_json(ep_cache_path, ep_cache)
        ranking_updates = apply_sizes_to_rankings(rankings, meta)
        save_json(rankings_path, rankings)
        tsv_updates = apply_sizes_to_tsv(tsv_path, meta)
        log(f"Updated rankings fields: {ranking_updates}, TSV fields: {tsv_updates}")

    after = count_missing(rankings)
    log(f"After: {after}/{len(rankings)} players missing height or weight")
    log(f"Resolved this run: {fetched}, meta entries: {len(meta)}")


if __name__ == "__main__":
    main()
