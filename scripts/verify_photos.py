#!/usr/bin/env python3
"""Vérifie que chaque joueur a un fichier portrait local valide."""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from build_site_data import slug_from_file
from draft_config import DEFAULT_DRAFT_YEAR, paths_for_year
from portrait_svg import REAL_EXTENSIONS

YEAR = DEFAULT_DRAFT_YEAR
paths = paths_for_year(YEAR)
rankings = json.loads(paths["rankings"].read_text(encoding="utf-8"))
players = json.loads((BASE / "site" / "data" / str(YEAR) / "players.json").read_text(encoding="utf-8"))
manifest = json.loads((paths["data_dir"] / "player_photos.json").read_text(encoding="utf-8"))
img_root = BASE / "site" / "images" / "players" / str(YEAR)

missing_file = []
no_url = []
ep_count = 0
svg_count = 0

for p in players:
    url = p.get("photoUrl") or ""
    if not url:
        no_url.append(p["name"])
        continue
    rel = url.lstrip("./")
    path = BASE / "site" / rel.replace("/", "\\")
    if not path.exists() or path.stat().st_size < 50:
        missing_file.append((p["name"], url))
    elif path.suffix.lower() in REAL_EXTENSIONS:
        slug = p["id"]
        if manifest.get(slug, {}).get("source") == "eliteprospects":
            ep_count += 1
        else:
            ep_count += 1
    elif path.suffix.lower() == ".svg":
        svg_count += 1

print(f"Players: {len(players)}")
print(f"photoUrl set: {len(players) - len(no_url)}/{len(players)}")
print(f"Files exist: {len(players) - len(missing_file)}/{len(players)}")
print(f"EP photos: {ep_count}, SVG: {svg_count}")
if missing_file:
    print("Missing files:", missing_file[:10])
if no_url:
    print("No URL:", no_url[:10])
sys.exit(1 if missing_file or no_url else 0)
