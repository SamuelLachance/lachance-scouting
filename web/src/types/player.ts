export interface PlayerSkills {
  starCeiling: number;
  hockeyIQ: number;
  skatingEngine: number;
  offensiveStarPower: number;
  competitionProof: number;
  characterCompete: number;
  developmentArc: number;
}

export interface DiscoverySignal {
  score: number;
  label: string;
  marketGap: number | null;
  marketStatus: string;
  upsideCore: number;
  rareToolCount: number;
  peakTool: {
    label: string;
    score: number;
  };
  confidence: number;
  confidenceLabel: string;
  reasons: string[];
}

export interface PlayerAnalysis {
  resume: string;
  forces: string[];
  faiblesses: string[];
  comparable: string;
  projection: string;
  upsideThesis?: string;
}

export interface Player {
  id: string;
  draftYear?: number;
  rank: number;
  northstarRank?: number;
  apexRank?: number;
  name: string;
  position: string;
  height: string;
  weight: number | string;
  shoots: string;
  country: string;
  photoUrl?: string;
  overall: number;
  starTier?: string;
  reportCoverage?: string;
  consensusRank: number | null;
  consensusDelta?: number | null;
  tier: string;
  eaTier?: string;
  tierGroup?: string;
  projection?: string;
  projectionEn?: string;
  isOverAge?: boolean;
  overAgePenalty?: number;
  spiBeforePenalty?: number | string | null;
  skills: PlayerSkills;
  skillRationales?: Partial<Record<keyof PlayerSkills, string>>;
  sourceMix?: string[];
  discoverySignal?: DiscoverySignal;
  analysis: PlayerAnalysis;
}

export const SKILL_LABELS: Record<keyof PlayerSkills, { label: string; weight: number }> = {
  starCeiling: { label: "Plafond étoile NHL", weight: 35 },
  hockeyIQ: { label: "IQ / processing élite", weight: 18 },
  skatingEngine: { label: "Moteur de patinage", weight: 15 },
  offensiveStarPower: { label: "Pouvoir offensif star", weight: 12 },
  competitionProof: { label: "Preuve vs compétition", weight: 10 },
  characterCompete: { label: "Compétitivité / caractère", weight: 5 },
  developmentArc: { label: "Arc de développement", weight: 5 },
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
