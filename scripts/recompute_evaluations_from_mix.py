#!/usr/bin/env python3
"""Re-merge NORTHSTAR evaluations from cached source_mix (no web re-fetch)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from draft_config import DEFAULT_DRAFT_YEAR, paths_for_year
from generate_draft_board import load_players
from northstar_scoring import (
    MIN_SOURCE_ATTEMPTS,
    NORTHSTAR_LABELS,
    NORTHSTAR_WEIGHTS,
    _confidence_multiplier,
    apply_physical_adjustments,
    northstar_overall,
    source_count_confidence_multiplier,
    weighted_merge_sources,
)
from scripts.evaluate_players_northstar import (
    OUT,
    build_pillar_rationales,
    build_forces_faiblesses,
    load_reports,
    save_checkpoint,
)

_paths = paths_for_year(DEFAULT_DRAFT_YEAR)
REPORTS = _paths["scouting_reports"]


def mix_to_contributions(source_mix: list[dict]) -> list[dict]:
    contributions = []
    for entry in source_mix:
        sid = entry.get("source")
        if not sid or not entry.get("pillars"):
            continue
        quality = float(entry.get("quality", 1.0))
        contributions.append({
            "source_id": sid,
            "pillars": entry["pillars"],
            "evidence": {},
            "quality": quality,
            "text_quality": quality,
            "snippet": entry.get("snippet", ""),
            "url": entry.get("url", ""),
        })
    return contributions


def recompute_player(ev: dict, player, report: dict) -> dict:
    contributions = mix_to_contributions(ev.get("source_mix") or [])
    if not contributions:
        return ev

    dims, evidence, source_mix, cov = weighted_merge_sources(contributions)
    dims = apply_physical_adjustments(dims, player.pos, player.height, player.weight)
    pillars = build_pillar_rationales(
        dims, evidence, report, cov, source_mix, player.full_name,
    )
    forces, faiblesses = build_forces_faiblesses(
        dims, report, evidence, player.pos, player.height, player.weight, cov,
    )
    n_sources = len(source_mix)
    spi = (
        northstar_overall(dims)
        * _confidence_multiplier(cov)
        * source_count_confidence_multiplier(n_sources)
    )
    spi = round(min(99.9, max(0, spi)), 2)

    raw = dict(ev.get("raw") or {})
    raw["top_source_share"] = max((s.get("weight_share", 0) for s in source_mix), default=0)
    raw["contributions"] = len(contributions)

    return {
        **ev,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "confidence": cov,
        "report_coverage": cov,
        "source_mix": source_mix,
        "pillars": pillars,
        "forces": forces,
        "faiblesses": faiblesses,
        "spi": spi,
        "raw": raw,
    }


def main() -> None:
    players = {p.key: p for p in load_players()}
    reports = load_reports()
    data = json.loads(OUT.read_text(encoding="utf-8"))
    updated = 0
    for key, ev in data.get("players", {}).items():
        if ev.get("status") != "done" or not ev.get("source_mix"):
            continue
        player = players.get(key)
        if not player:
            continue
        data["players"][key] = recompute_player(ev, player, reports.get(key, {}))
        updated += 1

    data["meta"]["version"] = 5
    data["meta"]["weighting"] = "reliability_redistributed"
    data["meta"]["weight_formula"] = (
        "reliability_effective × quality; missing catalog weight redistributed equally"
    )
    data["meta"]["min_source_attempts"] = MIN_SOURCE_ATTEMPTS
    data["meta"]["recomputed_at"] = datetime.now(timezone.utc).isoformat()
    save_checkpoint(data)
    print(f"Recomputed {updated} players with reliability-redistributed weights.")


if __name__ == "__main__":
    main()
