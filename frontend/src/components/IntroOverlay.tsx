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

        <div className="section-title" style={{ marginBottom: 8 }}>Try it yourself &mdash; 3 steps</div>
        <ol style={{ margin: 0, paddingLeft: 20, fontSize: 13.5, lineHeight: 1.7 }}>
          <li>
            Open the <strong>Scenario</strong> tab (right side) and spike demand in any zone &mdash;
            watch the map marker turn amber/red and the Allocation Feed (left) explain the reallocation.
          </li>
          <li>
            Open the <strong>Controls</strong> tab, switch the active allocation strategy, and press
            <strong> Run Benchmark</strong> to see the trained policy compared against classical
            baselines on real numbers.
          </li>
          <li>
            Open the <strong>Ledger</strong> tab and press <strong>Verify Chain</strong> &mdash; it
            re-hashes every record in the browser itself, not just asking the server to vouch for it.
          </li>
        </ol>

        <button className="hard-button full tone-info" style={{ marginTop: 22 }} onClick={onClose}>
          Start exploring
        </button>
      </div>
    </div>
  );
}
