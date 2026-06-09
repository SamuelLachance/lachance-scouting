#!/usr/bin/env python3
"""Migration unique vers structure multi-repêchages (2026 = premier)."""
from __future__ import annotations

import shutil
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

MOVES = [
    (BASE / "data" / "rankings.json", BASE / "data" / "drafts" / "2026" / "rankings.json"),
    (BASE / "data" / "eligible_players.tsv", BASE / "data" / "drafts" / "2026" / "eligible_players.tsv"),
    (BASE / "data" / "scouting_reports.json", BASE / "data" / "drafts" / "2026" / "scouting_reports.json"),
    (BASE / "data" / "birthdates.json", BASE / "data" / "drafts" / "2026" / "birthdates.json"),
    (BASE / "data" / "dph_index_keys.json", BASE / "data" / "drafts" / "2026" / "dph_index_keys.json"),
    (BASE / "NHL_2026_Classement_Complet.csv", BASE / "exports" / "2026" / "NHL_2026_Classement_Complet.csv"),
]


def main() -> None:
    # analyses/joueurs -> analyses/2026
    src_analyses = BASE / "analyses_joueurs"
    dst_analyses = BASE / "analyses" / "2026"
    dst_analyses.mkdir(parents=True, exist_ok=True)

    if src_analyses.exists():
        for f in src_analyses.glob("*.md"):
            target = dst_analyses / f.name
            if not target.exists():
                shutil.move(str(f), str(target))
        if not any(src_analyses.iterdir()):
            src_analyses.rmdir()

    for src, dst in MOVES:
        if not src.exists():
            print(f"  skip (absent): {src.name}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            print(f"  keep existing: {dst}")
            continue
        shutil.move(str(src), str(dst))
        print(f"  moved: {src.name} -> {dst.relative_to(BASE)}")

    print("Migration terminée.")


if __name__ == "__main__":
    main()
