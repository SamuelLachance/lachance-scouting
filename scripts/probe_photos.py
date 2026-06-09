#!/usr/bin/env python3
import re
import urllib.request

SAMPLES = [
    ("DPH McKenna", "https://draftprospectshockey.com/prospects/gavin-mckenna"),
    ("DPH Ruck", "https://draftprospectshockey.com/prospects/liam-ruck"),
    ("EP McKenna", "https://www.eliteprospects.com/player/614234/gavin-mckenna"),
    ("HDB McKenna", "https://www.hockeydb.com/ihdb/stats/pdisplay.php?pid=266123"),
    ("OHL", "https://chl.ca/ohl/blades/players/8987/"),
]


def probe(label, url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            html = r.read().decode("utf-8", "replace")
    except Exception as e:
        print(label, "ERR", e)
        return
    print(f"\n=== {label} ({len(html)} bytes) ===")
    for pat, name in [
        (r'<img[^>]+class="[^"]*hero-photo[^"]*"[^>]+src="([^"]+)"', "hero-photo"),
        (r'<img[^>]+src="([^"]+)"[^>]+class="[^"]*hero-photo', "hero-photo2"),
        (r'"image"\s*:\s*"([^"]+)"', "json-ld image"),
        (r'property="og:image"\s+content="([^"]+)"', "og:image"),
        (r'cdn\.eliteprospects\.com/player/[^"\']+\.(?:jpg|webp|png)', "ep cdn"),
        (r'files\.eliteprospects\.com/[^"\']+\.(?:jpg|webp|png)', "ep files"),
    ]:
        m = re.search(pat, html, re.I)
        if m:
            print(f"  {name}: {m.group(0) if name.startswith('ep') else m.group(1)[:120]}")
    imgs = re.findall(r'<img[^>]+src="([^"]+)"', html)
    for u in imgs[:8]:
        if "logo" not in u.lower() and "icon" not in u.lower() and "svg" not in u.lower():
            print(f"  img: {u[:100]}")


if __name__ == "__main__":
    for label, url in SAMPLES:
        probe(label, url)
