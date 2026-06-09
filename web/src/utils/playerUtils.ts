import { DiscoverySignal, Player, PlayerSkills } from "../types/player";

export function tierColor(tier: string): string {
  switch (tier) {
    case "Élite":
      return "from-gold/20 to-amber-500/10 border-gold/40 text-gold";
    case "1er tour":
      return "from-ice-500/20 to-cyan-500/10 border-ice-400/30 text-ice-300";
    case "2e-3e tour":
      return "from-emerald-500/15 to-green-500/5 border-emerald-500/25 text-emerald-300";
    case "Milieu":
      return "from-slate-500/15 to-slate-600/5 border-slate-500/25 text-slate-300";
    default:
      return "from-zinc-600/15 to-zinc-700/5 border-zinc-600/25 text-zinc-400";
  }
}

export function scoreColor(score: number): string {
  if (score >= 90) return "text-gold";
  if (score >= 75) return "text-ice-300";
  if (score >= 60) return "text-emerald-400";
  if (score >= 45) return "text-slate-300";
  return "text-zinc-500";
}

export function positionColor(pos: string): string {
  const p = pos.toUpperCase();
  if (p === "G") return "bg-amber-500/20 text-amber-300 border-amber-500/30";
  if (p.includes("D")) return "bg-blue-500/20 text-blue-300 border-blue-500/30";
  if (p === "C") return "bg-purple-500/20 text-purple-300 border-purple-500/30";
  return "bg-rose-500/20 text-rose-300 border-rose-500/30";
}

export function discoveryColor(score: number): string {
  if (score >= 85) return "text-fuchsia-300 border-fuchsia-400/30 bg-fuchsia-500/10";
  if (score >= 75) return "text-gold border-gold/30 bg-gold/10";
  if (score >= 65) return "text-ice-300 border-ice-400/30 bg-ice-500/10";
  if (score >= 55) return "text-emerald-300 border-emerald-400/30 bg-emerald-500/10";
  return "text-slate-400 border-slate-500/25 bg-slate-500/10";
}

export function getDiscoverySignal(player: Player): DiscoverySignal {
  if (player.discoverySignal) return player.discoverySignal;

  const skills = player.skills;
  const upsideCore =
    (skills.starCeiling ?? 5) * 3 +
    (skills.hockeyIQ ?? 5) * 1.8 +
    (skills.skatingEngine ?? 5) * 1.6 +
    (skills.offensiveStarPower ?? 5) * 1.6 +
    (skills.developmentArc ?? 5) * 1.2 +
    (skills.competitionProof ?? 5) * 0.8;
  const marketGap = player.consensusRank == null ? null : player.consensusRank - player.rank;
  const marketBoost = marketGap == null ? 8 : Math.max(-10, Math.min(22, marketGap * 0.45));
  const rareToolCount = Object.values(skills).filter((value) => value >= 8.5).length;
  const peakTool = Object.entries(skills).reduce(
    (best, [label, score]) => (score > best.score ? { label, score } : best),
    { label: "profil", score: 0 }
  );
  const score = Math.max(
    0,
    Math.min(99, player.overall * 0.42 + upsideCore * 0.34 + marketBoost + rareToolCount * 2)
  );

  return {
    score: Number(score.toFixed(1)),
    label: score >= 75 ? "Diamant sous-évalué" : score >= 65 ? "Upside à surveiller" : "Signal latent",
    marketGap,
    marketStatus:
      marketGap == null
        ? "Aucun consensus public fiable"
        : marketGap > 0
          ? `Consensus ${marketGap} rangs plus bas que NORTHSTAR`
          : marketGap < 0
            ? `Consensus ${Math.abs(marketGap)} rangs plus haut que NORTHSTAR`
            : "Consensus aligné avec NORTHSTAR",
    upsideCore: Number(upsideCore.toFixed(1)),
    rareToolCount,
    peakTool,
    confidence: 0.5,
    confidenceLabel: "Confiance moyenne",
    reasons: ["Signal généré côté interface en attente des données Discovery."],
  };
}

export function skillsToRadar(skills: PlayerSkills) {
  return [
    { skill: "Plafond", value: skills.starCeiling, fullMark: 10 },
    { skill: "IQ", value: skills.hockeyIQ, fullMark: 10 },
    { skill: "Patinage", value: skills.skatingEngine, fullMark: 10 },
    { skill: "Offensif", value: skills.offensiveStarPower, fullMark: 10 },
    { skill: "Preuve", value: skills.competitionProof, fullMark: 10 },
    { skill: "Compete", value: skills.characterCompete, fullMark: 10 },
    { skill: "Arc", value: skills.developmentArc, fullMark: 10 },
  ];
}

export function filterPlayers(
  players: Player[],
  query: string,
  position: string,
  country: string,
  tier: string,
  minScore: number,
  minDiscovery = 0,
  hiddenOnly = false
): Player[] {
  const q = query.toLowerCase().trim();
  return players.filter((p) => {
    const discovery = getDiscoverySignal(p);
    if (q && !p.name.toLowerCase().includes(q)) return false;
    if (position !== "ALL" && p.position !== position) return false;
    if (country !== "ALL" && p.country !== country) return false;
    if (tier !== "ALL" && p.tier !== tier) return false;
    if (p.overall < minScore) return false;
    if (discovery.score < minDiscovery) return false;
    if (hiddenOnly && !(discovery.marketGap === null || discovery.marketGap >= 8)) return false;
    return true;
  });
}

export function getStats(players: Player[]) {
  if (!players.length) {
    return {
      total: 0,
      elite: 0,
      firstRound: 0,
      avgScore: 0,
      avgDiscovery: 0,
      hiddenStars: 0,
      countries: 0,
    };
  }

  const elite = players.filter((p) => p.tier === "Élite").length;
  const firstRound = players.filter((p) => p.tier === "1er tour").length;
  const avgScore = players.reduce((s, p) => s + p.overall, 0) / players.length;
  const hiddenStars = players.filter((p) => {
    const signal = getDiscoverySignal(p);
    return signal.score >= 75 && (signal.marketGap === null || signal.marketGap >= 8);
  }).length;
  const avgDiscovery =
    players.reduce((s, p) => s + getDiscoverySignal(p).score, 0) / players.length;
  const countries = new Set(players.map((p) => p.country)).size;
  return { total: players.length, elite, firstRound, avgScore, avgDiscovery, hiddenStars, countries };
}
