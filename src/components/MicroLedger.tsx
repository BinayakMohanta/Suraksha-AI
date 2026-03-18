import { motion } from "framer-motion";
import { ArrowDownRight } from "lucide-react";

interface LedgerEntry {
  id: string;
  trigger: string;
  amount: string;
  date: string;
  status: "completed" | "processing";
}

const entries: LedgerEntry[] = [
  { id: "1", trigger: "Heavy Rain > 15mm/hr", amount: "₹120", date: "Today, 2:34 PM", status: "processing" },
  { id: "2", trigger: "AQI > 300 (Hazardous)", amount: "₹95", date: "Yesterday, 11:20 AM", status: "completed" },
  { id: "3", trigger: "Heatwave > 42°C", amount: "₹80", date: "Mar 15, 3:15 PM", status: "completed" },
  { id: "4", trigger: "Heavy Rain > 15mm/hr", amount: "₹120", date: "Mar 12, 6:45 PM", status: "completed" },
];

const MicroLedger = () => {
  return (
    <motion.div
      className="safety-card p-5"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="flex items-center justify-between mb-4">
        <span className="data-label">Recent Protections</span>
        <span className="text-xs text-muted-foreground">Last 7 days</span>
      </div>

      <div className="space-y-1">
        {entries.map((entry, i) => (
          <motion.div
            key={entry.id}
            className="flex items-center justify-between py-3 border-b border-white/[0.04] last:border-0"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3 + i * 0.06, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="flex items-center gap-3">
              <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${
                entry.status === "processing" ? "bg-warning/10" : "bg-success/10"
              }`}>
                <ArrowDownRight className={`w-3.5 h-3.5 ${
                  entry.status === "processing" ? "text-warning" : "text-success"
                }`} />
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">{entry.trigger}</p>
                <p className="text-xs text-muted-foreground">{entry.date}</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-sm font-bold tabular-nums text-success">{entry.amount}</p>
              <p className={`text-[10px] uppercase tracking-wider ${
                entry.status === "processing" ? "text-warning" : "text-muted-foreground"
              }`}>
                {entry.status === "processing" ? "Processing" : "Paid"}
              </p>
            </div>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
};

export default MicroLedger;
