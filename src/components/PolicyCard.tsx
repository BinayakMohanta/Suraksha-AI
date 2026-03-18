import { motion } from "framer-motion";
import { Shield, ToggleLeft, ToggleRight } from "lucide-react";
import { useState } from "react";

interface CoverageToggle {
  label: string;
  active: boolean;
  premium: string;
}

const PolicyCard = () => {
  const [coverages, setCoverages] = useState<CoverageToggle[]>([
    { label: "Heavy Rain", active: true, premium: "₹15" },
    { label: "Heatwave", active: true, premium: "₹12" },
    { label: "Air Quality", active: true, premium: "₹8" },
    { label: "Traffic Disruption", active: false, premium: "₹5" },
  ]);

  const totalPremium = coverages
    .filter(c => c.active)
    .reduce((sum, c) => sum + parseInt(c.premium.replace("₹", "")), 0);

  const toggle = (index: number) => {
    setCoverages(prev => prev.map((c, i) => i === index ? { ...c, active: !c.active } : c));
  };

  return (
    <motion.div
      className="safety-card p-5"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.15, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="flex items-center gap-2 mb-4">
        <Shield className="w-4 h-4 text-primary" />
        <span className="data-label">Micro-Premium · Weekly</span>
      </div>

      <div className="mb-5">
        <span className="text-3xl font-bold tabular-nums text-foreground">₹{totalPremium}</span>
        <span className="text-sm text-muted-foreground ml-1">/week</span>
      </div>

      <div className="space-y-3">
        {coverages.map((coverage, i) => (
          <button
            key={coverage.label}
            onClick={() => toggle(i)}
            className="w-full flex items-center justify-between py-2 group"
          >
            <div className="flex items-center gap-2.5">
              {coverage.active ? (
                <ToggleRight className="w-5 h-5 text-success" />
              ) : (
                <ToggleLeft className="w-5 h-5 text-muted-foreground" />
              )}
              <span className={`text-sm ${coverage.active ? "text-foreground" : "text-muted-foreground"}`}>
                {coverage.label}
              </span>
            </div>
            <span className={`text-xs tabular-nums ${coverage.active ? "text-foreground" : "text-muted-foreground"}`}>
              {coverage.premium}/wk
            </span>
          </button>
        ))}
      </div>
    </motion.div>
  );
};

export default PolicyCard;
