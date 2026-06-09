#!/usr/bin/env python3
import re
import urllib.request
from pathlib import Path

URL = "https://draftprospectshockey.com/prospects/gavin-mckenna"
req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=30) as r:
    html = r.read().decode("utf-8", "replace")

Path(__file__).parent.joinpath("dph_player_page.txt").write_text(html, encoding="utf-8")

for pat in [r"born", r"birth", r"2005", r"2006", r"2007", r"2008", r"DOB", r"dateOfBirth"]:
    m = re.search(pat, html, re.I)
    print(pat, "found" if m else "no")

# extract birth-related snippets
for m in re.finditer(r".{0,80}(200[5-8]-\d{2}-\d{2}|Born|birth).{0,80}", html, re.I):
    print(m.group(0)[:160])
