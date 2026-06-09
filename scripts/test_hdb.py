#!/usr/bin/env python3
import re, urllib.request, urllib.parse

def search_hockeydb(name: str):
    q = urllib.parse.quote(name)
    url = f"https://www.hockeydb.com/ihdb/stats/league_search.php?league=NHL&season=2025&search={q}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        html = urllib.request.urlopen(req, timeout=20).read().decode("latin-1", "replace")
    except Exception as e:
        return None
    m = re.search(r"(\d{4}-\d{2}-\d{2})", html)
    return m.group(1) if m else None

for name in ["Gavin McKenna", "Liam Ruck", "Chase Reid"]:
    print(name, search_hockeydb(name))
