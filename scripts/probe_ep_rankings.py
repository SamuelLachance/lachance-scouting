#!/usr/bin/env python3
import json
import re
import urllib.request

urls = [
    "https://www.eliteprospects.com/draft/nhl-entry-draft/2026/rankings",
    "https://www.eliteprospects.com/draft/nhl-entry-draft/2026",
]
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"}
for url in urls:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode("utf-8", "replace")
    except Exception as e:
        print(url, e)
        continue
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html)
    if not m:
        print(url, "no next", len(html))
        continue
    data = json.loads(m.group(1))
    text = json.dumps(data)
    ids = len(re.findall(r'"imageUrl":"https://', text))
    players = len(re.findall(r'"playerId":', text))
    names = re.findall(r'"name":"(Gavin McKenna|Wyatt Cullen)"', text)
    print(url, "imageUrls", ids, "playerIds", players, "names", names[:5])
