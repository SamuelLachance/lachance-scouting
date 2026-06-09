#!/usr/bin/env python3
"""
Évaluation NORTHSTAR multi-sources — 574 prospects 2026.

Sources pondérées par tier de fiabilité (voir northstar_scoring.SOURCE_TIER_WEIGHTS):
  Tier 1: DPH full, analyses locales
  Tier 2: EP, web scouting (TSN/ESPN/etc.)
  Tier 3: DPH template, Wikipedia
  Tier 4: consensus CSV, heuristiques stats

Usage:
  python scripts/evaluate_players_northstar.py --force
  python scripts/evaluate_players_northstar.py --resume
  python scripts/evaluate_players_northstar.py --workers 16 --batch-save 5
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from draft_config import DEFAULT_DRAFT_YEAR, paths_for_year
from generate_draft_board import Player, load_players
from name_utils import canonical_key
from scripts.fetch_scouting_reports import parse_dph_html, slug_from_name
from northstar_scoring import (
    NORTHSTAR_LABELS,
    NORTHSTAR_WEIGHTS,
    SOURCE_TIER_WEIGHTS,
    _band,
    _confidence_multiplier,
    _report_quality,
    _scoring_text,
    apply_physical_adjustments,
    build_forces_faiblesses,
    build_rationales,
    dph_source_id,
    northstar_overall,
    pillars_from_consensus_rank,
    pillars_from_stats_heuristic,
    pillars_from_text_blob,
    source_label,
    source_tier,
    weighted_merge_sources,
)

_paths = paths_for_year(DEFAULT_DRAFT_YEAR)
OUT = _paths["player_evaluations"]
REPORTS = _paths["scouting_reports"]
RANKINGS = _paths["rankings"]
ANALYSES = _paths["analyses"]
EP_CACHE = _paths["data_dir"] / "ep_cache.json"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
HOST_DELAYS = {
    "draftprospectshockey.com": 0.35,
    "eliteprospects.com": 0.40,
    "www.bing.com": 0.50,
    "html.duckduckgo.com": 0.50,
    "en.wikipedia.org": 0.30,
    "default": 0.35,
}
MAX_RETRIES = 3

_checkpoint_lock = threading.Lock()
_ep_cache_lock = threading.Lock()


class HostRateLimitedFetcher:
    """Per-host rate limiting for parallel player evaluation."""

    def __init__(self) -> None:
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def fetch(self, url: str, *, timeout: int = 20) -> str | None:
        host = urllib.parse.urlparse(url).netloc or "default"
        delay = HOST_DELAYS.get(host, HOST_DELAYS["default"])
        with self._lock:
            elapsed = time.monotonic() - self._last.get(host, 0.0)
            if elapsed < delay:
                time.sleep(delay - elapsed)
        req = urllib.request.Request(
            url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"},
        )
        for attempt in range(MAX_RETRIES):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    body = r.read().decode("utf-8", "replace")
                    with self._lock:
                        self._last[host] = time.monotonic()
                    return body
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < MAX_RETRIES - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                return None
            except Exception:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(1.0)
                    continue
                return None
        return None


def load_checkpoint() -> dict:
    if OUT.exists():
        return json.loads(OUT.read_text(encoding="utf-8"))
    return {"meta": {"version": 2, "total": 0, "done": 0}, "players": {}}


def save_checkpoint(data: dict) -> None:
    with _checkpoint_lock:
        data["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
        data["meta"]["version"] = 2
        data["meta"]["source_tier_weights"] = SOURCE_TIER_WEIGHTS
        data["meta"]["done"] = sum(
            1 for p in data.get("players", {}).values() if p.get("status") == "done"
        )
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_reports() -> dict:
    if REPORTS.exists():
        return json.loads(REPORTS.read_text(encoding="utf-8"))
    return {}


def load_consensus_map() -> dict[str, int | None]:
    if not RANKINGS.exists():
        return {}
    rows = json.loads(RANKINGS.read_text(encoding="utf-8"))
    out: dict[str, int | None] = {}
    for row in rows:
        cr = row.get("Rang_Consensus")
        if cr in (None, "N/A", ""):
            out[canonical_key(row["Nom"])] = None
        else:
            out[canonical_key(row["Nom"])] = int(cr)
    return out


def load_analysis_index() -> dict[str, Path]:
    if not ANALYSES.exists():
        return {}
    index: dict[str, Path] = {}
    for md in ANALYSES.glob("*.md"):
        stem = md.stem
        name_part = re.sub(r"^\d+_", "", stem).replace("_", " ")
        index[canonical_key(name_part)] = md
    return index


def load_ep_cache() -> dict:
    if EP_CACHE.exists():
        return json.loads(EP_CACHE.read_text(encoding="utf-8"))
    return {}


def save_ep_cache(cache: dict) -> None:
    with _ep_cache_lock:
        EP_CACHE.parent.mkdir(parents=True, exist_ok=True)
        EP_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_analysis_md(text: str) -> str:
    parts: list[str] = []
    section = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("## Résumé exécutif"):
            section = "resume"
            continue
        if line.startswith("## Thèse star") or line.startswith("## Thèse upside"):
            section = "thesis"
            continue
        if line.startswith("## Forces"):
            section = "forces"
            continue
        if line.startswith("## Faiblesses"):
            section = "weaknesses"
            continue
        if line.startswith("## ") and section:
            section = None
            continue
        if section in ("resume", "thesis") and line and not line.startswith("|"):
            parts.append(line)
        elif section == "forces" and line.startswith("- "):
            parts.append(line[2:])
        elif section == "weaknesses" and line.startswith("- "):
            parts.append(line[2:])
    return " ".join(parts)


def find_ep_id(fetcher: HostRateLimitedFetcher, name: str, cache: dict) -> str | None:
    key = canonical_key(name)
    if key in cache and cache[key].get("ep_id"):
        return cache[key]["ep_id"]
    q = urllib.parse.quote(f"site:eliteprospects.com/player {name} 2026")
    html = fetcher.fetch(f"https://html.duckduckgo.com/html/?q={q}")
    if not html:
        html = fetcher.fetch(f"https://www.bing.com/search?q={q}")
    if not html:
        return None
    m = re.search(r"eliteprospects\.com/player/(\d+)/", html)
    if m:
        cache[key] = {"ep_id": m.group(1), "found_at": datetime.now(timezone.utc).isoformat()}
        return m.group(1)
    return None


def parse_ep_page(html: str) -> dict:
    out: dict[str, Any] = {"stats_lines": [], "bio": {}, "snippets": []}
    stat_rows = re.findall(r'<td[^>]*class="[^"]*stat[^"]*"[^>]*>(\d+)</td>', html)
    if len(stat_rows) >= 4:
        out["latest_stats"] = {
            "gp": int(stat_rows[0]),
            "g": int(stat_rows[1]),
            "a": int(stat_rows[2]),
            "pts": int(stat_rows[3]),
        }
    for pat, key in [
        (r'"height"\s*:\s*"([^"]+)"', "height"),
        (r'"weight"\s*:\s*(\d+)', "weight"),
        (r'"position"\s*:\s*"([^"]+)"', "position"),
        (r'"team"\s*:\s*"([^"]+)"', "team"),
    ]:
        m = re.search(pat, html, re.I)
        if m:
            out["bio"][key] = m.group(1)
    for m in re.finditer(r'<p[^>]*>([^<]{40,300})</p>', html):
        t = unescape(re.sub(r"\s+", " ", m.group(1))).strip()
        if any(k in t.lower() for k in ("draft", "scout", "skating", "project", "elite", "prospect")):
            out["snippets"].append(t)
    out["snippets"] = out["snippets"][:5]
    return out


def fetch_ep_data(
    fetcher: HostRateLimitedFetcher,
    name: str,
    ep_cache: dict,
) -> dict:
    key = canonical_key(name)
    cached = ep_cache.get(key, {})
    if cached.get("parsed"):
        return cached["parsed"]
    ep_id = cached.get("ep_id") or find_ep_id(fetcher, name, ep_cache)
    if not ep_id:
        return {}
    slug = name.lower().replace(" ", "-").replace("'", "")
    html = fetcher.fetch(f"https://www.eliteprospects.com/player/{ep_id}/{slug}")
    if not html:
        return {}
    data = parse_ep_page(html)
    data["ep_id"] = ep_id
    ep_cache[key] = {
        **ep_cache.get(key, {}),
        "ep_id": ep_id,
        "parsed": data,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    return data


def fetch_dph_live(player: Player, report: dict, fetcher: HostRateLimitedFetcher) -> dict:
    href = report.get("href") or f"/prospects/{slug_from_name(player.first, player.last)}"
    if report.get("fetched") and report.get("grade") and _report_quality(report) == "full":
        return report
    html = fetcher.fetch(
        href if href.startswith("http") else f"https://draftprospectshockey.com{href}",
    )
    if not html or "rank-pill" not in html:
        alt = f"/prospects/{slug_from_name(player.first.split()[0], player.last)}"
        if alt != href:
            html = fetcher.fetch(f"https://draftprospectshockey.com{alt}")
            if html and "rank-pill" in html:
                href = alt
    if html and ("Scouting Report" in html or "scout-text" in html or "rank-pill" in html):
        parsed = parse_dph_html(html)
        return {**report, **parsed, "href": href, "fetched": True, "source": "dph"}
    return report


def wikipedia_snippet(fetcher: HostRateLimitedFetcher, name: str) -> tuple[str, str]:
    search_url = (
        "https://en.wikipedia.org/w/api.php?"
        f"action=query&list=search&srsearch={urllib.parse.quote(name + ' ice hockey')}&format=json"
    )
    try:
        html = fetcher.fetch(search_url, timeout=20)
        if not html:
            return "", ""
        data = json.loads(html)
        hits = data.get("query", {}).get("search", [])
        if not hits:
            return "", ""
        title = hits[0]["title"]
        q2 = urllib.parse.quote(title.replace(" ", "_"))
        url2 = (
            "https://en.wikipedia.org/w/api.php?"
            f"action=query&prop=extracts&exintro&explaintext&titles={q2}&format=json"
        )
        html2 = fetcher.fetch(url2, timeout=20)
        if html2:
            data2 = json.loads(html2)
            for p in data2.get("query", {}).get("pages", {}).values():
                extract = p.get("extract", "")
                if extract and len(extract) > 80:
                    return extract[:800], f"https://en.wikipedia.org/wiki/{q2}"
    except Exception:
        pass
    return "", ""


def web_search_snippets(fetcher: HostRateLimitedFetcher, name: str, draft_year: int = 2026) -> list[str]:
    q = urllib.parse.quote(f'"{name}" NHL draft {draft_year} scouting')
    html = fetcher.fetch(f"https://www.bing.com/search?q={q}")
    snippets: list[str] = []
    if html:
        for m in re.finditer(r'class="b_caption"[^>]*>.*?<p>(.*?)</p>', html, re.DOTALL | re.I):
            t = unescape(re.sub(r"<[^>]+>", " ", m.group(1)))
            t = re.sub(r"\s+", " ", t).strip()
            if len(t) > 30 and name.split()[-1].lower() in t.lower():
                snippets.append(t[:400])
    if not snippets:
        html = fetcher.fetch(f"https://html.duckduckgo.com/html/?q={q}")
        if html:
            for m in re.finditer(
                r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div|span)>',
                html, re.DOTALL | re.I,
            ):
                t = unescape(re.sub(r"<[^>]+>", " ", m.group(1)))
                t = re.sub(r"\s+", " ", t).strip()
                if len(t) > 30:
                    snippets.append(t[:400])
    return list(dict.fromkeys(snippets))[:4]


def merge_stats(dph_stats: dict, ep_data: dict) -> dict:
    stats = dict(dph_stats or {})
    latest = (ep_data or {}).get("latest_stats") or {}
    if latest.get("gp") and (not stats.get("gp") or latest["gp"] > stats.get("gp", 0)):
        stats.update(latest)
    return stats


def build_pillar_rationales(
    dims: dict[str, float],
    evidence: dict[str, list[str]],
    report: dict,
    cov: str,
    source_mix: list[dict],
    player_name: str,
) -> dict[str, dict]:
    pillars: dict[str, dict] = {}
    top_sources = sorted(source_mix, key=lambda x: -x.get("weight_share", 0))[:3]
    src_txt = ", ".join(
        f"{s['label']} (T{s['tier']}, {s['weight_share']*100:.0f}%)"
        for s in top_sources
    ) or "heuristique"

    for dim, label in NORTHSTAR_LABELS.items():
        v = dims.get(dim, 5.0)
        b, d = _band(v)
        w = int(NORTHSTAR_WEIGHTS[dim] * 100)
        ev = evidence.get(dim, [])
        ev_txt = ", ".join(f"«{e}»" for e in ev[:4]) if ev else "inférence contextuelle"
        rationale = (
            f"**{v}/10 — {b.capitalize()}** ({d}). Pilier NORTHSTAR ({w}%). "
            f"Signaux: {ev_txt}. Sources pondérées: {src_txt}."
        )
        if cov == "full":
            rationale += " Confiance: multi-sources substantielles."
        elif cov == "partial":
            rationale += " Confiance: couverture partielle."
        elif cov == "thin":
            rationale += " Confiance: sources limitées."
        else:
            rationale += " Confiance: fallback heuristique."
        pillars[dim] = {"score": v, "rationale": rationale, "evidence": ev[:5]}
    return pillars


def evaluate_player(
    player: Player,
    report: dict,
    fetcher: HostRateLimitedFetcher,
    *,
    consensus_rank: int | None,
    analysis_text: str,
    ep_cache: dict,
    skip_web: bool = False,
    skip_ep: bool = False,
    refresh_dph: bool = False,
) -> dict:
    contributions: list[dict[str, Any]] = []
    source_ids: list[str] = []

    if refresh_dph:
        report = fetch_dph_live(player, report, fetcher)

    merged_report = dict(report or {})
    cov_dph = _report_quality(merged_report) if merged_report else "none"

    # --- Tier 1/2/3: DPH (any cached metadata) ---
    dph_text = _scoring_text(merged_report) if merged_report else ""
    if dph_text.strip() or merged_report.get("grade") or merged_report.get("dph_rank"):
        sid = dph_source_id(merged_report, cov_dph) if dph_text.strip() else "dph_partial"
        dims, ev = pillars_from_text_blob(
            dph_text or f"grade {merged_report.get('grade')} rank {merged_report.get('dph_rank')}",
            pos=player.pos,
            report=merged_report,
            apply_coverage=(sid == "dph_full"),
        )
        quality = {"dph_full": 1.0, "dph_partial": 0.75, "dph_thin": 0.5}.get(sid, 0.5)
        contributions.append({
            "source_id": sid,
            "pillars": dims,
            "evidence": ev,
            "quality": quality,
            "snippet": (dph_text or str(merged_report.get("grade", "")))[:200],
            "url": merged_report.get("href", ""),
        })
        source_ids.append(sid)

    # --- Tier 1: local analysis markdown ---
    if analysis_text.strip():
        dims, ev = pillars_from_text_blob(
            analysis_text, pos=player.pos, report=merged_report, apply_coverage=False,
        )
        contributions.append({
            "source_id": "local_analysis",
            "pillars": dims,
            "evidence": ev,
            "quality": 0.95,
            "snippet": analysis_text[:200],
        })
        source_ids.append("local_analysis")

    # Parallel fetch: EP, web, wiki
    ep_data: dict = {}
    web_snippets: list[str] = []
    wiki_text, wiki_url = "", ""

    tasks: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        if not skip_ep:
            tasks["ep"] = pool.submit(fetch_ep_data, fetcher, player.full_name, ep_cache)
        if not skip_web:
            tasks["web"] = pool.submit(web_search_snippets, fetcher, player.full_name)
            tasks["wiki"] = pool.submit(wikipedia_snippet, fetcher, player.full_name)

        for key, fut in tasks.items():
            try:
                result = fut.result(timeout=50)
            except Exception:
                result = None
            if key == "ep" and result:
                ep_data = result
            elif key == "web" and result:
                web_snippets = result
            elif key == "wiki" and result:
                wiki_text, wiki_url = result

    merged_stats = merge_stats(merged_report.get("stats") or {}, ep_data)
    if merged_stats:
        merged_report["stats"] = merged_stats

    # --- Tier 2: Elite Prospects ---
    if ep_data:
        ep_parts = list(ep_data.get("snippets") or [])
        bio = ep_data.get("bio") or {}
        if bio.get("team"):
            ep_parts.append(f"plays for {bio['team']}")
        ep_text = " ".join(ep_parts)
        if ep_text.strip() or merged_stats:
            dims, ev = pillars_from_text_blob(
                ep_text or f"elite prospects {player.full_name}",
                pos=player.pos,
                report={**merged_report, "stats": merged_stats},
                stats=merged_stats,
                apply_coverage=False,
            )
            contributions.append({
                "source_id": "elite_prospects",
                "pillars": dims,
                "evidence": ev,
                "quality": 0.85 if ep_text else 0.6,
                "snippet": ep_text[:200] if ep_text else f"stats GP={merged_stats.get('gp')}",
                "url": f"https://www.eliteprospects.com/player/{ep_data.get('ep_id')}/",
            })
            source_ids.append("elite_prospects")

    # --- Tier 2: web scouting ---
    extra_web = list(web_snippets)
    if wiki_text:
        extra_web.insert(0, wiki_text[:400])
    if extra_web:
        web_text = " ".join(extra_web)
        dims, ev = pillars_from_text_blob(
            web_text, pos=player.pos, report=merged_report, apply_coverage=False,
        )
        contributions.append({
            "source_id": "web_scouting",
            "pillars": dims,
            "evidence": ev,
            "quality": min(1.0, 0.5 + len(extra_web) * 0.12),
            "snippet": extra_web[0][:200],
        })
        source_ids.append("web_scouting")

    # --- Tier 3: Wikipedia (standalone if not merged into web) ---
    if wiki_text and "wikipedia" not in source_ids:
        dims, ev = pillars_from_text_blob(wiki_text, pos=player.pos, apply_coverage=False)
        contributions.append({
            "source_id": "wikipedia",
            "pillars": dims,
            "evidence": ev,
            "quality": 0.7,
            "snippet": wiki_text[:200],
            "url": wiki_url,
        })
        source_ids.append("wikipedia")

    # --- Tier 4: consensus rank ---
    if consensus_rank is not None:
        dims = pillars_from_consensus_rank(consensus_rank, player.pos)
        contributions.append({
            "source_id": "consensus_rank",
            "pillars": dims,
            "evidence": {},
            "quality": 0.9,
            "snippet": f"consensus rank #{consensus_rank}",
        })
        source_ids.append("consensus_rank")

    # --- Tier 4: stats heuristic (always — low-weight anchor) ---
    dims = pillars_from_stats_heuristic(
        merged_stats,
        merged_report.get("league", ""),
        player.pos,
        player.height,
        player.weight,
    )
    contributions.append({
        "source_id": "stats_heuristic",
        "pillars": dims,
        "evidence": {},
        "quality": 0.8 if merged_stats.get("gp") else 0.35,
        "snippet": f"production GP={merged_stats.get('gp')} PTS={merged_stats.get('pts')}",
    })
    source_ids.append("stats_heuristic")

    if not contributions:
        contributions.append({
            "source_id": "stats_heuristic",
            "pillars": {k: 5.0 for k in NORTHSTAR_WEIGHTS},
            "evidence": {},
            "quality": 0.3,
            "snippet": "neutral fallback — no external evidence",
        })
        source_ids.append("stats_heuristic")

    dims, evidence, source_mix, cov = weighted_merge_sources(contributions)
    dims = apply_physical_adjustments(dims, player.pos, player.height, player.weight)

    pillars = build_pillar_rationales(
        dims, evidence, merged_report, cov, source_mix, player.full_name,
    )
    forces, faiblesses = build_forces_faiblesses(
        dims, merged_report, evidence, player.pos, player.height, player.weight, cov,
    )

    spi = northstar_overall(dims) * _confidence_multiplier(cov)
    spi = round(min(99.9, max(0, spi)), 2)

    return {
        "status": "done",
        "name": player.full_name,
        "key": player.key,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "confidence": cov,
        "report_coverage": cov,
        "sources": source_ids,
        "source_mix": source_mix,
        "pillars": pillars,
        "forces": forces,
        "faiblesses": faiblesses,
        "spi": spi,
        "notes": merged_report.get("report") or merged_report.get("meta_description") or "",
        "projection": merged_report.get("projection") or "",
        "raw": {
            "dph_grade": report.get("grade"),
            "dph_rank": report.get("dph_rank"),
            "dph_league": report.get("league"),
            "consensus_rank": consensus_rank,
            "stats": merged_stats,
            "ep": {k: v for k, v in ep_data.items() if k != "parsed"} if ep_data else {},
            "web_snippets": web_snippets,
            "wiki_words": len(wiki_text.split()) if wiki_text else 0,
            "contributions": len(contributions),
        },
    }


def _safe_print(msg: str, **kwargs) -> None:
    try:
        print(msg, **kwargs, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"), **kwargs, flush=True)


def evaluate_one(
    player: Player,
    report: dict,
    fetcher: HostRateLimitedFetcher,
    consensus_map: dict,
    analysis_index: dict,
    ep_cache: dict,
    args: argparse.Namespace,
) -> tuple[str, dict]:
    analysis_path = analysis_index.get(player.key)
    analysis_text = ""
    if analysis_path and analysis_path.exists():
        analysis_text = parse_analysis_md(analysis_path.read_text(encoding="utf-8"))
    ev = evaluate_player(
        player,
        report,
        fetcher,
        consensus_rank=consensus_map.get(player.key),
        analysis_text=analysis_text,
        ep_cache=ep_cache,
        skip_web=args.skip_web,
        skip_ep=args.skip_ep,
        refresh_dph=not args.no_refresh_dph,
    )
    return player.key, ev


def main() -> None:
    parser = argparse.ArgumentParser(description="Évaluation NORTHSTAR multi-sources 2026")
    parser.add_argument("--force", action="store_true", help="Réévaluer même si déjà done")
    parser.add_argument("--resume", action="store_true", help="Reprendre depuis checkpoint")
    parser.add_argument("--limit", type=int, default=0, help="Max joueurs (0=tous)")
    parser.add_argument("--skip-web", action="store_true", help="Ignorer recherche web")
    parser.add_argument("--skip-ep", action="store_true", help="Ignorer Elite Prospects")
    parser.add_argument("--no-refresh-dph", action="store_true", help="Ne pas re-fetch DPH")
    parser.add_argument("--player", type=str, default="", help="Un seul joueur (nom)")
    parser.add_argument("--batch-save", type=int, default=5, help="Sauvegarder tous les N joueurs")
    parser.add_argument("--workers", type=int, default=12, help="Workers parallèles")
    args = parser.parse_args()

    t0 = time.monotonic()
    players = load_players()
    reports = load_reports()
    checkpoint = load_checkpoint()
    consensus_map = load_consensus_map()
    analysis_index = load_analysis_index()
    ep_cache = load_ep_cache()
    fetcher = HostRateLimitedFetcher()

    checkpoint.setdefault("meta", {})["total"] = len(players)
    checkpoint.setdefault("meta", {})["source_tier_weights"] = SOURCE_TIER_WEIGHTS
    checkpoint.setdefault("players", {})

    if args.player:
        targets = [p for p in players if args.player.lower() in p.full_name.lower()]
        if not targets:
            print(f"Joueur introuvable: {args.player}")
            sys.exit(1)
    else:
        targets = players

    pending: list[Player] = []
    skipped = 0
    for player in targets:
        if args.limit and len(pending) >= args.limit:
            break
        if args.resume and not args.force and checkpoint["players"].get(player.key, {}).get("status") == "done":
            skipped += 1
            continue
        pending.append(player)

    processed = 0
    errors = 0
    workers = max(1, min(args.workers, 20))

    _safe_print(
        f"NORTHSTAR multi-source: {len(pending)} à traiter, {skipped} ignorés, "
        f"{workers} workers, tiers={SOURCE_TIER_WEIGHTS}",
    )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                evaluate_one, p, reports.get(p.key, {}), fetcher,
                consensus_map, analysis_index, ep_cache, args,
            ): p
            for p in pending
        }
        for i, fut in enumerate(as_completed(futures), 1):
            player = futures[fut]
            try:
                key, ev = fut.result()
                checkpoint["players"][key] = ev
                if ev.get("status") == "done":
                    processed += 1
                    mix = ev.get("source_mix") or []
                    top = mix[0]["label"] if mix else "?"
                    _safe_print(
                        f"[{i}/{len(pending)}] {player.full_name} SPI={ev['spi']} "
                        f"cov={ev['confidence']} src={len(ev.get('sources', []))} top={top}",
                    )
                else:
                    errors += 1
            except Exception as e:
                errors += 1
                checkpoint["players"][player.key] = {
                    "status": "error",
                    "name": player.full_name,
                    "error": str(e),
                }
                _safe_print(f"[{i}/{len(pending)}] {player.full_name} ERROR: {e}")

            if processed % args.batch_save == 0:
                save_checkpoint(checkpoint)

    save_ep_cache(ep_cache)
    save_checkpoint(checkpoint)
    elapsed = time.monotonic() - t0
    done = checkpoint["meta"]["done"]
    _safe_print(
        f"\nTerminé: {done}/{len(players)} évalués "
        f"({processed} cette session, {skipped} ignorés, {errors} erreurs) "
        f"en {elapsed:.1f}s ({elapsed/max(processed,1):.1f}s/joueur)",
    )


if __name__ == "__main__":
    main()
