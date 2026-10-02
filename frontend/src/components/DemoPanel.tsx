import { useState } from "react";
import { api, ApiError, DEMO_SCENARIOS, type DemoScenarioName, type DemoScenarioResult } from "../api";

function formatResult(r: DemoScenarioResult): string {
  if (r.scenario === "hospital_cascade") {
    const off = r.equity_floor_off as { served_pct: number };
    const on = r.equity_floor_on as { served_pct: number };
    return `Hospital ${r.hospital_id} pushed toward capacity. Under genuine scarcity, zone ${r.vulnerable_zone_id} served ${off.served_pct.toFixed(0)}% with the equity floor OFF vs ${on.served_pct.toFixed(0)}% with it ON.`;
  }
  if (r.scenario === "road_block_reroute") {
    const servedPct = r.served_pct as number;
    return `Blocked ${r.blocked_edge}. Zone ${r.zone_id}'s spike was still ${servedPct.toFixed(0)}% served -- rerouted via a longer path instead of failing.`;
  }
  const servedPct = r.served_pct as number;
  return `Zone ${r.zone_id} spiked (+${(r.amount as number).toFixed(0)} units ${r.resource}) -- ${servedPct.toFixed(0)}% served in ${(r.elapsed_ms as number).toFixed(0)}ms.`;
}

export function DemoPanel() {
  const [running, setRunning] = useState<DemoScenarioName | null>(null);
  const [results, setResults] = useState<Partial<Record<DemoScenarioName, { ok: boolean; summary: string }>>>({});

  const run = async (id: DemoScenarioName) => {
    setRunning(id);
    setResults((prev) => ({ ...prev, [id]: undefined }));
    try {
      const r = await api.runDemoScenario(id);
      setResults((prev) => ({ ...prev, [id]: { ok: true, summary: formatResult(r) } }));
    } catch (e) {
      setResults((prev) => ({
        ...prev,
        [id]: { ok: false, summary: e instanceof ApiError ? e.message : "Scenario failed to run." },
      }));
    } finally {
      setRunning(null);
    }
  };

  return (
    <div>
      <div className="field-label" style={{ marginBottom: 10 }}>
        Scripted demo scenarios -- one click, real allocation decisions
      </div>
      {DEMO_SCENARIOS.map((s) => {
        const result = results[s.id];
        return (
          <div key={s.id} className="demo-scenario-card">
            <div className="title">{s.label}</div>
            <div className="blurb">{s.blurb}</div>
            <button
              className="hard-button sm full tone-relief"
              disabled={running !== null}
              onClick={() => run(s.id)}
            >
              {running === s.id ? "Running…" : "Run scenario"}
            </button>
            {result && <div className={`action-result ${result.ok ? "ok" : "err"}`}>{result.summary}</div>}
          </div>
        );
      })}
      <p style={{ fontSize: 10.5, opacity: 0.55, margin: "4px 0 0" }}>
        Each scenario drives the real simulation through the Supervisor's full pipeline --
        watch the map and Allocation Feed (left) react live.
      </p>
    </div>
  );
}
