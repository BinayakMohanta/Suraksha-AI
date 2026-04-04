import { FormEvent, useEffect, useState } from "react";
import { PlusCircle, Shield, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getSupabase } from "@/integrations/supabase/client";

interface Policy {
  id: string;
  worker_name: string;
  policy_number: string;
  coverage_type: string;
  weekly_premium: number;
  active: boolean;
  notes?: string;
  updated_at?: string;
}

const coverageOptions = [
  "Basic Coverage",
  "Standard Coverage",
  "Extended Coverage",
];

const PolicyManagement = () => {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [selectedPolicyId, setSelectedPolicyId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    worker_name: "",
    policy_number: "",
    coverage_type: coverageOptions[0],
    weekly_premium: "45",
    notes: "",
  });

  const defaultPremiumForCoverage = (coverageType: string) => {
    if (coverageType === "Extended Coverage") {
      return "65";
    }
    if (coverageType === "Standard Coverage") {
      return "55";
    }
    return "45";
  };

  const handleCoverageChange = (value: string) => {
    setForm({
      ...form,
      coverage_type: value,
      weekly_premium: defaultPremiumForCoverage(value),
    });
  };

  const parseError = async (response: Response) => {
    const body = await response.json().catch(() => null);
    if (!body) {
      return response.statusText || "Unknown error";
    }

    if (body.detail) {
      if (typeof body.detail === "string") {
        return body.detail;
      }
      if (Array.isArray(body.detail)) {
        return body.detail
          .map(item => (typeof item === "string" ? item : JSON.stringify(item)))
          .join("; ");
      }
      return JSON.stringify(body.detail);
    }

    return JSON.stringify(body);
  };

  const authHeaders = async (includeJsonContentType = false) => {
    const headers: Record<string, string> = {};
    if (includeJsonContentType) {
      headers["Content-Type"] = "application/json";
    }
    const supabase = getSupabase();
    if (!supabase) return headers;
    const { data } = await supabase.auth.getSession();
    const token = data?.session?.access_token;
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    return headers;
  };

  const fetchPolicies = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch("/api/policies", {
        headers: await authHeaders(),
      });
      if (!response.ok) {
        const message = await parseError(response);
        throw new Error(message || "Failed to load insurance policies.");
      }
      const data = await response.json();
      setPolicies(data);
      setSelectedPolicyId(null);
    } catch (err) {
      setError((err as Error).message || "Unable to load policies.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPolicies();
  }, []);

  useEffect(() => {
    if (selectedPolicyId && !policies.find(policy => policy.id === selectedPolicyId)) {
      setSelectedPolicyId(null);
    }
  }, [policies, selectedPolicyId]);

  const latestPolicy = policies[0] ?? null;
  const selectedOtherPolicy =
    selectedPolicyId && latestPolicy?.id !== selectedPolicyId
      ? policies.find(policy => policy.id === selectedPolicyId) ?? null
      : null;

  const resetForm = () => {
    setForm({
      worker_name: "",
      policy_number: "",
      coverage_type: coverageOptions[0],
      weekly_premium: defaultPremiumForCoverage(coverageOptions[0]),
      notes: "",
    });
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const payload = {
        worker_name: form.worker_name.trim(),
        policy_number: form.policy_number.trim(),
        coverage_type: form.coverage_type,
        weekly_premium: Number(form.weekly_premium),
        active: true,
        notes: form.notes.trim(),
      };

      const response = await fetch("/api/policies", {
        method: "POST",
        headers: await authHeaders(true),
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const message = await parseError(response);
        throw new Error(message || "Unable to create policy.");
      }

      const createdPolicy = await response.json().catch(() => null);

      resetForm();
      await fetchPolicies();
      window.dispatchEvent(
        new CustomEvent("policies:changed", {
          detail: { action: "created", policyId: createdPolicy?.id || null },
        })
      );
    } catch (err) {
      setError((err as Error).message || "Failed to save policy.");
    } finally {
      setLoading(false);
    }
  };

  const toggleActive = async (policy: Policy) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/policies/${policy.id}`, {
        method: "PUT",
        headers: await authHeaders(true),
        body: JSON.stringify({ active: !policy.active }),
      });

      if (!response.ok) {
        const message = await parseError(response);
        throw new Error(message || "Unable to update policy status.");
      }

      await fetchPolicies();
      window.dispatchEvent(
        new CustomEvent("policies:changed", {
          detail: { action: "updated", policyId: policy.id },
        })
      );
    } catch (err) {
      setError((err as Error).message || "Failed to update policy.");
    } finally {
      setLoading(false);
    }
  };

  const deletePolicy = async (policyId: string) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/policies/${policyId}`, {
        method: "DELETE",
        headers: await authHeaders(),
      });

      if (!response.ok) {
        const message = await parseError(response);
        throw new Error(message || "Unable to delete policy.");
      }

      await fetchPolicies();
      window.dispatchEvent(
        new CustomEvent("policies:changed", {
          detail: { action: "deleted", policyId },
        })
      );
    } catch (err) {
      setError((err as Error).message || "Failed to delete policy.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="safety-card premium-interactive p-5">
      <div className="flex items-center gap-2 mb-4">
        <Shield className="w-4 h-4 text-primary" />
        <span className="data-label">Insurance Policy Management</span>
      </div>

      <form className="space-y-4" onSubmit={handleSubmit}>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="space-y-1">
            <span className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Worker name</span>
            <Input
              value={form.worker_name}
              onChange={event => setForm({ ...form, worker_name: event.target.value })}
              placeholder="Name of delivery worker"
              required
            />
          </label>

          <label className="space-y-1">
            <span className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Policy number</span>
            <Input
              value={form.policy_number}
              onChange={event => setForm({ ...form, policy_number: event.target.value })}
              placeholder="POL-12345"
              required
            />
          </label>

          <label className="space-y-1">
            <span className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Coverage</span>
            <Select value={form.coverage_type} onValueChange={handleCoverageChange}>
              <SelectTrigger aria-label="Coverage type">
                <SelectValue placeholder="Choose coverage" />
              </SelectTrigger>
              <SelectContent>
                {coverageOptions.map(option => (
                  <SelectItem key={option} value={option}>
                    {option}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </label>

          <label className="space-y-1">
            <span className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Weekly premium</span>
            <Input
              type="number"
              min={0}
              step={0.5}
              inputMode="decimal"
              value={form.weekly_premium}
              onChange={event => setForm({ ...form, weekly_premium: event.target.value })}
              required
            />
          </label>
        </div>

        <label className="space-y-1">
          <span className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Notes</span>
          <Textarea
            value={form.notes}
            onChange={event => setForm({ ...form, notes: event.target.value })}
            placeholder="Optional policy details"
          />
        </label>

        <Button className="w-full" type="submit" disabled={loading}>
          <PlusCircle className="w-4 h-4 mr-2" />
          Save policy
        </Button>
      </form>

      <div className="mt-5">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-semibold">Current policies</span>
          <span className="text-xs text-muted-foreground">{policies.length} records</span>
        </div>

        {error ? (
          <div className="rounded-lg border border-destructive/10 bg-destructive/5 p-3 text-sm text-destructive">{error}</div>
        ) : null}

        {loading ? (
          <div className="text-sm text-muted-foreground">Loading policies…</div>
        ) : policies.length === 0 ? (
          <div className="text-sm text-muted-foreground">No policies available yet.</div>
        ) : (
          <div className="space-y-4">
            <div className="space-y-2">
              <span className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Latest policy</span>
              {latestPolicy ? (
                <div className="rounded-xl border p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2 text-sm font-semibold">
                        <Shield className="w-4 h-4 text-primary" />
                        <span>{latestPolicy.coverage_type}</span>
                      </div>
                      <p className="text-lg font-semibold">{latestPolicy.worker_name}</p>
                      <p className="text-sm text-muted-foreground">{latestPolicy.policy_number}</p>
                    </div>

                    <div className="text-right text-sm">
                      <div className="font-semibold">₹{latestPolicy.weekly_premium}</div>
                      <div className={latestPolicy.active ? "text-success" : "text-destructive"}>
                        {latestPolicy.active ? "Active" : "Inactive"}
                      </div>
                    </div>
                  </div>

                  {latestPolicy.notes ? <p className="mt-3 text-sm text-muted-foreground">{latestPolicy.notes}</p> : null}

                  <div className="mt-4 flex flex-wrap gap-2">
                    <Button variant="outline" size="sm" type="button" onClick={() => toggleActive(latestPolicy)}>
                      {latestPolicy.active ? "Disable" : "Enable"}
                    </Button>
                    <Button variant="ghost" size="sm" className="text-destructive" type="button" onClick={() => deletePolicy(latestPolicy.id)}>
                      <Trash2 className="w-4 h-4 mr-2" />
                      Delete
                    </Button>
                  </div>
                </div>
              ) : null}
            </div>

            {policies.length > 1 ? (
              <div className="space-y-2">
                <span className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Other saved policies</span>
                <Select value={selectedPolicyId ?? ""} onValueChange={value => setSelectedPolicyId(value)}>
                  <SelectTrigger aria-label="Select a different policy">
                    <SelectValue placeholder="Choose another policy" />
                  </SelectTrigger>
                  <SelectContent>
                    {policies.slice(1).map(policy => (
                      <SelectItem key={policy.id} value={policy.id}>
                        {`${policy.policy_number} • ${policy.worker_name}`}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ) : null}

            {selectedOtherPolicy ? (
              <div className="rounded-xl border p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 text-sm font-semibold">
                      <Shield className="w-4 h-4 text-primary" />
                      <span>{selectedOtherPolicy.coverage_type}</span>
                    </div>
                    <p className="text-lg font-semibold">{selectedOtherPolicy.worker_name}</p>
                    <p className="text-sm text-muted-foreground">{selectedOtherPolicy.policy_number}</p>
                  </div>

                  <div className="text-right text-sm">
                    <div className="font-semibold">₹{selectedOtherPolicy.weekly_premium}</div>
                    <div className={selectedOtherPolicy.active ? "text-success" : "text-destructive"}>
                      {selectedOtherPolicy.active ? "Active" : "Inactive"}
                    </div>
                  </div>
                </div>

                {selectedOtherPolicy.notes ? <p className="mt-3 text-sm text-muted-foreground">{selectedOtherPolicy.notes}</p> : null}

                <div className="mt-4 flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" type="button" onClick={() => toggleActive(selectedOtherPolicy)}>
                    {selectedOtherPolicy.active ? "Disable" : "Enable"}
                  </Button>
                  <Button variant="ghost" size="sm" className="text-destructive" type="button" onClick={() => deletePolicy(selectedOtherPolicy.id)}>
                    <Trash2 className="w-4 h-4 mr-2" />
                    Delete
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
};

export default PolicyManagement;
