"""Configuration centralisée des repêchages NHL — Lachance Scouting."""
from __future__ import annotations

from pathlib import Path

BASE = Path(__file__).parent
DEFAULT_DRAFT_YEAR = 2026

# Registre des repêchages (2026 = premier)
DRAFTS: dict[int, dict] = {
    2026: {
        "year": 2026,
        "label": "Repêchage 2026",
        "status": "active",
        "subtitle": "Buffalo · 26–27 juin 2026",
        "model": "northstar",
    },
    2027: {
        "year": 2027,
        "label": "Repêchage 2027",
        "status": "upcoming",
        "subtitle": "À venir",
        "model": "northstar",
    },
    2028: {
        "year": 2028,
        "label": "Repêchage 2028",
        "status": "upcoming",
        "subtitle": "À venir",
        "model": "northstar",
    },
    2029: {
        "year": 2029,
        "label": "Repêchage 2029",
        "status": "upcoming",
        "subtitle": "À venir",
        "model": "northstar",
    },
    2030: {
        "year": 2030,
        "label": "Repêchage 2030",
        "status": "upcoming",
        "subtitle": "À venir",
        "model": "northstar",
    },
}


def draft_data_dir(year: int) -> Path:
    return BASE / "data" / "drafts" / str(year)


def analyses_dir(year: int) -> Path:
    return BASE / "analyses" / str(year)


def export_dir(year: int) -> Path:
    return BASE / "exports" / str(year)


def paths_for_year(year: int) -> dict[str, Path]:
    d = draft_data_dir(year)
    e = export_dir(year)
    return {
        "data_dir": d,
        "rankings": d / "rankings.json",
        "eligible_tsv": d / "eligible_players.tsv",
        "scouting_reports": d / "scouting_reports.json",
        "player_evaluations": d / "player_evaluations.json",
        "birthdates": d / "birthdates.json",
        "analyses": analyses_dir(year),
        "csv": e / f"NHL_{year}_Classement_Complet.csv",
    }


def manifest_for_site() -> dict:
    years = []
    for year in sorted(DRAFTS.keys(), reverse=True):
        meta = DRAFTS[year].copy()
        p = paths_for_year(year)
        count = 0
        if p["rankings"].exists():
            import json
            count = len(json.loads(p["rankings"].read_text(encoding="utf-8")))
        meta["playerCount"] = count
        years.append(meta)
    return {
        "defaultYear": DEFAULT_DRAFT_YEAR,
        "brand": "Lachance Scouting",
        "years": years,
    }
