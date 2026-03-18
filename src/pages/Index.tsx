import { CloudRain, Thermometer, Wind, Car } from "lucide-react";
import StatusHeader from "@/components/StatusHeader";
import RiskPulse from "@/components/RiskPulse";
import PayoutBanner from "@/components/PayoutBanner";
import TelemetryCard from "@/components/TelemetryCard";
import MicroLedger from "@/components/MicroLedger";
import PolicyCard from "@/components/PolicyCard";

const telemetry = [
  { icon: CloudRain, label: "Rainfall", value: "18.2", unit: "mm/hr", status: "critical" as const },
  { icon: Thermometer, label: "Temperature", value: "34", unit: "°C", status: "elevated" as const },
  { icon: Wind, label: "AQI", value: "187", unit: "index", status: "elevated" as const },
  { icon: Car, label: "Traffic", value: "Low", unit: "flow", status: "normal" as const },
];

const Index = () => {
  return (
    <div className="min-h-screen bg-background">
      <div className="container max-w-lg mx-auto px-4 pb-8">
        <StatusHeader />
        
        <div className="mt-2">
          <PayoutBanner />
        </div>

        <div className="mt-6">
          <RiskPulse level="warning" value={72} label="Heavy rainfall approaching threshold · AQI elevated" />
        </div>

        <div className="mt-6">
          <span className="data-label mb-3 block">Live Telemetry</span>
          <div className="grid grid-cols-2 gap-3">
            {telemetry.map((t, i) => (
              <TelemetryCard key={t.label} {...t} index={i} />
            ))}
          </div>
        </div>

        <div className="mt-6">
          <PolicyCard />
        </div>

        <div className="mt-6">
          <MicroLedger />
        </div>

        <footer className="mt-8 text-center">
          <p className="text-[10px] text-muted-foreground uppercase tracking-[0.1em]">
            Your income, protected by the atmosphere.
          </p>
        </footer>
      </div>
    </div>
  );
};

export default Index;
