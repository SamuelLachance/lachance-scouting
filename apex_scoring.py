"""
APEX — Analytical Prospect EXcellence Index
Modèle propriétaire orienté UPSIDE (plafond), indépendant du consensus.

8 dimensions /100 → 7 dimensions (sans frame).
"""

from __future__ import annotations

import re
from typing import Any

# Pondérations APEX — plafond + patinage dominent (~88%)
APEX_WEIGHTS = {
    "plafond_elite": 0.52,      # Plafond si tout clique (★ pilier #1)
    "patinage_upside": 0.36,  # Vitesse + marge d'amélioration (pilier #2)
    "outils_offensifs": 0.03,  # Skill pur — faible valeur prédictive upside
    "creation_jeu": 0.03,       # Création 5v5 — secondaire
    "iq_realisation": 0.02,     # IQ — secondaire
    "trajectoire": 0.02,        # Momentum — secondaire
    "variance_positive": 0.02,  # Boom/bust — secondaire
}

APEX_LABELS = {
    "outils_offensifs": "Outils offensifs bruts",
    "plafond_elite": "Plafond élite (★)",
    "patinage_upside": "Patinage + projection",
    "creation_jeu": "Création indépendante",
    "iq_realisation": "IQ de réalisation",
    "trajectoire": "Trajectoire / momentum",
    "variance_positive": "Variance positive (boom)",
}

META_KEYS = ("resume", "forces", "faiblesses", "comparable", "projection", "upside_thesis", "consensus_delta", "rationales")


def _p(
    oo, pl, pa, cr, iq, tr, fr, va,
    resume, forces, faiblesses, comparable, projection, thesis,
    rationales: dict[str, str] | None = None,
) -> dict[str, Any]:
    d = {
        "outils_offensifs": oo, "plafond_elite": pl, "patinage_upside": pa,
        "creation_jeu": cr, "iq_realisation": iq, "trajectoire": tr,
        "variance_positive": va,
        "resume": resume, "forces": forces, "faiblesses": faiblesses,
        "comparable": comparable, "projection": projection,
        "upside_thesis": thesis,
    }
    if rationales:
        d["rationales"] = rationales
    return d


def _band(v: float) -> tuple[str, str]:
    if v >= 9.5:
        return "élite", "niveau franchise / top-3 de la classe"
    if v >= 9.0:
        return "exceptionnel", "premier quart de repêchage, outil différenciant"
    if v >= 8.5:
        return "très élevé", "profil NHL top-6 / top-pair crédible"
    if v >= 8.0:
        return "solide", "transposable en NHL mais pas généralement game-breaking"
    if v >= 7.5:
        return "correct", "NHLable sans être un levier de plafond"
    if v >= 7.0:
        return "modeste", "limitera le upside si non compensé ailleurs"
    if v >= 6.0:
        return "faible", "frein structurel au plafond élite"
    return "très faible", "incompatible avec un pari upside agressif"


def build_rationales(
    scores: dict,
    *,
    full_name: str,
    pos: str,
    height: str,
    weight: str,
    country: str,
    consensus_rank: int | None,
    adj: float = 0.0,
) -> dict[str, str]:
    """Justification détaillée de chaque note APEX /10."""
    if scores.get("rationales"):
        return {k: v for k, v in scores["rationales"].items() if k in APEX_WEIGHTS}

    resume = scores.get("resume", "")
    forces = scores.get("forces") or []
    faiblesses = scores.get("faiblesses") or []
    thesis = scores.get("upside_thesis", "")
    h = parse_height(height)
    w = parse_weight(weight)
    is_g = pos.upper() in ("G", "GK")
    is_d = "D" in pos.upper() or pos.upper() == "D"
    is_w = pos.upper() in ("LW", "RW", "W")
    is_c = pos.upper() == "C"
    cr_txt = f"#{consensus_rank}" if consensus_rank else "hors top-100 public"

    oo = scores.get("outils_offensifs", 5.0)
    pl = scores.get("plafond_elite", 5.0)
    pa = scores.get("patinage_upside", 5.0)
    cj = scores.get("creation_jeu", 5.0)
    iq = scores.get("iq_realisation", 5.0)
    tr = scores.get("trajectoire", 5.0)
    va = scores.get("variance_positive", 5.0)

    b_oo, d_oo = _band(oo)
    b_pl, d_pl = _band(pl)
    b_pa, d_pa = _band(pa)
    b_cj, d_cj = _band(cj)
    b_iq, d_iq = _band(iq)
    b_tr, d_tr = _band(tr)
    b_va, d_va = _band(va)

    pos_label = {"G": "gardien", "D": "défenseur"}.get(pos.upper(), "attaquant")
    if is_w:
        pos_label = "ailier"
    elif is_c:
        pos_label = "centre"

    # --- Outils offensifs ---
    oo_parts = [
        f"**{oo}/10 — {b_oo.capitalize()}** ({d_oo}). "
        f"Dimension secondaire ({int(APEX_WEIGHTS['outils_offensifs']*100)}%): "
        f"skills offensifs bruts — faible poids car peu prédictif du plafond élite seul."
    ]
    if oo >= 9.0:
        oo_parts.append(
            f"Pour {full_name}, le toolkit offensif se situe dans le tier le plus élevé de la classe — "
            f"les skills se transfèrent contre des adversaires plus âgés et plus physiques."
        )
    elif oo >= 8.0:
        oo_parts.append(
            f"Les outils sont clairement NHL top-6, mais un cran en dessous des créateurs franchise "
            f"de la tête de classe."
        )
    else:
        oo_parts.append(
            f"Les outils offensifs ne justifient pas à euls seuls un pari franchise; "
            f"le joueur devra compenser par IQ, physique ou situation de linemates."
        )
    if is_d and oo >= 8.0:
        oo_parts.append("En défense, la note intègre la qualité de sortie de zone, le tir de la pointe et la capacité à activer en zone offensive.")
    if forces:
        oo_parts.append(f"Éléments clés: {forces[0].lower()}.")

    # --- Plafond élite ---
    pl_w = int(APEX_WEIGHTS["plafond_elite"] * 100)
    pa_w = int(APEX_WEIGHTS["patinage_upside"] * 100)
    pl_parts = [
        f"**{pl}/10 — {b_pl.capitalize()}** ({d_pl}). "
        f"Pilier APEX #{1} ({pl_w}% du score): le plafond si tout converge — "
        f"votes Hart/Norris, impact franchise, pas le floor safe."
    ]
    if pl >= 9.5:
        pl_parts.append(
            f"{full_name} a un chemin crédible vers l'élite NHL absolue; "
            f"c'est le critère qui justifie le rang APEX global."
        )
    elif pl >= 8.5:
        pl_parts.append(
            "Plafond de star / top-pair offensif réaliste, mais pas de candidat Hart "
            "sans progression significative."
        )
    elif pl <= 7.5:
        pl_parts.append(
            "Plafond limité à un rôle solide (2e ligne / 2e paire) — "
            "APEX pénalise volontairement ce profil vs le consensus qui valorise le floor."
        )
    if thesis:
        pl_parts.append(thesis)

    # --- Patinage + projection ---
    pa_parts = [
        f"**{pa}/10 — {b_pa.capitalize()}** ({d_pa}). "
        f"Pilier APEX #{2} ({pa_w}% du score): vitesse actuelle, accélération, "
        f"agilité latérale et marge d'amélioration physique ({height}, {weight} lbs)."
    ]
    if pa >= 9.0:
        pa_parts.append("Patinage différenciant qui crée de l'espace en transition et en 1v1.")
    elif pa >= 8.0:
        pa_parts.append("Patinage NHL-ready; peut jouer au tempo NHL sans être un avantage structurel.")
    elif pa <= 7.0:
        pa_parts.append(
            f"La vitesse est un plafond structurel — particulièrement critique pour un {pos_label} "
            f"{'petit' if h <= 70 else 'de cette taille'}."
        )
    if h <= 70 and pa >= 8.5:
        pa_parts.append("Malgré la petite taille, les patins compensent et créent de la marge en NHL.")
    if is_d and pa >= 8.5:
        pa_parts.append("Pour un D, la note inclut le pivot arrière et la capacité à fermer en transition.")

    # --- Création indépendante ---
    cj_parts = [
        f"**{cj}/10 — {b_cj.capitalize()}** ({d_cj}). "
        f"Dimension secondaire ({int(APEX_WEIGHTS['creation_jeu']*100)}%): "
        f"création 5v5 indépendante — inclus pour contexte, poids minimal."
    ]
    if is_g:
        cj_parts.append("Non applicable aux gardiens — score neutre par défaut.")
    elif cj >= 9.0:
        cj_parts.append(
            f"{full_name} peut porter une ligne offensive seul; "
            f"c'est un multiplicateur de valeur en repêchage upside."
        )
    elif cj >= 8.0:
        cj_parts.append("Crée régulièrement des occasions mais partage souvent la charge avec des linemates compétents.")
    else:
        cj_parts.append(
            "Profil finisseur ou complémentaire plutôt que driver — "
            "la valeur dépendra du contexte d'équipe et du PP."
        )
    if is_d and cj >= 8.5:
        cj_parts.append("En défense: activation, transport de rondelle et création depuis la pointe en PP.")

    # --- IQ réalisation ---
    iq_parts = [
        f"**{iq}/10 — {b_iq.capitalize()}** ({d_iq}). "
        f"Dimension secondaire ({int(APEX_WEIGHTS['iq_realisation']*100)}%): "
        f"IQ de réalisation — faible poids vs plafond/patinage."
    ]
    if iq >= 9.0:
        iq_parts.append("IQ qui accélère la courbe de développement — le plafond se concrétise plus vite.")
    elif iq >= 8.0:
        iq_parts.append("Décisions généralement solides; quelques ajustements attendus vs la vitesse NHL.")
    else:
        iq_parts.append(
            "Écart possible entre le talent brut et la production réelle — "
            "risque que le plafond théorique ne se matérialise jamais."
        )
    if faiblesses and any("iq" in f.lower() or "décision" in f.lower() for f in faiblesses):
        iq_parts.append(f"Attention: {faiblesses[0]}.")

    # --- Trajectoire ---
    tr_parts = [
        f"**{tr}/10 — {b_tr.capitalize()}** ({d_tr}). "
        f"Dimension secondaire ({int(APEX_WEIGHTS['trajectoire']*100)}%): "
        f"trajectoire récente — signal faible vs plafond et patinage."
    ]
    if tr >= 9.0:
        tr_parts.append(
            "Trajectoire ascendante nette — le joueur est en train de devenir un autre prospect "
            "comparé au début de saison."
        )
    elif tr >= 8.0:
        tr_parts.append("Progression constante; pas de signal d'alarme mais pas de breakout récent non plus.")
    else:
        tr_parts.append(
            "Courbe plate ou ralentie — APEX pénalise car le momentum prédit souvent "
            "le prochain saut de plafond."
        )
    if consensus_rank and adj >= 1.5:
        tr_parts.append(
            f"APEX voit une trajectoire sous-estimée par le consensus ({cr_txt}) "
            f"— ajustement upside +{adj:.1f}."
        )

    # --- Variance positive ---
    va_parts = [
        f"**{va}/10 — {b_va.capitalize()}** ({d_va}). "
        f"Dimension secondaire ({int(APEX_WEIGHTS['variance_positive']*100)}%): "
        f"variance boom/bust — contexte uniquement, le plafond et le patinage priment."
    ]
    if va >= 9.0:
        va_parts.append(
            "Variance maximale — peut devenir une étoile ou un spécialiste limité; "
            "exactement le profil que APEX cherche pour battre le consensus."
        )
    elif va >= 7.5:
        va_parts.append("Upside intéressant avec un chemin clair vers le boom si 1-2 faiblesses se corrigent.")
    elif va <= 5.0:
        va_parts.append(
            "Profil « safe » — floor élevé mais plafond plafonné. "
            "Le consensus surévalue souvent ce type vs APEX upside pur."
        )
    if adj <= -1.5:
        va_parts.append(f"APEX ajuste à la baisse vs consensus ({cr_txt}): profil trop safe pour un pari franchise.")
    if h <= 70 and oo >= 8.5:
        va_parts.append("Combo petite taille + skill élite = variance naturellement élevée.")
    if is_g:
        va_parts.append("Les gardiens ont typiquement moins de variance upside que les patineurs.")

    if resume and len(resume) > 20:
        context = resume[:180].rstrip() + ("…" if len(resume) > 180 else "")
        oo_parts.append(f"Contexte: {context}")

    return {
        "outils_offensifs": " ".join(oo_parts),
        "plafond_elite": " ".join(pl_parts),
        "patinage_upside": " ".join(pa_parts),
        "creation_jeu": " ".join(cj_parts),
        "iq_realisation": " ".join(iq_parts),
        "trajectoire": " ".join(tr_parts),
        "variance_positive": " ".join(va_parts),
    }


# Profils APEX — évaluations manuelles orientées plafond (324 couverts via heuristique + ~85 détaillés)
APEX_PROFILES: dict[str, dict] = {
    "Gavin McKenna": _p(
        9.8, 10.0, 9.0, 9.9, 9.7, 9.8, 6.5, 8.5,
        "Génie offensif NCAA. 51 pts/35 matchs, domination post-JO junior. Talent le plus transposable en création 5v5 de la classe.",
        ["Vision élite", "Confiance avec rondelle", "Production vs older competition", "Créateur franchise"],
        ["Frame léger", "Peut over-handle", "Défense perfectible"],
        "Clayton Keller / Matthew Knies (haut de gamme)",
        "Franchise LW, 75-95 pts, Hart votes possible",
        "Seul prospect avec plafond Hart + probabilité top-6 élevée. APEX #1 — le consensus a raison ici.",
    ),
    "Viggo Björck": _p(
        9.5, 9.8, 9.2, 9.4, 9.6, 9.5, 5.0, 9.8,
        "Centre suédois fearless. Domine aux internationaux malgré 5'9. Tir trompeur, IQ de franchise.",
        ["Audace vs tout le monde", "Tir PP élite", "IQ top-3 classe", "Clutch international"],
        ["Taille", "Battles vs NHL heavy D", "Centre vs ailier en NHL"],
        "Zach Benson / William Nylander (petit élite)",
        "Top-line C/W, 65-80 pts si taille non limitante",
        "UPSIDE > CONSENSUS (#7→#2). Variance maximale: petite taille × skill élite = pari franchise.",
    ),
    "Carson Carels": _p(
        8.2, 9.6, 8.5, 8.0, 9.5, 9.0, 8.5, 8.0,
        "D WHL underrated. IQ défensif élite, physique farm, conscience positionnelle rare pour 18 ans.",
        ["IQ défensif top-pair", "Leadership", "Transition propre", "Frame rempli"],
        ["Offense limitée parfois", "Public sous-estime"],
        "Jake Sanderson / Ryan Murray (deux sens)",
        "Norris vote candidate si offense progresse",
        "Plafond D1 deux sens > Verhoeff/Reid pour réalisation long terme.",
    ),
    "Ethan Belchetz": _p(
        8.8, 9.7, 8.8, 8.5, 8.0, 8.5, 9.5, 9.0,
        "6'5/227 power forward. Clavicule cassée mais toolkit unique: vitesse + puissance + confiance.",
        ["Combo size/speed rare", "Net-front élite", "Intimidation physique", "PP option"],
        ["Blessure clavicule", "IQ moyen", "Consistency pré-blessure"],
        "Tom Wilson avec plus de skill / Brady Tkachuk",
        "Top-line power forward, 55-70 pts",
        "Consensus #14 → APEX top-5: profil NHL le plus projectable physiquement parmi les forwards.",
    ),
    "Chase Reid": _p(
        8.8, 9.4, 9.0, 8.5, 8.5, 9.0, 8.0, 7.5,
        "D OHL dynamique. Transition élite, compétitivité maximale, JO junior dominant.",
        ["Skating élite", "Compete", "Puck moving", "Confiance"],
        ["OHL level debate", "Décisions sous pression"],
        "Miro Heiskanen offensive mode",
        "Top-pair D, 40-55 pts, matchup driver",
        "Légèrement sous Carels APEX: plus polished mais plafond Norris un cran en dessous.",
    ),
    "Ryan Lin": _p(
        9.0, 9.5, 9.5, 9.2, 9.0, 9.2, 4.5, 9.5,
        "D WHL 5'11. Transition machine, possession dominante, style Hutson-lite sans même hype.",
        ["Transition élite", "Puck retention", "Offensive activation", "Évasivité"],
        ["Taille", "D-zone vs heavy forecheck", "Reach"],
        "Quinn Hutson / Cale Makar (aspirationnel)",
        "PP1 QB si défense OK → 55+ pts",
        "Consensus #12 → APEX #6: variance énorme. Boom = franchise D, bust = PP2 only.",
    ),
    "Oscar Hemming": _p(
        8.5, 9.6, 8.8, 8.0, 7.5, 7.0, 9.0, 9.0,
        "6'4 ailier finlandais BC. Saison raccourcie mais toolkit rare: size + speed + hands.",
        ["Frame NHL+", "Skill ceiling", "Skating pour taille", "Net-front"],
        ["Production incomplète", "Temps perdu contrat", "Consistency"],
        "Jake DeBrusk++ / Rick Nash elements",
        "Top-6 power winger 50+ pts si dev continue",
        "Raw upside top-10. Trajectoire pénalisée mais plafond > Hemming consensus #17.",
    ),
    "Xavier Villeneuve": _p(
        9.2, 9.5, 8.5, 9.0, 8.5, 8.5, 4.0, 9.8,
        "D QMJHL 5'10/150. Offense de point élite, PP wizard, gold U18.",
        ["PP quarterback", "Vision", "Activation", "Confidence"],
        ["Taille extrême", "D-zone translatability", "Polarizing"],
        "Torey Krug / Shayne Gostisbehere (aspirationnel)",
        "PP1 specialist ou top-4 offensive D",
        "Boom/bust max. APEX love: skill transposable > size fear du consensus.",
    ),
    "Wyatt Cullen": _p(
        9.5, 9.8, 9.8, 9.4, 9.6, 10.0, 7.0, 9.2,
        "USNTDP riser élite. +5 po en 2 ans (5'8→6'1), patinage shifty élite, IQ qui élève ses linemates. Parmi les plus jeunes de la classe.",
        ["Trajectoire #1 de la classe", "Patinage shifty élite", "IQ play-driving", "Growth spurt massif", "Mains + vision top-tier"],
        ["Effort inconsistant par moments", "Peut over-handle", "Encore en train de remplir son frame"],
        "Jack Hughes / Ryan Nugent-Hopkins (skill + courbe)",
        "Franchise 1C/1LW, 75+ pts si le moteur suit le talent",
        "BOOST APEX: ses 3 piliers (plafond 9.8, patinage 9.8, trajectoire 10.0) placent Cullen parmi les risers les plus chauds — consensus #10 est conservateur.",
    ),
    "Tommy Bleyl": _p(
        8.8, 9.3, 9.0, 8.5, 8.5, 9.8, 5.5, 9.0,
        "81 pts QMJHL rookie D. Explosion offensive, patineur, came from nowhere.",
        ["Production D élite", "Skating", "Offensive instincts", "Riser profile"],
        ["Force", "D-zone vs men", "Small sample peak?"],
        "Lane Hutson path",
        "Offensive D 50+ pts si D-zone suit",
        "Consensus #27 → APEX top-10: courbe de dev la plus pentue des défenseurs.",
    ),
    "Ivar Stenberg": _p(
        8.8, 8.8, 8.5, 8.5, 9.2, 8.5, 7.0, 5.5,
        "Ailier SHL complet. Floor le plus haut de la classe — plafond Hart limité.",
        ["Floor élite", "200-foot", "Tir", "SHL experience"],
        ["Plafond offensif sous McKenna", "Variance faible", "Safe not spectacular"],
        "William Nylander",
        "Top-line 55-70 pts, Selke votes possible",
        "CONSENSUS OVER-RATE pour upside: #2→#11. Parfait si vous voulez un floor, pas un home run.",
    ),
    "Keaton Verhoeff": _p(
        7.8, 9.0, 7.0, 7.5, 8.5, 8.0, 9.5, 6.5,
        "6'4 D NCAA. Frame franchise, physicality, but skating limits Norris upside.",
        ["Size", "Physicality", "Reach", "NCAA tested"],
        ["Skating ceiling", "Frozen Four flat", "Decision speed"],
        "Colton Parayko offensive",
        "Top-pair defensive D, 25-35 pts",
        "Plafond limité par patins vs Carels/Reid/Lin.",
    ),
    "Nikita Klepov": _p(
        9.0, 9.2, 7.5, 9.5, 8.5, 8.5, 7.5, 7.5,
        "Playmaker OHL élite. Vision top-5 classe, finesse + strength.",
        ["Playmaking élite", "PP vision", "Hands", "CHL production"],
        ["Skating average", "Defensive detail"],
        "Nikita Kucherov lite (aspirationnel) / Artemi Panarin",
        "Top-line W, 70+ pts ceiling",
        "Creation indépendante > Ruck brothers pour upside pur.",
    ),
    "Mathis Preston": _p(
        8.5, 8.8, 9.0, 7.5, 8.0, 8.0, 6.5, 6.0,
        "Tir NHL-ready. U18 star, spacing élite, release top de la classe.",
        ["Shot NHL-ready", "Skating", "Spacing", "U18 dominance"],
        ["Play-driving limité", "Consistency WHL"],
        "Filip Forsberg shot / Brock Boeser",
        "Finisher top-6, 35-50 goals potential",
        "Floor haut, plafond star limité vs créateurs.",
    ),
    "Liam Ruck": _p(
        8.0, 8.5, 8.0, 7.0, 7.5, 8.5, 6.5, 5.5,
        "45 buts WHL. Finisseur élite mais chimie jumelle + play-driving questions.",
        ["Goal scoring", "Release", "Net-front", "Production"],
        ["Dépendance linemates", "5v5 creation", "Twin factor draft"],
        "Brock Nelson finisher",
        "30-40 goal winger, pas driver franchise",
        "Production > skill transposable pour APEX.",
    ),
    "Adam Novotný": _p(
        8.0, 8.8, 8.0, 7.5, 8.0, 8.5, 8.5, 7.0,
        "Power forward OHL 30G. Process élite, heavy game, responsible two-way.",
        ["Power game", "Process", "Two-way", "International"],
        ["Skating top speed", "Offense ceiling debate"],
        "Evander Kane lite / Tom Wilson",
        "Top-6 power forward 45-55 pts",
        "Safe power upside, pas variance max.",
    ),
    "Caleb Malhotra": _p(
        7.5, 7.8, 7.5, 7.0, 9.0, 8.0, 7.0, 4.0,
        "Centre OHL deux sens. CONSENSUS #4 — APEX pénalise: floor > ceiling.",
        ["Floor top-6 C", "Defensive IQ", "Compete", "Faceoffs"],
        ["Vitesse", "Plafond offensif limité", "Not a game-breaker"],
        "Jean-Gabriel Pageau / Ryan O'Reilly lite",
        "2C two-way 45-55 pts, pas franchise",
        "⚠️ CONSENSUS OVER-RATE #4→#22 APEX: parfait pour win-now, mauvais pour upside pur.",
    ),
    "J.P. Hurlbert": _p(
        8.5, 8.8, 7.5, 8.0, 8.5, 9.0, 7.0, 7.0,
        "97 pts WHL rookie. Volume scorer, one-touch élite, Michigan commit.",
        ["Volume scoring", "One-touch", "PP", "Rookie dominance"],
        ["Away from puck", "Top-end speed"],
        "Jonathan Marchessault / Johnny Gaudreau path",
        "Top-6 scorer 55-65 pts",
        "Production-driven upside solide.",
    ),
    "Elton Hermansson": _p(
        8.5, 8.8, 8.0, 7.5, 7.5, 8.0, 6.5, 7.0,
        "Goal-scorer suédois. Release élite, PP weapon, 5v5 impact question.",
        ["Shot", "PP", "Goal-scoring instinct", "Offensive tools"],
        ["5v5 impact", "Defensive detail", "Urgency"],
        "Patrik Laine lite finisher",
        "35-45 goal winger si 5v5 suit",
        "Finisher upside > floor.",
    ),
    "Daxon Rudolph": _p(
        7.8, 8.5, 8.0, 7.5, 9.0, 8.5, 8.0, 6.0,
        "D WHL IQ élite. Safe top-4, PP option, playoffs strong.",
        ["Hockey sense", "Two-way", "Shot from blue", "Poise"],
        ["Passivity parfois", "Physical ceiling"],
        "Ryan Ellis / Tony DeAngelo lite",
        "Top-4 D 35-45 pts",
        "Safe D — APEX modéré sur variance.",
    ),
    "Alberts Smits": _p(
        7.5, 8.5, 8.0, 7.0, 8.5, 8.5, 8.5, 6.5,
        "D letton pro-experienced. DEL/Liiga/JO, mobile big body.",
        ["Pro experience young", "Size + mobility", "International", "Poise"],
        ["Offense ceiling", "Adjustment NA"],
        "Moritz Seider elements",
        "Top-4 D two-way",
        "Experience boosts floor more than ceiling.",
    ),
    "Tynan Lawrence": _p(
        8.0, 8.2, 7.5, 8.0, 9.0, 7.5, 6.5, 5.5,
        "C NCAA intelligent. Power playmaker, two-way, BU transfer.",
        ["IQ", "Two-way C", "Power", "Passing"],
        ["Skating not elite", "Offense ceiling"],
        "Patrice Bergeron lite offensively",
        "2C 45-55 pts, high floor",
        "IQ high but star upside limited.",
    ),
    "Ryan Roobroeck": _p(
        7.5, 8.8, 7.0, 7.0, 7.0, 6.5, 9.5, 8.5,
        "6'4/99G carrière OHL. Net-front élite, effort questions = variance.",
        ["Size", "Goal scoring history", "Net-front", "PP"],
        ["Work ethic concerns", "Motor inconsistent", "Skating"],
        "Chris Kreider si motor fixé",
        "30-40 goal power forward OU bust",
        "Variance positive haute — effort risk.",
    ),
    "Ilia Morozov": _p(
        7.8, 8.5, 7.5, 7.5, 8.0, 8.0, 8.5, 6.5,
        "6'3 C NCAA youngest. Power center projection, mature game.",
        ["Size at C", "Maturity", "Passing", "Physicality"],
        ["Offense ceiling", "Skating average"],
        "Anze Kopitar lite frame",
        "2C power 40-55 pts",
        "Safe power C, modéré upside.",
    ),
    "Yegor Shilov": _p(
        8.5, 8.8, 7.5, 8.5, 7.5, 8.0, 6.0, 7.5,
        "82 pts QMJHL. Skill élite, pace questions, dominant avec Vlasov.",
        ["Skill", "Puck dominance", "Offensive creativity", "Production"],
        ["Pace", "Defensive habits", "Off-puck"],
        "Nikita Kucherov (skill only)",
        "Top-6 skill winger si pace suit",
        "Skill upside > Suvanto/Malhotra types.",
    ),
    "Adam Valentini": _p(
        8.8, 8.8, 9.0, 8.0, 7.5, 8.5, 5.5, 8.0,
        "Energy skill C Michigan. Footwork élite, pest, shot improving.",
        ["Skating/feet", "Energy", "Skill", "Compete"],
        ["Size", "Consistency", "Physical strength"],
        "Matthew Tkachuk lite energy",
        "Top-6 agitator scorer 50+ pts ceiling",
        "Undersized variance play.",
    ),
    "Oliver Suvanto": _p(
        6.5, 6.8, 7.5, 6.0, 8.5, 7.0, 8.0, 3.5,
        "C finlandais two-way. CONSENSUS top-20 — APEX: floor pick, plafond bas.",
        ["Two-way", "Pro experience", "Defensive reliability"],
        ["Offense limited", "No star tools", "Low variance"],
        "Valtteri Filppula",
        "3C two-way, 25-35 pts",
        "⚠️ CONSENSUS OVER-RATE: #26→#45 APEX. Éviter pour upside draft.",
    ),
    "Markus Ruck": _p(
        7.5, 8.0, 7.5, 8.5, 8.0, 7.0, 6.0, 5.0,
        "Playmaker jumeau. Vision élite, playoffs weak, séparation des twins difficile.",
        ["Playmaking", "Brother chemistry", "Work ethic", "Vision"],
        ["Playoffs fade", "Skating", "Twin draft complexity"],
        "Henrik Sedin lite (playmaker)",
        "Top-6 setup man 50-65 pts",
        "Sous Liam pour upside scoring.",
    ),
    "Jack Hextall": _p(
        7.8, 8.0, 8.0, 7.5, 8.5, 8.0, 7.0, 5.5,
        "C USHL motor éternel. Utility élevé, setup > finish.",
        ["Motor", "Versatility", "IQ", "Two-way"],
        ["Ceiling limited", "Not dynamic"],
        "Ryan O'Reilly lite utility",
        "3C utility, 35-45 pts",
        "Floor > ceiling.",
    ),
    "Nikita Shcherbakov": _p(
        6.5, 7.8, 7.0, 6.0, 7.5, 7.5, 9.0, 5.0,
        "6'5 D VHL. Shutdown projection, mobile for size.",
        ["Size", "Defensive reliability", "Mobility for size"],
        ["Offense limited", "IQ average"],
        "Zdeno Chara lite defensive",
        "3rd pair shutdown",
        "Low upside D.",
    ),
    "Filip Růžička": _p(
        7.0, 8.5, 7.5, 5.0, 8.0, 9.0, 9.5, 7.0,
        "G 6'7 WHL. Plus grand gardien du draft, prise du poste #1 rapidement.",
        ["Size unique", "Calme", "Positionnement", "Trajectoire WHL"],
        ["Mobilité latérale", "Rebounds", "Deep goalie class"],
        "Ben Bishop / Stuart Skinner",
        "Starter NHL si dev suit",
        "Upside gardien #1 de la classe — APEX G #1.",
    ),
    "Vertti Svensk": _p(
        8.5, 9.0, 8.5, 8.0, 6.5, 8.0, 5.5, 9.5,
        "D/wing Finlande boom-bust. Skill fascinant, D-zone chaos.",
        ["Skill", "Offensive flash", "Shot volume", "Versatility tried"],
        ["Defensive chaos", "Consistency", "IQ D-zone"],
        "Brent Burns offensive mode only",
        "PP weapon ou AHL",
        "Internet favorite — APEX reward variance #86→#35.",
    ),
    "Axel Elofsson": _p(
        8.8, 9.2, 7.5, 8.5, 8.0, 8.5, 4.5, 9.0,
        "D suédois puck-moving. Hutson-lite offense, size concern.",
        ["Puck moving", "PP potential", "Offensive numbers", "Hands"],
        ["Size", "Defense", "Giveaways"],
        "Erik Karlsson lite (offense)",
        "PP1 D si defense OK",
        "Consensus #60 → APEX top-40: offensive D upside.",
    ),
    "Braidy Wassilyn": _p(
        9.0, 8.8, 8.0, 8.5, 7.5, 7.5, 6.0, 8.0,
        "Skill forward London. Puck control top de classe, consistency issues.",
        ["Puck control élite", "Clutch gene", "Offensive hands", "Compete"],
        ["Consistency", "Two-way", "Size"],
        "Patrick Kane lite skill",
        "Top-6 skill winger boom/bust",
        "Skill > consensus #80.",
    ),
    "Matias Vanhanen": _p(
        8.0, 8.2, 7.0, 9.0, 9.0, 8.5, 4.5, 6.0,
        "Playmaker WHL élite. Vision top, pas de physique, setup artist.",
        ["Playmaking", "Vision", "PP setup", "Heads-up"],
        ["Physicality", "Skating top-end", "Goal scoring"],
        "Marcus Pettersson setup / Joe Thornton lite",
        "Playmaker top-6 60+ assists ceiling",
        "Creation > finisher upside.",
    ),
    "Victor Plante": _p(
        8.5, 8.5, 8.0, 8.0, 9.5, 8.0, 4.0, 7.5,
        "5'9 USNTDP IQ monster. Brothers NCAA stars, processing élite.",
        ["IQ élite", "Processing", "Two-way detail", "Family skill"],
        ["Size", "No elite tool", "Jack-of-all"],
        "Theo Walman IQ / Tyler Johnson",
        "Middle-6 IQ driver",
        "IQ high, physical upside capped.",
    ),
    "Giorgos Pantelas": _p(
        8.0, 8.5, 8.5, 7.5, 7.5, 7.5, 7.5, 7.5,
        "D WHL mobile. Confidence, transition, fin de saison plate.",
        ["Skating", "Confidence", "Transition", "Work rate"],
        ["Fin de saison fade", "Consistency"],
        "Sam Girard lite",
        "Top-4 mobile D",
        "Solid mid-round upside.",
    ),
    "Pierce Mbuyi": _p(
        8.0, 8.5, 8.5, 7.5, 7.5, 8.5, 4.5, 8.5,
        "Small OHL skill. Penn State, breakaway artist, growing frame.",
        ["Skill", "1v1", "Offensive creativity", "Growth"],
        ["Size still", "Consistency", "Defensive"],
        "Kirill Kaprizov lite size",
        "Skill top-6 si bulk ajouté",
        "Undersized variance riser.",
    ),
    "Niklas Aaram-Olsen": _p(
        8.0, 8.2, 7.5, 7.0, 7.0, 7.5, 6.0, 7.0,
        "Pure goal scorer Norvège. PP one-timer, international dominance age group.",
        ["Shot", "PP", "Goal scoring", "International"],
        ["5v5 vs men", "Complete game", "Pace"],
        "Anders Lee lite finisher",
        "25-30 goal specialist",
        "Finisher not creator.",
    ),
    "Malte Gustafsson": _p(
        7.0, 8.0, 8.0, 6.5, 8.0, 7.5, 9.0, 5.5,
        "6'4 D SHL. Mobile big, competitive, offense flash late.",
        ["Size + skate", "Compete", "Reach", "Pro experience"],
        ["Offense ceiling", "Puck moving consistency"],
        "Victor Hedman lite (very lite)",
        "Top-4 defensive D",
        "Frame > skill pour upside.",
    ),
    "Adam Goljer": _p(
        7.5, 8.8, 7.5, 7.0, 7.5, 8.5, 8.0, 8.0,
        "D slovaque raw. 17 ans vs pros 20 min/night, confidence high.",
        ["Pro experience", "Size", "Confidence", "Physicality"],
        ["Raw reads", "Foot speed", "Mistakes"],
        "Radko Gudas with offense upside",
        "Top-4 physical D if refines",
        "Raw tools riser.",
    ),
    "Lavr Gashilov": _p(
        8.0, 8.2, 8.5, 8.5, 7.5, 8.0, 7.5, 6.5,
        "MHL leading scorer. Speed, playmaking, avoids physicality.",
        ["Speed", "Playmaking", "MHL dominance", "Puck skill"],
        ["Physical avoidance", "Shot", "Defensive"],
        "Artemi Panarin lite skill",
        "Top-6 skill if physicality comes",
        "Skill upside MHL.",
    ),
    "Joe Iginla": _p(
        6.5, 5.5, 7.0, 5.0, 5.5, 5.0, 5.5, 6.0,
        "Fils de Jarome. Bon tir mais production WHL insuffisante (31/59).",
        ["Shot hérité", "Name recognition", "Work ethic"],
        ["Production", "Impact 5v5", "Size", "Translatable offense"],
        "AHL shooter / sentimental pick",
        "Probable non-NHL ou 4e ligne",
        "APEX pénalise sévèrement: narrative > skill. #185 consensus → bottom APEX.",
    ),
}

# Ajustements APEX vs consensus (nom normalisé → bonus/malus sur heuristique)
APEX_ADJUSTMENTS: dict[str, float] = {
    "viggo bjorck": +2.8, "viggo björck": +2.8,
    "ethan belchetz": +2.5, "carson carels": +2.0, "ryan lin": +2.2,
    "oscar hemming": +1.8, "xavier villeneuve": +2.5, "wyatt cullen": +2.0,
    "tommy bleyl": +2.5, "axel elofsson": +1.5, "vertti svensk": +2.0,
    "braidy wassilyn": +1.8, "pierce mbuyi": +1.5, "adam goljer": +1.2,
    "nikita klepov": +1.0, "adam valentini": +1.0,
    "caleb malhotra": -2.5, "oliver suvanto": -2.2, "alexander command": -1.8,
    "jack hex tall": -1.0, "casey mutryn": -1.5, "olivers murnieks": -1.2,
    "ivar stenberg": -1.0,  # floor not upside
    "markus ruck": -0.8, "liam ruck": -0.5,
    "keaton verhoeff": -0.5, "joe iginla": -3.0,
    "simas ignatavicius": +1.5,  # if in list
}


def parse_height(h: str) -> float:
    if h in ("NA", "", None):
        return 72.0
    m = re.match(r"(\d)'(\d+)", h)
    if m:
        return int(m.group(1)) * 12 + int(m.group(2))
    return 72.0


def parse_weight(w: str) -> int:
    if w in ("NA", "", None):
        return 180
    try:
        return int(w)
    except ValueError:
        return 180


def compute_frame_score(height: str, weight: str) -> float:
    h = parse_height(height)
    w = parse_weight(weight)
    # Projectable frame: room to grow + NHL size
    h_s = min(10, max(3, (h - 66) / 5.5))
    w_s = min(10, max(3, (w - 145) / 85 * 10))
    # Young light frame with height = projection upside
    proj = 7.0 if h >= 74 and w < 195 else 5.5
    return round(min(10, h_s * 0.45 + w_s * 0.35 + proj * 0.2), 1)


def apex_overall(scores: dict) -> float:
    total = sum(scores.get(k, 5.0) * w * 10 for k, w in APEX_WEIGHTS.items())
    return round(total, 2)


def _normalize(name: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.strip().lower()


def _tier_apex(score: float) -> str:
    if score >= 88:
        return "Upside Élite"
    if score >= 75:
        return "Upside 1er tour"
    if score >= 62:
        return "Upside 2e-3e tour"
    if score >= 48:
        return "Upside milieu"
    return "Upside limité"


def apex_generate(
    full_name: str,
    pos: str,
    height: str,
    weight: str,
    country: str,
    consensus_rank: int | None,
) -> dict:
    """Génère profil APEX complet pour un joueur."""
    key = _normalize(full_name)
    is_g = pos.upper() in ("G", "GK")
    is_d = "D" in pos.upper() or pos.upper() == "D"
    is_w = pos.upper() in ("LW", "RW", "W")

    if full_name in APEX_PROFILES:
        profile = dict(APEX_PROFILES[full_name])
        profile.pop("frame_projectable", None)
        cr = consensus_rank or "N/A"
        if isinstance(cr, int):
            profile["consensus_delta"] = f"Consensus ~#{cr}. {profile.get('upside_thesis', '')}"
        profile["rationales"] = build_rationales(
            profile, full_name=full_name, pos=pos, height=height, weight=weight,
            country=country, consensus_rank=consensus_rank,
        )
        return profile

    frame = compute_frame_score(height, weight)
    adj = APEX_ADJUSTMENTS.get(key, 0.0)
    for k, v in APEX_ADJUSTMENTS.items():
        if k in key:
            adj = max(adj, v) if v > 0 else min(adj, v)

    # Prior de plafond depuis consensus (inversé: on réduit l'ancrage consensus)
    if consensus_rank:
        ceiling_prior = max(4.0, 9.8 - (consensus_rank - 1) * 0.035)
        traj_prior = max(4.0, 8.5 - (consensus_rank - 1) * 0.025)
    else:
        ceiling_prior = 4.5 + frame * 0.25
        traj_prior = 5.0

    ceiling_prior = min(10, ceiling_prior + adj * 0.35)
    jitter = ((hash(key) % 7) - 3) * 0.08

    # Heuristique upside
    variance = 5.5
    if frame >= 8 and ceiling_prior >= 7:
        variance += 1.2  # big + skilled
    if parse_height(height) <= 70 and ceiling_prior >= 7.5:
        variance += 1.5  # small skilled = boom/bust
    if is_w and country in ("RUS", "KAZ", "BLR"):
        variance += 0.8
    if consensus_rank and consensus_rank > 100:
        variance += 0.5
    if pos.upper() == "C" and parse_weight(weight) < 170:
        variance += 0.4
    # Safe types penalty
    if is_g:
        variance = max(4, variance - 1)

    if is_g:
        scores = {
            "outils_offensifs": round(min(10, ceiling_prior - 1), 1),
            "plafond_elite": round(min(10, ceiling_prior + 0.5), 1),
            "patinage_upside": round(min(10, ceiling_prior - 0.5), 1),
            "creation_jeu": 5.0,
            "iq_realisation": round(min(10, ceiling_prior), 1),
            "trajectoire": round(min(10, traj_prior + 0.5), 1),
            "variance_positive": round(min(10, variance), 1),
        }
    else:
        scores = {
            "outils_offensifs": round(min(10, max(3, ceiling_prior + jitter + (0.3 if is_w else 0))), 1),
            "plafond_elite": round(min(10, max(3, ceiling_prior + adj * 0.15)), 1),
            "patinage_upside": round(min(10, max(3, ceiling_prior - 0.3 + jitter + (0.4 if is_d else 0))), 1),
            "creation_jeu": round(min(10, max(3, ceiling_prior - 0.2 + (0.5 if is_w else 0))), 1),
            "iq_realisation": round(min(10, max(3, ceiling_prior - 0.5)), 1),
            "trajectoire": round(min(10, max(3, traj_prior + jitter)), 1),
            "variance_positive": round(min(10, max(3, variance)), 1),
        }

    overall = apex_overall(scores)
    tier = _tier_apex(overall)
    cr_txt = f"#{consensus_rank}" if consensus_rank else "hors top-100 public"

    scores["resume"] = (
        f"{full_name} ({pos}, {height}, {weight} lbs). "
        f"Évaluation APEX orientée plafond. Consensus public: {cr_txt}. "
        f"Score upside {overall}/100 — tier {tier}."
    )
    scores["forces"] = [
        f"Plafond élite APEX: {scores['plafond_elite']}/10",
        f"Patinage upside: {scores['patinage_upside']}/10",
        f"Variance (boom): {scores['variance_positive']}/10",
    ]
    scores["faiblesses"] = [
        "Profil heuristique — valider au combine",
        "Données publiques limitées vs top prospects",
    ]
    scores["comparable"] = "À affiner via vidéo/combine"
    scores["projection"] = f"{tier} — sélection APEX upside"
    scores["upside_thesis"] = (
        f"Heuristique APEX: plafond priorisé sur floor. "
        f"Ajustement vs consensus: {adj:+.1f}."
    )
    scores["consensus_delta"] = f"Consensus {cr_txt} · APEX {overall}/100"
    scores["rationales"] = build_rationales(
        scores, full_name=full_name, pos=pos, height=height, weight=weight,
        country=country, consensus_rank=consensus_rank, adj=adj,
    )
    return scores
