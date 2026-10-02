import type { FeedItem, WorldSnapshot } from "../store";

function StatusBadge({ status }: { status: "connecting" | "connected" | "disconnected" }) {
  const label = status === "connected" ? "Live" : status === "connecting" ? "Connecting" : "Reconnecting";
  return (
    <span className={`badge status-${status}`}>
      <span className="badge-dot" />
      {label}
    </span>
  );
}

function TotalBudget({ world }: { world: WorldSnapshot }) {
  const total = world.depots.reduce((sum, d) => sum + d.budget_inr, 0);
  return (
    <div style={{ fontFamily: "var(--font-display)" }}>
      <div style={{ fontSize: 12, opacity: 0.7, textTransform: "uppercase", letterSpacing: "0.04em" }}>
        Relief funds on hand
      </div>
      <div style={{ fontSize: 28, fontWeight: 700 }}>
        &#8377;{Math.round(total).toLocaleString("en-IN")}
      </div>
    </div>
  );
}

export function Hud({
  status,
  world,
  feed,
  replayMode,
  onExitReplay,
}: {
  status: "connecting" | "connected" | "disconnected";
  world: WorldSnapshot | null;
  feed: FeedItem[];
  replayMode: boolean;
  onExitReplay: () => void;
}) {
  return (
    <div
      style={{
        position: "absolute",
        top: 16,
        left: 16,
        width: 340,
        maxHeight: "calc(100vh - 32px)",
        display: "flex",
        flexDirection: "column",
        gap: 12,
        pointerEvents: "none",
      }}
    >
      {replayMode && (
        <div className="hard-panel tone-alert" style={{ padding: "10px 14px", pointerEvents: "auto" }}>
          <div style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 12.5 }}>
            ⚠ REPLAY MODE — live connection lost
          </div>
          <div style={{ fontSize: 11.5, opacity: 0.8, marginTop: 2 }}>
            Showing the last ~60s of real activity while reconnecting automatically.{" "}
            <button
              onClick={onExitReplay}
              style={{ background: "none", border: "none", textDecoration: "underline", cursor: "pointer", font: "inherit", padding: 0, color: "inherit" }}
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      <div className="hard-panel" style={{ padding: 16, pointerEvents: "auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <h1 style={{ fontFamily: "var(--font-display)", fontSize: 22, margin: 0, lineHeight: 1.1 }}>
            RAAHAT
            <div style={{ fontSize: 11, fontWeight: 500, opacity: 0.7, textTransform: "none", marginTop: 2 }}>
              Disaster Relief Command Map
            </div>
          </h1>
          <StatusBadge status={status} />
        </div>
        {world && (
          <div style={{ marginTop: 14 }}>
            <TotalBudget world={world} />
          </div>
        )}
      </div>

      <div className="hard-panel" style={{ padding: 16, pointerEvents: "auto" }}>
        <div style={{ fontFamily: "var(--font-display)", fontSize: 13, fontWeight: 700, textTransform: "uppercase", marginBottom: 10 }}>
          Legend
        </div>
        <LegendRow color="#1f7a4d" label="Zone — low urgency" />
        <LegendRow color="#ffb800" label="Zone — rising urgency" />
        <LegendRow color="#ff3b1f" label="Zone — critical / blocked road" />
        <LegendRow color="#1d4ed8" label="Hospital" />
        <LegendRow color="#f4f1e8" border label="Relief depot" />
      </div>

      <div
        className="hard-panel"
        style={{ padding: 16, flex: 1, overflowY: "auto", pointerEvents: "auto", minHeight: 0 }}
      >
        <div style={{ fontFamily: "var(--font-display)", fontSize: 13, fontWeight: 700, textTransform: "uppercase", marginBottom: 10 }}>
          Allocation feed
        </div>
        {feed.length === 0 ? (
          <div style={{ fontSize: 13, opacity: 0.6 }}>Waiting for the first event…</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {feed.map((item, i) => (
              <div key={i} style={{ fontSize: 12.5, lineHeight: 1.4, borderLeft: "3px solid var(--line)", paddingLeft: 8 }}>
                {item.message}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function LegendRow({ color, label, border }: { color: string; label: string; border?: boolean }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13, marginBottom: 6 }}>
      <span
        style={{
          width: 14,
          height: 14,
          borderRadius: "50%",
          background: color,
          border: border ? "2px solid var(--ink)" : "2px solid transparent",
          flexShrink: 0,
        }}
      />
      {label}
    </div>
  );
}
