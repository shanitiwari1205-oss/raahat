import { useMemo, useState, type ReactNode } from "react";
import { api, ApiError, RESOURCE_TYPES, type ResourceType } from "../api";
import type { WorldSnapshot } from "../store";

type ActionResult = { ok: boolean; message: string } | null;

function ResultBanner({ result }: { result: ActionResult }) {
  if (!result) return null;
  return <div className={`action-result ${result.ok ? "ok" : "err"}`}>{result.message}</div>;
}

function useBusyResult() {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ActionResult>(null);
  const run = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(true);
    setResult(null);
    try {
      await fn();
      setResult({ ok: true, message: `${label} -- sent. Watch the map and Allocation Feed.` });
    } catch (e) {
      setResult({ ok: false, message: e instanceof ApiError ? e.message : `${label} failed.` });
    } finally {
      setBusy(false);
    }
  };
  return { busy, result, run };
}

export function ScenarioInjector({ world }: { world: WorldSnapshot | null }) {
  if (!world) {
    return <div style={{ fontSize: 13, opacity: 0.6 }}>Waiting for live world state&hellip;</div>;
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <DemandSpikeForm world={world} />
      <RoadBlockForm world={world} />
      <HospitalCapacityForm world={world} />
      <DepotDepletionForm world={world} />
    </div>
  );
}

function FieldGroup({ children }: { children: ReactNode }) {
  return <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>{children}</div>;
}

function DemandSpikeForm({ world }: { world: WorldSnapshot }) {
  const [zoneId, setZoneId] = useState(world.zones[0]?.id ?? "");
  const [resource, setResource] = useState<ResourceType>("water");
  const [amount, setAmount] = useState(40);
  const { busy, result, run } = useBusyResult();

  return (
    <div>
      <div className="field-label">Spike demand in a zone</div>
      <FieldGroup>
        <select className="hard-select" value={zoneId} onChange={(e) => setZoneId(e.target.value)}>
          {world.zones.map((z) => (
            <option key={z.id} value={z.id}>
              {z.id} &mdash; pop. {z.population.toLocaleString()} (urgency {(z.urgency * 100).toFixed(0)}%)
            </option>
          ))}
        </select>
        <div style={{ display: "flex", gap: 8 }}>
          <select className="hard-select" value={resource} onChange={(e) => setResource(e.target.value as ResourceType)}>
            {RESOURCE_TYPES.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
          <input
            className="hard-input"
            type="number"
            min={1}
            style={{ width: 90 }}
            value={amount}
            onChange={(e) => setAmount(Number(e.target.value))}
          />
        </div>
        <button
          className="hard-button sm full tone-alert"
          disabled={busy || !zoneId}
          onClick={() => run("Demand spike", () => api.demandSpike(zoneId, resource, amount))}
        >
          {busy ? "Sending…" : "Trigger demand spike"}
        </button>
      </FieldGroup>
      <ResultBanner result={result} />
    </div>
  );
}

function RoadBlockForm({ world }: { world: WorldSnapshot }) {
  const options = useMemo(
    () => world.roads.filter((r) => !r.blocked).map((r) => ({ key: `${r.u}|${r.v}`, label: `${r.u} → ${r.v}`, u: r.u, v: r.v })),
    [world.roads],
  );
  const [selected, setSelected] = useState(options[0]?.key ?? "");
  const { busy, result, run } = useBusyResult();
  const blockedCount = world.roads.length - options.length;

  if (options.length === 0) {
    return (
      <div>
        <div className="field-label">Block a road</div>
        <div style={{ fontSize: 12, opacity: 0.6 }}>All {world.roads.length} roads are already blocked.</div>
      </div>
    );
  }

  return (
    <div>
      <div className="field-label">Block a road {blockedCount > 0 ? `(${blockedCount} already blocked)` : ""}</div>
      <FieldGroup>
        <select className="hard-select" value={selected} onChange={(e) => setSelected(e.target.value)}>
          {options.map((o) => (
            <option key={o.key} value={o.key}>{o.label}</option>
          ))}
        </select>
        <button
          className="hard-button sm full tone-alert"
          disabled={busy || !selected}
          onClick={() => {
            const opt = options.find((o) => o.key === selected);
            if (!opt) return;
            run("Road block", () => api.roadBlock(opt.u, opt.v));
          }}
        >
          {busy ? "Sending…" : "Block this road"}
        </button>
      </FieldGroup>
      <ResultBanner result={result} />
    </div>
  );
}

function HospitalCapacityForm({ world }: { world: WorldSnapshot }) {
  const [hospitalId, setHospitalId] = useState(world.hospitals[0]?.id ?? "");
  const [beds, setBeds] = useState(10);
  const { busy, result, run } = useBusyResult();

  return (
    <div>
      <div className="field-label">Drop hospital bed capacity</div>
      <FieldGroup>
        <select className="hard-select" value={hospitalId} onChange={(e) => setHospitalId(e.target.value)}>
          {world.hospitals.map((h) => (
            <option key={h.id} value={h.id}>
              {h.id} &mdash; {h.beds_used}/{h.bed_capacity} beds used
            </option>
          ))}
        </select>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            className="hard-input"
            type="number"
            min={1}
            style={{ width: 90 }}
            value={beds}
            onChange={(e) => setBeds(Number(e.target.value))}
          />
          <span style={{ fontSize: 11.5, opacity: 0.6 }}>beds removed from capacity</span>
        </div>
        <button
          className="hard-button sm full tone-alert"
          disabled={busy || !hospitalId}
          onClick={() => run("Hospital capacity drop", () => api.hospitalCapacityDrop(hospitalId, beds))}
        >
          {busy ? "Sending…" : "Drop capacity"}
        </button>
      </FieldGroup>
      <ResultBanner result={result} />
    </div>
  );
}

function DepotDepletionForm({ world }: { world: WorldSnapshot }) {
  const [depotId, setDepotId] = useState(world.depots[0]?.id ?? "");
  const [resource, setResource] = useState<ResourceType>("water");
  const [wipeAll, setWipeAll] = useState(true);
  const [amount, setAmount] = useState(100);
  const { busy, result, run } = useBusyResult();

  return (
    <div>
      <div className="field-label">Deplete depot supply</div>
      <FieldGroup>
        <select className="hard-select" value={depotId} onChange={(e) => setDepotId(e.target.value)}>
          {world.depots.map((d) => (
            <option key={d.id} value={d.id}>{d.id}</option>
          ))}
        </select>
        <select className="hard-select" value={resource} onChange={(e) => setResource(e.target.value as ResourceType)}>
          {RESOURCE_TYPES.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
          <input type="checkbox" checked={wipeAll} onChange={(e) => setWipeAll(e.target.checked)} />
          Wipe out entire stock of this resource
        </label>
        {!wipeAll && (
          <input
            className="hard-input"
            type="number"
            min={1}
            value={amount}
            onChange={(e) => setAmount(Number(e.target.value))}
          />
        )}
        <button
          className="hard-button sm full tone-alert"
          disabled={busy || !depotId}
          onClick={() => run("Depot depletion", () => api.depotDepletion(depotId, resource, wipeAll ? undefined : amount))}
        >
          {busy ? "Sending…" : "Deplete stock"}
        </button>
      </FieldGroup>
      <ResultBanner result={result} />
    </div>
  );
}
