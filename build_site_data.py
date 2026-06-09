#!/usr/bin/env python3
"""Fusionne rankings + analyses → site/data/{year}/players.json + manifest multi-repêchages."""

import json
import re
from pathlib import Path

from draft_config import DRAFTS, DEFAULT_DRAFT_YEAR, manifest_for_site, paths_for_year
from name_utils import canonical_key
from northstar_scoring import (
    build_forces_faiblesses,
    _load_evaluations,
    _load_reports,
    _scores_from_evaluation,
    northstar_overall,
)

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


def tier(note: float) -> str:
    if note >= 88:
        return "Upside Élite"
    if note >= 75:
        return "Upside 1er tour"
    if note >= 62:
        return "Upside 2e-3e tour"
    if note >= 48:
        return "Upside milieu"
    return "Upside limité"


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
    enriched = []
    for p in players_raw:
        slug = slug_from_file(p.get("Fichier_Local", p["Nom"].lower().replace(" ", "-")))
        md_path = analyses_dir / Path(p.get("Fichier_Local", "").replace("\\", "/")).name
        analysis = parse_md(md_path.read_text(encoding="utf-8")) if md_path.exists() else {}
        scores = northstar_scores_for_player(p)
        analysis = enrich_analysis(analysis, p, reports, scores)
        note = (
            northstar_overall(scores)
            if scores
            else float(p.get("Score_NORTHSTAR") or p.get("Score_APEX", 50))
        )
        cr = p.get("Rang_Consensus")
        delta = p.get("Delta_vs_Consensus")
        delta_val = None if delta in ("N/A", None) else int(delta)
        skill_rationales = rationales_from_scores(scores, p)
        photo_entry = photos_map.get(slug, {})
        photo_url = photo_entry.get("local") or f"./images/players/{year}/{slug}.svg"
        enriched.append({
            "id": slug,
            "draftYear": year,
            "rank": p["Rang_Final"],
            "northstarRank": p.get("Rang_NORTHSTAR") or p.get("Rang_APEX"),
            "apexRank": p.get("Rang_NORTHSTAR") or p.get("Rang_APEX"),
            "blendRank": float(p.get("Rang_NORTHSTAR") or p.get("Moyenne_Rang", p["Rang_Final"])),
            "name": p["Nom"],
            "position": p["Position"],
            "height": p["Taille"],
            "weight": int(p["Poids_lbs"]) if str(p.get("Poids_lbs", "")).isdigit() else p.get("Poids_lbs"),
            "shoots": p["Tire"],
            "country": p["Pays"],
            "photoUrl": photo_url,
            "overall": note,
            "starTier": (scores or {}).get("star_tier") or p.get("Star_Tier", ""),
            "reportCoverage": (scores or {}).get("report_coverage") or p.get("Couverture_Rapport", ""),
            "consensusRank": cr if cr != "N/A" else None,
            "consensusDelta": delta_val,
            "tier": tier(note),
            "skills": skills_from_scores(scores, p),
            "skillRationales": skill_rationales,
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
