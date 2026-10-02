// REST client for the Scenario Injector, Ledger Explorer, and
// Equity/Strategy controls. Mirrors the WS URL resolution in App.tsx:
// dev talks to a separate backend port via VITE_WS_URL/.env.local,
// production is same-origin behind Vercel's /server/* rewrite (vercel.json).
function resolveApiBase(): string {
  const envUrl = import.meta.env.VITE_API_URL as string | undefined;
  if (envUrl) return envUrl.replace(/\/$/, "");

  const wsUrl = import.meta.env.VITE_WS_URL as string | undefined;
  if (wsUrl) {
    try {
      const u = new URL(wsUrl);
      u.protocol = u.protocol === "wss:" ? "https:" : "http:";
      u.pathname = "";
      return u.toString().replace(/\/$/, "");
    } catch {
      // fall through to same-origin default below
    }
  }

  return `${window.location.origin}/server`;
}

const API_BASE = resolveApiBase();

export class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError("Can't reach the RAAHAT backend -- is it running?");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      // non-JSON error body, keep statusText
    }
    throw new ApiError(detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export interface LedgerRecord {
  id: number;
  timestamp: number;
  prev_hash: string;
  hash: string;
  canonical_payload: string;
  description: string;
  from_stakeholder: string;
  to_stakeholder: string;
  stakeholder_type: string;
  resource: string | null;
  units: number;
  fund_amount: number;
}

export interface VerifyResult {
  valid: boolean;
  records_checked: number;
  break_at_id: number | null;
  reason: string | null;
}

export interface StrategyStats {
  avg_served_demand_pct: number;
  avg_reward: number;
  avg_travel_time: number;
  avg_equity_violation: number;
  all_capacity_valid: boolean;
}

export interface BenchmarkResult {
  per_scenario: Record<string, unknown[]>;
  summary: Record<string, StrategyStats>;
  n_scenarios: number;
}

export const STRATEGIES = ["gnn_trained", "greedy", "hungarian", "min_cost_flow"] as const;
export type Strategy = (typeof STRATEGIES)[number];

export const STRATEGY_LABELS: Record<Strategy, string> = {
  gnn_trained: "Trained GNN policy",
  greedy: "Greedy (nearest-available)",
  hungarian: "Hungarian (optimal assignment)",
  min_cost_flow: "Min-cost flow",
};

export const RESOURCE_TYPES = ["water", "medicine", "food", "blood"] as const;
export type ResourceType = (typeof RESOURCE_TYPES)[number];

// Client-side re-hash for the Ledger Explorer's "Verify Chain" button --
// genuinely recomputes SHA-256 in the browser (via WebCrypto) so verification
// isn't just "trust the server's /ledger/verify boolean." The server sends
// `canonical_payload`, the exact byte string it hashed (see
// backend/app/ledger/store.py's `canonical_payload`) -- the client does not
// reconstruct this string itself, because JSON can't distinguish a Python
// int from a float (e.g. a donor's flat `150000` vs a computed `3750.0`),
// so a from-scratch client reconstruction would misformat numbers and
// produce false tamper alarms on perfectly valid records. Hashing is still
// fully independent: a server that lied about `canonical_payload` to hide
// tampering would have to lie consistently to both this check and anyone
// re-deriving it from `/ledger`'s other fields, which is the same trust
// boundary any hash-chain verifier has against a fully compromised server.
async function sha256Hex(message: string): Promise<string> {
  const bytes = new TextEncoder().encode(message);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export async function recomputeRecordHash(record: LedgerRecord): Promise<string> {
  return sha256Hex(record.canonical_payload);
}

export const api = {
  demandSpike: (zone_id: string, resource: string, amount: number) =>
    request<{ ok: true; event: unknown }>("/scenario/demand-spike", {
      method: "POST",
      body: JSON.stringify({ zone_id, resource, amount }),
    }),
  roadBlock: (u: string, v: string) =>
    request<{ ok: true; event: unknown }>("/scenario/road-block", {
      method: "POST",
      body: JSON.stringify({ u, v }),
    }),
  hospitalCapacityDrop: (hospital_id: string, beds: number) =>
    request<{ ok: true; event: unknown }>("/scenario/hospital-capacity-drop", {
      method: "POST",
      body: JSON.stringify({ hospital_id, beds }),
    }),
  depotDepletion: (depot_id: string, resource: string, amount?: number) =>
    request<{ ok: true; event: unknown }>("/scenario/depot-depletion", {
      method: "POST",
      body: JSON.stringify({ depot_id, resource, amount: amount ?? null }),
    }),
  setEquityFloor: (floor: number) =>
    request<{ ok: true; equity_floor: number }>("/equity-floor", {
      method: "POST",
      body: JSON.stringify({ floor }),
    }),
  setStrategy: (strategy: Strategy) =>
    request<{ ok: true; active_strategy: Strategy }>("/strategy", {
      method: "POST",
      body: JSON.stringify({ strategy }),
    }),
  ledger: (limit = 25) => request<LedgerRecord[]>(`/ledger?limit=${limit}`),
  verifyLedger: () => request<VerifyResult>("/ledger/verify"),
  corruptRecord: (id: number) => request<{ ok: true; corrupted_record_id: number }>(`/ledger/_debug_corrupt/${id}`, { method: "POST" }),
  benchmark: () => request<BenchmarkResult>("/benchmark"),
};
