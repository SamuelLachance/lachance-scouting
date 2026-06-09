#!/usr/bin/env python3
import re, urllib.request
url = "https://draftprospectshockey.com/prospects/liam-ruck"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
open(r"C:\Users\Admin\Projects\nhl-2026-draft\scripts\liam_ruck.html", "w", encoding="utf-8").write(html)
for pat in ['birthDate', 'Born', '2007', '2006', '2008']:
    print(pat, pat in html)
m = re.search(r'"birthDate"\s*:\s*"([^"]+)"', html)
print("json birth", m.group(1) if m else None)
m2 = re.search(r'bio-lbl">Born</div><div class="bio-val">([^<]+)', html)
print("bio born", m2.group(1) if m2 else None)
