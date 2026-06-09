#!/usr/bin/env python3
import urllib.request

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"}
for url in [
    "https://www.eliteprospects.com/player/gavin-mckenna",
    "https://www.eliteprospects.com/search/player?q=gavin+mckenna",
]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            print(url, "->", r.url, r.status)
    except Exception as e:
        print(url, e)
