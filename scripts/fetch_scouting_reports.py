#!/usr/bin/env python3
"""
Collecte les rapports de scouting DPH pour chaque prospect 2026.
Parse: grade, report, strengths, weaknesses, projection, stats, ligue.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from html import unescape
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from draft_config import DEFAULT_DRAFT_YEAR, paths_for_year
from generate_draft_board import load_players  # noqa: E402
from name_utils import canonical_key  # noqa: E402
from scripts.fetch_dph_prospects import fetch_dph_prospects  # noqa: E402

_paths = paths_for_year(DEFAULT_DRAFT_YEAR)
OUT = _paths["scouting_reports"]
BASE_URL = "https://draftprospectshockey.com"


def slug_from_name(first: str, last: str) -> str:
    raw = f"{first}-{last}".lower()
    raw = re.sub(r"[^a-z0-9\-']", "", raw.replace("'", "").replace(".", ""))
    return raw.replace("--", "-").strip("-")


def parse_dph_html(html: str) -> dict:
    html = unescape(html)

    def section_text(title: str) -> str:
        m = re.search(
            rf'<div class="section-title">{re.escape(title)}</div>\s*'
            r'(?:<p class="scout-text">([^<]+)</p>|'
            r'<div class="proj-card">.*?<div class="proj-val">([^<]+)</div>)',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        if m:
            return (m.group(1) or m.group(2) or "").strip()
        return ""

    grade_m = re.search(r'Grade:\s*([A-F][+-]?)', html, re.I)
    grade = grade_m.group(1).upper() if grade_m else ""

    tags = re.findall(r'<span class="tag[^"]*">([^<]+)</span>', html)
    tags = [t.strip() for t in tags if not t.lower().startswith("grade:")]

    strengths = re.findall(r'<ul class="strengths-list"><li><strong>([^<]+)</strong></li>', html)
    if not strengths:
        strengths = re.findall(r'<ul class="strengths-list">(.*?)</ul>', html, re.DOTALL)
        if strengths:
            strengths = re.findall(r'<strong>([^<]+)</strong>', strengths[0])

    weaknesses = re.findall(r'<ul class="weaknesses-list"><li>([^<]+)</li>', html)
    if not weaknesses:
        weaknesses = re.findall(r'<ul class="weaknesses-list">(.*?)</ul>', html, re.DOTALL)
        if weaknesses:
            weaknesses = [re.sub(r"<[^>]+>", "", x).strip() for x in re.findall(r"<li>(.*?)</li>", weaknesses[0], re.DOTALL)]

    projection = section_text("NHL Projection")
    report = section_text("Scouting Report")

    desc_m = re.search(r'"description"\s*:\s*"([^"]+)"', html)
    meta_desc = desc_m.group(1) if desc_m else ""

    rank_m = re.search(r'<span class="rank-pill">#(\d+)</span>', html)
    dph_rank = int(rank_m.group(1)) if rank_m else None

    league_m = re.search(r"· ([^·]+) · ([^<]+)</div>", html)
    league = league_m.group(2).strip() if league_m else ""

    stats = {}
    stat_blocks = re.findall(
        r'<div class="stat"><div class="stat-num">([^<]*)</div><div class="stat-lbl">([^<]+)</div></div>',
        html,
    )
    for num, lbl in stat_blocks:
        lbl = lbl.strip().upper()
        if lbl in ("GP", "G", "A", "PTS", "SV%", "GAA"):
            try:
                stats[lbl.lower().replace("%", "pct")] = float(num) if num and num != "-" else None
            except ValueError:
                stats[lbl.lower()] = num

    faq_texts = re.findall(r'<div class="faq-a">([^<]+(?:&#x27;|&amp;|[^<])*)</div>', html)
    faq_blob = " ".join(unescape(t) for t in faq_texts)

    birth_m = re.search(
        r'<div class="bio-lbl">Born</div><div class="bio-val">([^<]+)</div>', html
    )
    birth = birth_m.group(1).strip() if birth_m else ""

    height_m = re.search(
        r'<div class="bio-lbl">Height</div><div class="bio-val">([^<]+)</div>', html
    )
    height = height_m.group(1).strip() if height_m else ""

    weight_m = re.search(
        r'<div class="bio-lbl">Weight</div><div class="bio-val">([^<]+)</div>', html
    )
    weight = weight_m.group(1).strip() if weight_m else ""

    return {
        "grade": grade,
        "tags": tags,
        "report": report or meta_desc,
        "meta_description": meta_desc,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "projection": projection,
        "faq_text": faq_blob,
        "dph_rank": dph_rank,
        "league": league,
        "stats": stats,
        "birth": birth,
        "height": height,
        "weight": weight,
        "has_full_report": bool(report or strengths or grade),
    }


def fetch_page(href: str) -> str | None:
    url = href if href.startswith("http") else BASE_URL + href
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            if r.status != 200:
                return None
            return r.read().decode("utf-8", "replace")
    except Exception:
        return None


def build_href_map() -> dict[str, str]:
    """canonical_key -> DPH href"""
    m: dict[str, str] = {}
    for row in fetch_dph_prospects():
        key = canonical_key(row["name"])
        m[key] = row["href"]
    return m


def main() -> None:
    players = load_players()
    href_map = build_href_map()
    cache: dict = {}
    if OUT.exists():
        cache = json.loads(OUT.read_text(encoding="utf-8"))

    fetched = 0
    for i, p in enumerate(players):
        key = p.key
        if key in cache and cache[key].get("fetched"):
            continue

        href = href_map.get(key) or f"/prospects/{slug_from_name(p.first, p.last)}"
        html = fetch_page(href)
        entry: dict = {
            "name": p.full_name,
            "href": href,
            "source": "dph",
            "fetched": False,
        }

        if html and ("Scouting Report" in html or "scout-text" in html or "rank-pill" in html):
            parsed = parse_dph_html(html)
            entry.update(parsed)
            entry["fetched"] = True
            fetched += 1
        else:
            # fallback: try alternate slug without middle names
            alt = f"/prospects/{slug_from_name(p.first.split()[0], p.last)}"
            if alt != href:
                html2 = fetch_page(alt)
                if html2 and "rank-pill" in html2:
                    parsed = parse_dph_html(html2)
                    entry.update(parsed)
                    entry["href"] = alt
                    entry["fetched"] = True
                    fetched += 1
                else:
                    entry["report"] = ""
                    entry["has_full_report"] = False
            else:
                entry["report"] = ""
                entry["has_full_report"] = False

        cache[key] = entry
        if (i + 1) % 20 == 0:
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  {i + 1}/{len(players)} — {fetched} rapports DPH")
        time.sleep(0.08)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    with_report = sum(1 for v in cache.values() if v.get("has_full_report"))
    print(f"Terminé: {len(cache)} joueurs, {with_report} avec rapport DPH complet")


if __name__ == "__main__":
    main()
