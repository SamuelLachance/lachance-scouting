"""Règles d'éligibilité au repêchage NHL 2026 (CBA / NHL)."""
from __future__ import annotations

from datetime import date
from typing import Optional

# Fenêtre principale : tous les joueurs
PRIMARY_START = date(2006, 1, 1)
PRIMARY_END = date(2008, 9, 15)

# Re-entry 2024 : repêchés en 2024 non signés, nés après le 30 juin 2006
REENTRY_CUTOFF = date(2006, 6, 30)

NA_COUNTRIES = frozenset({"CAN", "CDN", "USA"})


def normalize_country(country: str) -> str:
    c = (country or "").strip().upper()
    if c == "CDN":
        return "CAN"
    return c


def is_north_american(country: str) -> bool:
    return normalize_country(country) in NA_COUNTRIES


def is_draft_eligible_2026(
    dob: Optional[date],
    country: str,
    *,
    prior_draft_year: Optional[int] = None,
    signed_with_nhl: bool = False,
) -> Optional[bool]:
    """
    Retourne True/False si éligible, None si DOB inconnue (non filtrable).
    """
    if dob is None:
        return None

    # Règle principale : 1er jan 2006 — 15 sept 2008 (inclus)
    if PRIMARY_START <= dob <= PRIMARY_END:
        return True

    # Européens / non-NA non repêchés nés en 2005
    if not is_north_american(country) and prior_draft_year is None and dob.year == 2005:
        return True

    # Re-entry repêchage 2024
    if (
        prior_draft_year == 2024
        and not signed_with_nhl
        and dob > REENTRY_CUTOFF
    ):
        return True

    return False


def eligibility_label(
    dob: Optional[date],
    country: str,
    **kwargs,
) -> str:
    result = is_draft_eligible_2026(dob, country, **kwargs)
    if result is None:
        return "DOB_inconnue"
    return "eligible" if result else "ineligible"


def parse_dob(value: str) -> Optional[date]:
    """Parse YYYY-MM-DD ou formats DPH ('Dec 20, 2007')."""
    if not value or value in ("NA", "?", ""):
        return None
    value = value.strip()
    if re_match_iso := __import__("re").match(r"(\d{4})-(\d{2})-(\d{2})", value):
        y, m, d = map(int, re_match_iso.groups())
        return date(y, m, d)
    months = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    m = __import__("re").match(
        r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", value
    )
    if m:
        mon = months.get(m.group(1).lower()[:3])
        if mon:
            return date(int(m.group(3)), mon, int(m.group(2)))
    return None
