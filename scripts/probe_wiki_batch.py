#!/usr/bin/env python3
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
rankings = json.loads((BASE / "data/drafts/2026/rankings.json").read_text(encoding="utf-8"))


def wiki_photo(name: str, birth_year: str | None) -> str | None:
    search = f"{name} ice hockey"
    if birth_year:
        search += f" born {birth_year}"
    q = urllib.parse.quote(search)
    url = (
        "https://en.wikipedia.org/w/api.php?"
        f"action=query&generator=search&gsrsearch={q}&gsrlimit=5"
        "&prop=pageimages|categories&piprop=thumbnail&pithumbsize=480&format=json"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "LachanceScouting/1.0 (contact: local)"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode())
    pages = data.get("query", {}).get("pages", {})
    last = name.split()[-1].lower()
    first = name.split()[0].lower()
    for p in pages.values():
        title = p.get("title", "")
        tl = title.lower()
        if last not in tl or first not in tl:
            continue
        cats = [c.get("title", "").lower() for c in p.get("categories", [])]
        if not any("ice hockey" in c or "hockey" in c for c in cats):
            continue
        thumb = p.get("thumbnail", {}).get("source")
        if thumb:
            return thumb
    return None


def ep_photo(name: str, birth: str | None) -> str | None:
    # brute: try common EP IDs from search in pageProps - skip if no id file
    return None


hits = 0
for p in rankings[:30]:
    name = p["Nom"]
    birth = (p.get("Date_Naissance") or "")[:4] or None
    url = wiki_photo(name, birth)
    if url:
        hits += 1
        print(f"OK  {name}")
    else:
        print(f"--- {name}")
print(f"\n{hits}/30 wiki photos")
