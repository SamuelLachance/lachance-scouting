#!/usr/bin/env python3
"""
Évaluation NORTHSTAR détaillée — 574 prospects 2026.

Pour chaque joueur:
  1. Rapport DPH (cache)
  2. Elite Prospects (stats, bio)
  3. Recherche web (snippets scouting)
  4. Score 7 piliers avec rationales + preuves
  5. Checkpoint immédiat (reprise: --resume)

Usage:
  python scripts/evaluate_players_northstar.py
  python scripts/evaluate_players_northstar.py --resume
  python scripts/evaluate_players_northstar.py --limit 50 --skip-web
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from draft_config import DEFAULT_DRAFT_YEAR, paths_for_year
from generate_draft_board import Player, load_players
from name_utils import canonical_key
from scripts.fetch_scouting_reports import fetch_page, parse_dph_html, slug_from_name
from northstar_scoring import (
    NORTHSTAR_LABELS,
    NORTHSTAR_WEIGHTS,
    _apply_coverage_penalty,
    _band,
    _confidence_multiplier,
    _dph_rank_score,
    _grade_score,
    _league_score,
    _lex_score,
    _merge_scores,
    _production_score,
    _report_quality,
    _scoring_text,
    build_forces_faiblesses,
    build_rationales,
    northstar_overall,
    parse_height,
    parse_weight,
)

_paths = paths_for_year(DEFAULT_DRAFT_YEAR)
OUT = _paths["player_evaluations"]
REPORTS = _paths["scouting_reports"]

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
REQUEST_DELAY = 0.85
MAX_RETRIES = 3


class RateLimitedFetcher:
    def __init__(self, delay: float = REQUEST_DELAY) -> None:
        self.delay = delay
        self._last = 0.0

    def fetch(self, url: str, *, timeout: int = 25) -> str | None:
        elapsed = time.monotonic() - self._last
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        for attempt in range(MAX_RETRIES):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    self._last = time.monotonic()
                    return r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < MAX_RETRIES - 1:
                    time.sleep(5 * (attempt + 1))
                    continue
                return None
            except Exception:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2)
                    continue
                return None
        return None


def load_checkpoint() -> dict:
    if OUT.exists():
        return json.loads(OUT.read_text(encoding="utf-8"))
    return {"meta": {"version": 1, "total": 0, "done": 0}, "players": {}}


def save_checkpoint(data: dict) -> None:
    data["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    data["meta"]["done"] = sum(
        1 for p in data.get("players", {}).values() if p.get("status") == "done"
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_reports() -> dict:
    if REPORTS.exists():
        return json.loads(REPORTS.read_text(encoding="utf-8"))
    return {}


def find_ep_id(fetcher: RateLimitedFetcher, name: str) -> str | None:
    q = urllib.parse.quote(f"site:eliteprospects.com/player {name} 2026")
    html = fetcher.fetch(f"https://html.duckduckgo.com/html/?q={q}")
    if not html:
        return None
    m = re.search(r"eliteprospects\.com/player/(\d+)/", html)
    return m.group(1) if m else None


def parse_ep_page(html: str) -> dict:
    out: dict[str, Any] = {"stats_lines": [], "bio": {}}
    # Season stats rows
    for row in re.findall(
        r'<tr[^>]*>.*?<td[^>]*>([^<]*(?:Regular|Playoffs|Total)[^<]*)</td>.*?</tr>',
        html, re.DOTALL | re.I,
    ):
        nums = re.findall(r'<td[^>]*>(\d+)</td>', row)
        if len(nums) >= 4:
            out["stats_lines"].append({"gp": int(nums[0]), "g": int(nums[1]), "a": int(nums[2]), "pts": int(nums[3])})

    # JSON-LD / meta
    for pat, key in [
        (r'"height"\s*:\s*"([^"]+)"', "height"),
        (r'"weight"\s*:\s*(\d+)', "weight"),
        (r'"position"\s*:\s*"([^"]+)"', "position"),
        (r'"team"\s*:\s*"([^"]+)"', "team"),
    ]:
        m = re.search(pat, html, re.I)
        if m:
            out["bio"][key] = m.group(1)

    # Latest season from stat blocks
    stat_rows = re.findall(
        r'<td[^>]*class="[^"]*stat[^"]*"[^>]*>(\d+)</td>',
        html,
    )
    if len(stat_rows) >= 4:
        out["latest_stats"] = {
            "gp": int(stat_rows[0]),
            "g": int(stat_rows[1]) if len(stat_rows) > 1 else 0,
            "a": int(stat_rows[2]) if len(stat_rows) > 2 else 0,
            "pts": int(stat_rows[3]) if len(stat_rows) > 3 else 0,
        }

    # Text snippets from page
    snippets = []
    for m in re.finditer(r'<p[^>]*>([^<]{40,300})</p>', html):
        t = unescape(re.sub(r"\s+", " ", m.group(1))).strip()
        if any(k in t.lower() for k in ("draft", "scout", "skating", "project", "elite", "prospect")):
            snippets.append(t)
    out["snippets"] = snippets[:5]
    return out


def fetch_dph_live(player: Player, report: dict, fetcher: RateLimitedFetcher) -> dict:
    """Rafraîchit la fiche DPH si absente ou template."""
    href = report.get("href") or f"/prospects/{slug_from_name(player.first, player.last)}"
    if report.get("fetched") and report.get("grade") and report.get("stats"):
        return report
    html = fetcher.fetch(
        href if href.startswith("http") else f"https://draftprospectshockey.com{href}"
    )
    if not html or "rank-pill" not in html:
        alt = f"/prospects/{slug_from_name(player.first.split()[0], player.last)}"
        if alt != href:
            html = fetcher.fetch(f"https://draftprospectshockey.com{alt}")
            if html and "rank-pill" in html:
                href = alt
    if html and ("Scouting Report" in html or "scout-text" in html or "rank-pill" in html):
        parsed = parse_dph_html(html)
        out = {**report, **parsed, "href": href, "fetched": True, "source": "dph"}
        out["has_full_report"] = bool(parsed.get("report") or parsed.get("strengths") or parsed.get("grade"))
        return out
    return report


def wikipedia_snippet(fetcher: RateLimitedFetcher, name: str) -> tuple[str, list[str]]:
    """Extrait texte intro Wikipedia + URLs trouvées."""
    q = urllib.parse.quote(name.replace(" ", "_"))
    url = (
        "https://en.wikipedia.org/w/api.php?"
        f"action=query&prop=extracts&exintro&explaintext&titles={q}&format=json"
    )
    try:
        html = fetcher.fetch(url, timeout=20)
        if not html:
            return "", []
        data = json.loads(html)
        pages = data.get("query", {}).get("pages", {})
        for p in pages.values():
            extract = p.get("extract", "")
            if extract and len(extract) > 80:
                return extract[:800], [f"https://en.wikipedia.org/wiki/{q}"]
    except Exception:
        pass
    # Search fallback
    search_url = (
        "https://en.wikipedia.org/w/api.php?"
        f"action=query&list=search&srsearch={urllib.parse.quote(name + ' ice hockey')}&format=json"
    )
    try:
        html = fetcher.fetch(search_url, timeout=20)
        if html:
            data = json.loads(html)
            hits = data.get("query", {}).get("search", [])
            if hits:
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
                        if extract:
                            return extract[:800], [f"https://en.wikipedia.org/wiki/{q2}"]
    except Exception:
        pass
    return "", []


def bing_search_snippets(fetcher: RateLimitedFetcher, name: str, draft_year: int = 2026) -> list[str]:
    q = urllib.parse.quote(f'"{name}" NHL draft {draft_year} scouting')
    html = fetcher.fetch(f"https://www.bing.com/search?q={q}")
    if not html:
        return []
    snippets = []
    for m in re.finditer(r'<p[^>]*>([^<]{30,400})</p>', html):
        t = unescape(re.sub(r"\s+", " ", m.group(1))).strip()
        if name.split()[-1].lower() in t.lower() and any(
            k in t.lower() for k in ("draft", "scout", "prospect", "nhl", "skating", "elite")
        ):
            snippets.append(t[:400])
    # Bing result descriptions
    for m in re.finditer(r'class="b_caption"[^>]*>.*?<p>(.*?)</p>', html, re.DOTALL | re.I):
        t = unescape(re.sub(r"<[^>]+>", " ", m.group(1)))
        t = re.sub(r"\s+", " ", t).strip()
        if len(t) > 30:
            snippets.append(t[:400])
    return list(dict.fromkeys(snippets))[:4]


def web_search_snippets(fetcher: RateLimitedFetcher, name: str, draft_year: int = 2026) -> list[str]:
    snippets = bing_search_snippets(fetcher, name, draft_year)
    if snippets:
        return snippets
    q = urllib.parse.quote(f'"{name}" NHL draft {draft_year} scouting report')
    html = fetcher.fetch(f"https://html.duckduckgo.com/html/?q={q}")
    if not html:
        return []
    for m in re.finditer(r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div|span)>', html, re.DOTALL | re.I):
        t = unescape(re.sub(r"<[^>]+>", " ", m.group(1)))
        t = re.sub(r"\s+", " ", t).strip()
        if len(t) > 30 and name.split()[-1].lower() in t.lower():
            snippets.append(t[:400])
    return list(dict.fromkeys(snippets))[:4]


# Signaux web scouting → boost léger quand DPH template contredit sources externes
WEB_STAR_SIGNALS = [
    (r"top[- ]?10", 2.0), (r"top[- ]?five", 2.5), (r"first overall", 3.0),
    (r"#1 overall", 3.0), (r"generational", 2.8), (r"franchise", 2.0),
    (r"elite prospect", 1.8), (r"top prospect", 1.5), (r"calder", 1.5), (r"all-star", 1.8),
    (r"hockey sense", 1.5), (r"hockey iq", 1.5), (r"translatable", 1.2),
    (r"shl", 1.0), (r"ncaa", 0.8), (r"world junior", 1.0),
    (r"under.?18", 0.8), (r"ntdp", 0.8), (r"ushl", 0.6),
]


def apply_web_signal_boost(dims: dict[str, float], extra_text: str) -> dict[str, float]:
    """Ajuste les piliers si le texte web/wikipedia contient des signaux forts absents du DPH."""
    if not extra_text or len(extra_text.split()) < 20:
        return dims
    text = extra_text.lower()
    boost = 0.0
    for pattern, weight in WEB_STAR_SIGNALS:
        if re.search(pattern, text, re.I):
            boost += weight * 0.15
    if boost <= 0:
        return dims
    out = dims.copy()
    out["star_ceiling"] = round(min(10, out["star_ceiling"] + boost), 1)
    if re.search(r"hockey (sense|iq)|vision|playmaker|processing", text, re.I):
        out["hockey_iq"] = round(min(10, out["hockey_iq"] + boost * 0.6), 1)
    if re.search(r"skating|speed|acceleration|edges|dynamic", text, re.I):
        out["skating_engine"] = round(min(10, out["skating_engine"] + boost * 0.4), 1)
    if re.search(r"goal|scoring|points|production|offensive", text, re.I):
        out["offensive_star_power"] = round(min(10, out["offensive_star_power"] + boost * 0.5), 1)
    if re.search(r"shl|ncaa|world junior|international|men", text, re.I):
        out["competition_proof"] = round(min(10, out["competition_proof"] + boost * 0.4), 1)
    return out


def merge_stats(dph_stats: dict, ep_data: dict) -> dict:
    stats = dict(dph_stats or {})
    latest = (ep_data or {}).get("latest_stats") or {}
    if latest.get("gp") and (not stats.get("gp") or latest["gp"] > stats.get("gp", 0)):
        stats.update(latest)
    return stats


def build_extra_text(ep_data: dict, web_snippets: list[str]) -> str:
    parts: list[str] = []
    for s in (ep_data or {}).get("snippets") or []:
        parts.append(s)
    parts.extend(web_snippets or [])
    bio = (ep_data or {}).get("bio") or {}
    if bio.get("team"):
        parts.append(f"plays for {bio['team']}")
    return " ".join(parts)


def score_pillars(
    report: dict,
    extra_text: str,
    pos: str,
    height: str,
    weight: str,
) -> tuple[dict[str, float], dict[str, list[str]], str]:
    """Score 7 piliers à partir de DPH + texte externe enrichi."""
    enriched = dict(report)
    if extra_text:
        enriched = {**report, "web_evidence": extra_text}

    text = _scoring_text(report)
    if extra_text:
        text = f"{text} {extra_text.lower()}"

    lex: dict[str, float] = {}
    evidence: dict[str, list[str]] = {}
    for dim in NORTHSTAR_WEIGHTS:
        s, ev = _lex_score(dim, text)
        lex[dim] = s
        evidence[dim] = ev

    grade = _grade_score(report.get("grade", ""))
    league = _league_score(report.get("league", ""), text)
    stats = report.get("stats") or {}
    prod = _production_score(stats, pos)
    dph_r = _dph_rank_score(report.get("dph_rank"))
    cov = _report_quality(report)

    dims = _merge_scores(lex, grade, league, prod, dph_r, pos)
    dims = _apply_coverage_penalty(dims, cov, grade)

    h = parse_height(height)
    if h >= 76 and dims["star_ceiling"] >= 7.5:
        dims["star_ceiling"] = min(10, dims["star_ceiling"] + 0.2)
    if h <= 69 and "D" not in pos.upper():
        dims["star_ceiling"] = max(1, dims["star_ceiling"] - 0.3)

    return dims, evidence, cov


def build_pillar_rationales(
    dims: dict[str, float],
    evidence: dict[str, list[str]],
    report: dict,
    cov: str,
    sources: list[str],
    web_snippets: list[str],
) -> dict[str, dict]:
    """Construit rationales détaillées par pilier avec citations."""
    base_rationales = build_rationales(
        {**dims, "report_coverage": cov},
        full_name=report.get("name", ""),
        pos="",
        report=report,
        evidence=evidence,
    )
    pillars: dict[str, dict] = {}
    snippet = (report.get("report") or report.get("meta_description") or "")[:200]
    web_cite = web_snippets[0][:120] + "…" if web_snippets else ""

    for dim, label in NORTHSTAR_LABELS.items():
        v = dims.get(dim, 5.0)
        b, d = _band(v)
        w = int(NORTHSTAR_WEIGHTS[dim] * 100)
        ev = evidence.get(dim, [])
        ev_txt = ", ".join(f"«{e}»" for e in ev[:4]) if ev else "inférence contextuelle"
        src_parts = []
        if report.get("grade"):
            src_parts.append(f"DPH grade {report['grade']}")
        if report.get("dph_rank"):
            src_parts.append(f"DPH #{report['dph_rank']}")
        if "elite_prospects" in sources:
            src_parts.append("Elite Prospects")
        if "web" in sources and web_cite:
            src_parts.append(f"web: \"{web_cite}\"")
        src_txt = "; ".join(src_parts) if src_parts else "contexte limité"

        rationale = (
            f"**{v}/10 — {b.capitalize()}** ({d}). Pilier NORTHSTAR ({w}%). "
            f"Signaux: {ev_txt}. Sources: {src_txt}."
        )
        if snippet and dim == "star_ceiling":
            rationale += f' Extrait DPH: "{snippet[:100]}…".'
        if cov == "full":
            rationale += " Confiance: rapport DPH substantiel."
        elif cov == "partial":
            rationale += " Confiance: métadonnées partielles."
        elif cov == "thin":
            rationale += " Confiance: page DPH template."
        else:
            rationale += " Confiance: aucun rapport DPH."

        pillars[dim] = {
            "score": v,
            "rationale": rationale,
            "evidence": ev[:5],
        }
    return pillars


def evaluate_player(
    player: Player,
    report: dict,
    fetcher: RateLimitedFetcher,
    *,
    skip_web: bool = False,
    skip_ep: bool = False,
    refresh_dph: bool = True,
) -> dict:
    sources: list[str] = []
    if refresh_dph:
        report = fetch_dph_live(player, report, fetcher)
    if report:
        sources.append("dph")

    ep_data: dict = {}
    web_snippets: list[str] = []
    wiki_text = ""

    if not skip_ep:
        ep_id = find_ep_id(fetcher, player.full_name)
        if ep_id:
            html = fetcher.fetch(
                f"https://www.eliteprospects.com/player/{ep_id}/"
                f"{player.full_name.lower().replace(' ', '-')}"
            )
            if html:
                ep_data = parse_ep_page(html)
                ep_data["ep_id"] = ep_id
                sources.append("elite_prospects")

    if not skip_web:
        needs_enrichment = (
            not report.get("fetched")
            or not report.get("grade")
            or _report_quality(report) in ("thin", "none")
        )
        if needs_enrichment:
            web_snippets = web_search_snippets(fetcher, player.full_name)
            if web_snippets:
                sources.append("web")
            wiki_text, _wiki_urls = wikipedia_snippet(fetcher, player.full_name)
            if wiki_text:
                sources.append("wikipedia")
                web_snippets = [wiki_text[:400]] + web_snippets
        elif _report_quality(report) != "full":
            web_snippets = bing_search_snippets(fetcher, player.full_name)
            if web_snippets:
                sources.append("web")

    extra_text = build_extra_text(ep_data, web_snippets)
    if wiki_text:
        extra_text = f"{extra_text} {wiki_text}"
    merged_report = dict(report)
    merged_stats = merge_stats(report.get("stats") or {}, ep_data)
    if merged_stats:
        merged_report["stats"] = merged_stats

    dims, evidence, cov = score_pillars(
        merged_report, extra_text, player.pos, player.height, player.weight,
    )
    dims = apply_web_signal_boost(dims, extra_text)

    # Boost confidence if web/EP added substantive info
    if cov in ("thin", "none") and (web_snippets or ep_data.get("snippets")):
        cov = "partial"
    if cov == "partial" and len(extra_text.split()) > 80:
        cov = "full" if merged_stats else "partial"

    pillars = build_pillar_rationales(
        dims, evidence, merged_report, cov, sources, web_snippets,
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
        "sources": sources,
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
            "stats": merged_stats,
            "ep": ep_data,
            "web_snippets": web_snippets,
            "extra_text_words": len(extra_text.split()),
        },
    }


def _safe_print(msg: str, **kwargs) -> None:
    try:
        print(msg, **kwargs, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"), **kwargs, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Évaluation NORTHSTAR détaillée 2026")
    parser.add_argument("--force", action="store_true", help="Réévaluer même si déjà done")
    parser.add_argument("--resume", action="store_true", help="Reprendre depuis checkpoint")
    parser.add_argument("--limit", type=int, default=0, help="Max joueurs à traiter (0=tous)")
    parser.add_argument("--skip-web", action="store_true", help="Ignorer recherche web")
    parser.add_argument("--skip-ep", action="store_true", help="Ignorer Elite Prospects")
    parser.add_argument("--no-refresh-dph", action="store_true", help="Ne pas re-fetch DPH")
    parser.add_argument("--player", type=str, default="", help="Évaluer un seul joueur (nom)")
    parser.add_argument("--batch-save", type=int, default=1, help="Sauvegarder tous les N joueurs")
    args = parser.parse_args()

    players = load_players()
    reports = load_reports()
    checkpoint = load_checkpoint()
    checkpoint.setdefault("meta", {})["total"] = len(players)
    checkpoint.setdefault("players", {})

    fetcher = RateLimitedFetcher()

    if args.player:
        targets = [p for p in players if args.player.lower() in p.full_name.lower()]
        if not targets:
            print(f"Joueur introuvable: {args.player}")
            sys.exit(1)
    else:
        targets = players

    processed = 0
    skipped = 0
    for i, player in enumerate(targets):
        if args.limit and processed >= args.limit:
            break
        if args.resume and not args.force and checkpoint["players"].get(player.key, {}).get("status") == "done":
            skipped += 1
            continue

        report = reports.get(player.key, {})
        _safe_print(f"[{i+1}/{len(targets)}] {player.full_name}...", end=" ")
        try:
            ev = evaluate_player(
                player, report, fetcher,
                skip_web=args.skip_web,
                skip_ep=args.skip_ep,
                refresh_dph=not args.no_refresh_dph,
            )
            checkpoint["players"][player.key] = ev
            processed += 1
            _safe_print(f"SPI={ev['spi']} cov={ev['confidence']} src={','.join(ev['sources'])}")
        except Exception as e:
            checkpoint["players"][player.key] = {
                "status": "error",
                "name": player.full_name,
                "error": str(e),
            }
            _safe_print(f"ERROR: {e}")

        if processed % args.batch_save == 0 or args.batch_save == 1:
            save_checkpoint(checkpoint)

    save_checkpoint(checkpoint)
    done = checkpoint["meta"]["done"]
    print(f"\nTerminé: {done}/{len(players)} évalués ({processed} cette session, {skipped} ignorés)")


if __name__ == "__main__":
    main()
