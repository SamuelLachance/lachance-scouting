#!/usr/bin/env python3
import json
import re
import urllib.request
from pathlib import Path

URL = "https://draftprospectshockey.com/prospects-index"
req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=30) as r:
    html = r.read().decode("utf-8", "replace")

out = Path(__file__).parent / "dph_snippet.txt"
idx = html.find("Gavin McKenna")
out.write_text(html[idx - 500 : idx + 800], encoding="utf-8")

# search for embedded JSON with names
for pat in [
    r'(\[\{"id".*?"name":"Gavin McKenna".*?\])',
    r'"players"\s*:\s*(\[.*?\])',
    r'ALL_PROSPECTS\s*=\s*(\[.*?\])',
]:
    m = re.search(pat, html, re.DOTALL)
    if m:
        (Path(__file__).parent / "dph_json.txt").write_text(m.group(1)[:5000], encoding="utf-8")
        print("found json pattern", pat[:30])
        break
else:
    print("no json array found")

# find script with prospect data
for i, s in enumerate(re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)):
    if "Gavin McKenna" in s or "McKenna" in s and len(s) > 1000:
        (Path(__file__).parent / f"dph_script_{i}.txt").write_text(s[:10000], encoding="utf-8")
        print("wrote script", i, "len", len(s))

print("done, snippet written")
