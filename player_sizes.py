"""Normalize and resolve player height/weight for site display."""
from __future__ import annotations

import re
from typing import Any


def is_missing_size(value: Any) -> bool:
    if value is None:
        return True
    s = str(value).strip().upper()
    return s in ("", "NA", "N/A", "NONE", "NULL", "?")


def cm_to_feet_inches(cm: int | float) -> str:
    total_in = round(float(cm) / 2.54)
    feet, inches = divmod(total_in, 12)
    return f"{feet}'{inches}"


def kg_to_lbs(kg: int | float) -> int:
    return round(float(kg) * 2.20462)


def parse_imperial_height(raw: str) -> str | None:
    s = raw.strip().replace('"', "").replace("″", "")
    m = re.match(r"(\d+)['′]\s*(\d+)", s)
    if m:
        return f"{int(m.group(1))}'{int(m.group(2))}"
    m = re.match(r"(\d+)\s*ft\s*(\d+)\s*in", s, re.I)
    if m:
        return f"{int(m.group(1))}'{int(m.group(2))}"
    return None


def normalize_height(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        imp = raw.get("imperial")
        if imp:
            parsed = parse_imperial_height(str(imp))
            if parsed:
                return parsed
        metrics = raw.get("metrics")
        if metrics is not None:
            try:
                return cm_to_feet_inches(float(metrics))
            except (TypeError, ValueError):
                pass
        return None
    s = str(raw).strip()
    if is_missing_size(s):
        return None
    parsed = parse_imperial_height(s)
    if parsed:
        return parsed
    m = re.match(r"(\d+)['′](\d+)", s)
    if m:
        return f"{int(m.group(1))}'{int(m.group(2))}"
    return None


def normalize_weight_lbs(raw: Any) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        imp = raw.get("imperial")
        if imp is not None:
            try:
                return int(float(imp))
            except (TypeError, ValueError):
                pass
        metrics = raw.get("metrics")
        if metrics is not None:
            try:
                return kg_to_lbs(float(metrics))
            except (TypeError, ValueError):
                pass
        return None
    s = str(raw).strip().lower()
    if is_missing_size(s):
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if not m:
        return None
    val = float(m.group(1))
    if "kg" in s:
        return kg_to_lbs(val)
    return int(round(val))


def size_from_ep_player(player: dict) -> tuple[str | None, int | None]:
    return normalize_height(player.get("height")), normalize_weight_lbs(player.get("weight"))


def size_from_dph_report(report: dict) -> tuple[str | None, int | None]:
    h = normalize_height(report.get("height"))
    w = normalize_weight_lbs(report.get("weight"))
    return h, w
