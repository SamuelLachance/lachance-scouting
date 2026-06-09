#!/usr/bin/env python3
import json
import re
import urllib.request

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"}

def ep_player(url: str):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        html = r.read().decode("utf-8", "replace")
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html)
    data = json.loads(m.group(1))
    player = data.get("props", {}).get("pageProps", {}).get("playerData", {}).get("player", {})
    return player.get("id"), player.get("name"), player.get("imageUrl"), player.get("dateOfBirth")

for slug in [
    "https://www.eliteprospects.com/player/614234/gavin-mckenna",
    "https://www.eliteprospects.com/player/614234",
]:
    try:
        pid, name, img, dob = ep_player(slug)
        print(slug.split("/")[-1], "->", pid, name, dob, img)
    except Exception as e:
        print(slug, e)
