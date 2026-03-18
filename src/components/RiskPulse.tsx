import { motion } from "framer-motion";
import { useMemo } from "react";

type RiskLevel = "safe" | "warning" | "active";

interface RiskPulseProps {
  level: RiskLevel;
  value: number; // 0-100
  label: string;
}

const config: Record<RiskLevel, { color: string; bg: string; text: string; glowClass: string }> = {
  safe: { color: "hsl(155, 50%, 50%)", bg: "hsl(155, 50%, 50%)", text: "Safe", glowClass: "glow-success" },
  warning: { color: "hsl(30, 85%, 55%)", bg: "hsl(30, 85%, 55%)", text: "Warning", glowClass: "glow-warning" },
  active: { color: "hsl(0, 72%, 51%)", bg: "hsl(0, 72%, 51%)", text: "Active", glowClass: "glow-danger" },
};

const RiskPulse = ({ level, value, label }: RiskPulseProps) => {
  const c = config[level];
  const circumference = 2 * Math.PI * 90;
  const offset = circumference - (value / 100) * circumference;

  const gradient = useMemo(() => {
    if (level === "safe") return "conic-gradient(from 180deg, hsl(155 50% 50% / 0.1), hsl(155 50% 50% / 0.3), transparent)";
    if (level === "warning") return "conic-gradient(from 180deg, hsl(30 85% 55% / 0.1), hsl(30 85% 55% / 0.3), transparent)";
    return "conic-gradient(from 180deg, hsl(0 72% 51% / 0.1), hsl(0 72% 51% / 0.3), transparent)";
  }, [level]);

  return (
    <motion.div
      className="safety-card p-6 flex flex-col items-center gap-4"
      initial={{ scale: 0.95, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ type: "spring", stiffness: 300, damping: 20 }}
    >
      <span className="data-label">Current Risk Status</span>

      <div className="relative w-52 h-52 flex items-center justify-center">
        {/* Background glow */}
        <div
          className="absolute inset-0 rounded-full opacity-20 blur-2xl"
          style={{ background: gradient }}
        />

        {/* SVG Ring */}
        <svg className="absolute inset-0 -rotate-90" viewBox="0 0 200 200">
          <circle cx="100" cy="100" r="90" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="6" />
          <motion.circle
            cx="100"
            cy="100"
            r="90"
            fill="none"
            stroke={c.color}
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
          />
        </svg>

        {/* Center content */}
        <div className="relative z-10 flex flex-col items-center">
          <motion.div
            className={`w-3 h-3 rounded-full mb-2 ${level === "active" ? "animate-pulse-glow" : ""}`}
            style={{ backgroundColor: c.bg }}
          />
          <span className="text-3xl font-bold tabular-nums text-foreground">{value}%</span>
          <span className="text-sm font-semibold mt-1" style={{ color: c.color }}>{c.text}</span>
        </div>
      </div>

      <p className="text-sm text-muted-foreground text-center">{label}</p>
    </motion.div>
  );
};

export default RiskPulse;
