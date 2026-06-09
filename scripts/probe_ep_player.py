#!/usr/bin/env python3
import re
import urllib.request

url = "https://www.eliteprospects.com/player/614234/gavin-mckenna"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.eliteprospects.com/",
}
req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req, timeout=25) as r:
    html = r.read().decode("utf-8", "replace")

for pat in [
    r'"image"\s*:\s*"([^"]+)"',
    r'"profileImage"\s*:\s*"([^"]+)"',
    r'property="og:image"\s+content="([^"]+)"',
    r'files\.eliteprospects\.com/player/[^"\']+',
    r'cdn\.eliteprospects[^"\']*player[^"\']+',
    r'<img[^>]+alt="[^"]*Gavin[^"]*"[^>]+src="([^"]+)"',
    r'src="(https://files\.eliteprospects\.com/[^"]+)"',
]:
    ms = re.findall(pat, html, re.I)
    if ms:
        print("PAT", pat[:50])
        for x in ms[:5]:
            print(" ", x if isinstance(x, str) else x)

# dump lines with profile or player image
for line in html.split("\n"):
    ll = line.lower()
    if "profile" in ll and ("image" in ll or "photo" in ll or "src=" in ll):
        if "default" not in ll or "614234" in line:
            print("LINE", line.strip()[:200])
