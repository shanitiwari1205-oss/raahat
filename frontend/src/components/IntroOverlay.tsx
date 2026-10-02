export function IntroOverlay({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null;
  return (
    <div className="overlay-backdrop" onClick={onClose}>
      <div
        className="hard-panel"
        style={{ maxWidth: 560, width: "100%", padding: 28, maxHeight: "86vh", overflowY: "auto" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ fontFamily: "var(--font-display)", fontSize: 11, fontWeight: 700, letterSpacing: "0.04em", color: "var(--info)" }}>
          PS EL-02 &mdash; INTELLIGENT &amp; TRANSPARENT DISASTER RELIEF ALLOCATION
        </div>
        <h1 style={{ fontFamily: "var(--font-display)", fontSize: 32, margin: "6px 0 14px" }}>RAAHAT</h1>
        <p style={{ fontSize: 14, lineHeight: 1.55, margin: "0 0 18px" }}>
          A live disaster-response simulation for Mumbai: zones, hospitals, and relief depots
          connected by a road network. As conditions change &mdash; a demand spike, a blocked road,
          a hospital filling up &mdash; a <strong>trained GNN policy</strong> reallocates ambulances,
          relief trucks, and funds in real time, benchmarked live against classical dispatch
          algorithms (Greedy, Hungarian, min-cost flow). Every resource and fund movement is
          written to a <strong>tamper-evident, hash-chained ledger</strong> that anyone can
          independently re-verify in the browser.
        </p>

        <div className="section-title" style={{ marginBottom: 8 }}>Try it yourself &mdash; 4 steps</div>
        <ol style={{ margin: 0, paddingLeft: 20, fontSize: 13.5, lineHeight: 1.7 }}>
          <li>
            Open the <strong>Demo</strong> tab (right side, open by default) and press <strong>Run
            scenario</strong> on any of the 3 scripted scenarios &mdash; a real demand spike, a
            road block that forces a reroute, or a hospital cascade comparing the equity floor on vs off.
          </li>
          <li>
            Or open <strong>Scenario</strong> to trigger your own events, or click a road on the map
            to block it directly &mdash; watch the map and Allocation Feed (left) react live.
          </li>
          <li>
            Open <strong>Controls</strong>, switch the active allocation strategy, and press
            <strong> Run Benchmark</strong> to see the trained policy vs. classical baselines on real
            numbers, under both generous supply and genuine scarcity.
          </li>
          <li>
            Open <strong>Ledger</strong> and press <strong>Verify Chain</strong> &mdash; it re-hashes
            every record in the browser itself, not just asking the server to vouch for it.
          </li>
        </ol>

        <button className="hard-button full tone-info" style={{ marginTop: 22 }} onClick={onClose}>
          Start exploring
        </button>
      </div>
    </div>
  );
}
