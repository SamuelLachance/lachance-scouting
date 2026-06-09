#!/usr/bin/env python3
"""Rapport photos réelles pour un repêchage."""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from build_site_data import slug_from_file
from draft_config import DEFAULT_DRAFT_YEAR, paths_for_year
from portrait_svg import REAL_EXTENSIONS


def find_real(img_root: Path, slug: str) -> Path | None:
    for ext in REAL_EXTENSIONS:
        path = img_root / f"{slug}{ext}"
        if path.exists() and path.stat().st_size > 500:
            return path
    return None


def main() -> None:
    year = DEFAULT_DRAFT_YEAR
    paths = paths_for_year(year)
    rankings = json.loads(paths["rankings"].read_text(encoding="utf-8"))
    manifest = json.loads((paths["data_dir"] / "player_photos.json").read_text(encoding="utf-8"))
    img_root = BASE / "site" / "images" / "players" / str(year)

    with_real = []
    for p in rankings:
        slug = slug_from_file(p.get("Fichier_Local", p["Nom"].lower().replace(" ", "-")))
        real = find_real(img_root, slug)
        if real:
            entry = manifest.get(slug, {})
            with_real.append(
                (p["Rang_Final"], p["Nom"], real.name, entry.get("source", "?"))
            )

    print(f"Photos réelles: {len(with_real)}/{len(rankings)}")
    print("\nTop 10 (par rang):")
    for rank, name, fname, source in with_real[:10]:
        print(f"  #{rank} {name} — {fname} ({source})")

    print("\nÉchantillon:")
    for sample in ["Ivar Stenberg", "Wyatt Cullen", "Chase Reid", "Gavin McKenna"]:
        p = next((x for x in rankings if x["Nom"] == sample), None)
        if not p:
            continue
        slug = slug_from_file(p.get("Fichier_Local", p["Nom"].lower().replace(" ", "-")))
        real = find_real(img_root, slug)
        entry = manifest.get(slug, {})
        ext = real.suffix if real else (Path(entry.get("local", "")).suffix or "none")
        print(f"  {sample}: {ext} source={entry.get('source')} epId={entry.get('epId')}")


if __name__ == "__main__":
    main()
