#!/usr/bin/env python3
import json
import time
import urllib.parse
import urllib.request

UA = "LachanceScouting/1.0"


def wikidata_photo(name: str) -> str | None:
    q = urllib.parse.quote(name)
    url = (
        "https://www.wikidata.org/w/api.php?"
        f"action=wbsearchentities&search={q}&language=en&format=json&limit=5"
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode())
    last = name.split()[-1].lower()
    first = name.split()[0].lower()
    entity_id = None
    for item in data.get("search", []):
        label = item.get("label", "").lower()
        desc = (item.get("description") or "").lower()
        if first in label and last in label and ("hockey" in desc or "ice" in desc):
            entity_id = item.get("id")
            break
    if not entity_id:
        return None
    url2 = (
        "https://www.wikidata.org/w/api.php?"
        f"action=wbgetentities&ids={entity_id}&props=claims&format=json"
    )
    req2 = urllib.request.Request(url2, headers={"User-Agent": UA})
    with urllib.request.urlopen(req2, timeout=15) as r2:
        ent = json.loads(r2.read().decode())["entities"][entity_id]
    claims = ent.get("claims", {}).get("P18", [])
    if not claims:
        return None
    filename = claims[0]["mainsnak"]["datavalue"]["value"]
    file_url = (
        "https://commons.wikimedia.org/w/api.php?"
        f"action=query&titles=File:{urllib.parse.quote(filename.replace(' ', '_'))}"
        "&prop=imageinfo&iiprop=url&iiurlwidth=480&format=json"
    )
    req3 = urllib.request.Request(file_url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req3, timeout=15) as r3:
        pages = json.loads(r3.read().decode())["query"]["pages"]
    for page in pages.values():
        ii = page.get("imageinfo", [{}])[0]
        return ii.get("thumburl") or ii.get("url")
    return None


def ep_photo(ep_id: int) -> str | None:
    url = f"https://www.eliteprospects.com/player/{ep_id}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        html = r.read().decode("utf-8", "replace")
    import re
    m = re.search(r'"imageUrl"\s*:\s*"([^"]+)"', html)
    if m and m.group(1) and "default" not in m.group(1):
        return m.group(1)
    return None


for name, ep_id in [("Gavin McKenna", 614234), ("Jarome Iginla", None), ("Wyatt Cullen", None)]:
    wd = wikidata_photo(name)
    print(name, "wikidata", wd[:70] if wd else None)
    time.sleep(0.3)

print("ep mckenna", ep_photo(614234)[:70] if ep_photo(614234) else None)
