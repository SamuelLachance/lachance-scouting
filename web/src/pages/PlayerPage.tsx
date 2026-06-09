import { Link, useParams, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  Target,
  Shield,
  TrendingUp,
  User,
  Gem,
  Radar,
} from "lucide-react";
import { usePlayers } from "../context/PlayersContext";
import SkillRadar from "../components/SkillRadar";
import SkillBars from "../components/SkillBars";
import { COUNTRY_FLAGS } from "../types/player";
import { discoveryColor, getDiscoverySignal, scoreColor, positionColor, tierColor } from "../utils/playerUtils";

export default function PlayerPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { getPlayer, players, loading } = usePlayers();
  const player = id ? getPlayer(id) : undefined;

  if (loading) return null;

  if (!player) {
    return (
      <div className="glass rounded-xl p-12 text-center">
        <p className="text-slate-400 mb-4">Joueur introuvable.</p>
        <Link to="/" className="text-ice-400 hover:text-ice-300">
          ← Retour au classement
        </Link>
      </div>
    );
  }

  const prev = players.find((p) => p.rank === player.rank - 1);
  const next = players.find((p) => p.rank === player.rank + 1);
  const { analysis } = player;
  const discovery = getDiscoverySignal(player);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Retour
        </button>
        <div className="flex gap-2">
          {prev && (
            <Link
              to={`/player/${prev.id}`}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs glass-hover text-slate-400"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              #{prev.rank} {prev.name.split(" ").pop()}
            </Link>
          )}
          {next && (
            <Link
              to={`/player/${next.id}`}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs glass-hover text-slate-400"
            >
              #{next.rank} {next.name.split(" ").pop()}
              <ChevronRight className="w-3.5 h-3.5" />
            </Link>
          )}
        </div>
      </div>

      {/* Hero */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass rounded-2xl p-6 sm:p-8 relative overflow-hidden"
      >
        <div className="absolute top-0 right-0 w-64 h-64 bg-ice-500/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
        <div className="relative flex flex-col lg:flex-row gap-6 lg:items-start">
          <ScoreRing score={player.overall} rank={player.rank} />
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <span className="font-mono text-gold font-bold text-sm">#{player.rank} BPA</span>
              {player.consensusRank && (
                <span className="text-xs text-slate-500 font-mono">
                  Consensus #{player.consensusRank}
                </span>
              )}
              <span className={`px-2 py-0.5 rounded-full border text-[10px] bg-gradient-to-r ${tierColor(player.tier)}`}>
                {player.tier}
              </span>
              <span className={`px-2 py-0.5 rounded-full border text-[10px] ${discoveryColor(discovery.score)}`}>
                Discovery {discovery.score.toFixed(1)}
              </span>
            </div>
            <h1 className="font-display font-bold text-3xl sm:text-4xl mb-3">{player.name}</h1>
            <div className="flex flex-wrap gap-3 text-sm">
              <Badge icon={<User className="w-3.5 h-3.5" />}>
                <span className={`px-1.5 py-0.5 rounded border text-xs font-mono ${positionColor(player.position)}`}>
                  {player.position}
                </span>
              </Badge>
              <Badge icon={<Target className="w-3.5 h-3.5" />}>
                {player.height} · {player.weight} lbs · Tire {player.shoots}
              </Badge>
              <Badge icon={<Shield className="w-3.5 h-3.5" />}>
                {COUNTRY_FLAGS[player.country] ?? "🏳️"} {player.country}
              </Badge>
            </div>
            {analysis.resume && (
              <p className="mt-4 text-slate-300 leading-relaxed text-sm sm:text-base max-w-2xl">
                {analysis.resume}
              </p>
            )}
            {analysis.upsideThesis && (
              <p className="mt-3 pl-3 border-l-2 border-gold/50 text-sm text-slate-300 max-w-2xl">
                <span className="block text-[10px] uppercase tracking-wide text-gold mb-1">Thèse upside</span>
                {analysis.upsideThesis}
              </p>
            )}
          </div>
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.08 }}
        className="glass rounded-xl p-5 border border-fuchsia-400/15 bg-fuchsia-500/[0.03]"
      >
        <div className="flex flex-col lg:flex-row gap-5 lg:items-start">
          <div className="flex items-center gap-4 lg:w-72">
            <div className={`w-20 h-20 rounded-2xl border flex flex-col items-center justify-center ${discoveryColor(discovery.score)}`}>
              <span className="font-display font-bold text-2xl">{discovery.score.toFixed(1)}</span>
              <span className="text-[10px] uppercase tracking-wide">Discovery</span>
            </div>
            <div>
              <h3 className="font-display font-semibold flex items-center gap-2">
                <Gem className="w-4 h-4 text-fuchsia-300" />
                {discovery.label}
              </h3>
              <p className="text-xs text-slate-500 mt-1">{discovery.marketStatus}</p>
            </div>
          </div>
          <div className="grid sm:grid-cols-3 gap-3 flex-1">
            <SignalStat label="Upside pur" value={`${discovery.upsideCore.toFixed(1)}/100`} />
            <SignalStat label="Outil signature" value={`${discovery.peakTool.label} ${discovery.peakTool.score.toFixed(1)}`} />
            <SignalStat label="Confiance" value={discovery.confidenceLabel} />
            {player.baseNorthstarScore && (
              <SignalStat label="Talent pur ancien modèle" value={`${player.baseNorthstarScore.toFixed(1)}/100`} />
            )}
          </div>
        </div>
        <div className="mt-4 grid sm:grid-cols-2 gap-2">
          {discovery.reasons.map((reason) => (
            <div key={reason} className="flex items-start gap-2 rounded-lg bg-rink-800/60 border border-white/5 px-3 py-2 text-sm text-slate-300">
              <Radar className="w-3.5 h-3.5 mt-0.5 text-fuchsia-300 shrink-0" />
              {reason}
            </div>
          ))}
        </div>
      </motion.div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Radar */}
        <motion.div
          initial={{ opacity: 0, x: -12 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.1 }}
          className="glass rounded-xl p-5"
        >
          <h3 className="font-display font-semibold mb-2 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-ice-400" />
            Profil athlétique
          </h3>
          <SkillRadar skills={player.skills} />
        </motion.div>

        {/* Skill bars */}
        <motion.div
          initial={{ opacity: 0, x: 12 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.15 }}
          className="glass rounded-xl p-5"
        >
          <h3 className="font-display font-semibold mb-4">Grille NORTHSTAR détaillée</h3>
          <SkillBars skills={player.skills} rationales={player.skillRationales} />
          <div className="mt-4 pt-4 border-t border-white/5 flex justify-between items-center">
            <span className="text-sm text-slate-500">NORTHSTAR Discovery Rating</span>
            <span className={`font-display font-bold text-2xl ${scoreColor(player.overall)}`}>
              {player.overall.toFixed(1)}/100
            </span>
          </div>
        </motion.div>
      </div>

      {/* Analysis sections */}
      <div className="grid sm:grid-cols-2 gap-4">
        <AnalysisCard title="Forces" items={analysis.forces} variant="positive" />
        <AnalysisCard title="Faiblesses / Risques" items={analysis.faiblesses} variant="negative" />
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        <div className="glass rounded-xl p-5">
          <h3 className="text-xs uppercase tracking-wide text-slate-500 mb-2">Comparable NHL</h3>
          <p className="text-slate-200">{analysis.comparable || "—"}</p>
        </div>
        <div className="glass rounded-xl p-5">
          <h3 className="text-xs uppercase tracking-wide text-slate-500 mb-2">Projection</h3>
          <p className="text-slate-200">{player.projection || analysis.projection || "—"}</p>
        </div>
      </div>

      <div className="flex justify-center pt-4">
        <Link
          to={`/compare?a=${player.id}`}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-ice-500/15 border border-ice-500/30 text-ice-300 text-sm font-medium hover:bg-ice-500/25 transition-colors"
        >
          Comparer avec un autre prospect
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  );
}

function SignalStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-rink-800/60 border border-white/5 px-3 py-2">
      <p className="text-[10px] uppercase tracking-wide text-slate-500 mb-1">{label}</p>
      <p className="text-sm font-semibold text-slate-200">{value}</p>
    </div>
  );
}

function ScoreRing({ score, rank }: { score: number; rank: number }) {
  const pct = `${score}%`;
  return (
    <div className="relative w-32 h-32 shrink-0 mx-auto lg:mx-0">
      <div
        className="score-ring w-full h-full rounded-full p-1"
        style={{ "--score-pct": pct } as React.CSSProperties}
      >
        <div className="w-full h-full rounded-full bg-rink-900 flex flex-col items-center justify-center">
          <span className={`font-display font-bold text-3xl ${scoreColor(score)}`}>
            {score.toFixed(1)}
          </span>
          <span className="text-[10px] text-slate-500 uppercase">/ 100</span>
        </div>
      </div>
      {rank <= 10 && (
        <div className="absolute -top-1 -right-1 w-8 h-8 rounded-full bg-gold text-rink-950 flex items-center justify-center text-xs font-bold shadow-lg">
          {rank}
        </div>
      )}
    </div>
  );
}

function Badge({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-slate-400">
      {icon}
      {children}
    </span>
  );
}

function AnalysisCard({
  title,
  items,
  variant,
}: {
  title: string;
  items: string[];
  variant: "positive" | "negative";
}) {
  const colors =
    variant === "positive"
      ? "border-emerald-500/20 bg-emerald-500/5"
      : "border-rose-500/20 bg-rose-500/5";
  const dot = variant === "positive" ? "bg-emerald-400" : "bg-rose-400";

  return (
    <div className={`glass rounded-xl p-5 border ${colors}`}>
      <h3 className="font-display font-semibold mb-3">{title}</h3>
      <ul className="space-y-2">
        {items.length > 0 ? (
          items.map((item) => (
            <li key={item} className="flex items-start gap-2 text-sm text-slate-300">
              <span className={`w-1.5 h-1.5 rounded-full ${dot} mt-1.5 shrink-0`} />
              {item}
            </li>
          ))
        ) : (
          <li className="text-slate-500 text-sm">—</li>
        )}
      </ul>
    </div>
  );
}
