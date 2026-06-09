#!/usr/bin/env python3
"""Télécharge les portraits joueurs depuis Elite Prospects → site/images/players/{year}/."""
from __future__ import annotations

import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from draft_config import DEFAULT_DRAFT_YEAR, paths_for_year
from build_site_data import slug_from_file
from photo_fetch import (
    download_photo,
    elite_prospects_photo,
    load_ep_draft_players,
    load_photo_manifest,
    resolve_ep_id,
    save_photo_manifest,
    wiki_batch_lookup,
)
from portrait_svg import REAL_EXTENSIONS

EP_DELAY = 0.9
EP_WORKERS = 4
WIKI_BATCH_SIZE = 40
WIKI_BATCH_DELAY = 2.5
EP_SOURCES = {"eliteprospects", "eliteprospects-search"}


def log(msg: str) -> None:
    print(msg, flush=True)


_rate_lock = threading.Lock()
_last_fetch = 0.0


def rate_limit(delay: float = EP_DELAY) -> None:
    global _last_fetch
    with _rate_lock:
        now = time.monotonic()
        wait = delay - (now - _last_fetch)
        if wait > 0:
            time.sleep(wait)
        _last_fetch = time.monotonic()


def find_real_file(img_root: Path, slug: str) -> Path | None:
    for ext in REAL_EXTENSIONS:
        path = img_root / f"{slug}{ext}"
        if path.exists() and path.stat().st_size > 500:
            return path
    return None


def is_ep_cached(img_root: Path, slug: str, manifest: dict) -> bool:
    entry = manifest.get(slug, {})
    source = entry.get("source") or ""
    if source not in EP_SOURCES:
        return False
    return find_real_file(img_root, slug) is not None


def remove_real_files(img_root: Path, slug: str) -> None:
    for ext in REAL_EXTENSIONS:
        path = img_root / f"{slug}{ext}"
        path.unlink(missing_ok=True)


def update_manifest_entry(
    manifest: dict,
    slug: str,
    name: str,
    year: int,
    saved: Path,
    source_url: str,
    ep_id: int | None,
) -> None:
    manifest[slug] = {
        "name": name,
        "local": f"./images/players/{year}/{saved.name}",
        "sourceUrl": source_url,
        "source": "eliteprospects",
        "generated": False,
    }
    if ep_id:
        manifest[slug]["epId"] = ep_id


def fetch_one(
    *,
    slug: str,
    name: str,
    birth: str | None,
    year: int,
    img_root: Path,
    ep_id: int | None,
    draft_players,
) -> tuple[str, bool, int | None, str | None, Path | None]:
    rate_limit()
    hit = elite_prospects_photo(name, birth, ep_id, draft_players=draft_players)
    resolved_id = hit.ep_id or ep_id
    if not hit.url:
        return slug, False, resolved_id, None, None
    saved = download_photo(hit.url, img_root / slug)
    if not saved:
        return slug, False, resolved_id, hit.url, None
    for f in img_root.glob(slug + ".*"):
        if f != saved:
            f.unlink(missing_ok=True)
    return slug, True, resolved_id, hit.url, saved


def main() -> None:
    year = DEFAULT_DRAFT_YEAR
    paths = paths_for_year(year)
    rankings = json.loads(paths["rankings"].read_text(encoding="utf-8"))
    manifest_path = paths["data_dir"] / "player_photos.json"
    draft_cache = paths["data_dir"] / "ep_draft_index.json"
    img_root = BASE / "site" / "images" / "players" / str(year)
    img_root.mkdir(parents=True, exist_ok=True)
    manifest = load_photo_manifest(manifest_path)

    draft_players = load_ep_draft_players(cache_path=draft_cache)
    log(f"EP Draft Center index: {len(draft_players)} joueurs")

    ep_cached = 0
    pending: list[tuple[str, str, str | None, int | None]] = []
    for p in rankings:
        slug = slug_from_file(p.get("Fichier_Local", p["Nom"].lower().replace(" ", "-")))
        name = p["Nom"]
        birth = p.get("Date_Naissance") or None
        ep_id = manifest.get(slug, {}).get("epId")

        if is_ep_cached(img_root, slug, manifest):
            real = find_real_file(img_root, slug)
            update_manifest_entry(
                manifest,
                slug,
                name,
                year,
                real,
                manifest[slug].get("sourceUrl") or "",
                ep_id,
            )
            ep_cached += 1
            continue

        if find_real_file(img_root, slug):
            remove_real_files(img_root, slug)
        pending.append((slug, name, birth, ep_id))

    log(f"EP déjà en cache: {ep_cached}/{len(rankings)} — à traiter: {len(pending)}")

    ep_ids: dict[str, int] = {}
    for slug, name, birth, known_id in pending:
        resolved = resolve_ep_id(name, birth, known_id, draft_players=draft_players)
        if resolved:
            ep_ids[slug] = resolved

    still_missing = [
        (slug, name, birth)
        for slug, name, birth, _ in pending
        if slug not in ep_ids
    ]
    log(f"IDs EP (draft center): {len(ep_ids)}/{len(pending)}")

    for batch_start in range(0, len(still_missing), WIKI_BATCH_SIZE):
        batch = still_missing[batch_start : batch_start + WIKI_BATCH_SIZE]
        if not batch:
            break
        log(f"Wikipedia EP IDs {batch_start + 1}-{batch_start + len(batch)}/{len(still_missing)}")
        wiki_hits = wiki_batch_lookup(batch, delay=WIKI_BATCH_DELAY)
        for slug, _, _ in batch:
            hit = wiki_hits.get(slug)
            if hit and hit.ep_id:
                ep_ids[slug] = int(hit.ep_id)

    log(f"IDs EP totaux: {len(ep_ids)}/{len(pending)}")

    fetched = 0
    results: dict[str, tuple[bool, int | None, str | None, Path | None]] = {}
    with ThreadPoolExecutor(max_workers=EP_WORKERS) as pool:
        futures = {
            pool.submit(
                fetch_one,
                slug=slug,
                name=name,
                birth=birth,
                year=year,
                img_root=img_root,
                ep_id=ep_ids.get(slug),
                draft_players=draft_players,
            ): slug
            for slug, name, birth, _ in pending
        }
        done = 0
        for fut in as_completed(futures):
            slug = futures[fut]
            try:
                s, ok, ep_id, url, saved = fut.result()
                results[s] = (ok, ep_id, url, saved)
                if ok:
                    fetched += 1
            except Exception:
                results[slug] = (False, ep_ids.get(slug), None, None)
            done += 1
            if done % 50 == 0:
                log(f"  EP fetch {done}/{len(pending)} — {fetched} photos")

    for slug, name, birth, _ in pending:
        ok, ep_id, url, saved = results.get(slug, (False, ep_ids.get(slug), None, None))
        if ok and saved:
            update_manifest_entry(manifest, slug, name, year, saved, url or "", ep_id)
        else:
            entry = manifest.setdefault(slug, {"name": name})
            if ep_id:
                entry["epId"] = ep_id
            entry.pop("sourceUrl", None)
            entry.pop("source", None)
            entry["generated"] = True
            entry["local"] = None

    save_photo_manifest(manifest_path, manifest)
    log(f"EP photos téléchargées: {fetched} nouvelles ({ep_cached + fetched} total EP)")

    sys.path.insert(0, str(BASE / "scripts"))
    from generate_player_portraits import ensure_portraits

    stats = ensure_portraits(year)
    save_photo_manifest(manifest_path, manifest)

    ep_total = ep_cached + fetched
    svg_total = stats["generated"]
    log(
        f"Terminé: {ep_total} EP, {svg_total} SVG, "
        f"{len(rankings) - ep_total - svg_total} autres"
    )


if __name__ == "__main__":
    main()
