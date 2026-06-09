import { motion } from "framer-motion";
import { TrendingUp, Users, Globe, Star } from "lucide-react";

interface StatsBarProps {
  total: number;
  elite: number;
  firstRound: number;
  avgScore: number;
  countries: number;
}

export default function StatsBar({ total, elite, firstRound, avgScore, countries }: StatsBarProps) {
  const stats = [
    { icon: Users, label: "Prospects", value: total, color: "text-ice-400" },
    { icon: Star, label: "Tier Élite", value: elite, color: "text-gold" },
    { icon: TrendingUp, label: "1er tour", value: firstRound, color: "text-emerald-400" },
    { icon: Globe, label: "Pays", value: countries, color: "text-purple-400" },
    {
      icon: TrendingUp,
      label: "Note moy.",
      value: avgScore.toFixed(1),
      color: "text-ice-300",
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
      {stats.map((s, i) => (
        <motion.div
          key={s.label}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.05 }}
          className="glass rounded-xl p-4"
        >
          <div className="flex items-center gap-2 mb-1">
            <s.icon className={`w-4 h-4 ${s.color}`} />
            <span className="text-xs text-slate-500 uppercase tracking-wide">{s.label}</span>
          </div>
          <p className={`font-display font-bold text-2xl ${s.color}`}>{s.value}</p>
        </motion.div>
      ))}
    </div>
  );
}
