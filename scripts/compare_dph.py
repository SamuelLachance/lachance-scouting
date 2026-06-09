#!/usr/bin/env python3
"""Compare RAW_PLAYERS vs DPH index."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from generate_draft_board import RAW_PLAYERS, parse_players, normalize
from scripts.fetch_dph_prospects import fetch_dph_prospects

dph_rows = fetch_dph_prospects()
dph = {normalize(r["name"]): r for r in dph_rows}
ours = {p.key: p for p in parse_players(RAW_PLAYERS)}

missing = sorted(set(dph) - set(ours), key=lambda k: dph[k]["rank"])
extra = sorted(set(ours) - set(dph), key=lambda k: ours[k].full_name)

out = Path(__file__).parent / "compare_report.txt"
lines = [
    f"DPH: {len(dph)}",
    f"Ours: {len(ours)}",
    f"Missing in ours: {len(missing)}",
    f"Extra in ours (not DPH): {len(extra)}",
    "",
    "=== MISSING ===",
]
for k in missing:
    r = dph[k]
    lines.append(f"#{r['rank']:3d} {r['name']} | {r['pos']} | {r['nat']} | {r['team']}")

lines += ["", "=== EXTRA (ours only) ==="]
for k in extra:
    p = ours[k]
    lines.append(f"{p.full_name} | {p.pos} | {p.country}")

out.write_text("\n".join(lines), encoding="utf-8")
print("written", out)
