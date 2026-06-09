#!/usr/bin/env python3
"""Probe Draft Prospects Hockey for structured prospect data."""
import json
import re
import urllib.request

URL = "https://draftprospectshockey.com/prospects-index"
req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=30) as r:
    html = r.read().decode("utf-8", "replace")

print("html len", len(html))

# Next.js data
m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html)
if m:
    data = json.loads(m.group(1))
    print("NEXT_DATA keys", data.keys())
    props = data.get("props", {})
    page_props = props.get("pageProps", {})
    print("pageProps keys", page_props.keys())
    for k, v in page_props.items():
        if isinstance(v, list):
            print(f"  {k}: list len {len(v)}")
            if v:
                print("  sample", v[0])
        elif isinstance(v, dict):
            print(f"  {k}: dict keys {list(v.keys())[:10]}")
else:
    print("no __NEXT_DATA__")

# other JSON blobs
for pat in [r"window\.__INITIAL_STATE__\s*=\s*(\{.+?\});", r"prospects\s*:\s*(\[)"]:
    if re.search(pat, html):
        print("found pattern", pat[:40])

# inline script tags with prospects
scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
for i, s in enumerate(scripts):
    if "prospect" in s.lower() and len(s) > 500:
        print(f"script {i} len {len(s)} snippet: {s[:200]}")
