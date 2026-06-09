#!/usr/bin/env python3
import json
import re
import urllib.parse
import urllib.request

def wiki_links(name: str, birth_year: str | None):
    search = f"{name} ice hockey born {birth_year}" if birth_year else f"{name} ice hockey"
    q = urllib.parse.quote(search)
    url = (
        "https://en.wikipedia.org/w/api.php?"
        f"action=query&generator=search&gsrsearch={q}&gsrlimit=3"
        "&prop=revisions|pageimages|categories&rvprop=content&rvslots=main"
        "&piprop=thumbnail&pithumbsize=480&format=json"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "LachanceScouting/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode())
    pages = data.get("query", {}).get("pages", {})
    last = name.split()[-1].lower()
    first = name.split()[0].lower()
    for p in pages.values():
        title = p.get("title", "")
        if last not in title.lower() or first not in title.lower():
            continue
        rev = p.get("revisions", [{}])[0].get("slots", {}).get("main", {}).get("*", "")
        ep = re.search(r"eliteprospects\.com/player/(\d+)", rev)
        thumb = p.get("thumbnail", {}).get("source")
        print(name, "title", title, "wiki", bool(thumb), "ep", ep.group(1) if ep else None)

wiki_links("Gavin McKenna", "2007")
wiki_links("Wyatt Cullen", "2008")
wiki_links("Chase Reid", "2008")
