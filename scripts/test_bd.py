#!/usr/bin/env python3
import sys
sys.path.insert(0, r"C:\Users\Admin\Projects\nhl-2026-draft")
from scripts.fetch_dph_prospects import fetch_dph_birthdate

for href in [
    "/prospects/liam-ruck",
    "/prospects/gavin-mckenna",
    "/prospects/chase-reid",
    "/prospects/ivar-stenberg",
]:
    bd = fetch_dph_birthdate(href)
    open(r"C:\Users\Admin\Projects\nhl-2026-draft\scripts\bd_test.txt", "a", encoding="utf-8").write(
        f"{href}: {bd!r}\n"
    )
