"""Normalisation de noms pour fusion de listes de prospects."""
from __future__ import annotations

import re
import unicodedata

NAME_ALIASES: dict[str, str] = {}


def _build_aliases() -> None:
    global NAME_ALIASES
    if NAME_ALIASES:
        return
    pairs = [
        ("Adam Novotný", "Adam Novotony"),
        ("J.P. Hurlbert", "J.P Hurlbert"),
        ("Markus Ruck", "Marcus Ruck"),
        ("Ilya Morozov", "Ilia Morozov"),
        ("Beckett Hamilton", "Reese Hamilton"),
        ("Michael Berchild", "Mikey Berchild"),
        ("Yegor Shilov", "Egor Shilov"),
        ("Brady Wassilyn", "Braidy Wassilyn"),
        ("Andrew O'Neill", "Andrew Neill"),
        ("Aleksei Vlasov", "Alexei Vlasov"),
        ("Benjamin Cossette Ayotte", "Benjamin Cossette-Ayotte"),
        ("Eddy Doyle", "Eddie Doyle"),
        ("Alofa Tunoa Ta'Amu", "Noa Taamu"),
        ("Romain Litalien", "Romain L'Italien"),
        ("Thomas Rousseau", "Tomas Rousseau"),
        ("Robert Cowan", "Bobby Cowan"),
        ("Korney Korneyev", "Kornei Korneyev"),
        ("Oliwer Sjostrom", "Oliwer Sjöström"),
        ("Filip Ruzicka", "Filip Růžička"),
        ("Jonathan Prud'homme", "Jonathan Prud"),
        ("Carl-Otto Magnusson", "Carl Otto Magnusson"),
        ("Noa Ta'amu", "Noa Taamu"),
        ("Filip Holst Persson", "Filip Holst Persson"),
        ("Louis-Francois Bélanger", "Louis-Francois Belanger"),
        ("William Håkansson", "William Hakansson"),
        ("Viggo Björck", "Viggo Bjorck"),
        ("Alberts Šmits", "Alberts Smits"),
        ("Vladimír Dravecký", "Vladimir Dravecky"),
        ("Olivers Mūrnieks", "Olivers Murnieks"),
        ("Rūdolfs Bērzkalns", "Rudolfs Berzkalns"),
        ("Adam Novotný", "Adam Novotony"),
    ]
    for a, b in pairs:
        ka, kb = normalize(a), normalize(b)
        NAME_ALIASES[ka] = kb
        NAME_ALIASES[kb] = kb


def html_unescape(s: str) -> str:
    return (
        s.replace("&#8217;", "'")
        .replace("&#x27;", "'")
        .replace("&amp;", "&")
        .replace("&#8211;", "-")
        .replace("&apos;", "'")
    )


def normalize(s: str) -> str:
    s = html_unescape(s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w\s\-'.]", "", s)
    return s.strip().lower()


def canonical_key(name: str) -> str:
    _build_aliases()
    k = normalize(name)
    return NAME_ALIASES.get(k, k)
