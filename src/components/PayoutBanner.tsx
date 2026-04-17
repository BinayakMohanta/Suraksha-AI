import { motion } from "framer-motion";

const PayoutBanner = () => {
  return (
    <motion.div
      className="safety-card premium-interactive p-4 glow-success border-success/20 relative overflow-hidden"
      initial={{ scale: 0.95, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ type: "spring", stiffness: 300, damping: 20, delay: 0.1 }}
    >
      {/* Animated border glow */}
      <motion.div
        className="absolute inset-0 rounded-2xl border border-success/30"
        animate={{ opacity: [0.3, 0.8, 0.3] }}
        transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
      />

      <div className="relative z-10 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-foreground leading-tight break-words">Disruption Detected · Payout Initiated</p>
          <p className="text-xs text-muted-foreground mt-1 leading-relaxed break-words">Heavy rain detected in Sector 4. ₹120 payout processing.</p>
        </div>
        <div className="self-start sm:self-auto sm:flex-shrink-0">
          <span className="text-lg font-bold tabular-nums text-success leading-none">₹120</span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="relative z-10 mt-3 h-1 bg-white/5 rounded-full overflow-hidden">
        <motion.div
          className="h-full bg-success rounded-full"
          initial={{ width: "0%" }}
          animate={{ width: "65%" }}
          transition={{ duration: 2, ease: [0.16, 1, 0.3, 1], delay: 0.5 }}
        />
      </div>
      <p className="relative z-10 text-[10px] text-muted-foreground mt-1.5 break-words">Verifying conditions · 65% complete</p>
    </motion.div>
  );
};

export default PayoutBanner;
