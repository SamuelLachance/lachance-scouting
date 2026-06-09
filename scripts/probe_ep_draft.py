#!/usr/bin/env python3
import re
import urllib.request

url = "https://www.eliteprospects.com/draft/nhl-entry-draft/2026"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req, timeout=30) as r:
    html = r.read().decode("utf-8", "replace")
print("len", len(html))
# player links with images
blocks = re.findall(r'/player/(\d+)/[^"\']+', html)
print("player ids", len(set(blocks)), "sample", list(set(blocks))[:5])
for pat in [
    r'https://cdn\.eliteprospects\.com/player/[^"\']+',
    r'https://files\.eliteprospects\.com/[^"\']+\.(?:jpg|webp|png)',
    r'"imageUrl"\s*:\s*"([^"]+)"',
    r'data-src="([^"]+player[^"]+)"',
]:
    found = re.findall(pat, html)
    if found:
        print(pat[:40], len(found), found[0][:120] if found else "")
