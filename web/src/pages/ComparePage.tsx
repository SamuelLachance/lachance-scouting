import { useMemo } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { GitCompareArrows } from "lucide-react";
import { usePlayers } from "../context/PlayersContext";
import SkillRadar from "../components/SkillRadar";
import { scoreColor, positionColor } from "../utils/playerUtils";
import { COUNTRY_FLAGS } from "../types/player";

export default function ComparePage() {
  const { players, loading } = usePlayers();
  const [params, setParams] = useSearchParams();
  const idA = params.get("a") ?? "";
  const idB = params.get("b") ?? "";

  const playerA = players.find((p) => p.id === idA);
  const playerB = players.find((p) => p.id === idB);

  const top32 = useMemo(() => players.filter((p) => p.rank <= 32), [players]);

  if (loading) return null;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display font-bold text-2xl flex items-center gap-2">
          <GitCompareArrows className="w-6 h-6 text-ice-400" />
          Comparateur de prospects
        </h2>
        <p className="text-slate-500 text-sm mt-1">
          Superposez les profils radar pour évaluer deux options de repêchage
        </p>
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        <PlayerSelect
          label="Joueur A"
          value={idA}
          onChange={(v) => setParams({ a: v, b: idB })}
          players={players}
        />
        <PlayerSelect
          label="Joueur B"
          value={idB}
          onChange={(v) => setParams({ a: idA, b: v })}
          players={players}
        />
      </div>

      {playerA && playerB ? (
        <>
          <div className="glass rounded-xl p-5">
            <SkillRadar
              skills={playerA.skills}
              compareSkills={playerB.skills}
              compareName={playerB.name}
            />
            <div className="flex justify-center gap-8 mt-2 text-sm">
              <span className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-ice-500" />
                {playerA.name} ({playerA.overall.toFixed(1)})
              </span>
              <span className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-gold" />
                {playerB.name} ({playerB.overall.toFixed(1)})
              </span>
            </div>
          </div>

          <CompareTable a={playerA} b={playerB} />
        </>
      ) : (
        <div className="glass rounded-xl p-8 text-center text-slate-500">
          Sélectionnez deux joueurs pour comparer leurs profils.
        </div>
      )}

      <div className="glass rounded-xl p-5">
        <h3 className="text-sm font-semibold text-slate-400 mb-3">Raccourcis — Top 32</h3>
        <div className="flex flex-wrap gap-2">
          {top32.map((p) => (
            <button
              key={p.id}
              onClick={() => {
                if (!idA) setParams({ a: p.id, b: idB });
                else if (!idB) setParams({ a: idA, b: p.id });
                else setParams({ a: p.id, b: idB });
              }}
              className="px-2 py-1 rounded-lg text-xs glass-hover font-mono"
            >
              #{p.rank} {p.name.split(" ").pop()}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function PlayerSelect({
  label,
  value,
  onChange,
  players,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  players: { id: string; rank: number; name: string; overall: number }[];
}) {
  return (
    <div className="glass rounded-xl p-4">
      <label className="block text-xs uppercase tracking-wide text-slate-500 mb-2">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-3 py-2.5 rounded-lg bg-rink-800/80 border border-white/5 text-sm focus:outline-none focus:border-ice-500/40"
      >
        <option value="">— Choisir —</option>
        {players.map((p) => (
          <option key={p.id} value={p.id}>
            #{p.rank} {p.name} ({p.overall.toFixed(1)})
          </option>
        ))}
      </select>
    </div>
  );
}

function CompareTable({
  a,
  b,
}: {
  a: {
    id: string;
    name: string;
    rank: number;
    position: string;
    country: string;
    overall: number;
    skills: Record<string, number>;
  };
  b: typeof a;
}) {
  const rows = [
    { label: "Rang BPA", a: `#${a.rank}`, b: `#${b.rank}`, diff: a.rank - b.rank },
    { label: "Note globale", a: a.overall.toFixed(1), b: b.overall.toFixed(1), diff: a.overall - b.overall },
    { label: "Position", a: a.position, b: b.position, diff: null },
    { label: "Pays", a: `${COUNTRY_FLAGS[a.country] ?? ""} ${a.country}`, b: `${COUNTRY_FLAGS[b.country] ?? ""} ${b.country}`, diff: null },
  ];

  const skillRows = Object.entries(a.skills).map(([key, valA]) => {
    const valB = (b.skills as Record<string, number>)[key];
    return { label: key, a: valA.toFixed(1), b: valB.toFixed(1), diff: valA - valB };
  });

  return (
    <div className="glass rounded-xl overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-white/5 text-left text-xs text-slate-500">
            <th className="px-4 py-3">Métrique</th>
            <th className="px-4 py-3">
              <Link to={`/player/${a.id}`} className="text-ice-400 hover:underline">
                {a.name}
              </Link>
            </th>
            <th className="px-4 py-3">
              <Link to={`/player/${b.id}`} className="text-gold hover:underline">
                {b.name}
              </Link>
            </th>
            <th className="px-4 py-3 text-right">Δ A−B</th>
          </tr>
        </thead>
        <tbody>
          {[...rows, ...skillRows.slice(0, 6)].map((row) => (
            <tr key={row.label} className="border-b border-white/[0.03]">
              <td className="px-4 py-2.5 text-slate-400 capitalize">{row.label}</td>
              <td className="px-4 py-2.5 font-mono">{row.a}</td>
              <td className="px-4 py-2.5 font-mono">{row.b}</td>
              <td className="px-4 py-2.5 text-right font-mono">
                {row.diff !== null && typeof row.diff === "number" ? (
                  <span className={row.diff > 0 ? "text-emerald-400" : row.diff < 0 ? "text-rose-400" : "text-slate-500"}>
                    {row.diff > 0 ? "+" : ""}
                    {typeof row.diff === "number" && row.diff % 1 !== 0 ? row.diff.toFixed(1) : row.diff}
                  </span>
                ) : (
                  "—"
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
