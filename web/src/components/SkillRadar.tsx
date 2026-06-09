import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { PlayerSkills } from "../types/player";
import { skillsToRadar } from "../utils/playerUtils";

interface SkillRadarProps {
  skills: PlayerSkills;
  compareSkills?: PlayerSkills;
  compareName?: string;
}

export default function SkillRadar({ skills, compareSkills, compareName }: SkillRadarProps) {
  const data = skillsToRadar(skills);
  const compareData = compareSkills ? skillsToRadar(compareSkills) : null;

  const merged = data.map((d, i) => ({
    ...d,
    compare: compareData?.[i]?.value,
  }));

  return (
    <ResponsiveContainer width="100%" height={320}>
      <RadarChart data={merged} cx="50%" cy="50%" outerRadius="75%">
        <PolarGrid stroke="rgba(255,255,255,0.08)" />
        <PolarAngleAxis
          dataKey="skill"
          tick={{ fill: "#94a3b8", fontSize: 11 }}
        />
        <Tooltip
          contentStyle={{
            background: "#111827",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 8,
            fontSize: 12,
          }}
        />
        {compareSkills && (
          <Radar
            name={compareName ?? "Compare"}
            dataKey="compare"
            stroke="#fbbf24"
            fill="#fbbf24"
            fillOpacity={0.15}
            strokeWidth={2}
          />
        )}
        <Radar
          name="Joueur"
          dataKey="value"
          stroke="#38bdf8"
          fill="#0ea5e9"
          fillOpacity={0.25}
          strokeWidth={2}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
