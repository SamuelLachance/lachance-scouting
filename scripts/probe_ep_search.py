#!/usr/bin/env python3
import json
import re
import urllib.parse
import urllib.request

def search_ep(name: str):
    q = urllib.parse.quote(name)
    url = f"https://www.eliteprospects.com/search/player?q={q}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=25) as r:
        html = r.read().decode("utf-8", "replace")
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html)
    if not m:
        print(name, "no next")
        return
    data = json.loads(m.group(1))
    # find first player result
    blob = json.dumps(data)
    ids = re.findall(r'"id":(\d+),"name":"[^"]*' + re.escape(name.split()[-1]), blob, re.I)
    imgs = re.findall(r'"imageUrl":"([^"]+)"', blob)
    print(name, "ids", ids[:3], "imgs", [x for x in imgs if x and "default" not in x][:3])

for n in ["Gavin McKenna", "Wyatt Cullen", "Chase Reid", "Liam Ruck"]:
    try:
        search_ep(n)
    except Exception as e:
        print(n, e)
