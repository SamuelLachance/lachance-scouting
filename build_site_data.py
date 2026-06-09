#!/usr/bin/env python3
"""Fusionne rankings + analyses → site/data/{year}/players.json + manifest multi-repêchages."""

import json
import re
from pathlib import Path

from draft_config import DRAFTS, DEFAULT_DRAFT_YEAR, manifest_for_site, paths_for_year
from name_utils import canonical_key
from player_sizes import is_missing_size, normalize_weight_lbs
from northstar_scoring import (
    build_forces_faiblesses,
    _load_evaluations,
    _load_reports,
    _scores_from_evaluation,
    ea_projection_for_player,
    ea_tier_for_player,
    northstar_overall,
)
from truth_engine import compute_evidence_confidence, truth_discovery_rating

PILLAR_TO_SKILL = {
    "star_ceiling": "starCeiling",
    "hockey_iq": "hockeyIQ",
    "skating_engine": "skatingEngine",
    "offensive_star_power": "offensiveStarPower",
    "competition_proof": "competitionProof",
    "character_compete": "characterCompete",
    "development_arc": "developmentArc",
}

DIM_FROM_RANKING = {
    "Plafond_Etoile": "star_ceiling",
    "Plafond_Elite": "star_ceiling",
    "IQ_Elite": "hockey_iq",
    "IQ_Realisation": "hockey_iq",
    "Moteur_Patinage": "skating_engine",
    "Patinage_Upside": "skating_engine",
    "Pouvoir_Offensif": "offensive_star_power",
    "Outils_Offensifs": "offensive_star_power",
    "Creation_Jeu": "offensive_star_power",
    "Preuve_Competition": "competition_proof",
    "Competitivite": "character_compete",
    "Variance_Positive": "character_compete",
    "Arc_Developpement": "development_arc",
    "Trajectoire": "development_arc",
}

BASE = Path(__file__).parent
SITE_DATA = BASE / "site" / "data"
WEB_DATA = BASE / "web" / "public" / "data"


def load_player_meta(year: int) -> dict:
    path = paths_for_year(year)["data_dir"] / "player_meta.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def resolve_player_size(p: dict, meta: dict) -> tuple[str, int | str]:
    key = canonical_key(p["Nom"])
    height = p.get("Taille", "")
    weight = p.get("Poids_lbs", "")
    entry = meta.get(key, {})
    if is_missing_size(height) and not is_missing_size(entry.get("height")):
        height = entry["height"]
    if is_missing_size(weight) and not is_missing_size(entry.get("weight")):
        weight = entry["weight"]
    if str(weight).isdigit():
        weight = int(weight)
    elif not is_missing_size(weight):
        parsed = normalize_weight_lbs(weight)
        weight = parsed if parsed is not None else weight
    return height, weight


def slug_from_file(path: str) -> str:
    name = Path(path.replace("\\", "/")).stem
    name = re.sub(r"^\d+_", "", name)
    return name.replace("_", "-")


def parse_md(text: str) -> dict:
    out = {
        "resume": "", "forces": [], "faiblesses": [], "comparable": "",
        "projection": "", "upsideThesis": "",
    }
    section = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("## Résumé exécutif"):
            section = "resume"
            continue
        if line.startswith("## Thèse star") or line.startswith("## Thèse upside"):
            section = "upsideThesis"
            continue
        if line.startswith("## Forces"):
            section = "forces"
            continue
        if line.startswith("## Faiblesses"):
            section = "faiblesses"
            continue
        if section in ("forces", "faiblesses") and line.startswith("- "):
            out[section].append(line[2:])
            continue
        if line.startswith("## Comparable") or line.startswith("## Projection NHL"):
            section = "comparable" if "Comparable" in line else "projection"
            continue
        if line.startswith("## Projection"):
            section = "projection"
            continue
        if line.startswith("## ") and section:
            section = None
            continue
        if not line or line.startswith("|") or line.startswith("---") or line.startswith("#"):
            continue
        if line.startswith("**SCORE") or line.startswith("**STAR") or line.startswith("**TOTAL"):
            section = None
            continue
        if section == "resume":
            out["resume"] += (line + " ")
        elif section == "upsideThesis":
            out["upsideThesis"] += (line + " ")
        elif section == "comparable":
            out["comparable"] += (line + " ")
        elif section == "projection":
            out["projection"] += (line + " ")
    for k in ("resume", "comparable", "projection", "upsideThesis"):
        out[k] = out[k].strip()
    return out


def dims_from_ranking(p: dict) -> dict[str, float]:
    dims: dict[str, float] = {}
    for src, dst in DIM_FROM_RANKING.items():
        if src in p and dst not in dims:
            dims[dst] = float(p[src])
    for dim in (
        "star_ceiling", "hockey_iq", "skating_engine", "offensive_star_power",
        "competition_proof", "character_compete", "development_arc",
    ):
        dims.setdefault(dim, 5.0)
    return dims


def northstar_scores_for_player(p: dict) -> dict | None:
    """Manual eval from player_evaluations.json when done; else None (CSV fallback)."""
    key = canonical_key(p["Nom"])
    player_eval = (_load_evaluations().get("players") or {}).get(key)
    if not (
        player_eval
        and player_eval.get("status") == "done"
        and player_eval.get("pillars")
    ):
        return None
    report = _load_reports().get(key, {})
    return _scores_from_evaluation(
        player_eval,
        p["Nom"],
        p["Position"],
        p["Taille"],
        str(p.get("Poids_lbs", "")),
        report,
        country=p.get("Pays", ""),
        rankings_dob=p.get("Date_Naissance", ""),
    )


def skills_from_scores(scores: dict, p: dict) -> dict[str, float]:
    if scores:
        return {
            dst: float(scores.get(src, 5.0))
            for src, dst in PILLAR_TO_SKILL.items()
        }
    return {
        "starCeiling": float(p.get("Plafond_Etoile") or p.get("Plafond_Elite", 5)),
        "hockeyIQ": float(p.get("IQ_Elite") or p.get("IQ_Realisation", 5)),
        "skatingEngine": float(p.get("Moteur_Patinage") or p.get("Patinage_Upside", 5)),
        "offensiveStarPower": float(p.get("Pouvoir_Offensif") or p.get("Outils_Offensifs", 5)),
        "competitionProof": float(p.get("Preuve_Competition") or 5.0),
        "characterCompete": float(p.get("Competitivite") or p.get("Variance_Positive", 5)),
        "developmentArc": float(p.get("Arc_Developpement") or p.get("Trajectoire", 5)),
    }


def rationales_from_scores(scores: dict, p: dict) -> dict[str, str]:
    rat = scores.get("rationales") or {} if scores else {}
    skill_rationales: dict[str, str] = {}
    for src, dst in PILLAR_TO_SKILL.items():
        if src in rat:
            skill_rationales[dst] = rat[src]
    if skill_rationales:
        return skill_rationales

    legacy = p.get("Rationales") or {}
    skill_key_map = {
        "star_ceiling": "starCeiling",
        "hockey_iq": "hockeyIQ",
        "skating_engine": "skatingEngine",
        "offensive_star_power": "offensiveStarPower",
        "competition_proof": "competitionProof",
        "character_compete": "characterCompete",
        "development_arc": "developmentArc",
        "plafond_elite": "starCeiling",
        "patinage_upside": "skatingEngine",
        "outils_offensifs": "offensiveStarPower",
        "creation_jeu": "offensiveStarPower",
        "iq_realisation": "hockeyIQ",
        "trajectoire": "developmentArc",
        "variance_positive": "characterCompete",
    }
    for src, dst in skill_key_map.items():
        if src in legacy and dst not in skill_rationales:
            skill_rationales[dst] = legacy[src]
    return skill_rationales


def enrich_analysis(
    analysis: dict,
    p: dict,
    reports: dict,
    scores: dict | None = None,
) -> dict:
    """Complète forces/faiblesses si le markdown est incomplet."""
    forces = list(analysis.get("forces") or [])
    faiblesses = list(analysis.get("faiblesses") or [])
    if scores:
        for item in scores.get("forces") or []:
            if item not in forces:
                forces.append(item)
        for item in scores.get("faiblesses") or []:
            if item not in faiblesses:
                faiblesses.append(item)
    if len(forces) >= 3 and len(faiblesses) >= 2:
        out = dict(analysis)
        out["forces"] = forces[:5]
        out["faiblesses"] = faiblesses[:4]
        return out

    dims = (
        {k: float(scores.get(k, 5.0)) for k in PILLAR_TO_SKILL}
        if scores
        else dims_from_ranking(p)
    )
    report = reports.get(canonical_key(p["Nom"]), {})
    cov = p.get("Couverture_Rapport") or "none"
    synth_forces, synth_faiblesses = build_forces_faiblesses(
        dims,
        report,
        {},
        p.get("Position", ""),
        p.get("Taille", ""),
        str(p.get("Poids_lbs", "")),
        cov,
    )

    seen_f = set(forces)
    for item in synth_forces:
        if item not in seen_f and len(forces) < 5:
            forces.append(item)
            seen_f.add(item)

    seen_w = set(faiblesses)
    for item in synth_faiblesses:
        if item not in seen_w and len(faiblesses) < 4:
            faiblesses.append(item)
            seen_w.add(item)

    out = dict(analysis)
    out["forces"] = forces[:5]
    out["faiblesses"] = faiblesses[:4]
    return out


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def discovery_label(score: float) -> str:
    if score >= 85:
        return "Alerte star cachée"
    if score >= 75:
        return "Diamant sous-évalué"
    if score >= 65:
        return "Upside à surveiller"
    if score >= 55:
        return "Signal latent"
    return "Prix du marché"


def discovery_confidence(row: dict) -> tuple[float, str]:
    coverage = (row.get("reportCoverage") or "").lower()
    coverage_score = {
        "manual": 0.95,
        "full": 0.9,
        "partial": 0.74,
        "thin": 0.58,
        "none": 0.42,
    }.get(coverage, 0.55)
    source_count = len(row.get("sourceMix") or [])
    source_score = clamp(0.35 + source_count * 0.12, 0.35, 0.95)
    score = round(coverage_score * 0.65 + source_score * 0.35, 2)
    if score >= 0.78:
        label = "Confiance élevée"
    elif score >= 0.58:
        label = "Confiance moyenne"
    else:
        label = "Confiance basse"
    return score, label


def build_discovery_signal(row: dict, northstar_rank: int) -> dict:
    """TRUTH Discovery — détecte l'upside sous-évalué avec bornes scientifiques."""
    skills = row.get("skills") or {}
    base_score = float(row.get("baseNorthstarScore", row.get("overall", 50.0)))
    pillars = {
        "star_ceiling": float(skills.get("starCeiling", 5.0)),
        "hockey_iq": float(skills.get("hockeyIQ", 5.0)),
        "skating_engine": float(skills.get("skatingEngine", 5.0)),
        "offensive_star_power": float(skills.get("offensiveStarPower", 5.0)),
        "competition_proof": float(skills.get("competitionProof", 5.0)),
        "character_compete": float(skills.get("characterCompete", 5.0)),
        "development_arc": float(skills.get("developmentArc", 5.0)),
    }
    coverage = (row.get("reportCoverage") or "partial").lower()
    source_count = len(row.get("sourceMix") or [])
    conf_score, conf_label = compute_evidence_confidence(
        source_count,
        max(1, source_count // 2),
        coverage,
        0.85,
        0.60,
    )
    signal = truth_discovery_rating(
        spi=base_score,
        spi_rank=northstar_rank,
        pillars=pillars,
        consensus_rank=row.get("consensusRank"),
        confidence=conf_score,
        coverage=coverage,
        is_over_age=bool(row.get("isOverAge")),
    )
    signal["confidenceLabel"] = conf_label
    return signal


def build_year(year: int) -> int:
    paths = paths_for_year(year)
    rankings_path = paths["rankings"]
    analyses_dir = paths["analyses"]

    if not rankings_path.exists():
        legacy = BASE / "data" / "rankings.json"
        if legacy.exists():
            rankings_path = legacy
            analyses_dir = BASE / "analyses_joueurs"
        else:
            print(f"  skip {year}: pas de rankings.json")
            return 0

    players_raw = json.loads(rankings_path.read_text(encoding="utf-8"))
    reports = _load_reports()
    photos_path = paths["data_dir"] / "player_photos.json"
    photos_map: dict = {}
    if photos_path.exists():
        photos_map = json.loads(photos_path.read_text(encoding="utf-8"))
    player_meta = load_player_meta(year)
    staged = []
    for p in players_raw:
        height, weight = resolve_player_size(p, player_meta)
        slug = slug_from_file(p.get("Fichier_Local", p["Nom"].lower().replace(" ", "-")))
        md_path = analyses_dir / Path(p.get("Fichier_Local", "").replace("\\", "/")).name
        analysis = parse_md(md_path.read_text(encoding="utf-8")) if md_path.exists() else {}
        scores = northstar_scores_for_player(p)
        analysis = enrich_analysis(analysis, p, reports, scores)
        spi = (
            northstar_overall(scores, position=p["Position"])
            if scores
            else float(p.get("Score_NORTHSTAR") or p.get("Score_APEX", 50))
        )
        cr = p.get("Rang_Consensus")
        skill_rationales = rationales_from_scores(scores, p)
        photo_entry = photos_map.get(slug, {})
        photo_url = photo_entry.get("local") or f"./images/players/{year}/{slug}.svg"
        player_eval = (_load_evaluations().get("players") or {}).get(canonical_key(p["Nom"]), {})
        base_score = round(spi, 2)
        staged.append({
            "id": slug,
            "draftYear": year,
            "name": p["Nom"],
            "position": p["Position"],
            "height": height,
            "weight": weight,
            "shoots": p["Tire"],
            "country": p["Pays"],
            "photoUrl": photo_url,
            "overall": base_score,
            "baseNorthstarScore": base_score,
            "isOverAge": bool(
                (scores or {}).get("is_over_age")
                or p.get("Is_Over_Age")
            ),
            "overAgePenalty": float(
                (scores or {}).get("over_age_penalty")
                or p.get("Over_Age_Penalty")
                or 0
            ),
            "spiBeforePenalty": (
                (scores or {}).get("spi_before_penalty")
                or p.get("SPI_Before_Penalty")
            ),
            "starTier": (scores or {}).get("star_tier") or p.get("Star_Tier", ""),
            "reportCoverage": (scores or {}).get("report_coverage") or p.get("Couverture_Rapport", ""),
            "consensusRank": cr if cr != "N/A" else None,
            "skills": skills_from_scores(scores, p),
            "skillRationales": skill_rationales,
            "sourceMix": player_eval.get("source_mix") or [],
            "analysis": analysis,
        })

    # First pass: rank the pure talent model, then re-score everyone with
    # NORTHSTAR Discovery Rating (NDR), which rewards star tools the market may miss.
    staged.sort(key=lambda x: (-x["baseNorthstarScore"], x["name"]))
    for base_rank, row in enumerate(staged, 1):
        row["baseNorthstarRank"] = base_rank
        row["rank"] = base_rank

    for row in staged:
        discovery_signal = build_discovery_signal(row, row["baseNorthstarRank"])
        row["discoverySignal"] = discovery_signal
        row["overall"] = discovery_signal["score"]
    staged.sort(key=lambda x: (-x["overall"], -x["baseNorthstarScore"], x["name"]))
    for discovery_rank, row in enumerate(staged, 1):
        row["rank"] = discovery_rank

    enriched = []
    for discovery_rank, row in enumerate(staged, 1):
        cr = row["consensusRank"]
        delta_val = (cr - discovery_rank) if cr is not None else None
        discovery_signal = build_discovery_signal(row, row["baseNorthstarRank"])
        row["overall"] = discovery_signal["score"]
        ea_tier = ea_tier_for_player(row["overall"], row["position"], draft_rank=discovery_rank)
        projection_fr = ea_projection_for_player(
            row["overall"], row["position"], lang="fr", draft_rank=discovery_rank
        )
        projection_en = ea_projection_for_player(
            row["overall"], row["position"], lang="en", draft_rank=discovery_rank
        )
        analysis = dict(row["analysis"])
        analysis["projection"] = projection_fr
        enriched.append({
            **row,
            "rank": discovery_rank,
            "northstarRank": discovery_rank,
            "apexRank": discovery_rank,
            "baseNorthstarRank": row["baseNorthstarRank"],
            "consensusDelta": delta_val,
            "tier": ea_tier["tierLabel"],
            "eaTier": ea_tier["eaTier"],
            "tierGroup": ea_tier["tierGroup"],
            "projection": projection_fr,
            "projectionEn": projection_en,
            "discoverySignal": discovery_signal,
            "analysis": analysis,
        })

    out_dir = SITE_DATA / str(year)
    web_dir = WEB_DATA / str(year)
    out_dir.mkdir(parents=True, exist_ok=True)
    web_dir.mkdir(parents=True, exist_ok=True)
    content = json.dumps(enriched, ensure_ascii=False, indent=2)
    out_file = out_dir / "players.json"
    out_file.write_text(content, encoding="utf-8")
    (web_dir / "players.json").write_text(content, encoding="utf-8")
    if year == DEFAULT_DRAFT_YEAR:
        (SITE_DATA / "players.json").write_text(content, encoding="utf-8")
        (WEB_DATA / "players.json").write_text(content, encoding="utf-8")
    print(f"OK {year}: {len(enriched)} joueurs -> {out_file.relative_to(BASE)}")
    return len(enriched)


def write_manifest() -> None:
    manifest = manifest_for_site()
    text = json.dumps(manifest, ensure_ascii=False, indent=2)
    (SITE_DATA / "drafts.json").write_text(text, encoding="utf-8")
    (WEB_DATA / "drafts.json").write_text(text, encoding="utf-8")
    print(f"OK manifest -> site/data/drafts.json ({len(manifest['years'])} repêchages)")


def build_index_html():
    css = (BASE / "site" / "styles.css").read_text(encoding="utf-8")
    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Lachance Scouting — Repêchages NHL</title>
  <meta name="description" content="Lachance Scouting — repêchages NHL année par année, Star Probability NORTHSTAR" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,600;9..40,700&family=JetBrains+Mono:wght@500&family=Syne:wght@600;700;800&display=swap" rel="stylesheet" />
  <style>
{css}
  </style>
</head>
<body style="background:#030712;color:#e2e8f0;margin:0;min-height:100vh">
  <noscript><div style="padding:2rem;text-align:center">JavaScript requis.</div></noscript>
  <div id="app">
    <div class="loader">
      <div class="loader-ring"></div>
      <p>Chargement Lachance Scouting…</p>
    </div>
  </div>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <script src="app.js"></script>
</body>
</html>
"""
    (BASE / "site" / "index.html").write_text(html, encoding="utf-8")
    print("OK index.html regenere")


def main() -> int:
    total = 0
    for year in sorted(DRAFTS.keys()):
        if DRAFTS[year]["status"] == "active":
            total = max(total, build_year(year))
    write_manifest()
    return total


if __name__ == "__main__":
    n = main()
    build_index_html()
