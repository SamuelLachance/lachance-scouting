import { motion } from "framer-motion";
import { PlayerSkills, SKILL_LABELS } from "../types/player";

interface SkillBarsProps {
  skills: PlayerSkills;
  rationales?: Partial<Record<keyof PlayerSkills, string>>;
}

export default function SkillBars({ skills, rationales }: SkillBarsProps) {
  const entries = Object.entries(SKILL_LABELS) as [keyof PlayerSkills, { label: string; weight: number }][];

  return (
    <div className="space-y-3">
      {entries.map(([key, { label, weight }], i) => {
        const value = skills[key];
        const pct = (value / 10) * 100;
        const weighted = (value * weight) / 10;

        return (
          <div key={key}>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-400">{label}</span>
              <span className="font-mono">
                <span className={barColor(value)}>{value.toFixed(1)}</span>
                <span className="text-slate-600 ml-2">({weight}% → {weighted.toFixed(1)})</span>
              </span>
            </div>
            <div className="h-2 rounded-full bg-rink-800 overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${pct}%` }}
                transition={{ delay: i * 0.04, duration: 0.5, ease: "easeOut" }}
                className={`h-full rounded-full ${barBg(value)}`}
              />
            </div>
            {rationales?.[key] && (
              <p className="mt-1.5 text-xs leading-relaxed text-slate-500">
                {stripMarkdown(rationales[key])}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}

function stripMarkdown(value: string | undefined) {
  return (value ?? "").replace(/\*\*/g, "");
}

function barColor(v: number) {
  if (v >= 9) return "text-gold font-semibold";
  if (v >= 7.5) return "text-ice-300";
  if (v >= 6) return "text-emerald-400";
  return "text-slate-400";
}

function barBg(v: number) {
  if (v >= 9) return "bg-gradient-to-r from-gold to-amber-500";
  if (v >= 7.5) return "bg-gradient-to-r from-ice-600 to-ice-400";
  if (v >= 6) return "bg-gradient-to-r from-emerald-600 to-emerald-400";
  return "bg-gradient-to-r from-slate-600 to-slate-500";
}
