#!/usr/bin/env python3
"""Improved name matching between our list and DPH."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from generate_draft_board import RAW_PLAYERS, parse_players, normalize
from scripts.fetch_dph_prospects import fetch_dph_prospects

# Manual alias: normalized DPH key -> normalized our key
ALIASES = {
    normalize("Adam Novotný"): normalize("Adam Novotony"),
    normalize("J.P. Hurlbert"): normalize("J.P Hurlbert"),
    normalize("Markus Ruck"): normalize("Marcus Ruck"),
    normalize("Ilya Morozov"): normalize("Ilia Morozov"),
    normalize("Beckett Hamilton"): normalize("Reese Hamilton"),
    normalize("Michael Berchild"): normalize("Mikey Berchild"),
    normalize("Yegor Shilov"): normalize("Egor Shilov"),
    normalize("Brady Wassilyn"): normalize("Braidy Wassilyn"),
    normalize("Andrew O'Neill"): normalize("Andrew Neill"),
    normalize("Aleksei Vlasov"): normalize("Alexei Vlasov"),
    normalize("Benjamin Cossette Ayotte"): normalize("Benjamin Cossette-Ayotte"),
    normalize("Eddy Doyle"): normalize("Eddie Doyle"),
    normalize("Alofa Tunoa Ta'Amu"): normalize("Noa Taamu"),
    normalize("Romain Litalien"): normalize("Romain L'Italien"),
    normalize("Thomas Rousseau"): normalize("Tomas Rousseau"),
    normalize("Robert Cowan"): normalize("Bobby Cowan"),
    normalize("Cooper Cleaves"): normalize("Cooper Cleaves"),  # may be missing
    normalize("Korney Korneyev"): normalize("Kornei Korneyev"),
    normalize("Louis Felix Bourque"): normalize("Louis Felix Bourque"),
    normalize("Oliwer Sjostrom"): normalize("Oliwer Sjöström"),
    normalize("Filip Ruzicka"): normalize("Filip Růžička"),
    normalize("Jonathan Prud'homme"): normalize("Jonathan Prud"),
}


def map_dph_key(k: str, ours: set[str]) -> str | None:
    if k in ours:
        return k
    alias = ALIASES.get(k)
    if alias and alias in ours:
        return alias
    # fuzzy: last name match + first initial
    parts = k.split()
    if len(parts) >= 2:
        last = parts[-1]
        first = parts[0]
        for ok in ours:
            op = ok.split()
            if len(op) >= 2 and op[-1] == last and op[0][:2] == first[:2]:
                return ok
    return None


dph_rows = fetch_dph_prospects()
dph = {normalize(r["name"]): r for r in dph_rows}
ours = {p.key: p for p in parse_players(RAW_PLAYERS)}

matched = {}
missing = []
for dk, dr in sorted(dph.items(), key=lambda x: x[1]["rank"]):
    mk = map_dph_key(dk, set(ours))
    if mk:
        matched[dk] = mk
    else:
        missing.append(dr)

extra = [ours[k] for k in ours if k not in set(matched.values())]

out = Path(__file__).parent / "compare_report_v2.txt"
lines = [
    f"DPH: {len(dph)}",
    f"Ours: {len(ours)}",
    f"Matched: {len(matched)}",
    f"Missing in ours: {len(missing)}",
    f"Extra in ours: {len(extra)}",
    "",
    "=== MISSING (truly absent) ===",
]
for r in missing:
    lines.append(f"#{r['rank']:3d} {r['name']} | {r['pos']} | {r['nat']}")

out.write_text("\n".join(lines), encoding="utf-8")
print("written", out, "missing", len(missing))
