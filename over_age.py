"""
Détection des prospects over-age (2026) et cache des résultats du repêchage 2025.

Over-age = éligible au repêchage 2025 (né 2006-01-01 → 2007-09-15), non sélectionné,
et toujours éligible au repêchage 2026.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import date
from pathlib import Path
from typing import Optional

from draft_config import DEFAULT_DRAFT_YEAR, paths_for_year
from eligibility import is_over_age_2026, parse_dob
from name_utils import canonical_key

BASE = Path(__file__).parent

# Pénalité SPI explicite sur le score final (après multiplicateur de confiance).
# Rationale : un prospect déjà passé au repêchage sans être choisi offre moins
# de marge de développement et porte un signal négatif du marché NHL.
OVER_AGE_SPI_PENALTY = 5.0

_drafted_2025_cache: set[str] | None = None
_ep_dob_cache: dict[str, str] | None = None


def draft_2025_picks_path(year: int = DEFAULT_DRAFT_YEAR) -> Path:
    return paths_for_year(year)["data_dir"] / "draft_2025_picks.json"


def ep_draft_index_path(year: int = DEFAULT_DRAFT_YEAR) -> Path:
    return paths_for_year(year)["data_dir"] / "ep_draft_index.json"


def fetch_draft_2025_picks() -> list[dict]:
    """Télécharge les sélections 2025 depuis l'API NHL (User-Agent requis)."""
    url = "https://api-web.nhle.com/v1/draft/picks/2025/all"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data.get("picks") or []


def cache_draft_2025_picks(year: int = DEFAULT_DRAFT_YEAR) -> Path:
    """Persiste les résultats 2025 pour éviter des appels réseau répétés."""
    path = draft_2025_picks_path(year)
    if path.exists():
        return path
    picks = fetch_draft_2025_picks()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"draftYear": 2025, "picks": picks}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def load_drafted_2025_names(year: int = DEFAULT_DRAFT_YEAR) -> set[str]:
    """Noms canoniques des joueurs repêchés en 2025."""
    global _drafted_2025_cache
    if _drafted_2025_cache is not None:
        return _drafted_2025_cache

    path = draft_2025_picks_path(year)
    if not path.exists():
        cache_draft_2025_picks(year)
    data = json.loads(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for pick in data.get("picks") or []:
        fn = (pick.get("firstName") or {}).get("default", "")
        ln = (pick.get("lastName") or {}).get("default", "")
        if fn or ln:
            names.add(canonical_key(f"{fn} {ln}"))
    _drafted_2025_cache = names
    return names


def load_ep_dob_index(year: int = DEFAULT_DRAFT_YEAR) -> dict[str, str]:
    """DOB EP indexées par clé canonique."""
    global _ep_dob_cache
    if _ep_dob_cache is not None:
        return _ep_dob_cache

    path = ep_draft_index_path(year)
    index: dict[str, str] = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        for pl in data.get("players") or []:
            dob = pl.get("dateOfBirth") or ""
            if dob:
                index[canonical_key(pl.get("name", ""))] = dob
    _ep_dob_cache = index
    return index


def resolve_player_dob(
    full_name: str,
    *,
    rankings_dob: str = "",
    year: int = DEFAULT_DRAFT_YEAR,
) -> Optional[date]:
    """Résout la DOB : rankings → index EP."""
    dob = parse_dob(rankings_dob)
    if dob:
        return dob
    ep = load_ep_dob_index(year)
    return parse_dob(ep.get(canonical_key(full_name), ""))


def over_age_status(
    full_name: str,
    country: str,
    *,
    rankings_dob: str = "",
    year: int = DEFAULT_DRAFT_YEAR,
) -> dict:
    """
    Retourne is_over_age, penalty, drafted_in_2025, dob pour un prospect.
    """
    drafted = load_drafted_2025_names(year)
    key = canonical_key(full_name)
    drafted_in_2025 = key in drafted
    dob = resolve_player_dob(full_name, rankings_dob=rankings_dob, year=year)
    flag = is_over_age_2026(dob, country, drafted_in_2025=drafted_in_2025)
    is_oa = bool(flag)
    penalty = OVER_AGE_SPI_PENALTY if is_oa else 0.0
    return {
        "is_over_age": is_oa,
        "over_age_penalty": penalty,
        "drafted_in_2025": drafted_in_2025,
        "dob": dob.isoformat() if dob else None,
        "dob_known": dob is not None,
    }


def apply_over_age_spi_penalty(spi: float, is_over_age: bool) -> tuple[float, float]:
    """Applique la pénalité over-age sur le SPI final. Retourne (spi_final, penalty)."""
    if not is_over_age:
        return round(min(99.9, max(0.0, spi)), 2), 0.0
    penalty = OVER_AGE_SPI_PENALTY
    final = round(min(99.9, max(0.0, spi - penalty)), 2)
    return final, penalty
