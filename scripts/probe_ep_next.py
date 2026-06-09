#!/usr/bin/env python3
import json
import re
import urllib.request

url = "https://www.eliteprospects.com/player/614234/gavin-mckenna"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"}
req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req, timeout=25) as r:
    html = r.read().decode("utf-8", "replace")
m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html)
if m:
    data = json.loads(m.group(1))
    # walk for image keys
    def walk(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if any(x in k.lower() for x in ("image", "photo", "portrait", "avatar", "picture")):
                    print(path + k, ":", str(v)[:120])
                walk(v, path + k + ".")
        elif isinstance(obj, list):
            for i, v in enumerate(obj[:3]):
                walk(v, path + f"[{i}].")
    walk(data)
else:
    print("no next data")
