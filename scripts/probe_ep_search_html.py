#!/usr/bin/env python3
import re
import urllib.parse
import urllib.request

q = urllib.parse.quote("Gavin McKenna")
url = f"https://www.eliteprospects.com/search/player?q={q}"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"}
req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req, timeout=25) as r:
    html = r.read().decode("utf-8", "replace")
links = re.findall(r'href="(/player/\d+/[^"]+)"', html)
print("player links", links[:10])
imgs = re.findall(r'src="(https://files\.eliteprospects\.com/[^"]+)"', html)
print("files imgs", [x for x in imgs if "player" in x.lower() or "layout" not in x][:5])
