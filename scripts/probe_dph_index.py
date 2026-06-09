#!/usr/bin/env python3
import urllib.request
import re

url = "https://draftprospectshockey.com/prospects-index"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=60) as r:
    html = r.read().decode("utf-8", "replace")
# look for photo/img in rows
if "hero-photo" in html:
    print("has hero-photo class")
if "data-photo" in html:
    print("has data-photo")
imgs = re.findall(r'data-[a-z-]*photo[a-z-]*="([^"]+)"', html, re.I)
print("data photo attrs", imgs[:5])
# first row chunk
m = re.search(r'px-row.{0,800}', html)
if m:
    print(m.group(0)[:800])
