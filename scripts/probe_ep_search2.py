#!/usr/bin/env python3
import json
import re
import urllib.parse
import urllib.request

name = "Gavin McKenna"
q = urllib.parse.quote(name)
url = f"https://www.eliteprospects.com/search/player?q={q}"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"}
req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req, timeout=25) as r:
    html = r.read().decode("utf-8", "replace")
m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html)
data = json.loads(m.group(1))
text = json.dumps(data)
# find mckenna entries
for match in re.finditer(r'.{0,80}McKenna.{0,200}', text, re.I):
    s = match.group(0)
    if "Gavin" in s or "gavin" in s:
        print(s[:250])
        print("---")
