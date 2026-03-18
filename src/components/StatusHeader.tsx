import { motion } from "framer-motion";
import { Shield } from "lucide-react";

const StatusHeader = () => {
  return (
    <motion.header
      className="flex items-center justify-between py-4"
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
          <Shield className="w-4.5 h-4.5 text-primary" />
        </div>
        <div>
          <h1 className="text-base font-bold tracking-tight text-foreground">SurakshaAI</h1>
          <p className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground">Income Protection</p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-success animate-pulse-glow" />
        <span className="text-xs text-muted-foreground">Monitoring</span>
      </div>
    </motion.header>
  );
};

export default StatusHeader;
