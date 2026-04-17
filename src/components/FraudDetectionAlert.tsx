import React, { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertTriangle, Check, Clock, DollarSign } from "lucide-react";
import { getAuthToken } from "@/lib/api-client";

interface FraudAnalysis {
  is_fraudulent: boolean;
  risk_score: number;
  flags: string[];
  reason: string;
  recommendation: string;
}

interface PayoutTransaction {
  payout_id: string;
  status: string;
  amount: number;
  gateway: string;
  transaction_details: Record<string, any>;
  created_at: string;
}

export const FraudDetectionAlert: React.FC<{ claim: any }> = ({ claim }) => {
  const [analysis, setAnalysis] = useState<FraudAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    analyzeClaim();
  }, [claim]);

  const analyzeClaim = async () => {
    if (!claim) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const token = await getAuthToken();
      
      const response = await fetch("/api/fraud-check", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          claim,
          include_history: true,
        }),
      });

      if (!response.ok) throw new Error("Fraud analysis failed");
      
      const data = await response.json();
      setAnalysis(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Card className="border-yellow-200 bg-yellow-50">
        <CardContent className="pt-6">
          <p className="text-sm text-yellow-800">Analyzing claim for fraud indicators...</p>
        </CardContent>
      </Card>
    );
  }

  if (!analysis) return null;

  const isHighRisk = analysis.risk_score > 0.7;
  const isPaidOut = claim?.status === "paid_out";
  const displayReason = isPaidOut
    ? "Claim already processed and paid out"
    : analysis.reason;
  const displayRecommendation = isPaidOut
    ? "Already Done"
    : analysis.recommendation;
  const displayFlags = analysis.flags.map((flag) => {
    if (flag.toLowerCase().startsWith("duplicate alert:")) {
      return "Already submitted earlier by this worker.";
    }
    return flag;
  });

  return (
    <Alert
      className={`border-2 ${
        analysis.is_fraudulent
          ? isHighRisk
            ? "border-red-300 bg-red-50"
            : "border-orange-300 bg-orange-50"
          : "border-green-300 bg-green-50"
      }`}
    >
      <div className="flex items-start gap-3">
        {analysis.is_fraudulent ? (
          <AlertTriangle
            className={`h-5 w-5 ${isHighRisk ? "text-red-600" : "text-orange-600"}`}
          />
        ) : (
          <Check className="h-5 w-5 text-green-600" />
        )}
        <div className="flex-1">
          <AlertDescription
            className={`${
              analysis.is_fraudulent
                ? isHighRisk
                  ? "text-red-800"
                  : "text-orange-800"
                : "text-green-800"
            } break-words`}
          >
            <div className="font-semibold mb-2">{displayReason}</div>
            
            {/* Risk Score */}
            <div className="mb-2">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium">Risk Score</span>
                <span className={`text-sm font-bold ${
                  isHighRisk ? "text-red-600" : "text-orange-600"
                }`}>
                  {(analysis.risk_score * 100).toFixed(0)}%
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${
                    isHighRisk ? "bg-red-600" : "bg-orange-500"
                  }`}
                  style={{ width: `${analysis.risk_score * 100}%` }}
                />
              </div>
            </div>

            {/* Flags */}
            {displayFlags.length > 0 && (
              <div className="mb-2">
                <p className="text-sm font-medium mb-1">Detected Indicators:</p>
                <div className="space-y-1.5">
                  {displayFlags.map((flag, index) => (
                    <div
                      key={`${flag}-${index}`}
                      className="rounded-md border border-green-300/50 bg-white/60 px-2 py-1 text-xs leading-snug break-all"
                    >
                      {flag}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recommendation */}
            <div className="mt-3 p-2 bg-white/50 rounded text-sm">
              <strong>Recommendation:</strong> {displayRecommendation}
            </div>
          </AlertDescription>
        </div>
      </div>
    </Alert>
  );
};

export const PayoutBannerEnhanced: React.FC<{ claim: any }> = ({ claim }) => {
  const [payoutStatus, setPayoutStatus] = useState<PayoutTransaction | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const parseError = async (response: Response) => {
    const body = await response.json().catch(() => null);
    if (!body) return response.statusText || "Unknown error";
    if (typeof body.detail === "string") return body.detail;
    return JSON.stringify(body.detail || body);
  };

  const getRecipientIdentifier = (gateway: "upi" | "razorpay" | "stripe") => {
    if (gateway === "razorpay") return "123456789012";
    if (gateway === "stripe") return "tok_visa";
    return "worker@example.upi";
  };

  const processPayout = async (gateway: "upi" | "razorpay" | "stripe") => {
    setLoading(true);
    setError(null);
    
    try {
      const token = await getAuthToken();

      const response = await fetch("/api/payouts", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          claim_id: claim.id,
          amount: claim.claim_amount,
          recipient_identifier: getRecipientIdentifier(gateway),
          gateway,
        }),
      });

      if (!response.ok) throw new Error(await parseError(response));
      
      const data = await response.json();

      // Backend may return HTTP 200 with a failed payout status.
      if (data?.status === "failed") {
        const backendError = data?.transaction_details?.error;
        throw new Error(backendError || "Payout failed");
      }

      setPayoutStatus(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  if (payoutStatus) {
    const normalizedStatus = (payoutStatus.status || "").toLowerCase();
    const isSuccess = normalizedStatus === "success";
    const isInFlight = normalizedStatus === "processing" || normalizedStatus === "pending";
    const accent = isSuccess ? "green" : isInFlight ? "blue" : "red";

    return (
      <Card
        className={`border-2 ${
          accent === "green"
            ? "border-green-300 bg-green-50"
            : accent === "blue"
            ? "border-blue-300 bg-blue-50"
            : "border-red-300 bg-red-50"
        }`}
      >
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <DollarSign className={`h-5 w-5 ${accent === "green" ? "text-green-600" : accent === "blue" ? "text-blue-600" : "text-red-600"}`} />
            <CardTitle className={accent === "green" ? "text-green-800" : accent === "blue" ? "text-blue-800" : "text-red-800"}>
              {isSuccess ? "Payout Successful" : isInFlight ? "Payout In Progress" : "Payout Failed"}
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className={`space-y-2 text-sm ${accent === "green" ? "text-green-700" : accent === "blue" ? "text-blue-700" : "text-red-700"}`}>
            <p><strong>Payout ID:</strong> {payoutStatus.payout_id}</p>
            <p><strong>Amount:</strong> ₹{payoutStatus.amount}</p>
            <p><strong>Gateway:</strong> {payoutStatus.gateway.toUpperCase()}</p>
            <p>
              <strong>Status:</strong>{" "}
              <Badge className={`ml-2 ${accent === "green" ? "bg-green-600" : accent === "blue" ? "bg-blue-600" : "bg-red-600"}`}>
                {payoutStatus.status}
              </Badge>
            </p>
            
            {payoutStatus.transaction_details.settlement_time && (
              <p><strong>Expected Settlement:</strong> {payoutStatus.transaction_details.settlement_time}</p>
            )}
            
            {payoutStatus.transaction_details.rrn && (
              <p className="font-mono text-xs"><strong>RRN:</strong> {payoutStatus.transaction_details.rrn}</p>
            )}

            {payoutStatus.transaction_details.error && (
              <p><strong>Error:</strong> {payoutStatus.transaction_details.error}</p>
            )}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-2 border-blue-200 bg-blue-50/90 shadow-sm">
      <CardHeader className="pb-2 sm:pb-3">
        <CardTitle className="text-blue-900 text-xl sm:text-2xl leading-tight">Ready for Instant Payout</CardTitle>
        <CardDescription className="text-blue-700">
          Claim approved. Process instant payout to worker account.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="text-sm">
            <p className="font-semibold text-blue-900 mb-2">Payout Options:</p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              {[
                { label: "UPI", value: "upi" as const },
                { label: "Razorpay", value: "razorpay" as const },
                { label: "Stripe", value: "stripe" as const },
              ].map((gateway) => (
                <Button
                  key={gateway.value}
                  variant="outline"
                  size="sm"
                  disabled={loading}
                  onClick={() => processPayout(gateway.value)}
                  className={`w-full border-blue-300 text-blue-700 hover:bg-blue-100 bg-white/60 ${
                    loading ? "opacity-50 cursor-not-allowed" : ""
                  }`}
                >
                  {loading ? <Clock className="h-4 w-4 animate-spin" /> : gateway.label}
                </Button>
              ))}
            </div>
          </div>

          {error && (
            <Alert className="border-red-200 bg-red-50">
              <AlertDescription className="text-red-700">
                {error}
              </AlertDescription>
            </Alert>
          )}

          <div className="bg-white/60 p-3 rounded-md text-sm text-blue-900 border border-blue-100">
            <p>Amount: <strong>₹{claim.claim_amount}</strong></p>
            <p className="text-blue-700 mt-1">Simulates instant transfer - Test mode active</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default FraudDetectionAlert;
