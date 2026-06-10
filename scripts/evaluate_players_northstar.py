#!/usr/bin/env python3
"""
Évaluation NORTHSTAR multi-sources — 574 prospects 2026.

Agrégation par fiabilité source: poids fixes par type, redistribution égale
des sources absentes vers les sources disponibles, qualité texte en multiplicateur.
Cache par joueur: data/drafts/2026/source_cache/{player_key}.json

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
import xml.etree.ElementTree as ET
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
    MIN_SOURCE_ATTEMPTS,
    NORTHSTAR_LABELS,
    NORTHSTAR_WEIGHTS,
    SOURCE_TIER_WEIGHTS,
    _band,
    _confidence_multiplier,
    _report_quality,
    _scoring_text,
    apply_physical_adjustments,
    build_forces_faiblesses,
    compute_text_quality,
    dph_source_id,
    pillars_from_consensus_rank,
    pillars_from_stats_heuristic,
    pillars_from_text_blob,
    source_count_confidence_multiplier,
    weighted_merge_sources,
)
from truth_engine import compute_evidence_confidence, truth_spi
from scouting_fetch import enrich_with_full_text, pick_best_result

_paths = paths_for_year(DEFAULT_DRAFT_YEAR)
OUT = _paths["player_evaluations"]
REPORTS = _paths["scouting_reports"]
RANKINGS = _paths["rankings"]
ANALYSES = _paths["analyses"]
EP_CACHE = _paths["data_dir"] / "ep_cache.json"
SOURCE_CACHE_DIR = _paths["data_dir"] / "source_cache"

DOMAIN_SOURCE_MAP: dict[str, str] = {
    "draftprospectshockey.com": "dph_full",
    "eliteprospects.com": "elite_prospects",
    "tsn.ca": "tsn",
    "espn.com": "espn",
    "nhl.com": "nhl_com",
    "sportsnet.ca": "sportsnet",
    "flocountry.tv": "flohockey",
    "flohockey.tv": "flohockey",
    "puckpedia.com": "puckpedia",
    "dailyfaceoff.com": "daily_faceoff",
    "mckeenshockey.com": "mckeens",
    "theathletic.com": "the_athletic",
    "reddit.com": "reddit",
    "hfboards.com": "hfboards",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "youtube.com": "youtube",
    "hockeydb.com": "hockeydb",
    "en.wikipedia.org": "wikipedia",
    "smahtscouting.com": "smaht_scouting",
    "smahtscouting.wordpress.com": "smaht_scouting",
    "theleafsnation.com": "team_blog",
    "torontosun.com": "sportsnet",
    "cbc.ca": "web_scouting",
    "thehockeywriters.com": "web_scouting",
    "dobberprospects.com": "mckeens",
    "neutralzone.com": "web_scouting",
    "thehockeywriters.com": "web_scouting",
    "dobberprospects.com": "mckeens",
    "ushl.com": "team_blog",
    "chl.ca": "team_blog",
}

TARGETED_QUERIES: list[tuple[str, str]] = [
    ("tsn", 'site:tsn.ca "{name}" 2026 NHL draft'),
    ("espn", 'site:espn.com "{name}" NHL draft 2026'),
    ("nhl_com", 'site:nhl.com "{name}" draft prospect'),
    ("sportsnet", 'site:sportsnet.ca "{name}" 2026 draft'),
    ("flohockey", 'site:flohockey.tv "{name}" draft prospect'),
    ("puckpedia", 'site:puckpedia.com "{name}" draft'),
    ("daily_faceoff", 'site:dailyfaceoff.com "{name}" prospect'),
    ("mckeens", 'site:mckeenshockey.com "{name}" scouting'),
    ("the_athletic", 'site:theathletic.com "{name}" NHL draft'),
    ("smaht_scouting", 'site:smahtscouting.com "{name}" 2026'),
    ("pronman", '"{name}" Corey Pronman 2026 draft'),
    ("scott_wheeler", '"{name}" Scott Wheeler TSN draft'),
    ("reddit", 'site:reddit.com/r/hockey "{name}" 2026 draft'),
    ("hfboards", 'site:hfboards.com "{name}" 2026 draft'),
    ("twitter", 'site:twitter.com "{name}" NHL draft 2026'),
    ("youtube", 'site:youtube.com "{name}" scouting report 2026'),
    ("hockeydb", 'site:hockeydb.com "{name}"'),
    ("thehockeywriters", 'site:thehockeywriters.com "{name}" 2026 draft'),
    ("dobberprospects", 'site:dobberprospects.com "{name}" scouting'),
    ("neutralzone", 'site:neutralzone.com "{name}" 2026'),
]

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
_source_cache_lock = threading.Lock()


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
        data["meta"]["version"] = 7
        data["meta"]["weighting"] = "web_scouting_v7"
        data["meta"]["weight_formula"] = (
            "Validated web scouting + DPH full-text; no circular rankings bootstrap"
        )
        data["meta"]["min_source_attempts"] = MIN_SOURCE_ATTEMPTS
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


def load_rankings_index() -> dict[str, dict]:
    if not RANKINGS.exists():
        return {}
    rows = json.loads(RANKINGS.read_text(encoding="utf-8"))
    return {canonical_key(row["Nom"]): row for row in rows}


_RANKING_DIM_MAP = {
    "star_ceiling": ("Plafond_Etoile", "Plafond_Elite"),
    "hockey_iq": ("IQ_Elite", "IQ_Realisation"),
    "skating_engine": ("Moteur_Patinage", "Patinage_Upside"),
    "offensive_star_power": ("Pouvoir_Offensif", "Outils_Offensifs", "Creation_Jeu"),
    "competition_proof": ("Preuve_Competition",),
    "character_compete": ("Competitivite", "Variance_Positive"),
    "development_arc": ("Arc_Developpement", "Trajectoire"),
}


def pillars_from_rankings_row(row: dict) -> dict[str, float]:
    dims: dict[str, float] = {}
    for dim, keys in _RANKING_DIM_MAP.items():
        val = None
        for k in keys:
            if row.get(k) not in (None, "", "N/A"):
                val = float(row[k])
                break
        dims[dim] = round(min(10, max(1, val if val is not None else 5.0)), 1)
    return dims


def gather_dph_sources(
    report: dict,
    player: Player,
) -> list[dict[str, Any]]:
    """Split DPH cache into granular sources — no single DPH blob dominance."""
    out: list[dict[str, Any]] = []
    url = report.get("href", "")

    if report.get("report"):
        c = contribution_from_text("dph_report", report["report"], player=player, report=report, url=url)
        if c:
            out.append(c)
    if report.get("strengths"):
        c = contribution_from_text(
            "dph_strengths", " ".join(report["strengths"]),
            player=player, report=report, url=url,
        )
        if c:
            out.append(c)
    if report.get("weaknesses"):
        c = contribution_from_text(
            "dph_weaknesses", " ".join(report["weaknesses"]),
            player=player, report=report, url=url,
        )
        if c:
            out.append(c)
    if report.get("projection"):
        c = contribution_from_text(
            "dph_projection", report["projection"],
            player=player, report=report, url=url,
        )
        if c:
            out.append(c)
    tag_parts = []
    if report.get("grade"):
        tag_parts.append(f"grade {report['grade']}")
    for t in report.get("tags") or []:
        tag_parts.append(t)
    if report.get("meta_description") and not report.get("report"):
        tag_parts.append(report["meta_description"])
    if tag_parts:
        c = contribution_from_text(
            "dph_tags", " ".join(tag_parts),
            player=player, report=report, url=url,
        )
        if c:
            out.append(c)
    if not out and (_scoring_text(report).strip() or report.get("grade")):
        sid = dph_source_id(report, _report_quality(report))
        c = contribution_from_text(
            sid,
            _scoring_text(report) or f"grade {report.get('grade')}",
            player=player, report=report, url=url,
        )
        if c:
            out.append(c)
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


def _cache_key(player_key: str) -> str:
    return re.sub(r"[^\w\-]", "-", player_key.replace(" ", "-").lower())


def load_source_cache(player_key: str) -> dict:
    path = SOURCE_CACHE_DIR / f"{_cache_key(player_key)}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_source_cache(player_key: str, data: dict) -> None:
    with _source_cache_lock:
        SOURCE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = SOURCE_CACHE_DIR / f"{_cache_key(player_key)}.json"
        data["cached_at"] = datetime.now(timezone.utc).isoformat()
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def domain_to_source_id(domain: str) -> str:
    d = domain.lower().removeprefix("www.")
    for key, sid in DOMAIN_SOURCE_MAP.items():
        if key in d:
            return sid
    if any(x in d for x in (".ca", ".com", ".org", ".net")):
        if any(x in d for x in ("nittany", "pennstate", "gophers", "badgers", "huskies")):
            return "team_blog"
        return "web_scouting"
    return "web_scouting"


def _parse_bing_rss(xml_text: str, name: str) -> list[dict]:
    """Bing RSS feed — reliable when HTML SERP is captcha-blocked."""
    results: list[dict] = []
    last_name = name.split()[-1].lower()
    first = name.split()[0].lower() if name.split() else ""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return results
    for item in root.findall(".//item"):
        title = unescape(item.findtext("title", "") or "")
        desc = unescape(item.findtext("description", "") or "")
        link = item.findtext("link", "") or ""
        blob = f"{title}. {desc}".strip()
        if len(blob) < 20:
            continue
        if last_name not in blob.lower() and last_name not in link.lower():
            continue
        if first and first not in blob.lower() and first not in link.lower():
            continue
        domain = urllib.parse.urlparse(link).netloc if link else "bing_rss"
        results.append({
            "url": link,
            "snippet": blob[:500],
            "domain": domain,
            "title": title[:120],
        })
    return results


def _parse_bing_results(html: str, name: str) -> list[dict]:
    results: list[dict] = []
    last_name = name.split()[-1].lower()
    for m in re.finditer(
        r'<li[^>]*class="b_algo"[^>]*>(.*?)</li>',
        html, re.DOTALL | re.I,
    ):
        block = m.group(1)
        url_m = re.search(r'<a[^>]+href="(https?://[^"]+)"', block, re.I)
        snip_m = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL | re.I)
        if not url_m:
            continue
        url = url_m.group(1)
        snippet = ""
        if snip_m:
            snippet = unescape(re.sub(r"<[^>]+>", " ", snip_m.group(1)))
            snippet = re.sub(r"\s+", " ", snippet).strip()
        if len(snippet) < 25:
            continue
        if last_name not in snippet.lower() and last_name not in url.lower():
            continue
        domain = urllib.parse.urlparse(url).netloc
        results.append({"url": url, "snippet": snippet[:500], "domain": domain})
    return results


def _parse_ddg_results(html: str, name: str) -> list[dict]:
    results: list[dict] = []
    last_name = name.split()[-1].lower()
    for m in re.finditer(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>.*?</a>.*?'
        r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div|span)>',
        html, re.DOTALL | re.I,
    ):
        url = m.group(1)
        snippet = unescape(re.sub(r"<[^>]+>", " ", m.group(2)))
        snippet = re.sub(r"\s+", " ", snippet).strip()
        if len(snippet) < 25:
            continue
        if last_name not in snippet.lower():
            continue
        domain = urllib.parse.urlparse(url).netloc
        results.append({"url": url, "snippet": snippet[:500], "domain": domain})
    if not results:
        for m in re.finditer(
            r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div|span)>',
            html, re.DOTALL | re.I,
        ):
            t = unescape(re.sub(r"<[^>]+>", " ", m.group(1)))
            t = re.sub(r"\s+", " ", t).strip()
            if len(t) > 30:
                results.append({"url": "", "snippet": t[:500], "domain": "ddg"})
    return results


def search_web_results(
    fetcher: HostRateLimitedFetcher,
    query: str,
    *,
    name: str = "",
    max_results: int = 15,
    use_ddg_fallback: bool = True,
) -> list[dict]:
    q = urllib.parse.quote(query)
    results: list[dict] = []
    rss = fetcher.fetch(f"https://www.bing.com/search?format=rss&q={q}", timeout=15)
    if rss:
        results.extend(_parse_bing_rss(rss, name or query))
    if len(results) < max(2, max_results // 3):
        html = fetcher.fetch(f"https://www.bing.com/search?q={q}", timeout=12)
        if html:
            results.extend(_parse_bing_results(html, name or query))
    if use_ddg_fallback and len(results) < max(2, max_results // 3):
        html = fetcher.fetch(f"https://html.duckduckgo.com/html/?q={q}", timeout=12)
        if html:
            results.extend(_parse_ddg_results(html, name or query))
    seen: set[str] = set()
    out: list[dict] = []
    for r in results:
        key = r.get("url") or r.get("snippet", "")[:80]
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
        if len(out) >= max_results:
            break
    return out


def contribution_from_text(
    source_id: str,
    text: str,
    *,
    player: Player,
    report: dict,
    stats: dict | None = None,
    url: str = "",
    fetched_at: str | None = None,
) -> dict[str, Any] | None:
    if not text or not str(text).strip():
        return None
    text_q = compute_text_quality(text, fetched_at=fetched_at)
    dims, ev = pillars_from_text_blob(
        text,
        pos=player.pos,
        report=report,
        stats=stats,
        apply_coverage=False,
    )
    return {
        "source_id": source_id,
        "pillars": dims,
        "evidence": ev,
        "quality": text_q,
        "text_quality": text_q,
        "snippet": str(text)[:2000],
        "url": url,
    }


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
    q = urllib.parse.quote(name)
    html = fetcher.fetch(
        f"https://www.eliteprospects.com/search/player?q={q}",
        timeout=25,
    )
    if html:
        m = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>',
            html, re.DOTALL,
        )
        if m:
            try:
                data = json.loads(m.group(1))
                players = (
                    data.get("props", {})
                    .get("pageProps", {})
                    .get("players", [])
                )
                last = name.split()[-1].lower()
                for p in players:
                    pname = (p.get("name") or "").lower()
                    if last in pname and name.split()[0].lower() in pname:
                        ep_id = str(p.get("id", ""))
                        if ep_id:
                            cache[key] = {
                                "ep_id": ep_id,
                                "found_at": datetime.now(timezone.utc).isoformat(),
                            }
                            return ep_id
                if players and players[0].get("id"):
                    ep_id = str(players[0]["id"])
                    cache[key] = {
                        "ep_id": ep_id,
                        "found_at": datetime.now(timezone.utc).isoformat(),
                    }
                    return ep_id
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
    q2 = urllib.parse.quote(f"site:eliteprospects.com/player {name} 2026")
    html = fetcher.fetch(f"https://html.duckduckgo.com/html/?q={q2}")
    if not html:
        html = fetcher.fetch(f"https://www.bing.com/search?q={q2}")
    if html:
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


def _fetch_one_targeted(
    fetcher: HostRateLimitedFetcher,
    source_id: str,
    query: str,
    name: str,
) -> dict | None:
    results = search_web_results(
        fetcher, query, name=name, max_results=6, use_ddg_fallback=True,
    )
    hit = pick_best_result(results, source_id, name)
    if not hit:
        return None
    return enrich_with_full_text(fetcher, hit, source_id=source_id, name=name)


def gather_targeted_sources(
    fetcher: HostRateLimitedFetcher,
    name: str,
    *,
    cache: dict | None = None,
    skip_web: bool = False,
    refresh_web: bool = False,
) -> list[dict]:
    """Run site-specific scouting queries in parallel — one contribution per hit."""
    cache = cache or {}
    cached = cache.get("targeted") or {}
    if cached.get("results") and not refresh_web:
        return cached["results"]
    if skip_web:
        return []
    contributions: list[dict] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(
                _fetch_one_targeted,
                fetcher, source_id, query_tpl.format(name=name), name,
            ): source_id
            for source_id, query_tpl in TARGETED_QUERIES
        }
        for fut in as_completed(futures):
            try:
                item = fut.result(timeout=30)
            except Exception:
                item = None
            if item:
                contributions.append(item)
    cache["targeted"] = {
        "results": contributions,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    return contributions


def gather_general_scouting(
    fetcher: HostRateLimitedFetcher,
    name: str,
    *,
    draft_year: int = 2026,
    cache: dict | None = None,
    skip_web: bool = False,
    refresh_web: bool = False,
) -> list[dict]:
    """Bing/DDG scouting search — split by domain into separate sources."""
    cache = cache or {}
    cached = cache.get("general_scouting")
    if cached and cached.get("by_source") and not refresh_web:
        return cached["by_source"]
    if skip_web:
        return []
    query = f'"{name}" {draft_year} draft scouting report'
    results = search_web_results(fetcher, query, name=name, max_results=15)
    by_source: dict[str, list[dict]] = {}
    for r in results:
        domain = r.get("domain") or "web"
        sid = domain_to_source_id(domain)
        if sid.startswith("dph"):
            sid = "web_scouting"
        by_source.setdefault(sid, []).append(r)
    grouped: list[dict] = []
    for sid, items in by_source.items():
        text = " ".join(i["snippet"] for i in items if i.get("snippet"))
        if text.strip():
            grouped.append({
                "source_id": sid,
                "text": text,
                "url": items[0].get("url", ""),
                "count": len(items),
            })
    cache["general_scouting"] = {
        "by_source": grouped,
        "raw_count": len(results),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    return grouped


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
    top_sources = sorted(source_mix, key=lambda x: -x.get("weight_share", 0))[:5]
    src_txt = ", ".join(
        f"{s['label']} ({s['weight_share']*100:.0f}%)"
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
    rankings_row: dict | None,
    analysis_text: str,
    ep_cache: dict,
    skip_web: bool = False,
    skip_ep: bool = False,
    refresh_dph: bool = False,
    refresh_web: bool = False,
) -> dict:
    contributions: list[dict[str, Any]] = []
    source_ids: list[str] = []
    attempts = 0
    player_cache = load_source_cache(player.key)

    if refresh_dph:
        report = fetch_dph_live(player, report, fetcher)

    merged_report = dict(report or {})

    # --- DPH granular sources (report, strengths, weaknesses, projection, tags) ---
    attempts += 1
    for c in gather_dph_sources(merged_report, player):
        sid = c["source_id"]
        if sid not in source_ids:
            contributions.append(c)
            source_ids.append(sid)

    ep_data: dict = {}
    wiki_text, wiki_url = "", ""
    targeted_raw: list[dict] = []
    general_raw: list[dict] = []

    tasks: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        if not skip_ep:
            tasks["ep"] = pool.submit(fetch_ep_data, fetcher, player.full_name, ep_cache)
            attempts += 1
        if not skip_web:
            tasks["wiki"] = pool.submit(wikipedia_snippet, fetcher, player.full_name)
            attempts += 1
            tasks["targeted"] = pool.submit(
                gather_targeted_sources, fetcher, player.full_name,
                cache=player_cache, skip_web=skip_web, refresh_web=refresh_web,
            )
            attempts += len(TARGETED_QUERIES)
            tasks["general"] = pool.submit(
                gather_general_scouting, fetcher, player.full_name,
                cache=player_cache, skip_web=skip_web, refresh_web=refresh_web,
            )
            attempts += 1

        for key, fut in tasks.items():
            try:
                result = fut.result(timeout=120)
            except Exception:
                result = None
            if key == "ep" and result:
                ep_data = result
            elif key == "wiki" and result:
                wiki_text, wiki_url = result
            elif key == "targeted" and result:
                targeted_raw = result
            elif key == "general" and result:
                general_raw = result

    merged_stats = merge_stats(merged_report.get("stats") or {}, ep_data)
    if merged_stats:
        merged_report["stats"] = merged_stats

    # --- Elite Prospects ---
    if ep_data:
        ep_parts = list(ep_data.get("snippets") or [])
        bio = ep_data.get("bio") or {}
        if bio.get("team"):
            ep_parts.append(f"plays for {bio['team']}")
        ep_text = " ".join(ep_parts) or f"elite prospects {player.full_name}"
        c = contribution_from_text(
            "elite_prospects", ep_text,
            player=player,
            report={**merged_report, "stats": merged_stats},
            stats=merged_stats,
            url=f"https://www.eliteprospects.com/player/{ep_data.get('ep_id')}/",
            fetched_at=ep_data.get("fetched_at"),
        )
        if c:
            contributions.append(c)
            source_ids.append("elite_prospects")

    # --- Wikipedia ---
    if wiki_text:
        c = contribution_from_text(
            "wikipedia", wiki_text,
            player=player, report=merged_report,
            url=wiki_url,
        )
        if c:
            contributions.append(c)
            source_ids.append("wikipedia")

    # --- Targeted site searches (each source separate) ---
    for item in targeted_raw:
        sid = item["source_id"]
        if sid in source_ids:
            continue
        c = contribution_from_text(
            sid, item["text"],
            player=player, report=merged_report,
            url=item.get("url", ""),
            fetched_at=player_cache.get("targeted", {}).get("fetched_at"),
        )
        if c:
            contributions.append(c)
            source_ids.append(sid)

    # --- General scouting by domain (validated attribution) ---
    for item in general_raw:
        sid = item["source_id"]
        if sid in source_ids:
            continue
        enriched = enrich_with_full_text(
            fetcher if not skip_web else None,
            {"url": item.get("url", ""), "snippet": item.get("text", "")},
            source_id=sid,
            name=player.full_name,
        )
        if not enriched:
            continue
        c = contribution_from_text(
            sid, enriched["text"],
            player=player, report=merged_report,
            url=enriched.get("url", item.get("url", "")),
            fetched_at=player_cache.get("general_scouting", {}).get("fetched_at"),
        )
        if c:
            contributions.append(c)
            source_ids.append(sid)

    # --- Consensus rank (external market anchor only) ---
    attempts += 1
    if consensus_rank is not None:
        dims = pillars_from_consensus_rank(consensus_rank, player.pos)
        contributions.append({
            "source_id": "consensus_rank",
            "pillars": dims,
            "evidence": {},
            "quality": 0.55,
            "snippet": f"consensus rank #{consensus_rank}",
        })
        source_ids.append("consensus_rank")

    # --- Stats heuristic anchor ---
    attempts += 1
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
        "quality": 0.75 if merged_stats.get("gp") else 0.40,
        "snippet": f"production GP={merged_stats.get('gp')} PTS={merged_stats.get('pts')}",
    })
    source_ids.append("stats_heuristic")

    if not contributions:
        contributions.append({
            "source_id": "stats_heuristic",
            "pillars": {k: 5.0 for k in NORTHSTAR_WEIGHTS},
            "evidence": {},
            "quality": 0.30,
            "snippet": "neutral fallback — no external evidence",
        })
        source_ids.append("stats_heuristic")

    save_source_cache(player.key, {
        **player_cache,
        "player": player.full_name,
        "source_ids": source_ids,
        "attempts": attempts,
    })

    dims, evidence, source_mix, cov = weighted_merge_sources(
        contributions, position=player.pos,
    )
    dims = apply_physical_adjustments(dims, player.pos, player.height, player.weight)

    pillars = build_pillar_rationales(
        dims, evidence, merged_report, cov, source_mix, player.full_name,
    )
    forces, faiblesses = build_forces_faiblesses(
        dims, merged_report, evidence, player.pos, player.height, player.weight, cov,
    )

    n_sources = len(source_mix)
    avg_attr = sum(s.get("attribution", 1.0) for s in source_mix) / max(n_sources, 1)
    conf_score, _ = compute_evidence_confidence(
        n_sources, max(1, n_sources // 2), cov, avg_attr, 0.65,
    )
    spi = (
        truth_spi(dims, player.pos, confidence=conf_score, agreement=0.65)
        * _confidence_multiplier(cov)
        * source_count_confidence_multiplier(n_sources)
    )
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
            "targeted_hits": len(targeted_raw),
            "general_domains": len(general_raw),
            "wiki_words": len(wiki_text.split()) if wiki_text else 0,
            "contributions": len(contributions),
            "source_attempts": attempts,
            "top_source_share": max((s.get("weight_share", 0) for s in source_mix), default=0),
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
    rankings_index: dict,
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
        rankings_row=rankings_index.get(player.key),
        analysis_text=analysis_text,
        ep_cache=ep_cache,
        skip_web=args.skip_web,
        skip_ep=args.skip_ep,
        refresh_dph=not args.no_refresh_dph,
        refresh_web=args.force or args.refresh_web,
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
    parser.add_argument("--refresh-web", action="store_true", help="Ignorer cache web et re-fetch")
    parser.add_argument("--player", type=str, default="", help="Un seul joueur (nom)")
    parser.add_argument("--batch-save", type=int, default=5, help="Sauvegarder tous les N joueurs")
    parser.add_argument("--workers", type=int, default=12, help="Workers parallèles")
    args = parser.parse_args()

    t0 = time.monotonic()
    players = load_players()
    reports = load_reports()
    checkpoint = load_checkpoint()
    consensus_map = load_consensus_map()
    rankings_index = load_rankings_index()
    analysis_index = load_analysis_index()
    ep_cache = load_ep_cache()
    fetcher = HostRateLimitedFetcher()

    checkpoint.setdefault("meta", {})["total"] = len(players)
    checkpoint.setdefault("meta", {})["weighting"] = "reliability_redistributed"
    checkpoint.setdefault("meta", {})["weight_formula"] = (
        "reliability_effective × quality; missing catalog weight redistributed equally"
    )
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
        f"NORTHSTAR multi-source: {len(pending)} a traiter, {skipped} ignores, "
        f"{workers} workers, weighting=reliability_redistributed",
    )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                evaluate_one, p, reports.get(p.key, {}), fetcher,
                consensus_map, rankings_index, analysis_index, ep_cache, args,
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
                    n_src = len(mix)
                    max_sh = max((s.get("weight_share", 0) for s in mix), default=0)
                    top = mix[0]["label"] if mix else "?"
                    _safe_print(
                        f"[{i}/{len(pending)}] {player.full_name} SPI={ev['spi']} "
                        f"cov={ev['confidence']} src={n_src} max={max_sh:.0%} top={top}",
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
