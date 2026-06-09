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
print("player links", len(links))
print("sample", links[:5])

dobs = re.findall(r"(\d{4}-\d{2}-\d{2})", html)
print("dates found", len(dobs), "unique years", sorted(set(d[:4] for d in dobs)))

# dump snippet around first table
idx = html.find("Eligible")
print("Eligible idx", idx)
if idx >= 0:
    print(html[idx : idx + 500])
