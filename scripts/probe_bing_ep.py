#!/usr/bin/env python3
import re
import urllib.parse
import urllib.request

def find_ep(name: str):
    q = urllib.parse.quote(f"eliteprospects.com {name} hockey")
    url = f"https://www.bing.com/search?q={q}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        html = r.read().decode("utf-8", "replace")
    ids = re.findall(r"eliteprospects\.com/player/(\d+)/[^\"&<\\s]+", html)
    print(name, ids[:3])

for n in ["Gavin McKenna", "Wyatt Cullen", "Liam Ruck"]:
    find_ep(n)
