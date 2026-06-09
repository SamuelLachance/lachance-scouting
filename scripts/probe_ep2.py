#!/usr/bin/env python3
import urllib.request

url = "https://www.eliteprospects.com/player/614234/gavin-mckenna"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.eliteprospects.com/",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
}
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=25) as r:
        html = r.read().decode("utf-8", "replace")
    print("OK", len(html))
    import re
    for m in re.finditer(r'https://[^"\']+\.(?:jpg|jpeg|webp|png)', html):
        u = m.group(0)
        if "static" not in u and "favicon" not in u:
            print(u[:150])
except Exception as e:
    print("ERR", e)
