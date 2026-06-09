"""Recherche et téléchargement de portraits joueurs (Wikimedia / cache)."""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = "LachanceScouting/1.0 (NHL draft scouting; local project)"


def _get(url: str, timeout: int = 20, retries: int = 4) -> dict | bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                time.sleep(2.0 * (attempt + 1))
                continue
            raise
    if url.endswith("format=json") or "format=json" in url:
        return json.loads(raw.decode("utf-8"))
    return raw


def wikidata_photo(name: str) -> str | None:
    q = urllib.parse.quote(name)
    data = _get(
        "https://www.wikidata.org/w/api.php?"
        f"action=wbsearchentities&search={q}&language=en&format=json&limit=8"
    )
    last = name.split()[-1].lower()
    first = name.split()[0].lower()
    entity_id = None
    for item in data.get("search", []):
        label = item.get("label", "").lower()
        desc = (item.get("description") or "").lower()
        if first not in label or last not in label:
            continue
        if "hockey" in desc or "ice" in desc or "nhl" in desc or "goaltender" in desc:
            entity_id = item.get("id")
            break
    if not entity_id:
        return None
    ent = _get(
        "https://www.wikidata.org/w/api.php?"
        f"action=wbgetentities&ids={entity_id}&props=claims&format=json"
    )["entities"][entity_id]
    claims = ent.get("claims", {}).get("P18", [])
    if not claims:
        return None
    filename = claims[0]["mainsnak"]["datavalue"]["value"]
    file_title = f"File:{filename.replace(' ', '_')}"
    pages = _get(
        "https://commons.wikimedia.org/w/api.php?"
        f"action=query&titles={urllib.parse.quote(file_title)}"
        "&prop=imageinfo&iiprop=url&iiurlwidth=640&format=json"
    )["query"]["pages"]
    for page in pages.values():
        ii = page.get("imageinfo", [{}])[0]
        return ii.get("thumburl") or ii.get("url")
    return None


def wikipedia_photo(name: str, birth: str | None) -> str | None:
    titles = [f"{name} (ice hockey)"]
    if birth and len(birth) >= 4:
        titles.append(f"{name} (ice hockey, born {birth[:4]})")
    titles.append(name)
    for title in titles:
        t = urllib.parse.quote(title.replace(" ", "_"))
        try:
            data = _get(
                "https://en.wikipedia.org/w/api.php?"
                f"action=query&titles={t}&prop=pageimages&piprop=thumbnail"
                "&pithumbsize=640&format=json"
            )
        except Exception:
            continue
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            if page.get("missing") is not None:
                continue
            pt = page.get("title", "").lower()
            if name.split()[-1].lower() not in pt:
                continue
            thumb = page.get("thumbnail", {}).get("source")
            if thumb and "Flag_of" not in thumb and "Logo" not in thumb:
                return thumb
    return None


def find_photo_url(name: str, birth: str | None = None) -> str | None:
    try:
        url = wikidata_photo(name)
        if url:
            return url
        time.sleep(0.5)
        return wikipedia_photo(name, birth)
    except Exception:
        return None


def download_photo(url: str, dest: Path) -> Path | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
    except Exception:
        return None
    if len(data) < 500:
        return None
    ext = ".jpg"
    lower = url.lower()
    if ".png" in lower:
        ext = ".png"
    elif ".webp" in lower:
        ext = ".webp"
    out = dest.with_suffix(ext)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    return out


def slug_from_rankings_entry(p: dict, slug_fn) -> str:
    fichier = p.get("Fichier_Local", "")
    if fichier:
        return slug_fn(fichier)
    return p["Nom"].lower().replace(" ", "-")


def load_photo_manifest(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_photo_manifest(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
