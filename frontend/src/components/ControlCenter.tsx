import { useState } from "react";
import type { WorldSnapshot } from "../store";
import { ScenarioInjector } from "./ScenarioInjector";
import { ControlsPanel } from "./ControlsPanel";
import { LedgerExplorer } from "./LedgerExplorer";
import { DemoPanel } from "./DemoPanel";

type Tab = "demo" | "scenario" | "controls" | "ledger";

const TABS: { id: Tab; label: string }[] = [
  { id: "demo", label: "Demo" },
  { id: "scenario", label: "Scenario" },
  { id: "controls", label: "Controls" },
  { id: "ledger", label: "Ledger" },
];

export function ControlCenter({ world }: { world: WorldSnapshot | null }) {
  const [tab, setTab] = useState<Tab>("demo");

  return (
    <div className="hard-panel" style={{ padding: 16, pointerEvents: "auto", display: "flex", flexDirection: "column", minHeight: 0 }}>
      <div className="section-title">Control center</div>
      <div className="tab-strip">
        {TABS.map((t) => (
          <button key={t.id} className={`tab-btn ${tab === t.id ? "active" : ""}`} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>
      <div style={{ overflowY: "auto", minHeight: 0 }}>
        {tab === "demo" && <DemoPanel />}
        {tab === "scenario" && <ScenarioInjector world={world} />}
        {tab === "controls" && <ControlsPanel />}
        {tab === "ledger" && <LedgerExplorer />}
      </div>
    </div>
  );
}
