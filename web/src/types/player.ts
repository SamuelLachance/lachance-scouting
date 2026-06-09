export interface PlayerSkills {
  skating: number;
  puckSkills: number;
  shot: number;
  hockeyIQ: number;
  defense: number;
  compete: number;
  physical: number;
  production: number;
  ceiling: number;
  nhlProbability: number;
}

export interface PlayerAnalysis {
  resume: string;
  forces: string[];
  faiblesses: string[];
  comparable: string;
  projection: string;
}

export interface Player {
  id: string;
  rank: number;
  name: string;
  position: string;
  height: string;
  weight: number | string;
  shoots: string;
  country: string;
  overall: number;
  consensusRank: number | null;
  tier: string;
  skills: PlayerSkills;
  analysis: PlayerAnalysis;
}

export const SKILL_LABELS: Record<keyof PlayerSkills, { label: string; weight: number }> = {
  skating: { label: "Patinage", weight: 12 },
  puckSkills: { label: "Habiletés rondelle", weight: 14 },
  shot: { label: "Tir", weight: 10 },
  hockeyIQ: { label: "Vision / IQ", weight: 14 },
  defense: { label: "Jeu défensif", weight: 12 },
  compete: { label: "Compétitivité", weight: 10 },
  physical: { label: "Outils physiques", weight: 8 },
  production: { label: "Production", weight: 10 },
  ceiling: { label: "Potentiel", weight: 6 },
  nhlProbability: { label: "Prob. NHL", weight: 4 },
};

export const COUNTRY_FLAGS: Record<string, string> = {
  CAN: "🇨🇦",
  CDN: "🇨🇦",
  USA: "🇺🇸",
  SWE: "🇸🇪",
  FIN: "🇫🇮",
  CZE: "🇨🇿",
  SVK: "🇸🇰",
  RUS: "🇷🇺",
  SUI: "🇨🇭",
  GER: "🇩🇪",
  LAT: "🇱🇻",
  BLR: "🇧🇾",
  KAZ: "🇰🇿",
  AUT: "🇦🇹",
  NOR: "🇳🇴",
  USa: "🇺🇸",
};
