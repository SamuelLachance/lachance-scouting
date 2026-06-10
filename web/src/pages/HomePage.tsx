import { useMemo, useState } from "react";
import { usePlayers } from "../context/PlayersContext";
import StatsBar from "../components/StatsBar";
import SearchFilters from "../components/SearchFilters";
import RankingTable from "../components/RankingTable";
import { filterPlayers, getStats } from "../utils/playerUtils";
import { Loader2 } from "lucide-react";

export default function HomePage() {
  const { players, loading, error } = usePlayers();
  const [query, setQuery] = useState("");
  const [position, setPosition] = useState("ALL");
  const [country, setCountry] = useState("ALL");
  const [tier, setTier] = useState("ALL");
  const [minScore, setMinScore] = useState(0);
  const [minDiscovery, setMinDiscovery] = useState(0);
  const [hiddenOnly, setHiddenOnly] = useState(false);

  const positions = useMemo(() => [...new Set(players.map((p) => p.position))].sort(), [players]);
  const countries = useMemo(() => [...new Set(players.map((p) => p.country))].sort(), [players]);
  const tiers = useMemo(() => [...new Set(players.map((p) => p.tier))], [players]);

  const filtered = useMemo(
    () => filterPlayers(players, query, position, country, tier, minScore, minDiscovery, hiddenOnly),
    [players, query, position, country, tier, minScore, minDiscovery, hiddenOnly]
  );

  const stats = useMemo(() => getStats(players), [players]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-32 gap-4">
        <Loader2 className="w-8 h-8 text-ice-500 animate-spin" />
        <p className="text-slate-500 text-sm">Chargement Lachance Scouting…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass rounded-xl p-8 text-center text-red-400">
        Erreur: {error}. Exécutez <code className="text-ice-400">python build_site_data.py</code>
      </div>
    );
  }

  return (
    <>
      <div className="mb-6">
        <h2 className="font-display font-bold text-2xl sm:text-3xl mb-1">
          Classement NORTHSTAR
        </h2>
        <p className="text-slate-500 text-sm">
          Rating final = moyenne NORTHSTAR + upside caché — {players.length} prospects reclassés pour détecter les futures étoiles avant le consensus public
        </p>
      </div>

      <StatsBar {...stats} />

      <SearchFilters
        query={query}
        onQueryChange={setQuery}
        position={position}
        onPositionChange={setPosition}
        country={country}
        onCountryChange={setCountry}
        tier={tier}
        onTierChange={setTier}
        minScore={minScore}
        onMinScoreChange={setMinScore}
        minDiscovery={minDiscovery}
        onMinDiscoveryChange={setMinDiscovery}
        hiddenOnly={hiddenOnly}
        onHiddenOnlyChange={setHiddenOnly}
        positions={positions}
        countries={countries}
        tiers={tiers}
        resultCount={filtered.length}
      />

      <RankingTable players={filtered} />
    </>
  );
}
