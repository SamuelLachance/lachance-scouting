"""Génération de portraits SVG style carte prospect (thème sombre Lachance Scouting)."""
from __future__ import annotations

import re

REAL_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# accent primaire, accent secondaire (bande drapeau)
COUNTRY_COLORS: dict[str, tuple[str, str]] = {
    "CAN": ("#ef4444", "#ffffff"),
    "USA": ("#3b82f6", "#ffffff"),
    "SWE": ("#fbbf24", "#006aa7"),
    "FIN": ("#60a5fa", "#ffffff"),
    "CZE": ("#dc2626", "#11457e"),
    "SVK": ("#dc2626", "#0b4ea2"),
    "RUS": ("#dc2626", "#ffffff"),
    "LAT": ("#9f1239", "#ffffff"),
    "SUI": ("#dc2626", "#ffffff"),
    "GER": ("#fbbf24", "#111827"),
    "AUT": ("#dc2626", "#ffffff"),
    "NOR": ("#dc2626", "#2563eb"),
    "KAZ": ("#00afca", "#fbbf24"),
    "BLR": ("#dc2626", "#10b981"),
    "UNK": ("#0ea5e9", "#64748b"),
}

DEFAULT_COLORS = ("#0ea5e9", "#38bdf8")


def player_initials(name: str) -> str:
    parts = [p for p in re.split(r"\s+", name.strip()) if p]
    return "".join(p[0] for p in parts)[:2].upper()


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_portrait_svg(
    name: str,
    rank: int,
    position: str,
    country: str,
    draft_year: int = 2026,
) -> str:
    ini = _xml_escape(player_initials(name))
    pos = _xml_escape(position)
    ctry = _xml_escape(country or "UNK")
    accent, secondary = COUNTRY_COLORS.get(country, DEFAULT_COLORS)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="220" height="280" viewBox="0 0 220 280" role="img" aria-label="Portrait { _xml_escape(name) }">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.22"/>
      <stop offset="45%" stop-color="#111827"/>
      <stop offset="100%" stop-color="#0a0f1a"/>
    </linearGradient>
    <radialGradient id="glow" cx="50%" cy="18%" r="55%">
      <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.14"/>
      <stop offset="100%" stop-color="#030712" stop-opacity="0"/>
    </radialGradient>
    <clipPath id="card">
      <rect x="1" y="1" width="218" height="278" rx="14" ry="14"/>
    </clipPath>
  </defs>
  <g clip-path="url(#card)">
    <rect width="220" height="280" fill="#030712"/>
    <rect width="220" height="280" fill="url(#bg)"/>
    <rect width="220" height="280" fill="url(#glow)"/>
    <rect x="0" y="0" width="220" height="6" fill="{accent}" opacity="0.85"/>
    <rect x="0" y="6" width="220" height="4" fill="{secondary}" opacity="0.55"/>
    <line x1="16" y1="248" x2="204" y2="248" stroke="rgba(14,165,233,0.2)" stroke-width="1"/>
    <text x="110" y="128" text-anchor="middle" font-family="Syne, system-ui, sans-serif" font-size="72" font-weight="800" fill="rgba(226,232,240,0.92)" letter-spacing="4">{ini}</text>
    <text x="110" y="168" text-anchor="middle" font-family="'JetBrains Mono', monospace" font-size="11" font-weight="600" fill="#fbbf24" letter-spacing="2">#{rank}</text>
    <text x="110" y="190" text-anchor="middle" font-family="'JetBrains Mono', monospace" font-size="10" fill="#64748b" letter-spacing="2.5">{pos}</text>
    <text x="110" y="264" text-anchor="middle" font-family="'JetBrains Mono', monospace" font-size="9" fill="#475569" letter-spacing="1.5">{ctry} · NHL {draft_year}</text>
  </g>
  <rect x="1" y="1" width="218" height="278" rx="14" ry="14" fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="1"/>
  <rect x="1" y="1" width="218" height="278" rx="14" ry="14" fill="none" stroke="rgba(14,165,233,0.12)" stroke-width="1" transform="translate(0,0)"/>
</svg>
"""
