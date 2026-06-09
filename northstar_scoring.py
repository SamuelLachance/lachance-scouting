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
REPORTS_PATH = paths_for_year(DEFAULT_DRAFT_YEAR)["scouting_reports"]

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
        (r"skating", 2.0), (r"elite speed", 2.5), (r"acceleration", 2.0),
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


def _text_blob(report: dict) -> str:
    parts = [
        report.get("report", ""),
        report.get("meta_description", ""),
        report.get("projection", ""),
        report.get("faq_text", ""),
        " ".join(report.get("strengths") or []),
        " ".join(report.get("weaknesses") or []),
        " ".join(report.get("tags") or []),
        report.get("league", ""),
    ]
    return " ".join(p for p in parts if p).lower()


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


def _consensus_prior(rank: int | None) -> float:
    if rank is None:
        return 5.0
    if rank <= 5:
        return 9.5
    if rank <= 15:
        return 8.5
    if rank <= 32:
        return 7.5
    if rank <= 64:
        return 6.5
    if rank <= 100:
        return 5.8
    if rank <= 150:
        return 5.0
    return 4.2


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
            out[dim] += "Source: rapport DPH complet."
        elif cov == "partial":
            out[dim] += "Source: métadonnées partielles — confiance modérée."
        else:
            out[dim] += "Source: inférence sans rapport — confiance basse."

    return out


def _merge_scores(
    lex: dict[str, float],
    grade: float,
    league: float,
    prod: float,
    dph_rank: float,
    consensus: float,
    has_report: bool,
    pos: str,
) -> dict[str, float]:
    """Fusion bayésienne simplifiée des signaux."""
    is_g = pos.upper() in ("G", "GK")
    is_d = "D" in pos.upper()

    # Plafond étoile = lex + grade + rank
    star = lex["star_ceiling"] * 0.45 + grade * 0.30 + dph_rank * 0.15 + consensus * 0.10
    if not has_report:
        star = star * 0.55 + consensus * 0.45

    iq = lex["hockey_iq"] * 0.6 + grade * 0.2 + consensus * 0.2
    skate = lex["skating_engine"] * 0.65 + grade * 0.2 + prod * 0.15
    offense = lex["offensive_star_power"] * 0.5 + prod * 0.35 + lex["star_ceiling"] * 0.15
    if is_d:
        offense = lex["offensive_star_power"] * 0.4 + lex["hockey_iq"] * 0.3 + prod * 0.3
    if is_g:
        offense = grade * 0.5 + league * 0.3 + lex["competition_proof"] * 0.2

    comp = lex["competition_proof"] * 0.4 + league * 0.35 + prod * 0.25
    char = lex["character_compete"] * 0.7 + grade * 0.15 + consensus * 0.15
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


# Overrides manuels top prospects — ancrés sur rapports publics consolidés
MANUAL: dict[str, dict[str, float]] = {
    "Gavin McKenna": {
        "star_ceiling": 10.0, "hockey_iq": 9.8, "skating_engine": 9.0,
        "offensive_star_power": 9.9, "competition_proof": 9.5,
        "character_compete": 9.5, "development_arc": 9.8,
    },
    "Wyatt Cullen": {
        "star_ceiling": 9.8, "hockey_iq": 9.6, "skating_engine": 9.8,
        "offensive_star_power": 9.4, "competition_proof": 8.8,
        "character_compete": 8.5, "development_arc": 10.0,
    },
    "Ivar Stenberg": {
        "star_ceiling": 8.8, "hockey_iq": 9.2, "skating_engine": 8.5,
        "offensive_star_power": 8.5, "competition_proof": 9.0,
        "character_compete": 9.0, "development_arc": 8.0,
    },
    "Chase Reid": {
        "star_ceiling": 9.2, "hockey_iq": 8.8, "skating_engine": 9.2,
        "offensive_star_power": 8.5, "competition_proof": 8.5,
        "character_compete": 9.2, "development_arc": 8.8,
    },
    "Viggo Björck": {
        "star_ceiling": 9.6, "hockey_iq": 9.5, "skating_engine": 9.0,
        "offensive_star_power": 9.2, "competition_proof": 8.8,
        "character_compete": 9.5, "development_arc": 9.0,
    },
    "Viggo Bjorck": {
        "star_ceiling": 9.6, "hockey_iq": 9.5, "skating_engine": 9.0,
        "offensive_star_power": 9.2, "competition_proof": 8.8,
        "character_compete": 9.5, "development_arc": 9.0,
    },
    "Carson Carels": {
        "star_ceiling": 9.4, "hockey_iq": 9.5, "skating_engine": 8.5,
        "offensive_star_power": 8.0, "competition_proof": 8.5,
        "character_compete": 9.0, "development_arc": 9.0,
    },
    "Ryan Lin": {
        "star_ceiling": 9.5, "hockey_iq": 9.0, "skating_engine": 9.5,
        "offensive_star_power": 9.0, "competition_proof": 8.5,
        "character_compete": 8.8, "development_arc": 9.0,
    },
    "Ethan Belchetz": {
        "star_ceiling": 9.5, "hockey_iq": 8.0, "skating_engine": 8.8,
        "offensive_star_power": 8.8, "competition_proof": 8.5,
        "character_compete": 9.5, "development_arc": 8.5,
    },
}


def northstar_generate(
    full_name: str,
    pos: str,
    height: str,
    weight: str,
    country: str,
    consensus_rank: int | None,
    player_key: str | None = None,
) -> dict[str, Any]:
    from name_utils import canonical_key

    key = player_key or canonical_key(full_name)
    reports = _load_reports()
    report = reports.get(key, {})
    evidence: dict[str, list[str]] = {}

    manual_dims = None
    for mk, mv in MANUAL.items():
        if canonical_key(mk) == key:
            manual_dims = mv.copy()
            break

    if manual_dims is not None:
        dims = manual_dims
        cov = "manual"
    else:
        text = _text_blob(report)
        evidence: dict[str, list[str]] = {}
        lex: dict[str, float] = {}
        for dim in NORTHSTAR_WEIGHTS:
            if dim != "star_ceiling":
                s, ev = _lex_score(dim, text)
            else:
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
        cons = _consensus_prior(consensus_rank)
        has_report = bool(report.get("has_full_report"))

        cov = "full" if has_report else ("partial" if report.get("meta_description") else "none")

        dims = _merge_scores(lex, grade, league, prod, dph_r, cons, has_report, pos)

    # Ajustements physiques légers (star path)
    h = parse_height(height)
    w = parse_weight(weight)
    if h >= 76 and dims["star_ceiling"] >= 7.5:
        dims["star_ceiling"] = min(10, dims["star_ceiling"] + 0.2)
    if h <= 69 and "D" not in pos.upper():
        dims["star_ceiling"] = max(1, dims["star_ceiling"] - 0.3)

    overall = northstar_overall(dims)
    star_tier = _star_tier(overall)

    forces = list(report.get("strengths") or [])[:6]
    if not forces:
        forces = [f"Signal {k}: {v}/10" for k, v in sorted(dims.items(), key=lambda x: -x[1])[:3]]

    faiblesses = list(report.get("weaknesses") or [])[:5]
    if not faiblesses and dims["star_ceiling"] < 7:
        faiblesses = ["Plafond star limité selon rapport / signaux"]

    resume = report.get("report") or report.get("meta_description") or (
        f"{full_name} ({pos}) — évaluation NORTHSTAR basée sur "
        f"{'rapport DPH' if cov == 'full' else 'signaux partiels' if cov == 'partial' else 'inférence'}. "
        f"Star Probability Index: {overall}/100 ({star_tier})."
    )

    scores = {
        **dims,
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
