#!/usr/bin/env python3
import json
import re
import urllib.request

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"}

def ep_image(ep_id: int):
    url = f"https://www.eliteprospects.com/player/{ep_id}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", "replace")
    except Exception:
        return None, None
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html)
    if not m:
        return None, None
    data = json.loads(m.group(1))
    player = data.get("props", {}).get("pageProps", {}).get("playerData", {}).get("player", {})
    name = player.get("name")
    img = player.get("imageUrl")
    return name, img

# sample around mckenna + random 2025 picks
for pid in [614234, 614235, 614236, 600000, 550000, 500000, 480000]:
    name, img = ep_image(pid)
    if name:
        print(pid, name, "img", (img or "NONE")[:80])
