import { Player, PlayerSkills } from "../types/player";

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

export function skillsToRadar(skills: PlayerSkills) {
  return [
    { skill: "Patinage", value: skills.skating, fullMark: 10 },
    { skill: "Rondelle", value: skills.puckSkills, fullMark: 10 },
    { skill: "Tir", value: skills.shot, fullMark: 10 },
    { skill: "IQ", value: skills.hockeyIQ, fullMark: 10 },
    { skill: "Défense", value: skills.defense, fullMark: 10 },
    { skill: "Combat", value: skills.compete, fullMark: 10 },
    { skill: "Physique", value: skills.physical, fullMark: 10 },
    { skill: "Production", value: skills.production, fullMark: 10 },
  ];
}

export function filterPlayers(
  players: Player[],
  query: string,
  position: string,
  country: string,
  tier: string,
  minScore: number
): Player[] {
  const q = query.toLowerCase().trim();
  return players.filter((p) => {
    if (q && !p.name.toLowerCase().includes(q)) return false;
    if (position !== "ALL" && p.position !== position) return false;
    if (country !== "ALL" && p.country !== country) return false;
    if (tier !== "ALL" && p.tier !== tier) return false;
    if (p.overall < minScore) return false;
    return true;
  });
}

export function getStats(players: Player[]) {
  const elite = players.filter((p) => p.tier === "Élite").length;
  const firstRound = players.filter((p) => p.tier === "1er tour").length;
  const avgScore = players.reduce((s, p) => s + p.overall, 0) / players.length;
  const countries = new Set(players.map((p) => p.country)).size;
  return { total: players.length, elite, firstRound, avgScore, countries };
}
