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

    text = _scoring_text(report)
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
