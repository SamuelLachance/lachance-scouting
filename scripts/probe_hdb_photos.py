#!/usr/bin/env python3
import re
import urllib.request

url = "https://www.hockeydb.com/ihdb/draft/draft2026.html"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=30) as r:
    html = r.read().decode("latin-1", "replace")

links = re.findall(
    r'href="/ihdb/stats/pdisplay\.php\?pid=(\d+)"[^>]*>([^<]+)</a>', html
)
print("links", len(links), "sample", links[:8])

# check one player page for photo
if links:
    pid, name = links[0]
    url2 = f"https://www.hockeydb.com/ihdb/stats/pdisplay.php?pid={pid}"
    req2 = urllib.request.Request(url2, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req2, timeout=20) as r2:
        phtml = r2.read().decode("latin-1", "replace")
    for m in re.finditer(r'<img[^>]+src="([^"]+)"', phtml):
        src = m.group(1)
        if "menu" not in src and "hdr" not in src and "hdb" not in src.lower():
            print("img", src)
