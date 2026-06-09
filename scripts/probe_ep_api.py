#!/usr/bin/env python3
import json
import urllib.parse
import urllib.request

def try_url(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read().decode("utf-8", "replace")
        print(url[:80], "OK", body[:200])
        return body
    except Exception as e:
        print(url[:80], "ERR", e)
        return None

name = "Gavin McKenna"
slug = "gavin-mckenna"
for url in [
    f"https://www.eliteprospects.com/api/player/{slug}",
    f"https://www.eliteprospects.com/api/player/614234",
    "https://gc-search-app-prod.eliteprospects.com/search?q=gavin%20mckenna&type=player",
    "https://gc-search-app-prod.eliteprospects.com/v1/search?q=gavin%20mckenna",
]:
    try_url(url)
