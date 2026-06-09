import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ChevronRight } from "lucide-react";
import { Player, COUNTRY_FLAGS } from "../types/player";
import { scoreColor, positionColor, tierColor } from "../utils/playerUtils";

interface RankingTableProps {
  players: Player[];
}

export default function RankingTable({ players }: RankingTableProps) {
  return (
    <div className="glass rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/5 text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="px-4 py-3 font-medium w-14">#</th>
              <th className="px-4 py-3 font-medium">Joueur</th>
              <th className="px-4 py-3 font-medium hidden sm:table-cell">Pos</th>
              <th className="px-4 py-3 font-medium hidden md:table-cell">Taille</th>
              <th className="px-4 py-3 font-medium hidden lg:table-cell">Pays</th>
              <th className="px-4 py-3 font-medium hidden md:table-cell">Tier</th>
              <th className="px-4 py-3 font-medium text-right">Note</th>
              <th className="w-10" />
            </tr>
          </thead>
          <tbody>
            {players.map((p, i) => (
              <motion.tr
                key={p.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: Math.min(i * 0.015, 0.5) }}
                className="border-b border-white/[0.03] hover:bg-white/[0.02] group transition-colors"
              >
                <td className="px-4 py-3">
                  <span
                    className={`font-mono font-semibold ${p.rank <= 10 ? "text-gold" : p.rank <= 32 ? "text-ice-400" : "text-slate-500"}`}
                  >
                    {p.rank}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <Link to={`/player/${p.id}`} className="flex items-center gap-3 group/link">
                    <RankBadge rank={p.rank} />
                    <div>
                      <p className="font-semibold text-slate-100 group-hover/link:text-ice-300 transition-colors">
                        {p.name}
                      </p>
                      <p className="text-xs text-slate-500 sm:hidden">
                        {p.position} · {p.height}
                      </p>
                    </div>
                  </Link>
                </td>
                <td className="px-4 py-3 hidden sm:table-cell">
                  <span className={`inline-flex px-2 py-0.5 rounded border text-xs font-mono ${positionColor(p.position)}`}>
                    {p.position}
                  </span>
                </td>
                <td className="px-4 py-3 hidden md:table-cell font-mono text-slate-400 text-xs">
                  {p.height} / {p.weight}
                </td>
                <td className="px-4 py-3 hidden lg:table-cell">
                  <span title={p.country}>
                    {COUNTRY_FLAGS[p.country] ?? "🏳️"} {p.country}
                  </span>
                </td>
                <td className="px-4 py-3 hidden md:table-cell">
                  <span className={`inline-flex px-2 py-0.5 rounded-full border text-[10px] font-medium bg-gradient-to-r ${tierColor(p.tier)}`}>
                    {p.tier}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <span className={`font-display font-bold text-lg ${scoreColor(p.overall)}`}>
                    {p.overall.toFixed(1)}
                  </span>
                </td>
                <td className="px-2 py-3">
                  <Link
                    to={`/player/${p.id}`}
                    className="p-1.5 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-ice-500/10 text-ice-400 transition-all"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </Link>
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
      {players.length === 0 && (
        <div className="py-16 text-center text-slate-500">Aucun joueur ne correspond aux filtres.</div>
      )}
    </div>
  );
}

function RankBadge({ rank }: { rank: number }) {
  if (rank > 32) return null;
  const bg =
    rank === 1
      ? "from-gold to-amber-600"
      : rank <= 5
        ? "from-ice-400 to-ice-600"
        : rank <= 15
          ? "from-slate-400 to-slate-600"
          : "from-zinc-600 to-zinc-700";
  return (
    <div
      className={`hidden sm:flex w-8 h-8 rounded-lg bg-gradient-to-br ${bg} items-center justify-center text-xs font-bold text-white shadow-lg shrink-0`}
    >
      {rank}
    </div>
  );
}
