import { Search, SlidersHorizontal, X } from "lucide-react";

interface SearchFiltersProps {
  query: string;
  onQueryChange: (v: string) => void;
  position: string;
  onPositionChange: (v: string) => void;
  country: string;
  onCountryChange: (v: string) => void;
  tier: string;
  onTierChange: (v: string) => void;
  minScore: number;
  onMinScoreChange: (v: number) => void;
  positions: string[];
  countries: string[];
  tiers: string[];
  resultCount: number;
}

export default function SearchFilters(props: SearchFiltersProps) {
  const hasFilters =
    props.query ||
    props.position !== "ALL" ||
    props.country !== "ALL" ||
    props.tier !== "ALL" ||
    props.minScore > 0;

  const reset = () => {
    props.onQueryChange("");
    props.onPositionChange("ALL");
    props.onCountryChange("ALL");
    props.onTierChange("ALL");
    props.onMinScoreChange(0);
  };

  return (
    <div className="glass rounded-xl p-4 mb-4 space-y-3">
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="search"
            placeholder="Rechercher un joueur..."
            value={props.query}
            onChange={(e) => props.onQueryChange(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-rink-800/80 border border-white/5 text-sm placeholder:text-slate-500 focus:outline-none focus:border-ice-500/40 focus:ring-1 focus:ring-ice-500/20 transition-all"
          />
        </div>
        {hasFilters && (
          <button
            onClick={reset}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
          >
            <X className="w-4 h-4" />
            Réinitialiser
          </button>
        )}
      </div>

      <div className="flex items-center gap-2 text-xs text-slate-500">
        <SlidersHorizontal className="w-3.5 h-3.5" />
        <span>Filtres</span>
        <span className="ml-auto font-mono text-ice-400">{props.resultCount} résultats</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <Select label="Position" value={props.position} onChange={props.onPositionChange} options={["ALL", ...props.positions]} />
        <Select label="Pays" value={props.country} onChange={props.onCountryChange} options={["ALL", ...props.countries]} />
        <Select label="Tier" value={props.tier} onChange={props.onTierChange} options={["ALL", ...props.tiers]} />
        <div>
          <label className="block text-[10px] uppercase tracking-wide text-slate-500 mb-1">
            Note min: {props.minScore}
          </label>
          <input
            type="range"
            min={0}
            max={95}
            step={5}
            value={props.minScore}
            onChange={(e) => props.onMinScoreChange(Number(e.target.value))}
            className="w-full accent-ice-500"
          />
        </div>
      </div>
    </div>
  );
}

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: string[];
}) {
  return (
    <div>
      <label className="block text-[10px] uppercase tracking-wide text-slate-500 mb-1">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-2 py-2 rounded-lg bg-rink-800/80 border border-white/5 text-sm focus:outline-none focus:border-ice-500/40"
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {o === "ALL" ? "Tous" : o}
          </option>
        ))}
      </select>
    </div>
  );
}
