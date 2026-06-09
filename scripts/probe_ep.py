#!/usr/bin/env python3
import urllib.request
from pathlib import Path

urls = [
    "https://www.eliteprospects.com/draft/nhl-entry-draft/2026",
    "https://www.eliteprospects.com/nhl-entry-draft-coverage",
]
for url in urls:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode("utf-8", "replace")
        Path(__file__).parent.joinpath("ep_draft.html").write_text(html[:50000], encoding="utf-8")
        print(url, "len", len(html), "2006", "2006" in html)
    except Exception as e:
        print(url, e)
