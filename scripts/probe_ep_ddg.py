#!/usr/bin/env python3
import re
import urllib.parse
import urllib.request

def find_ep_id(name: str) -> str | None:
    q = urllib.parse.quote(f"site:eliteprospects.com/player {name}")
    url = f"https://html.duckduckgo.com/html/?q={q}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        html = r.read().decode("utf-8", "replace")
    m = re.search(r"eliteprospects\.com/player/(\d+)/", html)
    return m.group(1) if m else None

for n in ["Gavin McKenna", "Wyatt Cullen", "Chase Reid", "Liam Ruck", "Viggo Björck"]:
    print(n, find_ep_id(n))
