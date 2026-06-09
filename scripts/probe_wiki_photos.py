#!/usr/bin/env python3
import json
import urllib.parse
import urllib.request

def wiki_photo(name: str):
    q = urllib.parse.quote(name + " ice hockey")
    url = (
        "https://en.wikipedia.org/w/api.php?"
        f"action=query&generator=search&gsrsearch={q}&gsrlimit=3&prop=pageimages"
        "&piprop=thumbnail&pithumbsize=400&format=json"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "LachanceScouting/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode())
    pages = data.get("query", {}).get("pages", {})
    for p in pages.values():
        title = p.get("title", "")
        thumb = p.get("thumbnail", {}).get("source")
        if thumb:
            print(name, "->", title, thumb[:80])
            return thumb
    print(name, "-> none")
    return None

for n in ["Gavin McKenna", "Wyatt Cullen", "Chase Reid", "Joe Iginla", "Liam Ruck"]:
    wiki_photo(n)
