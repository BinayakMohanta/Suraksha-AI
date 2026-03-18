import { motion } from "framer-motion";
import { type LucideIcon } from "lucide-react";

interface TelemetryCardProps {
  icon: LucideIcon;
  label: string;
  value: string;
  unit: string;
  status: "normal" | "elevated" | "critical";
  index: number;
}

const statusColors: Record<string, string> = {
  normal: "text-success",
  elevated: "text-warning",
  critical: "text-danger",
};

const TelemetryCard = ({ icon: Icon, label, value, unit, status, index }: TelemetryCardProps) => {
  return (
    <motion.div
      className="safety-card p-4 flex flex-col gap-3"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="flex items-center justify-between">
        <span className="data-label">{label}</span>
        <Icon className="w-3.5 h-3.5 text-muted-foreground" />
      </div>
      <div className="flex items-baseline gap-1.5">
        <span className={`text-2xl font-bold tabular-nums ${statusColors[status]}`}>{value}</span>
        <span className="text-xs text-muted-foreground">{unit}</span>
      </div>
    </motion.div>
  );
};

export default TelemetryCard;
