import { useState } from "react";
import { api, ApiError, STRATEGIES, STRATEGY_LABELS, type BenchmarkResult, type Strategy } from "../api";

export function ControlsPanel() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <EquityFloorControl />
      <StrategyControl />
      <BenchmarkControl />
    </div>
  );
}

function EquityFloorControl() {
  const [floor, setFloor] = useState(0.3);
  const [applied, setApplied] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const apply = async (value: number) => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.setEquityFloor(value);
      setApplied(res.equity_floor);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't update the equity floor.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="field-label">
        Equity floor &mdash; minimum guaranteed demand per zone before efficiency-maximizing allocation
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <input
          className="hard-slider"
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={floor}
          onChange={(e) => setFloor(Number(e.target.value))}
          onMouseUp={() => apply(floor)}
          onTouchEnd={() => apply(floor)}
        />
        <span style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 16, minWidth: 44, textAlign: "right" }}>
          {Math.round(floor * 100)}%
        </span>
      </div>
      <p style={{ fontSize: 11.5, opacity: 0.65, margin: "6px 0 0" }}>
        {busy
          ? "Applying…"
          : applied !== null
            ? `Active: every zone is guaranteed ${Math.round(applied * 100)}% of its demand before the remaining supply is allocated by efficiency. Re-trigger a demand spike to see it take effect.`
            : "Drag and release to apply -- then re-trigger a scenario to see small/remote zones stop being starved."}
      </p>
      {error && <div className="action-result err">{error}</div>}
    </div>
  );
}

function StrategyControl() {
  const [strategy, setStrategy] = useState<Strategy>("gnn_trained");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);

  const apply = async (next: Strategy) => {
    setStrategy(next);
    setBusy(true);
    setResult(null);
    try {
      await api.setStrategy(next);
      setResult({ ok: true, message: `Now allocating with: ${STRATEGY_LABELS[next]}.` });
    } catch (e) {
      setResult({ ok: false, message: e instanceof ApiError ? e.message : "Couldn't switch strategy." });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="field-label">Active allocation strategy</div>
      <select className="hard-select" value={strategy} disabled={busy} onChange={(e) => apply(e.target.value as Strategy)}>
        {STRATEGIES.map((s) => (
          <option key={s} value={s}>{STRATEGY_LABELS[s]}</option>
        ))}
      </select>
      {result && <div className={`action-result ${result.ok ? "ok" : "err"}`}>{result.message}</div>}
    </div>
  );
}

function BenchmarkControl() {
  const [data, setData] = useState<BenchmarkResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      setData(await api.benchmark());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Benchmark run failed.");
    } finally {
      setBusy(false);
    }
  };

  const bestServed = data ? Math.max(...Object.values(data.summary).map((s) => s.avg_served_demand_pct)) : null;

  return (
    <div>
      <div className="field-label">Trained policy vs. classical baselines</div>
      <button className="hard-button sm full tone-info" disabled={busy} onClick={run}>
        {busy ? "Running…" : "Run benchmark"}
      </button>
      {error && <div className="action-result err">{error}</div>}
      {data && (
        <div className="stat-grid" style={{ marginTop: 10 }}>
          {STRATEGIES.map((s) => {
            const stats = data.summary[s];
            if (!stats) return null;
            const isBest = stats.avg_served_demand_pct === bestServed;
            return (
              <div key={s} className={`stat-cell ${isBest ? "best" : ""}`}>
                <div className="num">{stats.avg_served_demand_pct.toFixed(1)}%</div>
                <div className="lbl">{STRATEGY_LABELS[s]}</div>
              </div>
            );
          })}
        </div>
      )}
      {data && (
        <p style={{ fontSize: 11, opacity: 0.6, margin: "8px 0 0" }}>
          Served demand %, averaged over {data.n_scenarios} held-out scenarios.
        </p>
      )}
    </div>
  );
}
