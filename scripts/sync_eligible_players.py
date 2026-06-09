#!/usr/bin/env python3
"""
Synchronise le pool de joueurs éligibles NHL 2026 :
- Index DPH (354) + liste existante, dédoublonnage par nom canonique
- Dates de naissance (fiches DPH quand disponibles)
- Filtrage selon règles CBA quand DOB connue
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from draft_config import DEFAULT_DRAFT_YEAR, paths_for_year
from eligibility import is_draft_eligible_2026, parse_dob  # noqa: E402
from generate_draft_board import RAW_PLAYERS, parse_players  # noqa: E402
from name_utils import canonical_key, html_unescape  # noqa: E402
from scripts.fetch_dph_prospects import fetch_dph_birthdate, fetch_dph_prospects  # noqa: E402

_paths = paths_for_year(DEFAULT_DRAFT_YEAR)
OUT_TSV = _paths["eligible_tsv"]
CACHE = _paths["birthdates"]
REPORT = _paths["data_dir"] / "eligibility_report.txt"
DPH_KEYS_FILE = _paths["data_dir"] / "dph_index_keys.json"

NAT_MAP = {
    "Canada": "CAN",
    "USA": "USA",
    "Sweden": "SWE",
    "Finland": "FIN",
    "Czechia": "CZE",
    "Slovakia": "SVK",
    "Russia": "RUS",
    "Switzerland": "SUI",
    "Latvia": "LAT",
    "Germany": "GER",
    "Norway": "NOR",
    "Hungary": "HUN",
    "Belarus": "BLR",
    "Kazakhstan": "KAZ",
    "Austria": "AUT",
}


def pos_clean(pos: str) -> str:
    p = (pos or "F").upper().strip()
    mapping = {"RD": "D", "LD": "D", "F": "C", "G": "G", "C": "C", "LW": "LW", "RW": "RW", "D": "D"}
    return mapping.get(p, p.split("/")[0] if "/" in p else p)


def split_name(full: str) -> tuple[str, str]:
    full = html_unescape(full.strip())
    parts = full.split()
    if len(parts) < 2:
        return full, ""
    return parts[-1], " ".join(parts[:-1])


def load_cache() -> dict[str, str | None]:
    if CACHE.exists():
        raw = json.loads(CACHE.read_text(encoding="utf-8"))
        return {k: (v if v else None) for k, v in raw.items()}
    return {}


def save_cache(cache: dict[str, str | None]) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(
        json.dumps({k: (v or "") for k, v in cache.items()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


@dataclass
class PoolEntry:
    last: str
    first: str
    pos: str
    height: str
    weight: str
    shoots: str
    country: str
    dob: date | None
    on_dph: bool
    source: str

    @property
    def full_name(self) -> str:
        return f"{self.first} {self.last}".strip()

    @property
    def key(self) -> str:
        return canonical_key(self.full_name)

    def to_tsv_line(self) -> str:
        dob_s = self.dob.isoformat() if self.dob else ""
        return (
            f"{self.last}, {self.first}\t{self.pos}\t{self.height}\t{self.weight}\t"
            f"{self.shoots}\t{self.country}\t{dob_s}"
        )


def fetch_birthdates(dph_rows: list[dict], cache: dict[str, str | None]) -> dict[str, str | None]:
    todo = [r for r in dph_rows if r["href"] not in cache]
    for i, row in enumerate(todo):
        href = row["href"]
        try:
            cache[href] = fetch_dph_birthdate(href)
            if (i + 1) % 25 == 0:
                save_cache(cache)
                print(f"  DOB fetch: {i + 1}/{len(todo)}")
            time.sleep(0.12)
        except Exception as e:
            cache[href] = None
            print(f"  WARN {href}: {e}")
    save_cache(cache)
    return cache


def build_pool(refetch_dob: bool = False) -> tuple[list[PoolEntry], list[str]]:
    log: list[str] = []
    pool: dict[str, PoolEntry] = {}
    dph_index_keys: set[str] = set()

    # Liste existante
    for p in parse_players(RAW_PLAYERS):
        pool[p.key] = PoolEntry(
            last=p.last,
            first=p.first,
            pos=p.pos,
            height=p.height,
            weight=p.weight,
            shoots=p.shoots,
            country=p.country,
            dob=p.birth_date,
            on_dph=False,
            source="existing",
        )
    log.append(f"Liste existante: {len(pool)}")

    dph_rows = fetch_dph_prospects()
    log.append(f"Index DPH: {len(dph_rows)}")

    cache = {} if refetch_dob else load_cache()
    if refetch_dob or len(cache) < len(dph_rows):
        cache = fetch_birthdates(dph_rows, cache)

    merged_dph = 0
    added_dph = 0
    dob_set = 0
    for row in dph_rows:
        name = html_unescape(row["name"])
        last, first = split_name(name)
        key = canonical_key(name)
        dph_index_keys.add(key)
        country = NAT_MAP.get(row["nat"], row["nat"][:3].upper() if row["nat"] else "UNK")
        dob_raw = cache.get(row["href"])
        dob = parse_dob(dob_raw) if dob_raw else None

        if key in pool:
            pool[key].on_dph = True
            if dob and pool[key].dob is None:
                pool[key].dob = dob
                dob_set += 1
            merged_dph += 1
            continue

        pool[key] = PoolEntry(
            last=last,
            first=first,
            pos=pos_clean(row["pos"]),
            height="NA",
            weight="NA",
            shoots="?",
            country=country,
            dob=dob,
            on_dph=True,
            source="dph",
        )
        added_dph += 1

    log.append(f"DPH fusionnés (déjà présents): {merged_dph}")
    log.append(f"Ajoutés depuis DPH: {added_dph}")
    log.append(f"DOB complétées: {dob_set}")

    DPH_KEYS_FILE.write_text(
        json.dumps(sorted(dph_index_keys), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    eligible: list[PoolEntry] = []
    ineligible: list[tuple[PoolEntry, str]] = []
    dob_validated = 0
    dob_unknown = 0

    for e in pool.values():
        result = is_draft_eligible_2026(e.dob, e.country)
        if result is False:
            ineligible.append((e, e.dob.isoformat() if e.dob else ""))
            continue
        if result is True:
            dob_validated += 1
        else:
            dob_unknown += 1
        eligible.append(e)

    log.append(f"Total unique: {len(pool)}")
    log.append(f"Pool final: {len(eligible)}")
    log.append(f"  DOB validée éligible: {dob_validated}")
    log.append(f"  DOB inconnue (conservés): {dob_unknown}")
    log.append(f"  Retirés (DOB hors fenêtre): {len(ineligible)}")

    if ineligible:
        log.append("\n--- Retirés (règles date de naissance) ---")
        for e, ds in sorted(ineligible, key=lambda x: x[0].full_name):
            log.append(f"  {e.full_name} | {ds} | {e.country} | dph={e.on_dph}")

    eligible.sort(key=lambda x: x.full_name)
    return eligible, log


def main() -> None:
    refetch = "--refetch-dob" in sys.argv
    print("Synchronisation pool éligible NHL 2026...")
    entries, log = build_pool(refetch_dob=refetch)

    OUT_TSV.parent.mkdir(parents=True, exist_ok=True)
    OUT_TSV.write_text("\n".join(e.to_tsv_line() for e in entries) + "\n", encoding="utf-8")

    report = "\n".join(log + [f"\nExport: {OUT_TSV}", f"Joueurs finaux: {len(entries)}"])
    REPORT.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
