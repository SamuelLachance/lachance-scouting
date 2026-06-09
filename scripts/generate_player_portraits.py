#!/usr/bin/env python3
"""Garantit un portrait local pour chaque joueur (photo réelle ou SVG généré)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from build_site_data import slug_from_file
from draft_config import DEFAULT_DRAFT_YEAR, paths_for_year
from photo_fetch import download_photo, load_photo_manifest, save_photo_manifest
from portrait_svg import REAL_EXTENSIONS, build_portrait_svg


def find_real_file(img_root: Path, slug: str) -> Path | None:
    for ext in REAL_EXTENSIONS:
        path = img_root / f"{slug}{ext}"
        if path.exists() and path.stat().st_size > 500:
            return path
    return None


def local_rel(year: int, filename: str) -> str:
    return f"./images/players/{year}/{filename}"


def ensure_portraits(year: int = DEFAULT_DRAFT_YEAR) -> dict[str, int]:
    paths = paths_for_year(year)
    rankings = json.loads(paths["rankings"].read_text(encoding="utf-8"))
    manifest_path = paths["data_dir"] / "player_photos.json"
    img_root = BASE / "site" / "images" / "players" / str(year)
    img_root.mkdir(parents=True, exist_ok=True)
    manifest = load_photo_manifest(manifest_path)

    stats = {"real": 0, "generated": 0, "downloaded": 0, "skipped_real": 0}

    for p in rankings:
        slug = slug_from_file(p.get("Fichier_Local", p["Nom"].lower().replace(" ", "-")))
        name = p["Nom"]
        entry = manifest.get(slug, {})

        real_file = find_real_file(img_root, slug)
        if real_file:
            rel = local_rel(year, real_file.name)
            manifest[slug] = {
                "name": name,
                "local": rel,
                "sourceUrl": entry.get("sourceUrl"),
                "source": entry.get("source"),
                "generated": False,
            }
            if entry.get("epId"):
                manifest[slug]["epId"] = entry["epId"]
            stats["real"] += 1
            stats["skipped_real"] += 1
            continue

        source_url = entry.get("sourceUrl")
        if source_url:
            saved = download_photo(source_url, img_root / slug)
            if saved and saved.suffix.lower() in REAL_EXTENSIONS:
                rel = local_rel(year, saved.name)
                manifest[slug] = {
                    "name": name,
                    "local": rel,
                    "sourceUrl": source_url,
                    "source": entry.get("source"),
                    "generated": False,
                }
                if entry.get("epId"):
                    manifest[slug]["epId"] = entry["epId"]
                stats["real"] += 1
                stats["downloaded"] += 1
                continue

        svg_path = img_root / f"{slug}.svg"
        svg_path.write_text(
            build_portrait_svg(
                name=name,
                rank=int(p["Rang_Final"]),
                position=p.get("Position", ""),
                country=p.get("Pays", "UNK"),
                draft_year=year,
            ),
            encoding="utf-8",
        )
        rel = local_rel(year, svg_path.name)
        manifest[slug] = {
            "name": name,
            "local": rel,
            "sourceUrl": source_url,
            "generated": True,
        }
        stats["generated"] += 1

    save_photo_manifest(manifest_path, manifest)
    return stats


def main() -> None:
    year = DEFAULT_DRAFT_YEAR
    stats = ensure_portraits(year)
    paths = paths_for_year(year)
    rankings = json.loads(paths["rankings"].read_text(encoding="utf-8"))
    total = len(rankings)
    with_local = sum(
        1
        for slug_data in json.loads(
            (paths["data_dir"] / "player_photos.json").read_text(encoding="utf-8")
        ).values()
        if slug_data.get("local")
    )
    print(
        f"Terminé {year}: {with_local}/{total} portraits "
        f"({stats['real']} réels dont {stats['downloaded']} téléchargés, "
        f"{stats['generated']} générés SVG)"
    )


if __name__ == "__main__":
    main()
