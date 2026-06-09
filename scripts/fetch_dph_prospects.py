#!/usr/bin/env python3
"""Fetch prospects from Draft Prospects Hockey (index 2026)."""
from __future__ import annotations

import re
import urllib.request


def fetch_dph_prospects() -> list[dict]:
    url = "https://draftprospectshockey.com/prospects-index"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        html = r.read().decode("utf-8", "replace")

    pattern = re.compile(
        r'<a href="(?P<href>/prospects/[^"]+)" class="px-row"'
        r'[^>]*data-league="(?P<league>[^"]*)"'
        r'[^>]*data-pos="(?P<pos>[^"]*)"'
        r'[^>]*data-nat="(?P<nat>[^"]*)"'
        r'[^>]*data-name="(?P<name_key>[^"]*)"[^>]*>'
        r'\s*<span class="px-rank">#(?P<rank>\d+)</span>\s*'
        r'<span class="px-name">(?P<name>[^<]+)</span>',
        re.DOTALL,
    )
    rows = []
    for m in pattern.finditer(html):
        rows.append(
            {
                "href": m.group("href"),
                "league": m.group("league"),
                "pos": m.group("pos"),
                "nat": m.group("nat"),
                "name_key": m.group("name_key"),
                "rank": int(m.group("rank")),
                "name": m.group("name").strip(),
            }
        )
    return rows


def fetch_dph_birthdate(href: str) -> str | None:
    """Lit birthDate depuis le JSON-LD de la fiche DPH."""
    url = f"https://draftprospectshockey.com{href}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8", "replace")
    m = re.search(r'"birthDate"\s*:\s*"([^"]+)"', html)
    if m:
        return m.group(1)
    m = re.search(
        r'<div class="bio-lbl">Born</div><div class="bio-val">([^<]+)</div>',
        html,
    )
    return m.group(1).strip() if m else None
