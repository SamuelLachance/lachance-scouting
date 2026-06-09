#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from generate_draft_board import parse_players
from name_utils import canonical_key

players = parse_players(Path("data/eligible_players.tsv").read_text(encoding="utf-8"))
keys = [p.key for p in players]
print("count", len(players), "unique keys", len(set(keys)))
from collections import Counter
dups = [k for k,v in Counter(keys).items() if v>1]
print("dups", len(dups))
for k in dups[:10]:
    print(" ", k)
