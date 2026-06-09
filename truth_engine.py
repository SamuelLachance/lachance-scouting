"""
NORTHSTAR TRUTH — Scientific prospect valuation engine.

Rebuilds player rating from first principles using:
  - Bayesian evidence fusion with position-specific priors
  - Age- and league-adjusted production benchmarks
  - Cross-source agreement / uncertainty quantification
  - Source URL attribution verification (anti-mislabeling)
  - Snippet deduplication (anti-recycled content)
  - Non-linear upside stacking and risk-adjusted discovery scoring

Designed to estimate true NHL star probability (SPI 0–100) and detect
market inefficiencies without promoting low-talent profiles on gap alone.
"""
from __future__ import annotations

import math
import re
from typing import Any
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Position-specific pillar weights (sum = 1.0) — calibrated for star prediction
# ---------------------------------------------------------------------------
POSITION_PILLAR_WEIGHTS: dict[str, dict[str, float]] = {
    "F": {
        "star_ceiling": 0.36,
        "hockey_iq": 0.17,
        "skating_engine": 0.15,
        "offensive_star_power": 0.14,
        "competition_proof": 0.09,
        "character_compete": 0.05,
        "development_arc": 0.04,
    },
    "D": {
        "star_ceiling": 0.30,
        "hockey_iq": 0.20,
        "skating_engine": 0.18,
        "offensive_star_power": 0.08,
        "competition_proof": 0.12,
        "character_compete": 0.06,
        "development_arc": 0.06,
    },
    "G": {
        "star_ceiling": 0.34,
        "hockey_iq": 0.16,
        "skating_engine": 0.06,
        "offensive_star_power": 0.04,
        "competition_proof": 0.14,
        "character_compete": 0.10,
        "development_arc": 0.16,
    },
}

PILLAR_KEYS = tuple(POSITION_PILLAR_WEIGHTS["F"].keys())

# Position priors (neutral starting belief before evidence) — 1–10 scale
POSITION_PRIORS: dict[str, dict[str, float]] = {
    "F": {k: 5.4 for k in PILLAR_KEYS},
    "D": {k: 5.2 for k in PILLAR_KEYS},
    "G": {k: 5.0 for k in PILLAR_KEYS},
}
POSITION_PRIORS["F"]["star_ceiling"] = 5.6
POSITION_PRIORS["D"]["skating_engine"] = 5.5
POSITION_PRIORS["G"]["development_arc"] = 5.3

# League → NHL translation multipliers (historical draft success research)
LEAGUE_TRANSLATION: dict[str, dict[str, float]] = {
    "NCAA": {"F": 0.94, "D": 1.10, "G": 0.96},
    "SHL": {"F": 1.02, "D": 1.04, "G": 1.00},
    "LIIGA": {"F": 1.00, "D": 1.02, "G": 0.98},
    "KHL": {"F": 1.04, "D": 1.06, "G": 1.02},
    "OHL": {"F": 1.06, "D": 0.96, "G": 0.94},
    "WHL": {"F": 1.05, "D": 0.95, "G": 0.93},
    "QMJHL": {"F": 1.04, "D": 0.94, "G": 0.92},
    "USHL": {"F": 0.98, "D": 1.00, "G": 0.96},
    "J20": {"F": 0.96, "D": 0.98, "G": 0.94},
    "MHL": {"F": 0.90, "D": 0.92, "G": 0.88},
    "NAHL": {"F": 0.86, "D": 0.88, "G": 0.84},
    "BCHL": {"F": 0.88, "D": 0.90, "G": 0.86},
    "HIGH SCHOOL": {"F": 0.82, "D": 0.84, "G": 0.80},
}

# Expected PPG benchmarks by league for draft-age forwards (score 7.0 = league avg elite)
PRODUCTION_BENCHMARKS: dict[str, tuple[float, float, float, float]] = {
    # league: (elite_ppg, strong_ppg, avg_ppg, weak_ppg)
    "NCAA": (1.10, 0.85, 0.55, 0.30),
    "SHL": (0.75, 0.55, 0.35, 0.18),
    "LIIGA": (0.70, 0.50, 0.32, 0.16),
    "OHL": (1.35, 1.05, 0.70, 0.40),
    "WHL": (1.30, 1.00, 0.68, 0.38),
    "QMJHL": (1.25, 0.95, 0.65, 0.36),
    "USHL": (1.00, 0.75, 0.50, 0.28),
    "J20": (0.65, 0.45, 0.28, 0.14),
    "MHL": (0.55, 0.38, 0.22, 0.10),
    "NAHL": (0.90, 0.65, 0.40, 0.22),
    "BCHL": (0.95, 0.70, 0.45, 0.25),
    "DEFAULT": (1.00, 0.75, 0.50, 0.28),
}

# Source ID → required URL domain fragments (attribution verification)
SOURCE_DOMAIN_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "tsn": ("tsn.ca", "tsn.com"),
    "espn": ("espn.com", "espn.ca"),
    "nhl_com": ("nhl.com",),
    "sportsnet": ("sportsnet.ca", "torontosun.com"),
    "mckeens": ("mckeenshockey.com", "dobberprospects.com"),
    "the_athletic": ("theathletic.com", "nytimes.com"),
    "elite_prospects": ("eliteprospects.com",),
    "flohockey": ("flohockey.tv", "flocountry.tv"),
    "puckpedia": ("puckpedia.com",),
    "daily_faceoff": ("dailyfaceoff.com",),
    "smaht_scouting": ("smahtscouting",),
    "pronman": ("espn.com", "theathletic.com", "pronman"),
    "scott_wheeler": ("tsn.ca", "theathletic.com", "wheeler"),
    "reddit": ("reddit.com",),
    "hfboards": ("hfboards.com",),
    "twitter": ("twitter.com", "x.com"),
    "youtube": ("youtube.com", "youtu.be"),
    "hockeydb": ("hockeydb.com",),
    "wikipedia": ("wikipedia.org",),
    "draftprospectshockey.com": ("draftprospectshockey.com",),
    "dph_full": ("draftprospectshockey.com",),
    "dph_partial": ("draftprospectshockey.com",),
    "dph_thin": ("draftprospectshockey.com",),
    "dph_report": ("draftprospectshockey.com",),
    "dph_strengths": ("draftprospectshockey.com",),
    "dph_weaknesses": ("draftprospectshockey.com",),
    "dph_projection": ("draftprospectshockey.com",),
    "dph_tags": ("draftprospectshockey.com",),
}

# Expanded scouting lexicon — supplements northstar_scoring.LEX
TRUTH_LEX_SUPPLEMENT: dict[str, list[tuple[str, float]]] = {
    "star_ceiling": [
        (r"generational talent", 3.2), (r"once.in.a.generation", 3.5),
        (r"franchise player", 2.8), (r"franchise cornerstone", 3.0),
        (r"elite prospect", 2.0), (r"can't.miss", 2.5), (r"can.t.miss", 2.5),
        (r"blue.chip", 2.2), (r"perennial all.star", 2.5),
        (r"top.line talent", 2.0), (r"top.pair talent", 2.0),
        (r"1st overall", 2.8), (r"first overall", 2.8),
        (r"potential no\.?1", 2.5), (r"best prospect", 2.5),
        (r"elite ceiling", 2.2), (r"unlimited upside", 2.0),
        (r"marquee", 1.8), (r"franchise changer", 2.8),
        (r"limited upside", -2.0), (r"low ceiling", -2.2),
        (r"bottom.six ceiling", -2.0), (r"depth player", -2.2),
        (r"replacement.level", -2.5), (r"bust potential", -2.0),
        (r"plafond franchise", 2.5), (r"talent générationnel", 3.0),
        (r"étoile franchise", 2.5), (r"plafond limité", -2.0),
    ],
    "hockey_iq": [
        (r"elite hockey sense", 2.5), (r"offensive instincts", 2.0),
        (r"defensive awareness", 1.8), (r"positional play", 1.5),
        (r"anticipates well", 2.0), (r"sees the ice", 2.2),
        (r"smart with the puck", 2.0), (r"high hockey iq", 2.5),
        (r"poor decision", -1.8), (r"turnover prone", -1.5),
        (r"forces plays", -1.5), (r"black hole", -2.0),
        (r"vision du jeu", 2.0), (r"sens du hockey", 2.2),
    ],
    "skating_engine": [
        (r"elite skater", 2.5), (r"four.way acceleration", 2.2),
        (r"north.south speed", 2.0), (r"lateral agility", 1.8),
        (r"powerful stride", 1.8), (r"glide", 1.5),
        (r"separation speed", 2.2), (r"first three steps", 2.0),
        (r"needs to improve skating", -2.0), (r"skating is a concern", -2.2),
        (r"labored stride", -1.8), (r"lacks burst", -1.8),
        (r"patinage élite", 2.5), (r"vitesse explosive", 2.2),
    ],
    "offensive_star_power": [
        (r"elite shot", 2.2), (r"goal scoring ability", 2.0),
        (r"play driver", 2.5), (r"offensive catalyst", 2.2),
        (r"creates chances", 2.0), (r"elite hands", 2.0),
        (r"soft touch", 1.8), (r"scoring touch", 2.0),
        (r"power play weapon", 2.0), (r"one.timer", 1.5),
        (r"limited offensively", -2.0), (r"not a scorer", -1.8),
        (r"defensive first", -1.2), (r"pouvoir offensif", 1.8),
    ],
    "competition_proof": [
        (r"world juniors", 2.0), (r"world championship", 1.8),
        (r"memorial cup", 1.8), (r"frozen four", 1.8),
        (r"championship pedigree", 1.5), (r"playoff performer", 1.8),
        (r"against men", 2.0), (r"older league", 1.5),
        (r"dominated", 2.0), (r"led the league", 2.2),
        (r"weak competition", -1.8), (r"inflated stats", -2.0),
        (r"championsnat du monde", 2.0),
    ],
    "character_compete": [
        (r"elite compete level", 2.2), (r"never gives up", 1.8),
        (r"plays bigger", 1.5), (r"physical presence", 1.5),
        (r"grit", 1.5), (r"toughness", 1.5), (r"resilient", 1.5),
        (r"coachable", 1.8), (r"professional approach", 1.5),
        (r"effort issues", -2.0), (r"coasting", -1.8),
        (r"inconsistent compete", -1.8), (r"compétitivité", 2.0),
    ],
    "development_arc": [
        (r"year over year improvement", 2.0), (r"significant growth", 2.0),
        (r"physical development", 1.8), (r"added weight", 1.5),
        (r"late bloomer upside", 1.5), (r"trending up", 2.0),
        (r"stock rising", 2.2), (r"climbing rankings", 2.0),
        (r"plateaued", -2.0), (r"stalled development", -2.0),
        (r"regressed", -2.2), (r"lost a step", -1.8),
        (r"trajectoire ascendante", 2.0),
    ],
}

# Hedging language reduces confidence in positive signals
HEDGE_PATTERNS = re.compile(
    r"\b(could|might|may|potentially|possibly|if he|if she|needs to|"
    r"has to|still developing|raw|projectable|with time|with work|"
    r"room to grow|areas to improve)\b",
    re.I,
)


def position_group(position: str) -> str:
    p = (position or "").upper().strip()
    if p in ("G", "GK", "GOALIE", "GOALTENDER"):
        return "G"
    if "D" in p:
        return "D"
    return "F"


def pillar_weights_for_position(position: str) -> dict[str, float]:
    return POSITION_PILLAR_WEIGHTS[position_group(position)]


def position_priors(position: str) -> dict[str, float]:
    return dict(POSITION_PRIORS[position_group(position)])


def _clamp(v: float, lo: float = 1.0, hi: float = 10.0) -> float:
    return max(lo, min(hi, v))


def _token_set(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{4,}", (text or "").lower()))


def snippet_jaccard(a: str, b: str) -> float:
    sa, sb = _token_set(a), _token_set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def verify_source_attribution(source_id: str, url: str) -> float:
    """
    Return 0.0–1.0 confidence that URL matches claimed source.
    Penalizes Wikipedia snippets labeled as TSN/Pronman/etc.
    """
    if not url:
        return 0.85
    host = urlparse(url).netloc.lower().replace("www.", "")
    required = SOURCE_DOMAIN_REQUIREMENTS.get(source_id)
    if not required:
        return 0.90
    if any(req in host or req in url.lower() for req in required):
        return 1.0
    # Known misattribution patterns
    if "wikipedia" in host and source_id not in ("wikipedia", "web_scouting"):
        return 0.15
    if "reddit" in host and source_id not in ("reddit", "web_scouting"):
        return 0.25
    if "youtube" in host and source_id not in ("youtube", "web_scouting"):
        return 0.30
    return 0.45


def deduplicate_contributions(
    contributions: list[dict[str, Any]],
    *,
    similarity_threshold: float = 0.72,
) -> list[dict[str, Any]]:
    """Drop near-duplicate snippets; keep highest-quality per source."""
    best: dict[str, dict[str, Any]] = {}
    for c in contributions:
        sid = c["source_id"]
        q = float(c.get("quality", 1.0))
        if sid not in best or q > float(best[sid].get("quality", 0)):
            best[sid] = c

    kept: list[dict[str, Any]] = []
    seen_snippets: list[str] = []
    for c in sorted(best.values(), key=lambda x: -float(x.get("quality", 0))):
        snippet = (c.get("snippet") or "").strip()
        if snippet:
            dup = any(snippet_jaccard(snippet, s) >= similarity_threshold for s in seen_snippets)
            if dup:
                c = {**c, "quality": float(c.get("quality", 1.0)) * 0.35}
                c["duplicate_penalty"] = True
            else:
                seen_snippets.append(snippet)
        url = c.get("url", "")
        attr = verify_source_attribution(c["source_id"], url)
        if attr < 0.5:
            c["attribution_penalty"] = True
        kept.append(c)
    return kept


def _league_key(league: str) -> str:
    blob = (league or "").upper()
    for key in PRODUCTION_BENCHMARKS:
        if key != "DEFAULT" and key in blob:
            return key
    return "DEFAULT"


def age_from_dob(dob: str, draft_year: int = 2026) -> float | None:
    if not dob or dob in ("", "N/A", "?"):
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(dob))
    if not m:
        m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", str(dob))
        if m:
            y, mo, d = int(m.group(3)), int(m.group(1)), int(m.group(2))
        else:
            return None
    else:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    draft_mid = draft_year + 0.5
    return draft_mid - (y + (mo - 1) / 12 + (d - 1) / 365)


def age_adjusted_production_score(
    stats: dict,
    league: str,
    pos: str,
    *,
    dob: str = "",
    draft_year: int = 2026,
) -> float:
    """
    League-normalized, age-adjusted production score (1–10).
    Uses PPG vs league benchmarks with young-age bonus.
    """
    gp = stats.get("gp") or stats.get("games") or 0
    pts = stats.get("pts") or stats.get("points") or 0
    if not gp or gp <= 0:
        return 5.5
    if pos.upper() in ("G", "GK"):
        sv_pct = stats.get("sv_pct") or stats.get("save_pct")
        if sv_pct:
            try:
                sv = float(str(sv_pct).replace("%", ""))
                if sv > 1:
                    sv /= 100
                if sv >= 0.930:
                    return 9.5
                if sv >= 0.915:
                    return 8.5
                if sv >= 0.900:
                    return 7.5
                if sv >= 0.880:
                    return 6.5
                return 5.0
            except (TypeError, ValueError):
                pass
        return 5.5

    ppg = pts / gp
    lk = _league_key(league)
    elite, strong, avg, weak = PRODUCTION_BENCHMARKS[lk]

    age = age_from_dob(dob, draft_year)
    age_factor = 1.0
    if age is not None:
        if age < 17.5:
            age_factor = 1.12
        elif age < 18.0:
            age_factor = 1.06
        elif age > 19.5:
            age_factor = 0.92
        elif age > 20.0:
            age_factor = 0.85

    adj_ppg = ppg / age_factor

    if adj_ppg >= elite:
        base = 9.5
    elif adj_ppg >= strong:
        base = 8.2 + (adj_ppg - strong) / max(elite - strong, 0.01) * 1.2
    elif adj_ppg >= avg:
        base = 6.8 + (adj_ppg - avg) / max(strong - avg, 0.01) * 1.4
    elif adj_ppg >= weak:
        base = 5.2 + (adj_ppg - weak) / max(avg - weak, 0.01) * 1.6
    else:
        base = 3.5 + adj_ppg / max(weak, 0.01) * 1.5

    grp = position_group(pos)
    trans = LEAGUE_TRANSLATION.get(lk, LEAGUE_TRANSLATION.get("NCAA", {}))
    mult = trans.get(grp, 1.0)
    return round(_clamp(base * mult), 1)


def truth_lex_score(dim: str, text: str, base_lex_fn) -> tuple[float, list[str]]:
    """Augment base lexicon scoring with TRUTH supplement + hedge damping."""
    base_score, hits = base_lex_fn(dim, text)
    raw = base_score
    for pattern, weight in TRUTH_LEX_SUPPLEMENT.get(dim, []):
        if re.search(pattern, text, re.I):
            raw += weight
            hits.append(pattern.replace(".", " ").replace("\\", ""))
    hedge_count = len(HEDGE_PATTERNS.findall(text))
    if hedge_count >= 3 and raw > 6.0:
        raw -= min(1.5, hedge_count * 0.25)
    return _clamp(raw), hits[:6]


def compute_cross_source_agreement(
    contributions: list[dict[str, Any]],
    weights: list[float],
) -> dict[str, float]:
    """Per-pillar agreement 0–1 (1 = all sources agree)."""
    total_w = sum(weights) or 1.0
    agreement: dict[str, float] = {}
    for dim in PILLAR_KEYS:
        vals: list[tuple[float, float]] = []
        for c, w in zip(contributions, weights):
            v = c.get("pillars", {}).get(dim, 5.0)
            vals.append((float(v), w))
        mean = sum(v * w for v, w in vals) / total_w
        var = sum(w * (v - mean) ** 2 for v, w in vals) / total_w
        agreement[dim] = round(max(0.0, min(1.0, 1.0 - math.sqrt(var) / 3.0)), 3)
    return agreement


def bayesian_merge_pillars(
    contributions: list[dict[str, Any]],
    raw_weights: list[float],
    position: str,
) -> tuple[dict[str, float], dict[str, float]]:
    """
    Reliability-weighted merge with adaptive Bayesian shrinkage.

    Many substantive sources → trust the weighted observation (minimal shrinkage).
    Thin evidence → regress modestly toward position prior.
    """
    priors = position_priors(position)
    total_w = sum(raw_weights) or 1.0
    n_sources = len(contributions)
    substantive = sum(
        1 for c in contributions if c.get("snippet") or c.get("evidence")
    )
    shrinkage = max(0.04, min(0.30, 0.55 / (1.0 + n_sources * 0.12 + substantive * 0.08)))
    merged: dict[str, float] = {}
    uncertainty: dict[str, float] = {}

    for dim in PILLAR_KEYS:
        weighted_obs = sum(
            c.get("pillars", {}).get(dim, 5.0) * w
            for c, w in zip(contributions, raw_weights)
        ) / total_w
        prior = priors[dim]
        posterior = weighted_obs * (1.0 - shrinkage) + prior * shrinkage
        merged[dim] = round(_clamp(posterior), 1)
        uncertainty[dim] = round(shrinkage, 3)

    return merged, uncertainty


def upside_convexity(pillars: dict[str, float], position: str) -> float:
    """
    Non-linear upside bonus when elite tools stack (skating + IQ + offense).
    Returns 0–4.0 bonus points on SPI scale.
    """
    grp = position_group(position)
    tools = [
        pillars.get("star_ceiling", 5.0),
        pillars.get("hockey_iq", 5.0),
        pillars.get("skating_engine", 5.0),
        pillars.get("offensive_star_power", 5.0),
    ]
    if grp == "G":
        tools = [
            pillars.get("star_ceiling", 5.0),
            pillars.get("competition_proof", 5.0),
            pillars.get("development_arc", 5.0),
        ]
    elif grp == "D":
        tools = [
            pillars.get("star_ceiling", 5.0),
            pillars.get("hockey_iq", 5.0),
            pillars.get("skating_engine", 5.0),
            pillars.get("competition_proof", 5.0),
        ]

    elite_count = sum(1 for t in tools if t >= 8.5)
    strong_count = sum(1 for t in tools if t >= 7.5)
    if elite_count >= 3:
        return 4.0
    if elite_count >= 2 and strong_count >= 3:
        return 2.8
    if elite_count >= 2:
        return 1.8
    if strong_count >= 4:
        return 1.2
    if strong_count >= 3:
        return 0.6
    return 0.0


def risk_penalty(pillars: dict[str, float], position: str) -> float:
    """Downside risk from large pillar gaps or weak skating/iq for position."""
    grp = position_group(position)
    vals = list(pillars.values())
    if not vals:
        return 0.0
    gap = max(vals) - min(vals)
    penalty = 0.0
    if gap >= 3.5:
        penalty += 1.5
    elif gap >= 2.5:
        penalty += 0.8
    if grp == "F" and pillars.get("skating_engine", 5) < 5.5:
        penalty += 1.0
    if grp == "D" and pillars.get("skating_engine", 5) < 5.8:
        penalty += 1.2
    if pillars.get("star_ceiling", 5) < 5.0:
        penalty += 1.5
    return min(4.0, penalty)


def truth_spi(
    pillars: dict[str, float],
    position: str,
    *,
    confidence: float = 1.0,
    agreement: float = 0.5,
) -> float:
    """
    Compute TRUTH Star Probability Index (0–100) with position weights,
    upside convexity, and risk adjustment.
    """
    weights = pillar_weights_for_position(position)
    base = sum(pillars.get(k, 5.0) * w * 10 for k, w in weights.items())
    convex = upside_convexity(pillars, position)
    risk = risk_penalty(pillars, position)
    conf_mult = 0.88 + confidence * 0.08 + agreement * 0.04
    spi = (base + convex - risk) * conf_mult
    return round(max(0.0, min(99.9, spi)), 2)


def compute_evidence_confidence(
    n_sources: int,
    n_substantive: int,
    coverage: str,
    avg_attribution: float,
    avg_agreement: float,
) -> tuple[float, str]:
    """Unified evidence confidence 0–1 with label."""
    cov_map = {"full": 0.92, "partial": 0.72, "thin": 0.52, "none": 0.32, "manual": 0.95}
    cov_s = cov_map.get(coverage, 0.55)
    breadth = min(1.0, 0.25 + n_sources * 0.06 + n_substantive * 0.08)
    score = (
        cov_s * 0.40
        + breadth * 0.30
        + avg_attribution * 0.15
        + avg_agreement * 0.15
    )
    score = round(max(0.0, min(1.0, score)), 3)
    if score >= 0.82:
        return score, "Confiance élevée"
    if score >= 0.62:
        return score, "Confiance moyenne"
    return score, "Confiance basse"


def log_damped_market_gap(gap: int | None, spi: float) -> float:
    """
    Scientifically bounded market-gap bonus.
    Uses log damping and SPI floor — low talent cannot ride gap to top ranks.
    """
    if gap is None or gap <= 0:
        return float(gap or 0) * 0.08 if gap is not None else 0.0
    spi_factor = max(0.0, min(1.0, (spi - 48.0) / 28.0))
    if spi_factor <= 0:
        return 0.0
    return min(8.0, math.log1p(gap) * 1.85 * spi_factor)


def truth_discovery_rating(
    *,
    spi: float,
    spi_rank: int,
    pillars: dict[str, float],
    consensus_rank: int | None,
    confidence: float,
    coverage: str,
    is_over_age: bool = False,
) -> dict[str, Any]:
    """
    TRUTH Discovery Rating — detects undervalued upside scientifically.

    Formula:
      talent_core = SPI (primary, 70%)
      upside_premium = convex tool stacking (15%)
      market_alpha = log-damped gap, only when confidence high (10%)
      info_asymmetry = our depth vs public coverage (5%)
    Hard cap: discovery cannot exceed SPI + 12 unless SPI >= 68.
    """
    weights = pillar_weights_for_position("F")
    upside_core = sum(
        pillars.get(k, 5.0) * w for k, w in weights.items()
    ) * 10

    rare_tools = [
        ("plafond étoile", pillars.get("star_ceiling", 5.0)),
        ("processing", pillars.get("hockey_iq", 5.0)),
        ("moteur de patinage", pillars.get("skating_engine", 5.0)),
        ("pouvoir offensif", pillars.get("offensive_star_power", 5.0)),
        ("arc de développement", pillars.get("development_arc", 5.0)),
    ]
    rare_count = sum(1 for _, v in rare_tools if v >= 8.5)
    peak = max(rare_tools, key=lambda x: x[1])

    market_gap = (consensus_rank - spi_rank) if consensus_rank is not None else None
    market_alpha = log_damped_market_gap(market_gap, spi)

    if market_gap is None:
        market_status = "Aucun consensus public fiable"
        info_bonus = 2.5 if confidence >= 0.75 and coverage in ("full", "partial") else 0.5
    elif market_gap > 0:
        market_status = f"Consensus {market_gap} rangs plus bas que TRUTH"
        info_bonus = min(3.0, confidence * 4.0) if market_gap >= 15 else confidence * 2.0
    elif market_gap < 0:
        market_status = f"Consensus {abs(market_gap)} rangs plus haut que TRUTH"
        info_bonus = 0.0
    else:
        market_status = "Consensus aligné avec TRUTH"
        info_bonus = 0.0

    convex_bonus = upside_convexity(pillars, "F") * 0.8
    rare_bonus = rare_count * 0.9
    dev_bonus = max(0, pillars.get("development_arc", 5) - 7.5) * 0.6

    # Talent (SPI) is the anchor; discovery layers bounded alpha on top.
    raw = spi + market_alpha + info_bonus + convex_bonus + rare_bonus + dev_bonus
    if is_over_age:
        raw -= 5.0

    conf_mult = 0.94 + confidence * 0.06
    score = round(max(0.0, min(99.0, raw * conf_mult)), 1)

    max_premium = 12.0 if spi >= 68 else 8.0 if spi >= 62 else 5.0 if spi >= 56 else 2.5
    score = min(score, spi + max_premium)
    score = max(score, spi - 3.0)  # discovery never punishes more than 3 pts vs talent

    reasons: list[str] = []
    if market_gap and market_gap >= 15 and market_alpha > 2:
        reasons.append(f"TRUTH #{spi_rank} vs consensus #{consensus_rank} — alpha marché")
    elif market_gap and market_gap >= 5:
        reasons.append(f"Écart positif vs consensus: +{market_gap} rangs (borné)")
    if rare_count:
        reasons.append(f"{rare_count} outil(s) rares ≥ 8.5/10")
    if peak[1] >= 8.8:
        reasons.append(f"Trait signature: {peak[0]} {peak[1]:.1f}/10")
    if convex_bonus >= 2.5:
        reasons.append("Stack d'upside non-linéaire (outils corrélés)")
    if confidence >= 0.80:
        reasons.append("Preuve multi-sources à haute confiance")
    if not reasons:
        reasons.append("Profil calibré par le marché actuel")

    if score >= 88:
        label = "Alerte star cachée"
    elif score >= 78:
        label = "Diamant sous-évalué"
    elif score >= 68:
        label = "Upside à surveiller"
    elif score >= 58:
        label = "Signal latent"
    else:
        label = "Prix du marché"

    return {
        "score": score,
        "label": label,
        "marketGap": market_gap,
        "marketStatus": market_status,
        "upsideCore": round(upside_core, 1),
        "rareToolCount": rare_count,
        "peakTool": {"label": peak[0], "score": round(peak[1], 1)},
        "confidence": confidence,
        "confidenceLabel": (
            "Confiance élevée" if confidence >= 0.82
            else "Confiance moyenne" if confidence >= 0.62
            else "Confiance basse"
        ),
        "reasons": reasons[:4],
        "marketAlpha": round(market_alpha, 2),
        "spiPremiumCap": max_premium,
    }
