"""
NORTHSTAR — NHL Outcome Rating Through Scouting Heuristics And Report Text

Modèle refondu de zéro : chaque joueur est évalué à partir de son rapport
de scouting (DPH) + signaux contextuels. Objectif : probabilité d'étoile NHL.

7 piliers /10 → score NORTHSTAR /100 (Star Probability Index)
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from draft_config import DEFAULT_DRAFT_YEAR, paths_for_year

BASE = Path(__file__).parent
_paths = paths_for_year(DEFAULT_DRAFT_YEAR)
REPORTS_PATH = _paths["scouting_reports"]
EVALUATIONS_PATH = _paths["player_evaluations"]

# Pondérations — optimisées pour prédire le plafond ÉTOILE (pas le floor)
NORTHSTAR_WEIGHTS = {
    "star_ceiling": 0.35,       # Plafond franchise / all-star
    "hockey_iq": 0.18,          # Traitement, vision, maturité
    "skating_engine": 0.15,     # Patinage transposable NHL
    "offensive_star_power": 0.12,  # Création + finition élite
    "competition_proof": 0.10,  # Preuve vs compétition adulte/junior top
    "character_compete": 0.05,  # Moteur, leadership, clutch
    "development_arc": 0.05,    # Trajectoire / croissance
}

NORTHSTAR_LABELS = {
    "star_ceiling": "Plafond étoile NHL ★",
    "hockey_iq": "IQ / processing élite",
    "skating_engine": "Moteur de patinage",
    "offensive_star_power": "Pouvoir offensif star",
    "competition_proof": "Preuve vs compétition",
    "character_compete": "Compétitivité / caractère",
    "development_arc": "Arc de développement",
}

META_KEYS = (
    "resume", "forces", "faiblesses", "comparable", "projection",
    "star_thesis", "consensus_delta", "rationales", "evidence",
    "report_coverage", "star_tier",
)

# Lexiques — mots-clés scouting → signal dimension (poids)
LEX: dict[str, list[tuple[str, float]]] = {
    "star_ceiling": [
        (r"franchise", 2.5), (r"generational", 3.0), (r"cornerstone", 2.5),
        (r"superstar", 2.8), (r"elite talent", 2.2), (r"tier.of.his own", 3.0),
        (r"transcendent", 2.8), (r"hart", 2.5), (r"norris", 2.5),
        (r"rocket richard", 2.0), (r"top.line", 1.8), (r"top.pair", 1.8),
        (r"first.line", 1.8), (r"all.star", 2.0), (r"elite", 1.2),
        (r"franchise winger", 2.5), (r"franchise center", 2.5),
        (r"franchise defense", 2.5), (r"1st overall", 2.5), (r"#1 overall", 2.5),
        (r"best player", 2.0), (r"game.breaker", 2.2), (r"impact player", 1.5),
        (r"pp1", 1.2), (r"power play quarterback", 1.5),
        (r"top.nine", -1.2), (r"top.four", 0.5), (r"watch.list", 0.3),
        (r"depth", -1.5), (r"bottom.six", -2.0), (r"fourth line", -2.5),
        (r"role player", -1.8), (r"organizational", -2.0), (r"backup", -2.0),
        (r"project", -0.8), (r"ceiling limited", -1.5),
    ],
    "hockey_iq": [
        (r"hockey sense", 2.5), (r"hockey iq", 2.5), (r"processing", 2.0),
        (r"vision", 2.0), (r"playmaker", 1.8), (r"playmaking", 1.8),
        (r"maturity", 1.5), (r"decision", 1.5), (r"anticipat", 1.8),
        (r"awareness", 1.5), (r"intelligent", 1.5), (r"sense", 1.0),
        (r"creates time", 1.8), (r"dictate", 1.8), (r"reads the play", 2.0),
        (r"panic", -1.5), (r"inconsistent effort", -1.2),
    ],
    "skating_engine": [
        (r"skating", 2.0), (r"skater", 1.5), (r"strong skater", 2.2),
        (r"elite speed", 2.5), (r"acceleration", 2.0),
        (r"agility", 1.8), (r"edges", 1.8), (r"quickness", 2.0),
        (r"explosive", 2.0), (r"dynamic", 1.5), (r"transition", 1.5),
        (r"shifty", 1.8), (r"evasive", 1.8), (r"mobile", 1.5),
        (r"stride", 1.5), (r"footwork", 1.5), (r"slow", -2.0),
        (r"plodding", -2.0), (r"heavy feet", -1.8),
    ],
    "offensive_star_power": [
        (r"goal scorer", 2.0), (r"scoring", 1.5), (r"shot", 1.8),
        (r"release", 1.8), (r"hands", 1.8), (r"skill", 1.2),
        (r"offensive", 1.2), (r"creates offense", 2.0), (r"play.driver", 2.2),
        (r"production", 1.5), (r"points", 1.2), (r"pp threat", 1.8),
        (r"finishing", 1.8), (r"deke", 1.5), (r"dangle", 1.5),
        (r"limited offense", -1.8), (r"defensive specialist", -1.0),
    ],
    "competition_proof": [
        (r"ncaa", 1.5), (r"shl", 1.8), (r"liiga", 1.5), (r"khl", 1.8),
        (r"ohl", 1.2), (r"whl", 1.2), (r"qmjhl", 1.2), (r"international", 1.5),
        (r"world junior", 1.8), (r"u18", 1.0), (r"men", 1.5), (r"older competition", 2.0),
        (r"dominat", 1.8), (r"proven", 1.5), (r"high level", 1.5),
    ],
    "character_compete": [
        (r"compete", 2.0), (r"competitive", 2.0), (r"leadership", 1.8),
        (r"character", 1.5), (r"clutch", 1.8), (r"work ethic", 1.8),
        (r"battle", 1.5), (r"physical", 1.2), (r"intensity", 1.5),
        (r"fearless", 1.8), (r"confident", 1.2), (r"lazy", -2.0),
        (r"effort concern", -1.8), (r"disappear", -1.5),
    ],
    "development_arc": [
        (r"trajectory", 2.0), (r"rising", 2.0), (r"breakout", 2.0),
        (r"improved", 1.5), (r"growth", 1.8), (r"upside", 1.5),
        (r"development", 1.0), (r"youngest", 1.5), (r"late bloomer", 1.0),
        (r"stagnant", -1.8), (r"regress", -2.0), (r"plateau", -1.5),
        (r"growth spurt", 2.0), (r"added muscle", 1.5), (r"riser", 2.0),
    ],
}

GRADE_SCORES = {
    "A+": 9.8, "A": 9.2, "A-": 8.7,
    "B+": 8.0, "B": 7.3, "B-": 6.7,
    "C+": 6.0, "C": 5.3, "C-": 4.8,
    "D": 4.0, "F": 2.5,
}

LEAGUE_TIER = {
    "NCAA": 9.0, "SHL": 9.2, "LIIGA": 8.8, "KHL": 9.0, "MHL": 7.5,
    "OHL": 8.0, "WHL": 8.0, "QMJHL": 8.0, "USHL": 7.8,
    "J20": 7.5, "U20": 7.5, "HIGH SCHOOL": 6.5, "NAHL": 6.8, "BCHL": 7.0,
}

TAG_BOOSTS = {
    "elite": 1.5, "generational": 2.5, "1st round": 1.2, "first round": 1.2,
    "riser": 1.0, "safe": -0.5, "project": -0.8,
}

_reports_cache: dict | None = None
_evaluations_cache: dict | None = None


def _load_evaluations() -> dict:
    global _evaluations_cache
    if _evaluations_cache is None:
        if EVALUATIONS_PATH.exists():
            _evaluations_cache = json.loads(EVALUATIONS_PATH.read_text(encoding="utf-8"))
        else:
            _evaluations_cache = {"meta": {}, "players": {}}
    return _evaluations_cache


def _load_reports() -> dict:
    global _reports_cache
    if _reports_cache is None:
        if REPORTS_PATH.exists():
            _reports_cache = json.loads(REPORTS_PATH.read_text(encoding="utf-8"))
        else:
            _reports_cache = {}
    return _reports_cache


def parse_height(h: str) -> float:
    if not h or h in ("NA", "?"):
        return 72.0
    m = re.match(r"(\d)'(\d+)", h.replace("\\", ""))
    if m:
        return int(m.group(1)) * 12 + int(m.group(2))
    m2 = re.match(r"(\d)\s*ft?\s*(\d+)?", h.lower())
    if m2:
        return int(m2.group(1)) * 12 + int(m2.group(2) or 0)
    return 72.0


def parse_weight(w: str) -> int:
    if not w or w in ("NA", "?"):
        return 180
    m = re.search(r"(\d+)", str(w))
    return int(m.group(1)) if m else 180


def _scoring_text(report: dict) -> str:
    """Texte vérifiable pour scoring — exclut faq_text (boilerplate SEO DPH)."""
    parts = [
        report.get("report", ""),
        report.get("meta_description", ""),
        report.get("projection", ""),
        " ".join(report.get("strengths") or []),
        " ".join(report.get("weaknesses") or []),
        " ".join(report.get("tags") or []),
        report.get("league", ""),
    ]
    return " ".join(p for p in parts if p).lower()


def _text_blob(report: dict) -> str:
    return _scoring_text(report)


def _lex_score(dim: str, text: str) -> tuple[float, list[str]]:
    """Score 0-10 from keyword hits + evidence snippets."""
    hits: list[str] = []
    raw = 5.0
    for pattern, weight in LEX.get(dim, []):
        if re.search(pattern, text, re.I):
            raw += weight
            hits.append(pattern.replace(".", " ").replace("\\", ""))
    raw = max(1.0, min(10.0, raw))
    return raw, hits[:5]


def _grade_score(grade: str) -> float:
    return GRADE_SCORES.get(grade.upper().strip(), 5.5)


def _league_score(league: str, text: str) -> float:
    blob = (league + " " + text).upper()
    best = 5.5
    for key, val in LEAGUE_TIER.items():
        if key in blob:
            best = max(best, val)
    return best


def _production_score(stats: dict, pos: str) -> float:
    gp = stats.get("gp")
    pts = stats.get("pts")
    if not gp or not pts or gp <= 0:
        return 5.5
    rate = pts / gp
    is_g = pos.upper() in ("G", "GK")
    if is_g:
        return 5.5
    if rate >= 1.3:
        return 9.5
    if rate >= 1.0:
        return 8.5
    if rate >= 0.7:
        return 7.5
    if rate >= 0.5:
        return 6.5
    if rate >= 0.3:
        return 5.5
    return 4.5


def _dph_rank_score(rank: int | None) -> float:
    if rank is None:
        return 5.5
    if rank <= 5:
        return 9.8
    if rank <= 15:
        return 9.0
    if rank <= 32:
        return 8.0
    if rank <= 64:
        return 7.0
    if rank <= 100:
        return 6.0
    if rank <= 200:
        return 5.0
    return 4.0


# Phrases boilerplate DPH — pas du scouting substantiel
DPH_TEMPLATE_MARKERS = (
    r"watch-list",
    r"middle-rounds",
    r"translatable nhl tools",
    r"developmental runway",
    r"late-round watch-list",
)


def _is_dph_template(text: str) -> bool:
    return any(re.search(p, text, re.I) for p in DPH_TEMPLATE_MARKERS)


def _report_quality(report: dict) -> str:
    """
    Couverture rapport — signaux vérifiables uniquement.

    Règles objectives (pas de consensus externe):
    - none: aucune donnée DPH récupérée
    - thin: page DPH template (texte court, pas de stats) — confiance basse
    - partial: métadonnées ou extrait sans corps substantiel
    - full: rapport substantiel (≥150 mots OU stats de saison)
    """
    if not report or (not report.get("fetched") and not report.get("report")):
        return "none"
    text = _scoring_text(report)
    word_count = len(text.split())
    stats = report.get("stats") or {}
    has_stats = bool(stats.get("gp") or stats.get("pts"))
    if _is_dph_template(text) and not has_stats:
        return "thin"
    if has_stats and word_count >= 40:
        return "full"
    if word_count >= 150 and (report.get("strengths") or report.get("weaknesses")):
        return "full"
    if word_count < 80 and not has_stats:
        return "thin"
    if report.get("meta_description") or report.get("report"):
        return "partial"
    return "none"


def _confidence_multiplier(cov: str) -> float:
    """Pénalité explicite quand le rapport manque ou est mince."""
    return {"full": 1.0, "partial": 0.94, "thin": 0.86, "none": 0.76}.get(cov, 0.76)


def _apply_coverage_penalty(dims: dict[str, float], cov: str, grade: float) -> dict[str, float]:
    """
    Régression vers la neutre (5.0) + plafond star quand preuve insuffisante.
    Empêche les scores élite sur du boilerplate DPH.
    """
    out = dims.copy()
    if cov == "full":
        return out
    pull = {"partial": 0.12, "thin": 0.28, "none": 0.42}.get(cov, 0.42)
    for k in out:
        out[k] = out[k] * (1 - pull) + 5.0 * pull
    if cov in ("thin", "none"):
        # Plafond étoile borné par la note DPH + marge modeste (pas de hype)
        out["star_ceiling"] = min(out["star_ceiling"], grade + 1.2)
    if cov == "none":
        out["star_ceiling"] = min(out["star_ceiling"], 6.5)
    return {k: round(min(10, max(1, v)), 1) for k, v in out.items()}


def _star_tier(score: float) -> str:
    if score >= 92:
        return "Franchise / generational"
    if score >= 85:
        return "All-Star élevé"
    if score >= 75:
        return "Star potentielle"
    if score >= 65:
        return "Top-6 / top-pair"
    if score >= 55:
        return "NHL régulier"
    if score >= 45:
        return "Profondeur / tweener"
    return "Long shot"


# ---------------------------------------------------------------------------
# EA Sports NHL franchise-mode potential tiers (NHL 22–26 / Puck Drop reference)
# Mapped from SPI (0–100) → position-specific label (French UI).
#
# SPI thresholds are recalibrated for draft-prospect upside (not pro OVR).
# Draft-rank floors ensure top picks never project as depth roles.
# ---------------------------------------------------------------------------
EA_TIER_BANDS: dict[str, list[tuple[float, str, str]]] = {
    # (min_spi_inclusive, label_fr, label_en) — sorted high → low
    "F": [
        (88.0, "Générationnel", "Generational"),
        (82.0, "Franchise", "Franchise"),
        (75.0, "Élite", "Elite"),
        (68.0, "Top 6", "Top 6 F"),
        (62.0, "Top 9", "Top 9 F"),
        (58.0, "Quatrième trio", "Bottom 6 F"),
        (54.0, "LHA Top 6", "AHL Top 6 F"),
        (50.0, "LHA Quatrième trio", "AHL Bottom 6 F"),
        (46.0, "Profondeur mineure", "Minor Depth F"),
        (0.0, "Profondeur LHA", "AHL Depth F"),
    ],
    "D": [
        (88.0, "Générationnel", "Generational"),
        (82.0, "Franchise", "Franchise"),
        (75.0, "Élite", "Elite"),
        (68.0, "Top 4", "Top 4 D"),
        (62.0, "Top 6", "Top 6 D"),
        (58.0, "7e D", "7th D"),
        (54.0, "LHA Top 6", "AHL Top 6 D"),
        (50.0, "LHA Quatrième trio", "AHL Bottom 6 D"),
        (46.0, "Profondeur mineure", "Minor Depth D"),
        (0.0, "Profondeur LHA", "AHL Depth D"),
    ],
    "G": [
        (88.0, "Générationnel", "Generational"),
        (82.0, "Franchise", "Franchise"),
        (75.0, "Élite", "Elite"),
        (68.0, "Titulaire", "Starter"),
        (62.0, "Titulaire partiel", "Fringe Starter"),
        (58.0, "Remplaçant", "Backup"),
        (54.0, "LHA Titulaire", "AHL Starter"),
        (50.0, "LHA Remplaçant", "AHL Backup G"),
        (46.0, "Profondeur mineure", "Minor Backup G"),
        (0.0, "Profondeur LHA", "AHL Depth G"),
    ],
}


def ea_position_group(position: str) -> str:
    """Map C/LW/RW → F, D → D, G → G."""
    p = (position or "").upper().strip()
    if p in ("G", "GK", "GOALIE", "GOALTENDER"):
        return "G"
    if "D" in p:
        return "D"
    return "F"


# Role depth labels for EA-style NHL projection text (FR, EN) by position group + SPI.
EA_ROLE_DEPTH: dict[str, list[tuple[float, str, str]]] = {
    "F": [
        (75.0, "Premier trio", "Top-line"),
        (68.0, "Top six", "Top-six"),
        (62.0, "Troisième trio", "Top-nine"),
        (58.0, "Quatrième trio", "Bottom-six"),
        (54.0, "Top six LHA", "AHL top-six"),
        (50.0, "Quatrième trio LHA", "AHL bottom-six"),
        (46.0, "Profondeur mineure", "Depth"),
        (0.0, "Profondeur LHA", "AHL depth"),
    ],
    "D": [
        (75.0, "Première paire", "Top-pair"),
        (68.0, "Top six", "Top-six"),
        (62.0, "Troisième paire", "Third-pair"),
        (58.0, "7e D", "Seventh D"),
        (54.0, "Top six LHA", "AHL top-six"),
        (50.0, "Quatrième trio LHA", "AHL bottom-six"),
        (46.0, "Profondeur mineure", "Minor depth"),
        (0.0, "Profondeur LHA", "AHL depth"),
    ],
    "G": [
        (75.0, "Titulaire", "Starter"),
        (68.0, "Titulaire partiel", "Fringe starter"),
        (62.0, "Remplaçant", "Backup"),
        (58.0, "Titulaire LHA", "AHL starter"),
        (54.0, "Remplaçant LHA", "AHL backup"),
        (50.0, "Profondeur mineure", "Minor backup"),
        (0.0, "Profondeur LHA", "AHL depth"),
    ],
}

EA_TIER_ADJECTIVES: list[tuple[float, str, str]] = [
    (88.0, "générationnel", "generational"),
    (82.0, "franchise", "franchise"),
    (68.0, "élite", "elite"),
]

# Draft-rank floors: (min_rank, max_rank, min_role, min_adj_fr, min_adj_en, min_tier)
# Roles/tiers keyed by position group (F/D/G). Lists sorted best → worst.
EA_DRAFT_RANK_FLOORS: list[
    tuple[
        int,
        int,
        dict[str, tuple[str, str]],
        str,
        str,
        dict[str, tuple[str, str]],
    ]
] = [
    (
        1,
        5,
        {
            "F": ("Premier trio", "Top-line"),
            "D": ("Première paire", "Top-pair"),
            "G": ("Titulaire", "Starter"),
        },
        "élite",
        "elite",
        {
            "F": ("Élite", "Elite"),
            "D": ("Élite", "Elite"),
            "G": ("Élite", "Elite"),
        },
    ),
    (
        6,
        15,
        {
            "F": ("Top six", "Top-six"),
            "D": ("Première paire", "Top-pair"),
            "G": ("Titulaire", "Starter"),
        },
        "élite",
        "elite",
        {
            "F": ("Top 6", "Top 6 F"),
            "D": ("Top 4", "Top 4 D"),
            "G": ("Titulaire", "Starter"),
        },
    ),
    (
        16,
        31,
        {
            "F": ("Top six", "Top-six"),
            "D": ("Première paire", "Top-pair"),
            "G": ("Titulaire partiel", "Fringe starter"),
        },
        "",
        "",
        {
            "F": ("Top 6", "Top 6 F"),
            "D": ("Top 4", "Top 4 D"),
            "G": ("Titulaire partiel", "Fringe Starter"),
        },
    ),
    (
        32,
        62,
        {
            "F": ("Troisième trio", "Top-nine"),
            "D": ("Top six", "Top-six"),
            "G": ("Remplaçant", "Backup"),
        },
        "",
        "",
        {
            "F": ("Top 9", "Top 9 F"),
            "D": ("Top 6", "Top 6 D"),
            "G": ("Remplaçant", "Backup"),
        },
    ),
    (
        63,
        120,
        {
            "F": ("Quatrième trio", "Bottom-six"),
            "D": ("Troisième paire", "Third-pair"),
            "G": ("Remplaçant LHA", "AHL backup"),
        },
        "",
        "",
        {
            "F": ("Quatrième trio", "Bottom 6 F"),
            "D": ("7e D", "7th D"),
            "G": ("Remplaçant LHA", "AHL Backup G"),
        },
    ),
]

EA_ADJECTIVE_RANK: dict[str, int] = {
    "générationnel": 0,
    "franchise": 1,
    "élite": 2,
    "": 3,
}

EA_POSITION_NAMES: dict[str, dict[str, tuple[str, str]]] = {
    "F": {
        "C": ("centre", "center"),
        "LW": ("ailier", "winger"),
        "RW": ("ailier", "winger"),
        "default": ("attaquant", "forward"),
    },
    "D": {"default": ("défenseur", "defenseman")},
    "G": {"default": ("gardien", "goalie")},
}


def _ea_role_depth(spi: float, group: str) -> tuple[str, str]:
    spi_clamped = max(0.0, min(100.0, float(spi)))
    for min_spi, label_fr, label_en in EA_ROLE_DEPTH[group]:
        if spi_clamped >= min_spi:
            return label_fr, label_en
    fallback = EA_ROLE_DEPTH[group][-1]
    return fallback[1], fallback[2]


def _ea_tier_from_spi(spi: float, group: str) -> tuple[str, str]:
    spi_clamped = max(0.0, min(100.0, float(spi)))
    for min_spi, label_fr, label_en in EA_TIER_BANDS[group]:
        if spi_clamped >= min_spi:
            return label_fr, label_en
    fallback = EA_TIER_BANDS[group][-1]
    return fallback[1], fallback[2]


def _ea_tier_adjective(spi: float) -> tuple[str, str]:
    spi_clamped = max(0.0, min(100.0, float(spi)))
    for min_spi, adj_fr, adj_en in EA_TIER_ADJECTIVES:
        if spi_clamped >= min_spi:
            return adj_fr, adj_en
    return "", ""


def _ea_position_name(position: str, group: str) -> tuple[str, str]:
    pos = (position or "").upper().strip()
    names = EA_POSITION_NAMES[group]
    if pos in names:
        return names[pos]
    return names["default"]


def _ea_label_index(labels: list[tuple[float, str, str]], label_fr: str) -> int:
    for i, (_, fr, _) in enumerate(labels):
        if fr == label_fr:
            return i
    return len(labels) - 1


def _ea_better_label(
    current_fr: str,
    current_en: str,
    floor_fr: str,
    floor_en: str,
    labels: list[tuple[float, str, str]],
) -> tuple[str, str]:
    """Return the better (higher) label; lower index in *labels* = better."""
    if _ea_label_index(labels, floor_fr) < _ea_label_index(labels, current_fr):
        return floor_fr, floor_en
    return current_fr, current_en


def _ea_better_adjective(
    current_fr: str,
    current_en: str,
    floor_fr: str,
    floor_en: str,
) -> tuple[str, str]:
    if not floor_fr:
        return current_fr, current_en
    current_rank = EA_ADJECTIVE_RANK.get(current_fr, 3)
    floor_rank = EA_ADJECTIVE_RANK.get(floor_fr, 2)
    if floor_rank < current_rank:
        return floor_fr, floor_en
    return current_fr, current_en


def _ea_draft_rank_floor(draft_rank: int | float | None) -> tuple | None:
    if draft_rank is None:
        return None
    try:
        rank = int(round(float(draft_rank)))
    except (TypeError, ValueError):
        return None
    if rank < 1:
        return None
    for entry in EA_DRAFT_RANK_FLOORS:
        if entry[0] <= rank <= entry[1]:
            return entry
    return None


def _ea_apply_draft_floors(
    group: str,
    role_fr: str,
    role_en: str,
    tier_fr: str,
    tier_en: str,
    adj_fr: str,
    adj_en: str,
    draft_rank: int | float | None,
) -> tuple[str, str, str, str, str, str]:
    floor = _ea_draft_rank_floor(draft_rank)
    if not floor:
        return role_fr, role_en, tier_fr, tier_en, adj_fr, adj_en

    _, _, min_roles, min_adj_fr, min_adj_en, min_tiers = floor
    floor_role_fr, floor_role_en = min_roles[group]
    role_fr, role_en = _ea_better_label(
        role_fr, role_en, floor_role_fr, floor_role_en, EA_ROLE_DEPTH[group]
    )
    floor_tier_fr, floor_tier_en = min_tiers[group]
    tier_fr, tier_en = _ea_better_label(
        tier_fr, tier_en, floor_tier_fr, floor_tier_en, EA_TIER_BANDS[group]
    )
    adj_fr, adj_en = _ea_better_adjective(adj_fr, adj_en, min_adj_fr, min_adj_en)
    return role_fr, role_en, tier_fr, tier_en, adj_fr, adj_en


def ea_projection_for_player(
    spi: float,
    position: str,
    *,
    lang: str = "fr",
    draft_rank: int | float | None = None,
) -> str:
    """
    NHL role projection from SPI, position, and optional draft rank floor.

    Format EN: ``{role_depth} {tier_adjective} {position_name}``
    (tier adjective omitted below Élite / 68 SPI unless raised by rank floor).

    Examples:
      LW 90+ → "Top-line generational winger"
      LW rank 4, SPI 72 → "Top-six elite winger"
      C rank 6, SPI 67 → "Top-six center"
    """
    group = ea_position_group(position)
    role_fr, role_en = _ea_role_depth(spi, group)
    tier_fr, tier_en = _ea_tier_from_spi(spi, group)
    adj_fr, adj_en = _ea_tier_adjective(spi)
    role_fr, role_en, tier_fr, tier_en, adj_fr, adj_en = _ea_apply_draft_floors(
        group, role_fr, role_en, tier_fr, tier_en, adj_fr, adj_en, draft_rank
    )
    pos_fr, pos_en = _ea_position_name(position, group)

    if lang.lower().startswith("en"):
        parts = [role_en]
        if adj_en:
            parts.append(adj_en)
        parts.append(pos_en)
        return " ".join(parts)

    if adj_fr:
        return f"{role_fr} · {pos_fr} {adj_fr}"
    return f"{role_fr} · {pos_fr}"


def ea_tier_for_player(
    spi: float,
    position: str,
    *,
    draft_rank: int | float | None = None,
) -> dict[str, str]:
    """
    Return EA-style potential tier for a player from SPI, position, and draft rank.

    Keys: tierLabel (French), eaTier (English canonical), tierGroup (F/D/G).
    """
    group = ea_position_group(position)
    tier_fr, tier_en = _ea_tier_from_spi(spi, group)
    role_fr, role_en = _ea_role_depth(spi, group)
    adj_fr, adj_en = _ea_tier_adjective(spi)
    _, _, tier_fr, tier_en, _, _ = _ea_apply_draft_floors(
        group, role_fr, role_en, tier_fr, tier_en, adj_fr, adj_en, draft_rank
    )
    return {
        "tierLabel": tier_fr,
        "eaTier": tier_en,
        "tierGroup": group,
    }


def ea_tier_table(position_group: str | None = None) -> dict[str, list[dict]]:
    """Documented tier table for a position group or all groups."""
    groups = [position_group] if position_group else list(EA_TIER_BANDS)
    out: dict[str, list[dict]] = {}
    for g in groups:
        if g not in EA_TIER_BANDS:
            continue
        bands = EA_TIER_BANDS[g]
        rows: list[dict] = []
        for i, (min_spi, label_fr, label_en) in enumerate(bands):
            max_spi = 100.0 if i == 0 else bands[i - 1][0] - 0.01
            rows.append({
                "spi_min": min_spi,
                "spi_max": round(max_spi, 2),
                "tierLabel": label_fr,
                "eaTier": label_en,
            })
        out[g] = rows
    return out


def _band(v: float) -> tuple[str, str]:
    if v >= 9.5:
        return "élite", "signal star maximal"
    if v >= 9.0:
        return "exceptionnel", "profil all-star crédible"
    if v >= 8.5:
        return "très élevé", "upside star réel"
    if v >= 8.0:
        return "solide", "chemin star possible"
    if v >= 7.0:
        return "modeste", "plus probablement joueur solide"
    if v >= 6.0:
        return "faible", "star path improbable"
    return "très faible", "profil depth / bust"


def build_rationales(
    scores: dict,
    *,
    full_name: str,
    pos: str,
    report: dict,
    evidence: dict[str, list[str]],
) -> dict[str, str]:
    out = {}
    cov = scores.get("report_coverage", "partial")
    snippet = (report.get("report") or report.get("meta_description") or "")[:200]

    for dim, label in NORTHSTAR_LABELS.items():
        v = scores.get(dim, 5.0)
        b, d = _band(v)
        w = int(NORTHSTAR_WEIGHTS[dim] * 100)
        ev = evidence.get(dim, [])
        ev_txt = ", ".join(f"«{e}»" for e in ev[:4]) if ev else "inférence contextuelle"
        out[dim] = (
            f"**{v}/10 — {b.capitalize()}** ({d}). Pilier NORTHSTAR ({w}%). "
            f"Signaux détectés: {ev_txt}. "
        )
        if snippet and dim == "star_ceiling":
            out[dim] += f'Extrait rapport: "{snippet[:120]}…". '
        if cov == "full":
            out[dim] += "Source: rapport DPH substantiel."
        elif cov == "partial":
            out[dim] += "Source: métadonnées partielles — confiance modérée."
        elif cov == "thin":
            out[dim] += "Source: page DPH template (texte mince) — confiance basse."
        else:
            out[dim] += "Source: aucun rapport DPH — inférence stats/contexte uniquement."

    return out


MIN_FORCES = 3
MAX_FORCES = 5
MIN_FAIBLESSES = 2
MAX_FAIBLESSES = 4


def _unique_append(lst: list[str], item: str, max_len: int) -> bool:
    item = item.strip()
    if not item or item in lst or len(lst) >= max_len:
        return False
    lst.append(item)
    return True


def _strength_from_dim(dim: str, score: float, evidence: list[str]) -> str:
    label = NORTHSTAR_LABELS[dim]
    band, _ = _band(score)
    if evidence:
        ev = ", ".join(evidence[:2])
        return f"{label} — {score}/10 ({band}) : signaux «{ev}»"
    return f"{label} — {score}/10 ({band})"


def _weakness_from_dim(
    dim: str, score: float, gap: float, *, weakest: bool = False,
) -> str | None:
    label = NORTHSTAR_LABELS[dim]
    if weakest:
        return (
            f"{label} ({score}/10) — pilier le moins élevé du profil; "
            "marge limitée vs l'élite NHL"
        )
    if score >= 8.5 and gap < 1.5:
        return None
    if gap >= 1.5:
        return (
            f"{label} ({score}/10) — écart de {gap:.1f} vs le pilier dominant; "
            "risque si ce skill ne suit pas en pro"
        )
    return f"{label} ({score}/10) — pilier sous la moyenne du profil; traduction NHL à prouver"


def _physical_risks(pos: str, height: str, weight: str) -> list[str]:
    risks: list[str] = []
    h = parse_height(height)
    w = parse_weight(weight)
    pos_u = pos.upper()
    if h <= 69 and "D" not in pos_u and "G" not in pos_u:
        risks.append(
            f"Cadre compact ({height}) — translation physique en NHL "
            "à prouver vs défenseurs pro"
        )
    if w < 170 and "D" not in pos_u:
        risks.append(
            f"Poids léger ({w} lb) — tolérance au contact et batailles "
            "de coin à surveiller"
        )
    if h >= 77 and "G" not in pos_u:
        risks.append(
            f"Grande taille ({height}) — coordination et vitesse de rotation "
            "à valider à chaque niveau"
        )
    return risks


def _coverage_risks(cov: str) -> list[str]:
    if cov == "none":
        return ["Aucun rapport DPH — incertitude élevée sur la traduction NHL"]
    if cov == "thin":
        return ["Rapport DPH template (texte mince) — peu de détail scout disponible"]
    if cov == "partial":
        return ["Couverture scouting partielle — confiance modérée"]
    return []


def build_forces_faiblesses(
    dims: dict[str, float],
    report: dict,
    evidence: dict[str, list[str]],
    pos: str,
    height: str,
    weight: str,
    cov: str,
) -> tuple[list[str], list[str]]:
    """Construit 3-5 forces et 2-4 faiblesses à partir de DPH, signaux NORTHSTAR et profil."""
    forces: list[str] = []
    faiblesses: list[str] = []

    for s in report.get("strengths") or []:
        _unique_append(forces, s, MAX_FORCES)
    for w in report.get("weaknesses") or []:
        _unique_append(faiblesses, w, MAX_FAIBLESSES)

    text = _text_blob(report)
    if text:
        for dim, score in sorted(dims.items(), key=lambda x: -x[1]):
            if score < 7.0 or len(forces) >= MAX_FORCES:
                continue
            _, ev = _lex_score(dim, text)
            if ev:
                _unique_append(forces, _strength_from_dim(dim, score, ev), MAX_FORCES)

    sorted_dims = sorted(dims.items(), key=lambda x: -x[1])
    top_score = sorted_dims[0][1] if sorted_dims else 5.0
    for dim, score in sorted_dims:
        if len(forces) >= MAX_FORCES or score < 7.0:
            break
        _unique_append(forces, _strength_from_dim(dim, score, evidence.get(dim, [])), MAX_FORCES)

    sorted_asc = sorted(dims.items(), key=lambda x: x[1])
    for i, (dim, score) in enumerate(sorted_asc[:4]):
        if len(faiblesses) >= MAX_FAIBLESSES:
            break
        gap = top_score - score
        bullet = _weakness_from_dim(dim, score, gap, weakest=(i == 0))
        if bullet:
            _unique_append(faiblesses, bullet, MAX_FAIBLESSES)

    for r in _physical_risks(pos, height, weight):
        _unique_append(faiblesses, r, MAX_FAIBLESSES)
    for r in _coverage_risks(cov):
        _unique_append(faiblesses, r, MAX_FAIBLESSES)

    if dims.get("star_ceiling", 5) < 7.0:
        _unique_append(
            faiblesses,
            "Plafond étoile limité selon le profil NORTHSTAR — chemin star incertain",
            MAX_FAIBLESSES,
        )
    if dims.get("star_ceiling", 5) >= 9.0:
        _unique_append(
            faiblesses,
            "Attentes de sélection haute — très peu de marge si le développement ralentit",
            MAX_FAIBLESSES,
        )

    while len(forces) < MIN_FORCES:
        added = False
        for dim, score in sorted_dims:
            if _unique_append(
                forces, _strength_from_dim(dim, score, evidence.get(dim, [])), MAX_FORCES,
            ):
                added = True
                break
        if not added:
            break

    while len(faiblesses) < MIN_FAIBLESSES:
        added = False
        for dim, score in sorted_asc:
            if _unique_append(
                faiblesses,
                f"{NORTHSTAR_LABELS[dim]} ({score}/10) — à surveiller dans la montée vers la NHL",
                MAX_FAIBLESSES,
            ):
                added = True
                break
        if not added:
            break

    return forces[:MAX_FORCES], faiblesses[:MAX_FAIBLESSES]


# ---------------------------------------------------------------------------
# Multi-source aggregation — equal/near-equal weighting across ALL sources
# No single source may exceed MAX_SOURCE_SHARE (default 25%).
# Quality adjustment only (word count, scouting keywords, recency) — not tier monopoly.
# ---------------------------------------------------------------------------
MAX_SOURCE_SHARE = 0.25
BASE_SOURCE_WEIGHT = 1.0
MIN_SOURCE_ATTEMPTS = 5

# Legacy tier field kept for metadata only (all sources share equal base weight).
SOURCE_TIER_WEIGHTS: dict[int, float] = {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0}

SOURCE_CATALOG: dict[str, tuple[int, str]] = {
    # Major scouting outlets
    "dph_full": (2, "Draft Prospects Hockey (full report)"),
    "dph_partial": (2, "Draft Prospects Hockey (partial)"),
    "dph_thin": (2, "Draft Prospects Hockey (template)"),
    "dph_report": (2, "DPH scouting report body"),
    "dph_strengths": (2, "DPH listed strengths"),
    "dph_weaknesses": (2, "DPH listed weaknesses"),
    "dph_projection": (2, "DPH NHL projection"),
    "dph_tags": (2, "DPH grade & tags"),
    "rankings_csv": (2, "Rankings dimension profile"),
    "elite_prospects": (2, "Elite Prospects"),
    "mckeens": (2, "McKeen's Hockey"),
    "the_athletic": (2, "The Athletic"),
    "tsn": (2, "TSN"),
    "espn": (2, "ESPN"),
    "nhl_com": (2, "NHL.com"),
    "sportsnet": (2, "Sportsnet"),
    "flohockey": (2, "FloHockey"),
    # Rankings / lists
    "pronman": (2, "Corey Pronman (ESPN rankings)"),
    "scott_wheeler": (2, "Scott Wheeler (TSN)"),
    "smaht_scouting": (2, "Smaht Scouting"),
    "daily_faceoff": (2, "Daily Faceoff"),
    "puckpedia": (2, "PuckPedia"),
    "local_analysis": (2, "Local NORTHSTAR scouting analysis"),
    # Obscure / specialized / web
    "web_scouting": (2, "Web scouting snippet"),
    "bing_scouting": (2, "Bing scouting search"),
    "ddg_scouting": (2, "DuckDuckGo scouting search"),
    "reddit": (2, "Reddit r/hockey"),
    "hfboards": (2, "HFBoards"),
    "team_blog": (2, "Team / league blog"),
    # Social
    "twitter": (2, "Twitter / X"),
    "youtube": (2, "YouTube scouting"),
    # Stats / reference
    "hockeydb": (2, "HockeyDB"),
    "wikipedia": (2, "Wikipedia"),
    "consensus_rank": (2, "Public consensus rankings"),
    "stats_heuristic": (2, "Production / stats heuristic"),
}

# Subtle quality priors — never more than ~15% spread vs peers.
SOURCE_QUALITY_PRIORS: dict[str, float] = {
    "dph_full": 1.00,
    "dph_report": 0.96,
    "dph_strengths": 0.94,
    "dph_weaknesses": 0.94,
    "dph_projection": 0.93,
    "dph_tags": 0.90,
    "rankings_csv": 0.86,
    "local_analysis": 0.98,
    "elite_prospects": 0.97,
    "tsn": 0.96,
    "espn": 0.96,
    "nhl_com": 0.96,
    "the_athletic": 0.96,
    "mckeens": 0.95,
    "scott_wheeler": 0.95,
    "pronman": 0.95,
    "smaht_scouting": 0.94,
    "sportsnet": 0.94,
    "flohockey": 0.93,
    "puckpedia": 0.92,
    "daily_faceoff": 0.92,
    "hockeydb": 0.90,
    "wikipedia": 0.88,
    "dph_partial": 0.87,
    "team_blog": 0.85,
    "web_scouting": 0.84,
    "bing_scouting": 0.83,
    "ddg_scouting": 0.83,
    "youtube": 0.82,
    "twitter": 0.80,
    "reddit": 0.78,
    "hfboards": 0.78,
    "dph_thin": 0.75,
    "consensus_rank": 0.82,
    "stats_heuristic": 0.72,
}

_SCOUTING_KW = re.compile(
    r"\b(scout|scouting|prospect|skating|ceiling|upside|projection|elite|"
    r"draft|generational|franchise|playmaker|iq|processing|compete|"
    r"breakout|riser|comparable|tier|ranking|board)\b",
    re.I,
)


def source_tier(source_id: str) -> int:
    return SOURCE_CATALOG.get(source_id, (2, ""))[0]


def source_label(source_id: str) -> str:
    return SOURCE_CATALOG.get(source_id, (2, source_id))[1]


def compute_text_quality(
    text: str,
    *,
    fetched_at: str | None = None,
) -> float:
    """Quality multiplier from word count, scouting keywords, and recency."""
    if not text or not str(text).strip():
        return 0.30
    blob = str(text).lower()
    words = len(blob.split())
    word_factor = min(1.0, 0.35 + words / 180.0)
    kw_hits = len(_SCOUTING_KW.findall(blob))
    kw_factor = min(1.0, 0.40 + kw_hits * 0.07)
    recency_factor = 1.0
    if fetched_at:
        try:
            from datetime import datetime, timezone
            ts = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - ts).days
            if age_days <= 30:
                recency_factor = 1.0
            elif age_days <= 180:
                recency_factor = 0.95
            elif age_days <= 365:
                recency_factor = 0.90
            else:
                recency_factor = 0.85
        except (TypeError, ValueError):
            pass
    return round(max(0.30, min(1.0, (word_factor + kw_factor) / 2 * recency_factor)), 3)


def source_weight(source_id: str, *, quality: float = 1.0) -> float:
    """Effective weight = base × quality prior × text quality (capped downstream)."""
    prior = SOURCE_QUALITY_PRIORS.get(source_id, 0.84)
    q = max(0.30, min(1.0, float(quality)))
    return BASE_SOURCE_WEIGHT * prior * q


def _cap_source_weights(raw_weights: list[float], max_share: float) -> list[float]:
    """Iteratively cap so no source exceeds *max_share* of the blend."""
    if not raw_weights:
        return []
    weights = [float(w) for w in raw_weights]
    for _ in range(24):
        total = sum(weights)
        if total <= 0:
            return weights
        capped_any = False
        new_weights = list(weights)
        overflow = [(i, w) for i, w in enumerate(weights) if w / total > max_share]
        if not overflow:
            break
        cap_total = 0.0
        free: list[int] = []
        for i, w in enumerate(weights):
            if w / total > max_share:
                new_weights[i] = total * max_share
                cap_total += new_weights[i]
                capped_any = True
            else:
                free.append(i)
        if not capped_any:
            break
        remainder = total - cap_total
        free_sum = sum(weights[i] for i in free)
        if free_sum <= 0 or not free:
            weights = new_weights
            break
        for i in free:
            new_weights[i] = weights[i] / free_sum * remainder
        weights = new_weights
    return weights


def confidence_from_source_count(
    n_sources: int,
    n_substantive: int,
) -> str:
    """Coverage from breadth of sources — not tier-1 monopoly."""
    if n_sources >= 10 and n_substantive >= 5:
        return "full"
    if n_sources >= 7 and n_substantive >= 3:
        return "full"
    if n_sources >= 5 and n_substantive >= 2:
        return "partial"
    if n_sources >= 3 or n_substantive >= 1:
        return "partial"
    if n_sources >= 1:
        return "thin"
    return "none"


def source_count_confidence_multiplier(n_sources: int) -> float:
    """Penalty when few sources — replaces single-source monopoly boost."""
    if n_sources >= 12:
        return 1.00
    if n_sources >= 10:
        return 0.99
    if n_sources >= 8:
        return 0.97
    if n_sources >= 6:
        return 0.95
    if n_sources >= 4:
        return 0.92
    if n_sources >= 2:
        return 0.88
    return 0.82


def dph_source_id(report: dict, cov: str | None = None) -> str:
    cov = cov or _report_quality(report)
    if cov == "full":
        return "dph_full"
    if cov == "thin":
        return "dph_thin"
    if cov in ("partial", "none") and report.get("grade"):
        return "dph_partial"
    return "dph_thin" if cov == "thin" else "dph_partial"


def pillars_from_text_blob(
    text: str,
    *,
    pos: str,
    report: dict | None = None,
    stats: dict | None = None,
    apply_coverage: bool = True,
) -> tuple[dict[str, float], dict[str, list[str]]]:
    """Score 7 pillars from free text + optional DPH metadata/stats."""
    report = report or {}
    stats = stats or report.get("stats") or {}
    blob = text.lower()
    lex: dict[str, float] = {}
    evidence: dict[str, list[str]] = {}
    for dim in NORTHSTAR_WEIGHTS:
        s, ev = _lex_score(dim, blob)
        lex[dim] = s
        evidence[dim] = ev

    grade = _grade_score(report.get("grade", ""))
    for tag in report.get("tags") or []:
        for tk, boost in TAG_BOOSTS.items():
            if tk in tag.lower():
                grade = min(10, grade + boost * 0.15)

    league = _league_score(report.get("league", ""), blob)
    prod = _production_score(stats, pos)
    dph_r = _dph_rank_score(report.get("dph_rank"))
    dims = _merge_scores(lex, grade, league, prod, dph_r, pos)
    if apply_coverage and report:
        cov = _report_quality(report)
        dims = _apply_coverage_penalty(dims, cov, grade)
    return dims, evidence


def pillars_from_consensus_rank(rank: int | None, pos: str) -> dict[str, float]:
    """Tier-4 fallback from public consensus rank only."""
    base = _dph_rank_score(rank)
    is_d = "D" in pos.upper()
    is_g = pos.upper() in ("G", "GK")
    dims = {
        "star_ceiling": base,
        "hockey_iq": round(base * 0.92, 1),
        "skating_engine": round(base * 0.88, 1),
        "offensive_star_power": round(base * (0.85 if is_d else 0.95), 1),
        "competition_proof": round(base * 0.90, 1),
        "character_compete": round(base * 0.85, 1),
        "development_arc": round(base * 0.88, 1),
    }
    if is_g:
        dims["offensive_star_power"] = round(base * 0.80, 1)
    return {k: round(min(10, max(1, v)), 1) for k, v in dims.items()}


def pillars_from_stats_heuristic(
    stats: dict,
    league: str,
    pos: str,
    height: str,
    weight: str,
) -> dict[str, float]:
    """Tier-4 production / physical signals when scouting text is absent."""
    prod = _production_score(stats, pos)
    league_s = _league_score(league, league)
    dims = pillars_from_consensus_rank(None, pos)
    dims["offensive_star_power"] = round(prod * 0.6 + dims["offensive_star_power"] * 0.4, 1)
    dims["competition_proof"] = round(league_s * 0.55 + prod * 0.45, 1)
    dims["skating_engine"] = round(dims["skating_engine"] * 0.7 + prod * 0.3, 1)
    h = parse_height(height)
    if h >= 76:
        dims["star_ceiling"] = min(10, dims["star_ceiling"] + 0.15)
    if h <= 69 and "D" not in pos.upper():
        dims["star_ceiling"] = max(1, dims["star_ceiling"] - 0.2)
    return {k: round(min(10, max(1, v)), 1) for k, v in dims.items()}


def apply_physical_adjustments(
    dims: dict[str, float],
    pos: str,
    height: str,
    weight: str,
) -> dict[str, float]:
    out = dims.copy()
    h = parse_height(height)
    if h >= 76 and out["star_ceiling"] >= 7.5:
        out["star_ceiling"] = min(10, out["star_ceiling"] + 0.2)
    if h <= 69 and "D" not in pos.upper():
        out["star_ceiling"] = max(1, out["star_ceiling"] - 0.3)
    return {k: round(min(10, max(1, v)), 1) for k, v in out.items()}


def weighted_merge_sources(
    contributions: list[dict[str, Any]],
    *,
    max_share: float = MAX_SOURCE_SHARE,
) -> tuple[dict[str, float], dict[str, list[str]], list[dict], str]:
    """
    Merge per-source pillar scores — equal/near-equal blend with share cap.

    final_pillar = sum(effective_weight_i × pillar_i) / sum(effective_weights)
    No single source > max_share unless only 1–2 sources exist.

    Each contribution dict:
      source_id, pillars, evidence?, quality?, snippet?, text_quality?
    Returns: final_dims, merged_evidence, source_mix, confidence_coverage
    """
    if not contributions:
        neutral = {k: 5.0 for k in NORTHSTAR_WEIGHTS}
        return neutral, {}, [], "none"

    # Deduplicate by source_id — keep highest-quality contribution per source
    best: dict[str, dict[str, Any]] = {}
    for c in contributions:
        sid = c["source_id"]
        q = float(c.get("quality", 1.0))
        if sid not in best or q > float(best[sid].get("quality", 0)):
            best[sid] = c
    merged_contribs = list(best.values())

    raw_weights: list[float] = []
    substantive = 0
    for c in merged_contribs:
        text_q = c.get("text_quality")
        if text_q is None and c.get("snippet"):
            text_q = compute_text_quality(c["snippet"])
        elif text_q is None:
            text_q = float(c.get("quality", 1.0))
        combined_q = float(c.get("quality", 1.0)) * float(text_q)
        w = source_weight(c["source_id"], quality=combined_q)
        raw_weights.append(w)
        c["_effective_weight"] = w
        c["_combined_quality"] = round(combined_q, 3)
        if c.get("snippet") or c.get("evidence"):
            substantive += 1

    # Only cap when 3+ sources — allow natural dominance with 1–2 sources
    effective_cap = max_share if len(merged_contribs) >= 3 else 1.0
    capped_weights = _cap_source_weights(raw_weights, effective_cap)
    total_w = sum(capped_weights) or 1.0

    final: dict[str, float] = {}
    merged_ev: dict[str, list[str]] = {k: [] for k in NORTHSTAR_WEIGHTS}
    source_mix: list[dict] = []

    for c, w in zip(merged_contribs, capped_weights):
        sid = c["source_id"]
        tier = source_tier(sid)
        mix_entry = {
            "source": sid,
            "label": source_label(sid),
            "tier": tier,
            "tier_weight": SOURCE_TIER_WEIGHTS[tier],
            "quality": c.get("_combined_quality", round(float(c.get("quality", 1.0)), 2)),
            "effective_weight": round(w, 3),
            "weight_share": round(w / total_w, 4),
            "pillars": {k: c["pillars"].get(k, 5.0) for k in NORTHSTAR_WEIGHTS},
        }
        if c.get("url"):
            mix_entry["url"] = c["url"]
        if c.get("snippet"):
            mix_entry["snippet"] = c["snippet"][:200]
        mix_entry["pillar_contribution"] = {
            dim: round(mix_entry["pillars"][dim] * mix_entry["weight_share"], 3)
            for dim in NORTHSTAR_WEIGHTS
        }
        source_mix.append(mix_entry)
        for dim in NORTHSTAR_WEIGHTS:
            merged_ev[dim].extend((c.get("evidence") or {}).get(dim, [])[:3])

    for dim in NORTHSTAR_WEIGHTS:
        num = sum(
            c["pillars"].get(dim, 5.0) * w
            for c, w in zip(merged_contribs, capped_weights)
        )
        final[dim] = round(min(10, max(1, num / total_w)), 1)

    source_mix.sort(key=lambda x: -x["weight_share"])
    cov = confidence_from_source_count(len(merged_contribs), substantive)

    for dim in merged_ev:
        merged_ev[dim] = list(dict.fromkeys(merged_ev[dim]))[:5]

    return final, merged_ev, source_mix, cov


def _merge_scores(
    lex: dict[str, float],
    grade: float,
    league: float,
    prod: float,
    dph_rank: float,
    pos: str,
) -> dict[str, float]:
    """
    Fusion des signaux vérifiables uniquement: lexique rapport, grade DPH,
    ligue, production stats, rang DPH interne. Pas de consensus externe.
    """
    is_g = pos.upper() in ("G", "GK")
    is_d = "D" in pos.upper()

    star = lex["star_ceiling"] * 0.50 + grade * 0.30 + dph_rank * 0.20
    iq = lex["hockey_iq"] * 0.70 + grade * 0.30
    skate = lex["skating_engine"] * 0.65 + grade * 0.20 + prod * 0.15
    offense = lex["offensive_star_power"] * 0.55 + prod * 0.35 + lex["star_ceiling"] * 0.10
    if is_d:
        offense = lex["offensive_star_power"] * 0.40 + lex["hockey_iq"] * 0.30 + prod * 0.30
    if is_g:
        offense = grade * 0.50 + league * 0.30 + lex["competition_proof"] * 0.20

    comp = lex["competition_proof"] * 0.40 + league * 0.35 + prod * 0.25
    char = lex["character_compete"] * 0.75 + grade * 0.25
    dev = lex["development_arc"] * 0.55 + dph_rank * 0.25 + prod * 0.20

    return {
        "star_ceiling": round(min(10, max(1, star)), 1),
        "hockey_iq": round(min(10, max(1, iq)), 1),
        "skating_engine": round(min(10, max(1, skate)), 1),
        "offensive_star_power": round(min(10, max(1, offense)), 1),
        "competition_proof": round(min(10, max(1, comp)), 1),
        "character_compete": round(min(10, max(1, char)), 1),
        "development_arc": round(min(10, max(1, dev)), 1),
    }


def _scores_from_evaluation(
    evaluation: dict,
    full_name: str,
    pos: str,
    height: str,
    weight: str,
    report: dict,
) -> dict[str, Any]:
    """Applique une évaluation manuelle détaillée (pipeline evaluate_players_northstar)."""
    pillars = evaluation.get("pillars") or {}
    dims: dict[str, float] = {}
    evidence: dict[str, list[str]] = {}
    rationales: dict[str, str] = {}
    for dim in NORTHSTAR_WEIGHTS:
        p = pillars.get(dim) or {}
        dims[dim] = float(p.get("score", 5.0))
        evidence[dim] = list(p.get("evidence") or [])
        if p.get("rationale"):
            rationales[dim] = p["rationale"]

    cov = evaluation.get("confidence") or evaluation.get("report_coverage") or "partial"
    overall = northstar_overall(dims) * _confidence_multiplier(cov)
    overall = round(min(99.9, max(0, overall)), 2)
    star_tier = _star_tier(overall)

    forces = list(evaluation.get("forces") or [])
    faiblesses = list(evaluation.get("faiblesses") or [])
    if len(forces) < MIN_FORCES or len(faiblesses) < MIN_FAIBLESSES:
        auto_f, auto_w = build_forces_faiblesses(
            dims, report, evidence, pos, height, weight, cov,
        )
        for f in auto_f:
            if f not in forces and len(forces) < MAX_FORCES:
                forces.append(f)
        for w in auto_w:
            if w not in faiblesses and len(faiblesses) < MAX_FAIBLESSES:
                faiblesses.append(w)

    if not rationales:
        rationales = build_rationales(
            {**dims, "report_coverage": cov},
            full_name=full_name, pos=pos, report=report, evidence=evidence,
        )

    resume = evaluation.get("notes") or report.get("report") or (
        f"{full_name} ({pos}) — évaluation NORTHSTAR détaillée "
        f"(confiance: {cov}). SPI: {overall}/100 ({star_tier})."
    )

    return {
        **dims,
        "spi": overall,
        "resume": resume,
        "forces": forces[:MAX_FORCES],
        "faiblesses": faiblesses[:MAX_FAIBLESSES],
        "comparable": report.get("projection") or evaluation.get("projection") or "N/A",
        "projection": report.get("projection") or evaluation.get("projection") or star_tier,
        "star_thesis": (
            f"NORTHSTAR estime {full_name} à {overall}/100 pour devenir une étoile NHL "
            f"({star_tier}). Pilier dominant: plafond étoile {dims['star_ceiling']}/10."
        ),
        "report_coverage": cov,
        "star_tier": star_tier,
        "evidence": evidence,
        "rationales": rationales,
        "evaluation_sources": evaluation.get("sources") or [],
        "source_mix": evaluation.get("source_mix") or [],
    }


def northstar_generate(
    full_name: str,
    pos: str,
    height: str,
    weight: str,
    country: str,
    consensus_rank: int | None,
    player_key: str | None = None,
    extra_text: str = "",
) -> dict[str, Any]:
    from name_utils import canonical_key

    key = player_key or canonical_key(full_name)
    evals = _load_evaluations()
    player_eval = (evals.get("players") or {}).get(key)
    if player_eval and player_eval.get("status") == "done" and player_eval.get("pillars"):
        reports = _load_reports()
        report = reports.get(key, {})
        return _scores_from_evaluation(
            player_eval, full_name, pos, height, weight, report,
        )

    reports = _load_reports()
    report = reports.get(key, {})
    evidence: dict[str, list[str]] = {}

    text = _scoring_text(report)
    if extra_text:
        text = f"{text} {extra_text.lower()}"
    lex: dict[str, float] = {}
    for dim in NORTHSTAR_WEIGHTS:
        s, ev = _lex_score(dim, text)
        lex[dim] = s
        evidence[dim] = ev

    grade = _grade_score(report.get("grade", ""))
    for tag in report.get("tags") or []:
        for tk, boost in TAG_BOOSTS.items():
            if tk in tag.lower():
                grade = min(10, grade + boost * 0.15)

    league = _league_score(report.get("league", ""), text)
    prod = _production_score(report.get("stats") or {}, pos)
    dph_r = _dph_rank_score(report.get("dph_rank"))
    cov = _report_quality(report)

    dims = _merge_scores(lex, grade, league, prod, dph_r, pos)
    dims = _apply_coverage_penalty(dims, cov, grade)

    # Ajustements physiques légers (star path)
    h = parse_height(height)
    w = parse_weight(weight)
    if h >= 76 and dims["star_ceiling"] >= 7.5:
        dims["star_ceiling"] = min(10, dims["star_ceiling"] + 0.2)
    if h <= 69 and "D" not in pos.upper():
        dims["star_ceiling"] = max(1, dims["star_ceiling"] - 0.3)

    overall = northstar_overall(dims) * _confidence_multiplier(cov)
    overall = round(min(99.9, max(0, overall)), 2)
    star_tier = _star_tier(overall)

    forces, faiblesses = build_forces_faiblesses(
        dims, report, evidence, pos, height, weight, cov,
    )

    resume = report.get("report") or report.get("meta_description") or (
        f"{full_name} ({pos}) — évaluation NORTHSTAR basée sur "
        f"{'rapport DPH substantiel' if cov == 'full' else 'page DPH template' if cov == 'thin' else 'signaux partiels' if cov == 'partial' else 'inférence sans rapport'}. "
        f"Star Probability Index: {overall}/100 ({star_tier})."
    )

    scores = {
        **dims,
        "spi": overall,
        "resume": resume,
        "forces": forces,
        "faiblesses": faiblesses,
        "comparable": report.get("projection") or "N/A",
        "projection": report.get("projection") or star_tier,
        "star_thesis": (
            f"NORTHSTAR estime {full_name} à {overall}/100 pour devenir une étoile NHL "
            f"({star_tier}). Pilier dominant: plafond étoile {dims['star_ceiling']}/10."
        ),
        "report_coverage": cov,
        "star_tier": star_tier,
        "evidence": evidence,
    }

    scores["rationales"] = build_rationales(
        scores, full_name=full_name, pos=pos, report=report,
        evidence=scores.get("evidence") or {},
    )
    return scores


def northstar_overall(scores: dict) -> float:
    if "spi" in scores:
        return float(scores["spi"])
    total = 0.0
    for k, w in NORTHSTAR_WEIGHTS.items():
        total += scores.get(k, 5.0) * w * 10
    return round(min(99.9, max(0, total)), 2)


# Alias compatibilité temporaire
APEX_WEIGHTS = NORTHSTAR_WEIGHTS
APEX_LABELS = NORTHSTAR_LABELS


def apex_generate(*args, **kwargs):
    return northstar_generate(*args, **kwargs)


def apex_overall(scores: dict) -> float:
    return northstar_overall(scores)
