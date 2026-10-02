import { useEffect, useState } from "react";
import { api, ApiError, recomputeRecordHash, type LedgerRecord, type VerifyResult } from "../api";

export function LedgerExplorer() {
  const [records, setRecords] = useState<LedgerRecord[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [serverVerify, setServerVerify] = useState<VerifyResult | null>(null);
  const [clientVerify, setClientVerify] = useState<{ ok: boolean; checked: number; brokenId: number | null } | null>(null);
  const [verifying, setVerifying] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setRecords(await api.ledger(20));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't load the ledger.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const verify = async () => {
    setVerifying(true);
    setServerVerify(null);
    setClientVerify(null);
    try {
      const [server, full] = await Promise.all([api.verifyLedger(), api.ledger(5000)]);
      setServerVerify(server);

      // Genuine client-side re-hash -- re-walks the chain oldest-first and
      // recomputes every SHA-256 in the browser, not just trusting the server.
      const oldestFirst = [...full].sort((a, b) => a.id - b.id);
      let brokenId: number | null = null;
      for (const r of oldestFirst) {
        const recomputed = await recomputeRecordHash(r);
        if (recomputed !== r.hash) {
          brokenId = r.id;
          break;
        }
      }
      setClientVerify({ ok: brokenId === null, checked: oldestFirst.length, brokenId });
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Verification failed.");
    } finally {
      setVerifying(false);
    }
  };

  const corruptForDemo = async () => {
    if (!records || records.length === 0) return;
    setError(null);
    try {
      await api.corruptRecord(records[records.length - 1].id);
      await load();
      setServerVerify(null);
      setClientVerify(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't run the tamper demo.");
    }
  };

  return (
    <div>
      <div className="field-label">Verify the hash chain</div>
      <div style={{ display: "flex", gap: 8 }}>
        <button className="hard-button sm tone-info" style={{ flex: 1 }} disabled={verifying} onClick={verify}>
          {verifying ? "Verifying…" : "Verify chain"}
        </button>
        <button className="hard-button sm tone-alert" disabled={verifying || !records?.length} onClick={corruptForDemo}>
          Simulate tamper
        </button>
      </div>
      <p style={{ fontSize: 10.5, opacity: 0.55, margin: "6px 0 0" }}>
        "Simulate tamper" corrupts the most recent record directly in the database (demo-only
        endpoint) so you can watch Verify Chain catch it -- proving the tamper-evidence claim
        live instead of just asserting it.
      </p>

      {serverVerify && (
        <div className={`chip ${serverVerify.valid ? "valid" : "invalid"}`} style={{ marginTop: 10, display: "inline-block" }}>
          Server check: {serverVerify.valid ? "chain intact" : `break at record #${serverVerify.break_at_id}`}
        </div>
      )}
      {clientVerify && (
        <div className={`chip ${clientVerify.ok ? "valid" : "invalid"}`} style={{ marginTop: 6, marginLeft: 6, display: "inline-block" }}>
          Browser re-hash ({clientVerify.checked} records): {clientVerify.ok ? "chain intact" : `break at record #${clientVerify.brokenId}`}
        </div>
      )}
      {error && <div className="action-result err">{error}</div>}

      <div className="field-label" style={{ marginTop: 18 }}>Recent records (resource + fund, newest first)</div>
      {loading && <div style={{ fontSize: 12, opacity: 0.6 }}>Loading&hellip;</div>}
      {records && records.length === 0 && <div style={{ fontSize: 12, opacity: 0.6 }}>No records yet.</div>}
      {records?.map((r) => (
        <div key={r.id} className="ledger-row">
          <div className="desc">
            #{r.id} &middot; {r.description}
            {r.fund_amount > 0 && <strong> &middot; &#8377;{Math.round(r.fund_amount).toLocaleString("en-IN")}</strong>}
          </div>
          <div className="meta">
            <span>{r.stakeholder_type.replace(/_/g, " ")}</span>
            <span>{new Date(r.timestamp * 1000).toLocaleTimeString()}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
