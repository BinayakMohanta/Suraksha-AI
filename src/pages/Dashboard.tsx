import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Shield, FileText, AlertTriangle, TrendingUp, Plus, DollarSign, Activity, TrendingDown, CheckCircle2 } from "lucide-react";
import { authenticatedFetch } from "@/lib/api-client";
import PolicyManagement from "@/components/PolicyManagement";

interface Policy {
  id: string;
  worker_name: string;
  policy_number: string;
  coverage_type: string;
  weekly_premium: number;
  active: boolean;
  notes?: string;
}

interface Claim {
  id: string;
  policy_id: string;
  title: string;
  description: string;
  claim_amount: number;
  status: string;
  admin_notes?: string;
}

interface FraudAnalysis {
  is_fraudulent: boolean;
  risk_score: number;
  flags: string[];
  reason: string;
  recommendation: string;
}

interface PayoutRecord {
  payout_id: string;
  status: string;
  amount: number;
  gateway: string;
  created_at: string;
}

export default function Dashboard() {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [payouts, setPayouts] = useState<PayoutRecord[]>([]);
  const [fraudAlerts, setFraudAlerts] = useState<Record<string, FraudAnalysis>>({});
  const [loading, setLoading] = useState(true);
  const [userRole, setUserRole] = useState<"worker" | "admin">("admin");

  const fetchPolicies = async () => {
    try {
      const response = await authenticatedFetch("/api/policies");
      const data = response.ok ? await response.json() : [];
      setPolicies(Array.isArray(data) ? data : []);
    } catch {
      setPolicies([]);
    }
  };

  const fetchClaims = async () => {
    try {
      const response = await authenticatedFetch("/api/claims");
      const data = response.ok ? await response.json() : [];
      setClaims(Array.isArray(data) ? data : []);
    } catch {
      setClaims([]);
    }
  };

  const fetchPayouts = async () => {
    try {
      const response = await authenticatedFetch("/api/payouts");
      if (response.ok) {
        const data = await response.json();
        setPayouts(data.payouts || []);
      }
    } catch {
      setPayouts([]);
    }
  };

  const [advScanResult, setAdvScanResult] = useState<any | null>(null);
  const [payoutSimResult, setPayoutSimResult] = useState<any | null>(null);

  const triggerAdvancedScan = async () => {
    try {
      const response = await authenticatedFetch('/api/fraud-advanced', { method: 'POST' });
      if (response.ok) {
        const data = await response.json();
        setAdvScanResult(data);
      }
    } catch (e) {
      console.error('Advanced scan error', e);
    }
  };

  const triggerPayoutSim = async () => {
    try {
      const response = await fetch('/api/payout-sim', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ max_count: 6, amount: 150 }) });
      if (response.ok) {
        const data = await response.json();
        setPayoutSimResult(data);
        await fetchPayouts();
      }
    } catch (e) {
      console.error('Payout sim error', e);
    }
  };

  const analyzeClaimFraud = async (claim: Claim) => {
    try {
      const response = await fetch("/api/fraud-check", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer mock-token",
        },
        body: JSON.stringify({
          claim: {
            id: claim.id,
            title: claim.title,
            description: claim.description,
            claim_amount: claim.claim_amount,
            delivery_location: "Downtown Area",
            weather_condition: "rainy",
            claim_date: new Date().toISOString().split("T")[0],
            claim_frequency: Math.floor(Math.random() * 5),
          },
          include_history: true,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setFraudAlerts((prev) => ({ ...prev, [claim.id]: data }));
      }
    } catch (error) {
      console.error("Fraud analysis error:", error);
    }
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchPolicies(), fetchClaims(), fetchPayouts()]);
      setLoading(false);
    };
    loadData();
  }, []);

  useEffect(() => {
    claims.forEach((claim) => analyzeClaimFraud(claim));
  }, [claims]);

  const activePolicies = useMemo(() => policies.filter((p) => p.active), [policies]);
  const totalCoverage = activePolicies.length * 100000;
  const monthlyPremium = activePolicies.reduce((sum, p) => sum + Number(p.weekly_premium || 0), 0) * 4;
  const totalPayoutsProcessed = payouts.reduce((sum, p) => sum + p.amount, 0);
  const successfulPayouts = payouts.filter((p) => p.status === "success").length;

  // Fraud Statistics
  const fraudulentClaims = Object.values(fraudAlerts).filter((a) => a.is_fraudulent).length;
  const averageRiskScore =
    Object.values(fraudAlerts).length > 0
      ? (Object.values(fraudAlerts).reduce((sum, a) => sum + a.risk_score, 0) /
          Object.values(fraudAlerts).length).toFixed(2)
      : "0.00";

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <header className="border-b bg-slate-950/80 backdrop-blur sticky top-0 z-40 shadow-lg">
        <div className="container flex items-center justify-between h-16">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-amber-400 to-amber-600 rounded-lg">
              <Shield className="h-6 w-6 text-white" />
            </div>
            <span className="font-display text-xl font-bold text-white">GigGuard Dashboard</span>
            <Badge className="bg-blue-600 hover:bg-blue-700 text-white border-0 font-bold">
              {userRole.toUpperCase()} VIEW
            </Badge>
          </div>
          <div className="flex items-center gap-3">
            <Button
              size="sm"
              className={userRole === "admin" ? "bg-gradient-to-r from-orange-600 to-red-600 hover:from-orange-700 hover:to-red-700 text-white border-0" : "bg-slate-700 hover:bg-slate-600 text-slate-100 border-0"}
              onClick={() => setUserRole("admin")}
            >
              Admin
            </Button>
            <Button
              size="sm"
              className={userRole === "worker" ? "bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white border-0" : "bg-slate-700 hover:bg-slate-600 text-slate-100 border-0"}
              onClick={() => setUserRole("worker")}
            >
              Worker
            </Button>
            <Button size="sm" className="bg-slate-700 hover:bg-slate-600 text-slate-100 border-0" asChild>
              <Link to="/">📊 Monitor</Link>
            </Button>
            <Button size="sm" className="bg-slate-700 hover:bg-slate-600 text-slate-100 border-0" asChild>
              <Link to="/auth">
                <FileText className="h-4 w-4 mr-1" /> Auth
              </Link>
            </Button>
          </div>
        </div>
      </header>

      <main className="container py-8 space-y-8">
        {userRole === "admin" ? (
          <AdminDashboard
            policies={policies}
            claims={claims}
            payouts={payouts}
            fraudAlerts={fraudAlerts}
            advScanResult={advScanResult}
            payoutSimResult={payoutSimResult}
            activePolicies={activePolicies}
            totalCoverage={totalCoverage}
            monthlyPremium={monthlyPremium}
            totalPayoutsProcessed={totalPayoutsProcessed}
            successfulPayouts={successfulPayouts}
            fraudulentClaims={fraudulentClaims}
            averageRiskScore={averageRiskScore}
            loading={loading}
            onRunAdvancedScan={triggerAdvancedScan}
            onRunPayoutSim={triggerPayoutSim}
          />
        ) : (
          <WorkerDashboard
            policies={policies}
            claims={claims}
            payouts={payouts}
            activePolicies={activePolicies}
            totalCoverage={totalCoverage}
            monthlyPremium={monthlyPremium}
            loading={loading}
          />
        )}
      </main>
    </div>
  );
}

function AdminDashboard({
  policies,
  claims,
  payouts,
  fraudAlerts,
  advScanResult,
  payoutSimResult,
  activePolicies,
  totalCoverage,
  monthlyPremium,
  totalPayoutsProcessed,
  successfulPayouts,
  fraudulentClaims,
  averageRiskScore,
  loading,
  onRunAdvancedScan,
  onRunPayoutSim,
}: any) {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-display font-bold">Admin Portal</h1>
        <p className="text-muted-foreground mt-1">
          Monitor claims, detect fraud, and process instant payouts.
        </p>
        <div className="mt-3 flex items-center gap-3">
          <Button size="sm" variant="outline" onClick={onRunAdvancedScan}>Run Advanced Fraud Scan</Button>
          <Button size="sm" variant="outline" onClick={onRunPayoutSim}>Simulate Payouts</Button>
          {advScanResult && (
            <div className="ml-4 text-sm text-muted-foreground">Last scan: {advScanResult.flagged_count}/{advScanResult.scanned} flagged</div>
          )}
        </div>
      </div>

      {/* KPI Cards */}
      <div className="flex items-center justify-between">
        <div className="grid grid-cols-1 md:grid-cols-6 gap-4 flex-1">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <Shield className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-2xl font-bold">{activePolicies.length}</p>
                <p className="text-xs text-muted-foreground">Active Policies</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-destructive/10">
                <AlertTriangle className="h-5 w-5 text-destructive" />
              </div>
              <div>
                <p className="text-2xl font-bold">{fraudulentClaims}</p>
                <p className="text-xs text-muted-foreground">Fraud Flags</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-warning/10">
                <Activity className="h-5 w-5 text-warning" />
              </div>
              <div>
                <p className="text-2xl font-bold">{averageRiskScore}</p>
                <p className="text-xs text-muted-foreground">Avg Risk Score</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-500/10">
                <DollarSign className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">₹{totalPayoutsProcessed.toLocaleString()}</p>
                <p className="text-xs text-muted-foreground">Total Payouts</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-success/10">
                <CheckCircle2 className="h-5 w-5 text-success" />
              </div>
              <div>
                <p className="text-2xl font-bold">{successfulPayouts}</p>
                <p className="text-xs text-muted-foreground">Successful Payouts</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/10">
                <TrendingUp className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{claims.length}</p>
                <p className="text-xs text-muted-foreground">Total Claims</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Fraud Detection Alerts */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg font-display">🚨 Fraud Detection Alerts</CardTitle>
          <CardDescription>Real-time fraud indicators and risk assessment</CardDescription>
        </CardHeader>
        <CardContent>
          {advScanResult && (
            <div className="mb-3 p-3 bg-yellow-50 rounded border">
              <p className="font-semibold">Advanced Scan: {advScanResult.flagged_count} flagged of {advScanResult.scanned}</p>
              <div className="text-xs mt-2">Last run: {new Date(advScanResult.timestamp).toLocaleString()}</div>
            </div>
          )}
          {loading ? (
            <p className="text-muted-foreground text-sm">Analyzing claims...</p>
          ) : Object.values(fraudAlerts).length === 0 ? (
            <p className="text-muted-foreground text-sm">No fraud analysis available.</p>
          ) : (
            <div className="space-y-3">
              {Object.entries(fraudAlerts)
                .filter(([, alert]) => alert.is_fraudulent)
                .map(([claimId, alert]) => (
                  <Alert
                    key={claimId}
                    className="border-red-300 bg-red-50"
                  >
                    <AlertTriangle className="h-4 w-4 text-red-600" />
                    <AlertDescription className="text-red-700 ml-2">
                      <div className="font-semibold">Fraud Risk Detected</div>
                      <p className="text-sm mt-1">{alert.reason}</p>
                      <div className="flex gap-2 mt-2 flex-wrap">
                        {alert.flags.map((flag) => (
                          <Badge key={flag} variant="secondary" className="text-xs bg-red-100 text-red-800">
                            {flag}
                          </Badge>
                        ))}
                      </div>
                      <p className="text-xs mt-2">
                        <strong>Recommendation:</strong> {alert.recommendation}
                      </p>
                    </AlertDescription>
                  </Alert>
                ))}
              {Object.values(fraudAlerts).filter(([f]) => !f).length > 0 && (
                <p className="text-sm text-green-700 bg-green-50 p-2 rounded">
                  ✓ {Object.values(fraudAlerts).filter((f) => !f.is_fraudulent).length} claims verified as legitimate
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recent Payouts */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg font-display">💰 Recent Payouts</CardTitle>
          <CardDescription>Instant payout transactions processed</CardDescription>
        </CardHeader>
        <CardContent>
          {payouts.length === 0 ? (
            <p className="text-muted-foreground text-sm">No payouts yet.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {payouts.slice(0, 4).map((payout) => (
                <div key={payout.payout_id} className="rounded-lg border p-3 bg-green-50">
                  <div className="flex items-center justify-between mb-2">
                    <p className="font-semibold">₹{payout.amount}</p>
                    <Badge className={payout.status === "success" ? "bg-green-600" : "bg-yellow-600"}>
                      {payout.status}
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {payout.gateway.toUpperCase()} • {new Date(payout.created_at).toLocaleDateString()}
                  </p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Saved Policies */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg font-display">Saved Policies</CardTitle>
          <CardDescription>Active insurance policies</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-muted-foreground text-sm">Loading policies...</p>
          ) : policies.length === 0 ? (
            <p className="text-muted-foreground text-sm">No policies yet.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {policies.slice(0, 9).map((policy) => (
                <div key={policy.id} className="rounded-lg border p-3">
                  <div className="flex items-center justify-between">
                    <p className="font-semibold">{policy.worker_name}</p>
                    <Badge variant="outline" className={policy.active ? "text-success border-success/20" : "text-muted-foreground"}>
                      {policy.active ? "active" : "inactive"}
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">{policy.policy_number}</p>
                  <p className="text-xs text-muted-foreground mt-1">₹{policy.weekly_premium}/week</p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <PolicyManagement />
    </div>
  );
}

function WorkerDashboard({
  policies,
  claims,
  payouts,
  activePolicies,
  totalCoverage,
  monthlyPremium,
  loading,
}: any) {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-display font-bold">My Coverage</h1>
        <p className="text-muted-foreground mt-1">
          Your earnings protection and active coverage at a glance.
        </p>
      </div>

      {/* Worker KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="border-2 border-green-200 bg-green-50">
          <CardContent className="pt-6">
            <div>
              <div>
                <p className="text-xs text-green-700 font-semibold">EARNINGS PROTECTED</p>
                <p className="text-3xl font-bold text-green-900 mt-2">₹{totalCoverage.toLocaleString()}</p>
                <p className="text-sm text-green-700 mt-1">{activePolicies.length} active policies</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-2 border-blue-200 bg-blue-50">
          <CardContent className="pt-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs text-blue-700 font-semibold">WEEKLY COVERAGE</p>
                <p className="text-3xl font-bold text-blue-900 mt-2">Active</p>
                <p className="text-sm text-blue-700 mt-1">₹{monthlyPremium.toLocaleString()}/month</p>
              </div>
              <CheckCircle2 className="h-8 w-8 text-blue-600" />
            </div>
          </CardContent>
        </Card>

        <Card className="border-2 border-purple-200 bg-purple-50">
          <CardContent className="pt-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs text-purple-700 font-semibold">PAYOUTS RECEIVED</p>
                <p className="text-3xl font-bold text-purple-900 mt-2">₹{payouts.reduce((sum, p) => sum + p.amount, 0).toLocaleString()}</p>
                <p className="text-sm text-purple-700 mt-1">{payouts.filter((p) => p.status === "success").length} successful</p>
              </div>
              <DollarSign className="h-8 w-8 text-purple-600" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Payouts for Worker */}
      {payouts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Recent Payouts</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {payouts.slice(0, 5).map((payout) => (
                <div key={payout.payout_id} className="flex items-center justify-between p-3 bg-muted rounded-lg">
                  <div>
                    <p className="font-semibold">₹{payout.amount}</p>
                    <p className="text-xs text-muted-foreground">{payout.gateway.toUpperCase()}</p>
                  </div>
                  <Badge className="bg-green-600">{payout.status}</Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* My Policies */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">My Insurance Policies</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-muted-foreground text-sm">Loading...</p>
          ) : activePolicies.length === 0 ? (
            <p className="text-muted-foreground text-sm">No active policies.</p>
          ) : (
            <div className="space-y-2">
              {activePolicies.map((policy) => (
                <div key={policy.id} className="p-3 border rounded-lg">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-semibold">{policy.coverage_type}</p>
                      <p className="text-sm text-muted-foreground">{policy.policy_number}</p>
                    </div>
                    <p className="font-bold text-lg">₹{policy.weekly_premium}/week</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
          </div>
          <div className="flex items-center gap-3">
            <Button variant="outline" size="sm" asChild>
              <Link to="/">Live Monitor</Link>
            </Button>
            <Button variant="outline" size="sm" asChild>
              <Link to="/auth">
                <FileText className="h-4 w-4 mr-1" /> Auth
              </Link>
            </Button>
}
