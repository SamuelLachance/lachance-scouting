"""Recherche et téléchargement de portraits joueurs (EP, Wikimedia, cache)."""
from __future__ import annotations

import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

WIKI_UA = "LachanceScouting/1.0 (NHL draft scouting; local project)"
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
BROWSER_HEADERS = {
    "User-Agent": BROWSER_UA,
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.eliteprospects.com/",
}
EP_BAD_IMAGE_PARTS = (
    "ep-logo-bg",
    "default-player",
    "placeholder",
    "no-image",
    "silhouette",
)
WIKI_BAD_THUMB_PARTS = ("Flag_of", "Logo", ".svg")
HOCKEY_DESC_WORDS = ("hockey", "ice", "nhl", "goaltender", "player", "forward", "defence")


@dataclass
class PhotoHit:
    url: str | None
    source: str | None = None
    ep_id: int | None = None


def _normalize_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _compact_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _normalize_name(s))


def _name_parts(name: str) -> tuple[str, str]:
    parts = name.replace("-", " ").split()
    if not parts:
        return "", ""
    return _compact_name(parts[0]), _compact_name(parts[-1])


def _first_name_variants(name: str) -> list[str]:
    parts = name.replace("-", " ").split()
    if not parts:
        return []
    variants = [_compact_name(parts[0])]
    if len(parts) > 2:
        variants.append(_compact_name("".join(parts[:-1])))
    return [v for v in variants if v]


def _first_name_match(ours: str, theirs: str) -> bool:
    if not ours or not theirs:
        return False
    if ours == theirs:
        return True
    if ours.startswith(theirs) or theirs.startswith(ours):
        return True
    return len(ours) >= 3 and len(theirs) >= 3 and ours[:3] == theirs[:3]


def _name_matches(candidate: str, first: str, last: str) -> bool:
    parts = candidate.replace("-", " ").split()
    if not parts:
        return False
    cfirst = _compact_name(parts[0])
    clast = _compact_name(parts[-1])
    if clast != last:
        return False
    return _first_name_match(first, cfirst)


def _birth_year_ok(birth: str | None, ep_dob: str | None) -> bool:
    year = birth[:4] if birth and len(birth) >= 4 else None
    if not year:
        return True
    if not ep_dob:
        return True
    return year in str(ep_dob)


def _valid_photo_url(url: str | None) -> bool:
    if not url:
        return False
    lower = url.lower()
    if any(part in lower for part in EP_BAD_IMAGE_PARTS):
        return False
    if lower.endswith(".svg"):
        return False
    return True


def _valid_wiki_thumb(url: str | None) -> bool:
    if not _valid_photo_url(url):
        return False
    return not any(part in url for part in WIKI_BAD_THUMB_PARTS)


def _get_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 25,
    retries: int = 5,
    base_delay: float = 2.0,
) -> dict:
    hdrs = headers or {"User-Agent": WIKI_UA}
    last_err: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 503) and attempt < retries - 1:
                time.sleep(base_delay * (attempt + 1))
                continue
            raise
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(base_delay)
                continue
            raise
    raise last_err or RuntimeError("request failed")


def _get_bytes(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
    retries: int = 4,
) -> bytes | None:
    hdrs = headers or {"User-Agent": WIKI_UA}
    if "eliteprospects" in url:
        hdrs = {**BROWSER_HEADERS, **(headers or {})}
    for attempt in range(retries):
        req = urllib.request.Request(url, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 403, 503) and attempt < retries - 1:
                time.sleep(2.0 * (attempt + 1))
                continue
            return None
        except Exception:
            if attempt < retries - 1:
                time.sleep(1.5)
                continue
            return None
    return None


def _get_html(url: str, *, headers: dict[str, str] | None = None, timeout: int = 25) -> str | None:
    raw = _get_bytes(url, headers=headers or BROWSER_HEADERS, timeout=timeout)
    return raw.decode("utf-8", "replace") if raw else None


EP_DRAFT_CENTER_URL = "https://www.eliteprospects.com/draft-center"
_draft_players_cache: list[tuple[int, str, str]] | None = None


def load_ep_draft_players(*, cache_path: Path | None = None, max_age_hours: float = 12) -> list[tuple[int, str, str]]:
    """EP Draft Center rankings: (id, name, dateOfBirth)."""
    global _draft_players_cache
    if _draft_players_cache is not None:
        return _draft_players_cache

    if cache_path and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            age_h = (time.time() - cached.get("fetchedAt", 0)) / 3600
            if age_h < max_age_hours and cached.get("players"):
                _draft_players_cache = [
                    (int(p["id"]), p["name"], p.get("dateOfBirth") or "")
                    for p in cached["players"]
                ]
                return _draft_players_cache
        except Exception:
            pass

    html = _get_html(EP_DRAFT_CENTER_URL)
    if not html:
        _draft_players_cache = []
        return _draft_players_cache

    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html)
    if not m:
        _draft_players_cache = []
        return _draft_players_cache

    data = json.loads(m.group(1))
    rankings = (
        data.get("props", {})
        .get("pageProps", {})
        .get("draftRankings", {})
        .get("rankings", [])
    )
    players: list[tuple[int, str, str]] = []
    for item in rankings:
        player = item.get("player") or {}
        ep_id = player.get("id")
        name = player.get("name") or ""
        if ep_id and name:
            players.append((int(ep_id), name, str(player.get("dateOfBirth") or "")))

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(
                {
                    "fetchedAt": time.time(),
                    "players": [
                        {"id": pid, "name": n, "dateOfBirth": dob}
                        for pid, n, dob in players
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    _draft_players_cache = players
    return players


def resolve_ep_id_from_draft(
    name: str,
    birth: str | None = None,
    draft_players: list[tuple[int, str, str]] | None = None,
) -> int | None:
    players = draft_players if draft_players is not None else load_ep_draft_players()
    ours_first = _first_name_variants(name)
    ours_last = _compact_name(name.split()[-1])
    candidates: list[tuple[int, int, int]] = []
    for ep_id, ep_name, ep_dob in players:
        if _compact_name(ep_name.split()[-1]) != ours_last:
            continue
        if not _birth_year_ok(birth, ep_dob):
            continue
        ep_first = _first_name_variants(ep_name)
        score = 0
        for of in ours_first:
            for ef in ep_first:
                if of == ef:
                    score = max(score, 3)
                elif _first_name_match(of, ef):
                    score = max(score, 2)
        if score:
            candidates.append((score, ep_id, len(ep_name)))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (-x[0], x[2]))
    return candidates[0][1]


def resolve_ep_id(
    name: str,
    birth: str | None = None,
    ep_id: int | None = None,
    *,
    draft_players: list[tuple[int, str, str]] | None = None,
) -> int | None:
    if ep_id:
        return int(ep_id)
    return resolve_ep_id_from_draft(name, birth, draft_players)


def _parse_ep_player(html: str) -> dict:
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html)
    if not m:
        return {}
    data = json.loads(m.group(1))
    return data.get("props", {}).get("pageProps", {}).get("playerData", {}).get("player", {}) or {}


def _ep_player_photo(ep_id: int, name: str, birth: str | None = None) -> PhotoHit:
    url = f"https://www.eliteprospects.com/player/{ep_id}"
    html = _get_html(url)
    if not html:
        return PhotoHit(None, "eliteprospects", ep_id)
    player = _parse_ep_player(html)
    player_name = player.get("name") or ""
    first, last = _name_parts(name)
    if player_name and not _name_matches(player_name, first, last):
        return PhotoHit(None, "eliteprospects", ep_id)
    if not _birth_year_ok(birth, player.get("dateOfBirth")):
        return PhotoHit(None, "eliteprospects", ep_id)
    image = player.get("imageUrl")
    if not _valid_photo_url(image):
        og = re.search(r'property="og:image"\s+content="([^"]+)"', html)
        image = og.group(1) if og else None
    if _valid_photo_url(image):
        return PhotoHit(image, "eliteprospects", ep_id)
    return PhotoHit(None, "eliteprospects", ep_id)


def _ep_search(name: str, birth: str | None = None) -> PhotoHit:
    q = urllib.parse.quote(name)
    search_url = f"https://www.eliteprospects.com/search/player?q={q}"
    html = _get_html(search_url)
    if not html:
        return PhotoHit(None, "eliteprospects-search")
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html)
    if not m:
        return PhotoHit(None, "eliteprospects-search")
    data = json.loads(m.group(1))
    players = data.get("props", {}).get("pageProps", {}).get("players") or []
    first, last = _name_parts(name)
    birth_year = birth[:4] if birth and len(birth) >= 4 else None
    best_id: int | None = None
    best_img: str | None = None
    for player in players:
        pname = player.get("name") or ""
        if not _name_matches(pname, first, last):
            continue
        dob = str(player.get("dateOfBirth") or "")
        if birth_year and dob and birth_year not in dob:
            continue
        ep_id = player.get("id")
        image = player.get("imageUrl")
        if ep_id:
            best_id = int(ep_id)
        if _valid_photo_url(image):
            best_img = image
            break
    if best_img:
        return PhotoHit(best_img, "eliteprospects-search", best_id)
    if best_id:
        return _ep_player_photo(best_id, name, birth)
    return PhotoHit(None, "eliteprospects-search")


def elite_prospects_photo(
    name: str,
    birth: str | None = None,
    ep_id: int | None = None,
    *,
    draft_players: list[tuple[int, str, str]] | None = None,
) -> PhotoHit:
    resolved = resolve_ep_id(name, birth, ep_id, draft_players=draft_players)
    if resolved:
        hit = _ep_player_photo(resolved, name, birth)
        if hit.url or hit.ep_id:
            return hit
    if ep_id and ep_id != resolved:
        hit = _ep_player_photo(int(ep_id), name, birth)
        if hit.url:
            return hit
    return _ep_search(name, birth)


def wikipedia_titles(name: str, birth: str | None) -> list[str]:
    titles = [f"{name} (ice hockey)"]
    if birth and len(birth) >= 4:
        titles.append(f"{name} (ice hockey, born {birth[:4]})")
    return titles


def wiki_batch_lookup(
    players: list[tuple[str, str, str | None]],
    *,
    delay: float = 2.0,
) -> dict[str, PhotoHit]:
    """Batch Wikipedia lookup: slug -> PhotoHit (thumb and/or ep_id)."""
    title_map: dict[str, str] = {}
    for slug, name, birth in players:
        for title in wikipedia_titles(name, birth):
            key = title.replace(" ", "_")
            title_map[key] = slug

    hits: dict[str, PhotoHit] = {}
    titles = list(title_map.keys())
    for i in range(0, len(titles), 45):
        chunk = titles[i : i + 45]
        tparam = "|".join(urllib.parse.quote(t) for t in chunk)
        url = (
            "https://en.wikipedia.org/w/api.php?action=query&titles="
            + tparam
            + "&prop=pageimages|revisions&rvprop=content&rvslots=main"
            + "&piprop=thumbnail&pithumbsize=640&format=json"
        )
        try:
            data = _get_json(url, base_delay=3.0)
        except Exception:
            time.sleep(delay * 2)
            continue

        for page in data.get("query", {}).get("pages", {}).values():
            if page.get("missing") is not None:
                continue
            title_key = page.get("title", "").replace(" ", "_")
            slug = title_map.get(title_key)
            if not slug:
                continue
            current = hits.get(slug, PhotoHit(None))
            thumb = page.get("thumbnail", {}).get("source")
            if _valid_wiki_thumb(thumb):
                current = PhotoHit(thumb, "wikipedia", current.ep_id)
            rev = page.get("revisions", [{}])[0].get("slots", {}).get("main", {}).get("*", "")
            ep_ids = re.findall(r"eliteprospects\.com/player/(\d+)", rev)
            if ep_ids:
                ep_id = int(ep_ids[0])
                current = PhotoHit(current.url, current.source or "wikipedia", ep_id)
            hits[slug] = current
        time.sleep(delay)
    return hits


def wikidata_photo(name: str) -> str | None:
    q = urllib.parse.quote(name)
    data = _get_json(
        "https://www.wikidata.org/w/api.php?"
        f"action=wbsearchentities&search={q}&language=en&format=json&limit=8",
        base_delay=3.0,
    )
    first, last = _name_parts(name)
    entity_id = None
    for item in data.get("search", []):
        label = item.get("label", "").lower()
        desc = (item.get("description") or "").lower()
        if not _name_matches(label, first, last):
            continue
        if any(word in desc for word in HOCKEY_DESC_WORDS):
            entity_id = item.get("id")
            break
    if not entity_id:
        return None
    time.sleep(1.5)
    ent = _get_json(
        "https://www.wikidata.org/w/api.php?"
        f"action=wbgetentities&ids={entity_id}&props=claims&format=json",
        base_delay=3.0,
    )["entities"][entity_id]
    claims = ent.get("claims", {}).get("P18", [])
    if not claims:
        return None
    filename = claims[0]["mainsnak"]["datavalue"]["value"]
    file_title = f"File:{filename.replace(' ', '_')}"
    time.sleep(1.0)
    pages = _get_json(
        "https://commons.wikimedia.org/w/api.php?"
        f"action=query&titles={urllib.parse.quote(file_title)}"
        "&prop=imageinfo&iiprop=url&iiurlwidth=640&format=json",
        base_delay=3.0,
    )["query"]["pages"]
    for page in pages.values():
        ii = page.get("imageinfo", [{}])[0]
        url = ii.get("thumburl") or ii.get("url")
        if _valid_wiki_thumb(url):
            return url
    return None


def wikipedia_photo(name: str, birth: str | None) -> str | None:
    first, last = _name_parts(name)
    for title in wikipedia_titles(name, birth) + [name]:
        t = urllib.parse.quote(title.replace(" ", "_"))
        try:
            data = _get_json(
                "https://en.wikipedia.org/w/api.php?"
                f"action=query&titles={t}&prop=pageimages&piprop=thumbnail"
                "&pithumbsize=640&format=json",
            )
        except Exception:
            continue
        for page in data.get("query", {}).get("pages", {}).values():
            if page.get("missing") is not None:
                continue
            pt = page.get("title", "").lower()
            if not _name_matches(pt, first, last):
                continue
            thumb = page.get("thumbnail", {}).get("source")
            if _valid_wiki_thumb(thumb):
                return thumb
        time.sleep(1.0)
    return None


def find_photo_url(
    name: str,
    birth: str | None = None,
    ep_id: int | None = None,
) -> str | None:
    return find_photo(name, birth, ep_id).url


def find_photo(
    name: str,
    birth: str | None = None,
    ep_id: int | None = None,
) -> PhotoHit:
    if ep_id:
        ep_hit = _ep_player_photo(ep_id, name, birth)
        if ep_hit.url:
            return ep_hit

    ep_hit = elite_prospects_photo(name, birth, ep_id)
    if ep_hit.url:
        return ep_hit

    try:
        wiki = wikipedia_photo(name, birth)
        if wiki:
            return PhotoHit(wiki, "wikipedia", ep_hit.ep_id)
    except Exception:
        pass

    time.sleep(1.5)
    try:
        wd = wikidata_photo(name)
        if wd:
            return PhotoHit(wd, "wikidata", ep_hit.ep_id)
    except Exception:
        pass

    if ep_hit.ep_id and not ep_hit.url:
        retry = _ep_player_photo(ep_hit.ep_id, name, birth)
        if retry.url:
            return retry

    return PhotoHit(None, None, ep_hit.ep_id)


def download_photo(url: str, dest: Path) -> Path | None:
    headers = BROWSER_HEADERS if "eliteprospects" in url else {"User-Agent": WIKI_UA}
    data = _get_bytes(url, headers=headers)
    if not data or len(data) < 500:
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
