import { FormEvent, useEffect, useState } from "react";
import { AlertCircle, FileText, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { getSupabase } from "@/integrations/supabase/client";
import { useAuth } from "@/hooks/useAuth";

interface Policy {
  id: string;
  policy_number: string;
  worker_name: string;
}

interface Claim {
  id: string;
  policy_id: string;
  claim_number: string;
  title: string;
  description: string;
  claim_amount: number;
  status: string;
  admin_notes?: string;
}

const claimStatusStyles: Record<string, string> = {
  pending: "text-warning border-warning/20",
  under_review: "text-info border-info/20",
  approved: "text-success border-success/20",
  rejected: "text-destructive border-destructive/20",
};

const ClaimsManagement = () => {
  const { user, loading: authLoading } = useAuth();
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    policy_id: "",
    claim_number: "",
    title: "",
    description: "",
    claim_amount: "",
  });

  const authHeaders = async (includeJson = false) => {
    const headers: Record<string, string> = {};
    if (includeJson) headers["Content-Type"] = "application/json";
    const supabase = getSupabase();
    if (!supabase) return headers;
    const { data } = await supabase.auth.getSession();
    const token = data?.session?.access_token;
    if (token) headers.Authorization = `Bearer ${token}`;
    return headers;
  };

  const parseError = async (response: Response) => {
    const body = await response.json().catch(() => null);
    if (!body) return response.statusText || "Unknown error";
    if (typeof body.detail === "string") return body.detail;
    return JSON.stringify(body.detail || body);
  };

  const loadAll = async (preferredPolicyId?: string | null) => {
    setLoading(true);
    setError(null);
    try {
      const [policyRes, claimRes] = await Promise.all([
        fetch("/api/policies", { headers: await authHeaders() }),
        fetch("/api/claims", { headers: await authHeaders() }),
      ]);
      if (!policyRes.ok) throw new Error(await parseError(policyRes));
      if (!claimRes.ok) throw new Error(await parseError(claimRes));

      const policyData = await policyRes.json();
      const claimData = await claimRes.json();
      setPolicies(Array.isArray(policyData) ? policyData : []);
      setClaims(Array.isArray(claimData) ? claimData : []);
      setForm((prev) => {
        const availablePolicyIds = new Set((Array.isArray(policyData) ? policyData : []).map((p: Policy) => p.id));
        const nextPolicyId =
          (preferredPolicyId && availablePolicyIds.has(preferredPolicyId) && preferredPolicyId)
          || (prev.policy_id && availablePolicyIds.has(prev.policy_id) && prev.policy_id)
          || policyData?.[0]?.id
          || "";
        return { ...prev, policy_id: nextPolicyId };
      });
    } catch (err) {
      setError((err as Error).message || "Unable to load claims.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Wait for Supabase session to be resolved before first API call.
    if (authLoading) return;
    if (!user) {
      setPolicies([]);
      setClaims([]);
      return;
    }
    loadAll();
  }, [authLoading, user]);

  useEffect(() => {
    const onPoliciesChanged = (event: Event) => {
      const customEvent = event as CustomEvent<{ policyId?: string | null }>;
      const preferredPolicyId = customEvent?.detail?.policyId || null;
      loadAll(preferredPolicyId);
    };

    window.addEventListener("policies:changed", onPoliciesChanged);
    return () => {
      window.removeEventListener("policies:changed", onPoliciesChanged);
    };
  }, [authLoading, user]);

  const handleCreateClaim = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const payload = {
        policy_id: form.policy_id,
        claim_number: form.claim_number.trim(),
        title: form.title.trim(),
        description: form.description.trim(),
        claim_amount: Number(form.claim_amount),
        status: "pending",
        admin_notes: "",
      };

      const response = await fetch("/api/claims", {
        method: "POST",
        headers: await authHeaders(true),
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(await parseError(response));

      setForm({
        policy_id: form.policy_id,
        claim_number: "",
        title: "",
        description: "",
        claim_amount: "",
      });
      await loadAll();
    } catch (err) {
      setError((err as Error).message || "Failed to create claim.");
      setLoading(false);
    }
  };

  const handleDeleteClaim = async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/claims/${id}`, {
        method: "DELETE",
        headers: await authHeaders(),
      });
      if (!response.ok) throw new Error(await parseError(response));
      await loadAll();
    } catch (err) {
      setError((err as Error).message || "Failed to delete claim.");
      setLoading(false);
    }
  };

  return (
    <div className="safety-card premium-interactive p-5">
      <div className="flex items-center gap-2 mb-4">
        <AlertCircle className="w-4 h-4 text-primary" />
        <span className="data-label">Claims Management</span>
      </div>

      <form className="space-y-3" onSubmit={handleCreateClaim}>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <Label>Policy</Label>
            <Select value={form.policy_id} onValueChange={(value) => setForm({ ...form, policy_id: value })}>
              <SelectTrigger>
                <SelectValue placeholder="Select policy" />
              </SelectTrigger>
              <SelectContent>
                {policies.map((policy) => (
                  <SelectItem key={policy.id} value={policy.id}>{policy.policy_number} · {policy.worker_name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label>Claim Number</Label>
            <Input value={form.claim_number} onChange={(e) => setForm({ ...form, claim_number: e.target.value })} placeholder="CLM-0001" required />
          </div>
        </div>

        <div className="space-y-1">
          <Label>Title</Label>
          <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Accident damage" required />
        </div>

        <div className="space-y-1">
          <Label>Description</Label>
          <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Describe incident" required />
        </div>

        <div className="space-y-1">
          <Label>Claim Amount</Label>
          <Input type="number" min={0} value={form.claim_amount} onChange={(e) => setForm({ ...form, claim_amount: e.target.value })} required />
        </div>

        <Button className="w-full" type="submit" disabled={loading || policies.length === 0}>
          <FileText className="w-4 h-4 mr-2" /> Submit Claim
        </Button>
      </form>

      <div className="mt-5">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-semibold">Your Claims</span>
          <span className="text-xs text-muted-foreground">{claims.length} records</span>
        </div>

        {error ? <div className="rounded-lg border border-destructive/10 bg-destructive/5 p-3 text-sm text-destructive">{error}</div> : null}

        {loading ? (
          <div className="text-sm text-muted-foreground">Loading claims...</div>
        ) : claims.length === 0 ? (
          <div className="text-sm text-muted-foreground">No claims yet.</div>
        ) : (
          <div className="space-y-2">
            {claims.map((claim) => (
              <div key={claim.id} className="rounded-xl border p-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-semibold">{claim.title}</p>
                    <p className="text-sm text-muted-foreground">{claim.claim_number} · ₹{claim.claim_amount}</p>
                  </div>
                  <Badge variant="outline" className={claimStatusStyles[claim.status] || ""}>{claim.status}</Badge>
                </div>
                <p className="text-sm text-muted-foreground mt-2">{claim.description}</p>
                <div className="mt-3">
                  <Button variant="ghost" size="sm" className="text-destructive" onClick={() => handleDeleteClaim(claim.id)}>
                    <Trash2 className="w-4 h-4 mr-1" /> Delete
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ClaimsManagement;
