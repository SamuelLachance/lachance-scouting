#!/usr/bin/env python3
import re
import urllib.request

urls = [
    "https://puckpedia.com/player/gavin-mckenna",
    "https://puckpedia.com/player/wyatt-cullen",
    "https://puckpedia.com/player/chase-reid",
]
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"}
for url in urls:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode("utf-8", "replace")
        og = re.search(r'property="og:image"\s+content="([^"]+)"', html)
        imgs = [m.group(1) for m in re.finditer(r'<img[^>]+src="([^"]+)"', html) if "player" in m.group(1).lower() or "headshot" in m.group(1).lower() or "amazonaws" in m.group(1)]
        print(url, "status OK", "og", og.group(1)[:80] if og else None)
        for i in imgs[:3]:
            print(" ", i[:100])
    except Exception as e:
        print(url, e)
