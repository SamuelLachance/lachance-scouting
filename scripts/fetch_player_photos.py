#!/usr/bin/env python3
"""Télécharge les portraits joueurs → site/images/players/{year}/ + manifest JSON."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from draft_config import DEFAULT_DRAFT_YEAR, paths_for_year
from build_site_data import slug_from_file
from photo_fetch import download_photo, find_photo_url, load_photo_manifest, save_photo_manifest

DELAY = 0.75


def main() -> None:
    year = DEFAULT_DRAFT_YEAR
    paths = paths_for_year(year)
    rankings = json.loads(paths["rankings"].read_text(encoding="utf-8"))
    manifest_path = paths["data_dir"] / "player_photos.json"
    img_root = BASE / "site" / "images" / "players" / str(year)
    manifest = load_photo_manifest(manifest_path)

    found = 0
    skipped = 0
    for i, p in enumerate(rankings):
        slug = slug_from_file(p.get("Fichier_Local", p["Nom"].lower().replace(" ", "-")))
        name = p["Nom"]
        birth = p.get("Date_Naissance") or ""

        entry = manifest.get(slug, {})
        local_rel = entry.get("local")
        local_file = BASE / "site" / local_rel.lstrip("./") if local_rel else None
        if local_file and local_file.exists() and entry.get("name") == name:
            skipped += 1
            continue

        url = entry.get("sourceUrl")
        if not url:
            url = find_photo_url(name, birth or None)
            time.sleep(DELAY)

        if not url:
            manifest[slug] = {"name": name, "local": None, "sourceUrl": None}
            if (i + 1) % 25 == 0:
                save_photo_manifest(manifest_path, manifest)
                print(f"  {i + 1}/{len(rankings)} — {found} photos")
            continue

        dest = img_root / slug
        saved = download_photo(url, dest)
        if saved:
            for f in img_root.glob(slug + ".*"):
                if f != saved:
                    f.unlink(missing_ok=True)
            rel = f"./images/players/{year}/{saved.name}"
            manifest[slug] = {"name": name, "local": rel, "sourceUrl": url}
            found += 1
            print(f"  OK {name}")
        else:
            manifest[slug] = {"name": name, "local": None, "sourceUrl": url}

        if (i + 1) % 10 == 0:
            save_photo_manifest(manifest_path, manifest)

    save_photo_manifest(manifest_path, manifest)
    with_photo = sum(1 for v in manifest.values() if v.get("local"))
    print(f"Fetch Wikimedia: {with_photo}/{len(rankings)} photos réelles ({skipped} déjà en cache)")

    sys.path.insert(0, str(BASE / "scripts"))
    from generate_player_portraits import ensure_portraits

    stats = ensure_portraits(year)
    print(
        f"Portraits complets: {stats['real']} réels, {stats['generated']} SVG générés "
        f"({stats['downloaded']} téléchargés cette passe)"
    )


if __name__ == "__main__":
    main()
