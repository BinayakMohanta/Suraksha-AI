import { useState } from "react";
import { CloudRain, Thermometer, Wind, Car, Zap, BarChart3 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import StatusHeader from "@/components/StatusHeader";
import RiskPulse from "@/components/RiskPulse";
import TelemetryCard from "@/components/TelemetryCard";
import MicroLedger from "@/components/MicroLedger";
import PolicyCard from "@/components/PolicyCard";
import PolicyManagement from "@/components/PolicyManagement";
import ClaimsManagement from "@/components/ClaimsManagement";
import DynamicPricing from "@/components/DynamicPricing";
import { useAuth } from "@/hooks/useAuth";

const telemetry = [
  { icon: CloudRain, label: "Rainfall", value: "18.2", unit: "mm/hr", status: "critical" as const },
  { icon: Thermometer, label: "Temperature", value: "34", unit: "°C", status: "elevated" as const },
  { icon: Wind, label: "AQI", value: "187", unit: "index", status: "elevated" as const },
  { icon: Car, label: "Traffic", value: "Low", unit: "flow", status: "normal" as const },
];

interface RiskState {
  level: "normal" | "warning" | "critical";
  value: number;
  label: string;
}

const Index = () => {
  const { user, role } = useAuth();
  const navigate = useNavigate();
  const isWorker = role === "worker";
  const isAdmin = role === "admin";
  const [risk, setRisk] = useState<RiskState>({
    level: "warning",
    value: 72,
    label: "Heavy rainfall approaching threshold · AQI elevated",
  });

  const handleRiskUpdate = (riskScore: number) => {
    try {
      // Validate input
      if (typeof riskScore !== "number" || isNaN(riskScore)) {
        console.error("Invalid risk score:", riskScore);
        return;
      }

      // Clamp value between 0 and 1
      const clampedScore = Math.max(0, Math.min(1, riskScore));

      let level: "normal" | "warning" | "critical" = "normal";
      let label = "Conditions normal · Safe to operate";

      if (clampedScore <= 0.3) {
        level = "normal";
        label = "Risk score low · Optimal conditions for delivery";
      } else if (clampedScore <= 0.6) {
        level = "warning";
        label = "Risk score medium · Caution advised";
      } else {
        level = "critical";
        label = "Risk score high · Consider reducing hours";
      }

      setRisk({
        level,
        value: Math.round(clampedScore * 100),
        label,
      });
    } catch (error) {
      console.error("Error updating risk status:", error);
    }
  };

  const displayName =
    (user?.user_metadata?.full_name as string | undefined)?.trim()
    || user?.email?.split("@")[0]
    || "there";

  return (
    <div className="aurora-shell min-h-screen bg-background">
      <div className="pointer-events-none absolute -left-16 top-12 h-60 w-60 rounded-full bg-primary/15 blur-3xl drift-orb" />
      <div className="pointer-events-none absolute right-0 top-1/3 h-72 w-72 rounded-full bg-accent/12 blur-3xl drift-orb" />

      <div className="container relative max-w-6xl mx-auto px-4 pb-8">
        <div className="fade-up-enter" style={{ animationDelay: "30ms" }}>
          <StatusHeader />
        </div>

        {/* Dashboard Navigation */}
        <div className="fade-up-enter mt-3 flex items-center gap-2" style={{ animationDelay: "60ms" }}>
          <Button
            size="sm"
            variant="outline"
            className="bg-slate-900/70 text-slate-100 border-slate-600 hover:bg-slate-800"
            onClick={() => navigate("/")}
          >
            🏠 Overview
          </Button>
          {isWorker && (
            <Button
              size="sm"
              variant="outline"
              className="bg-indigo-900/60 text-indigo-100 border-indigo-400/50 hover:bg-indigo-900"
              onClick={() => navigate("/worker")}
            >
              <Zap className="w-4 h-4 mr-1" /> Worker Dashboard
            </Button>
          )}
          {isAdmin && (
            <Button
              size="sm"
              variant="outline"
              className="bg-amber-900/60 text-amber-100 border-amber-400/50 hover:bg-amber-900"
              onClick={() => navigate("/insurer")}
            >
              <BarChart3 className="w-4 h-4 mr-1" /> Insurer Analytics
            </Button>
          )}
        </div>

        <div className="fade-up-enter premium-surface premium-interactive mt-2 p-5" style={{ animationDelay: "90ms" }}>
          <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Welcome back</p>
          <h2 className="mt-1 text-2xl md:text-3xl font-bold tracking-tight">{displayName}</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Your risk, policies, and claims are now organized in one dashboard view.
          </p>
        </div>

        <div className="mt-6 grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
          <section className="lg:col-span-5 h-full dashboard-section space-y-6 fade-up-enter" style={{ animationDelay: "150ms" }}>
            <RiskPulse level={risk.level} value={risk.value} label={risk.label} />

            <DynamicPricing onRiskUpdate={handleRiskUpdate} />

            <div>
              <span className="data-label mb-3 block">Live Telemetry</span>
              <div className="grid grid-cols-2 gap-3">
                {telemetry.map((t, i) => (
                  <TelemetryCard key={t.label} {...t} index={i} />
                ))}
              </div>
            </div>

            <PolicyCard />
          </section>

          <section className="lg:col-span-7 h-full dashboard-section space-y-6 fade-up-enter" style={{ animationDelay: "210ms" }}>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <PolicyManagement />
              <ClaimsManagement />
            </div>

            <MicroLedger />
          </section>
        </div>

        <footer className="fade-up-enter premium-surface mt-8 p-3 text-center" style={{ animationDelay: "280ms" }}>
          <p className="text-[10px] text-muted-foreground uppercase tracking-[0.1em]">
            Your income, protected by the atmosphere.
          </p>
        </footer>
      </div>
    </div>
  );
};

export default Index;
