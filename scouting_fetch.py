"""
Validated scouting article fetch and text extraction.

Rejects misattributed search hits (e.g. Wikipedia labeled as TSN) and
extracts substantive scouting prose from article HTML.
"""
from __future__ import annotations

import re
from html import unescape
from urllib.parse import urlparse

from truth_engine import SOURCE_DOMAIN_REQUIREMENTS, verify_source_attribution

# Minimum attribution confidence to accept a hit as the claimed source.
MIN_ATTRIBUTION = 0.85

# Sources that accept name-in-query attribution without strict domain match.
QUERY_ATTRIBUTED_SOURCES = frozenset({"pronman", "scott_wheeler"})

_SCOUTING_SIGNAL = re.compile(
    r"\b(scout|scouting|prospect|skating|ceiling|upside|projection|elite|"
    r"draft|generational|franchise|playmaker|comparable|tier|ranking|"
    r"skill|tools|iq|processing|compete|breakout|riser|magician|"
    r"transcendent|game.breaker|creates|vision|release|stride)\b",
    re.I,
)

_STRIP_TAGS = re.compile(r"<(script|style|nav|footer|header|aside)[^>]*>.*?</\1>", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def url_matches_source(source_id: str, url: str) -> bool:
    """Return True when URL credibly belongs to the claimed source."""
    if not url:
        return source_id in ("web_scouting", "bing_scouting", "ddg_scouting")
    attr = verify_source_attribution(source_id, url)
    if attr >= MIN_ATTRIBUTION:
        return True
    if source_id in QUERY_ATTRIBUTED_SOURCES:
        host = urlparse(url).netloc.lower()
        blob = url.lower()
        if source_id == "pronman" and ("pronman" in blob or "espn.com" in host or "theathletic.com" in host):
            return True
        if source_id == "scott_wheeler" and ("wheeler" in blob or "tsn.ca" in host or "theathletic.com" in host):
            return True
    return False


def is_scouting_text(text: str, *, min_words: int = 35) -> bool:
    """Heuristic: does this blob look like scouting content, not a bio stub?"""
    if not text or len(text.split()) < min_words:
        return False
    hits = len(_SCOUTING_SIGNAL.findall(text))
    return hits >= 2


def extract_article_text(html: str, *, max_chars: int = 8000) -> str:
    """Extract readable article body from HTML."""
    if not html:
        return ""
    cleaned = _STRIP_TAGS.sub(" ", html)
    # Prefer structured article containers when present.
    for pattern in (
        r'<article[^>]*>(.*?)</article>',
        r'<div[^>]*class="[^"]*article[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]*class="[^"]*entry-content[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]*class="[^"]*post-content[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]*class="[^"]*story-body[^"]*"[^>]*>(.*?)</div>',
    ):
        m = re.search(pattern, cleaned, re.I | re.S)
        if m:
            cleaned = m.group(1)
            break

    chunks: list[str] = []
    for m in re.finditer(r"<p[^>]*>(.*?)</p>", cleaned, re.I | re.S):
        t = unescape(_TAG_RE.sub(" ", m.group(1)))
        t = _WS_RE.sub(" ", t).strip()
        if len(t) >= 40:
            chunks.append(t)
    if not chunks:
        t = unescape(_TAG_RE.sub(" ", cleaned))
        t = _WS_RE.sub(" ", t).strip()
        return t[:max_chars]
    return " ".join(chunks)[:max_chars]


def pick_best_result(
    results: list[dict],
    source_id: str,
    name: str,
) -> dict | None:
    """Choose the first search result with valid attribution and scouting signal."""
    last = name.split()[-1].lower()
    first = name.split()[0].lower() if name.split() else ""
    for r in results:
        url = r.get("url", "")
        snippet = r.get("snippet", "")
        if last not in (snippet + url).lower():
            continue
        if first and first not in (snippet + url).lower():
            continue
        if url and not url_matches_source(source_id, url):
            continue
        if not is_scouting_text(snippet, min_words=20) and not url:
            continue
        return r
    return None


def enrich_with_full_text(
    fetcher,
    item: dict,
    *,
    source_id: str,
    name: str,
) -> dict | None:
    """
    Given a search hit, optionally fetch the page and return enriched text.
    Returns None if attribution fails or text is not scouting-like.
    """
    url = item.get("url", "")
    snippet = item.get("snippet", "")
    if url and not url_matches_source(source_id, url):
        return None

    text = snippet
    if url and fetcher is not None:
        html = fetcher.fetch(url, timeout=20)
        if html:
            body = extract_article_text(html)
            if is_scouting_text(body, min_words=50):
                text = body
            elif is_scouting_text(snippet, min_words=20):
                text = snippet
            else:
                return None
    elif not is_scouting_text(text, min_words=25):
        return None

    return {
        "source_id": source_id,
        "text": text[:8000],
        "url": url,
        "snippets": [snippet] if snippet else [],
    }
