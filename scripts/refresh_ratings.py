#!/usr/bin/env python3
"""
Full NORTHSTAR rating refresh from web scouting reports.

Pipeline:
  1. fetch_scouting_reports.py  — refresh DPH pages
  2. evaluate_players_northstar.py — multi-source web evaluation
  3. generate_draft_board.py — rankings + markdown analyses
  4. build_site_data.py — site JSON

Usage:
  python scripts/refresh_ratings.py
  python scripts/refresh_ratings.py --skip-web
  python scripts/refresh_ratings.py --limit 50
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def run(cmd: list[str], label: str) -> None:
    print(f"\n=== {label} ===", flush=True)
    subprocess.run(cmd, cwd=BASE, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh all prospect ratings from scouting reports")
    parser.add_argument("--skip-web", action="store_true", help="Skip web re-fetch during evaluation")
    parser.add_argument("--skip-dph", action="store_true", help="Skip DPH report fetch")
    parser.add_argument("--limit", type=int, default=0, help="Limit players to evaluate (0=all)")
    parser.add_argument("--workers", type=int, default=12, help="Parallel evaluation workers")
    args = parser.parse_args()

    py = sys.executable

    if not args.skip_dph:
        run([py, "scripts/fetch_scouting_reports.py"], "Fetch DPH scouting reports")

    eval_cmd = [
        py, "scripts/evaluate_players_northstar.py",
        "--force", "--refresh-web", f"--workers={args.workers}", "--batch-save=10",
    ]
    if args.skip_web:
        eval_cmd.append("--skip-web")
    if args.limit:
        eval_cmd.extend(["--limit", str(args.limit)])
    run(eval_cmd, "Evaluate all players from web scouting sources")

    run([py, "generate_draft_board.py"], "Generate rankings and analyses")
    run([py, "build_site_data.py"], "Build site data")
    print("\nOK — ratings refreshed end-to-end.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
