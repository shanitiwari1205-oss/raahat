"""Hash-chained, tamper-evident ledger for resource AND fund movements.

Every record's hash covers the previous record's hash, so altering any
record breaks the chain from that point forward -- independently
verifiable by anyone via /ledger/verify (or client-side re-hash).
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass

GENESIS_HASH = "0" * 64


def _canonical_json(data: dict) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def compute_hash(prev_hash: str, data: dict) -> str:
    payload = prev_hash + _canonical_json(data)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class LedgerRecord:
    id: int
    timestamp: float
    prev_hash: str
    data: dict
    hash: str


class Ledger:
    """Thin wrapper around a SQLite table. Uses parameterized queries only."""

    def __init__(self, db_path: str = "ledger.db"):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ledger_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                prev_hash TEXT NOT NULL,
                data_json TEXT NOT NULL,
                hash TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def _last_hash(self) -> str:
        row = self._conn.execute(
            "SELECT hash FROM ledger_records ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else GENESIS_HASH

    def append(
        self,
        *,
        stakeholder_type: str,
        from_stakeholder: str,
        to_stakeholder: str,
        resource: str | None,
        units: float,
        fund_amount: float,
        description: str,
    ) -> LedgerRecord:
        """Appends one record. `stakeholder_type` categorizes the transfer
        (e.g. 'donor_to_depot', 'depot_to_zone') so the ledger demonstrates
        movement across multiple stakeholder types, not just one hop."""
        data = {
            "stakeholder_type": stakeholder_type,
            "from_stakeholder": from_stakeholder,
            "to_stakeholder": to_stakeholder,
            "resource": resource,
            "units": units,
            "fund_amount": fund_amount,
            "description": description,
        }
        prev_hash = self._last_hash()
        timestamp = time.time()
        record_hash = compute_hash(prev_hash, {"timestamp": timestamp, **data})
        cur = self._conn.execute(
            "INSERT INTO ledger_records (timestamp, prev_hash, data_json, hash) VALUES (?, ?, ?, ?)",
            (timestamp, prev_hash, _canonical_json(data), record_hash),
        )
        self._conn.commit()
        return LedgerRecord(id=cur.lastrowid, timestamp=timestamp, prev_hash=prev_hash, data=data, hash=record_hash)

    def list_records(self, limit: int = 50, offset: int = 0) -> list[LedgerRecord]:
        rows = self._conn.execute(
            "SELECT id, timestamp, prev_hash, data_json, hash FROM ledger_records "
            "ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [
            LedgerRecord(id=r[0], timestamp=r[1], prev_hash=r[2], data=json.loads(r[3]), hash=r[4])
            for r in rows
        ]

    def verify(self) -> dict:
        """Re-walks the entire chain from genesis, recomputing every hash.
        Returns {"valid": bool, "records_checked": int, "break_at_id": int|None}.
        """
        rows = self._conn.execute(
            "SELECT id, timestamp, prev_hash, data_json, hash FROM ledger_records ORDER BY id ASC"
        ).fetchall()
        expected_prev = GENESIS_HASH
        for rid, timestamp, prev_hash, data_json, stored_hash in rows:
            if prev_hash != expected_prev:
                return {"valid": False, "records_checked": rid, "break_at_id": rid,
                        "reason": "prev_hash does not match preceding record's hash"}
            data = json.loads(data_json)
            recomputed = compute_hash(prev_hash, {"timestamp": timestamp, **data})
            if recomputed != stored_hash:
                return {"valid": False, "records_checked": rid, "break_at_id": rid,
                        "reason": "stored hash does not match recomputed hash (data was altered)"}
            expected_prev = stored_hash
        return {"valid": True, "records_checked": len(rows), "break_at_id": None, "reason": None}

    def _debug_corrupt_record(self, record_id: int, new_units: float) -> None:
        """Test/demo-only helper: directly mutates a record's data without
        updating its hash, to prove /ledger/verify catches tampering."""
        row = self._conn.execute(
            "SELECT data_json FROM ledger_records WHERE id = ?", (record_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"no record {record_id}")
        data = json.loads(row[0])
        data["units"] = new_units
        self._conn.execute(
            "UPDATE ledger_records SET data_json = ? WHERE id = ?",
            (_canonical_json(data), record_id),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
