"""Durable causal evidence store for ICARUS APEX Ω."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import threading
from typing import Any, Mapping

from .contracts import authority_flags, evidence_id, normalize_evidence, parse_utc


class ApexStore:
    """SQLite-WAL store for immutable APEX evidence."""

    def __init__(self, base_dir: str | os.PathLike[str]):
        self.base_dir = Path(base_dir)
        self.path = self.base_dir / "research" / "apex.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, timeout=10.0, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self.journal_mode = str(self._conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]).lower()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS evidence (
                    evidence_id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    calculated_at TEXT NOT NULL,
                    observed_ts REAL NOT NULL,
                    received_ts REAL NOT NULL,
                    semantic_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_apex_evidence_asof
                    ON evidence(observed_ts, received_ts);
                CREATE INDEX IF NOT EXISTS idx_apex_evidence_subject_asof
                    ON evidence(subject, observed_ts, received_ts);
                CREATE TABLE IF NOT EXISTS beliefs (
                    belief_id TEXT PRIMARY KEY,
                    semantic_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_ts REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS belief_events (
                    event_id TEXT PRIMARY KEY,
                    belief_id TEXT NOT NULL REFERENCES beliefs(belief_id),
                    state TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    event_at TEXT NOT NULL,
                    event_ts REAL NOT NULL,
                    semantic_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_apex_belief_events_asof
                    ON belief_events(belief_id, event_ts);
                """
            )

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _decode_row(self, row: sqlite3.Row) -> dict[str, Any]:
        try:
            semantic = json.loads(row["semantic_json"])
        except (TypeError, json.JSONDecodeError) as ex:
            raise ValueError("stored evidence semantic_json is invalid") from ex
        if not isinstance(semantic, dict):
            raise ValueError("stored evidence semantic_json must be an object")
        if semantic.get("execution_authorized") is not False or semantic.get("production_decision_authorized") is not False:
            raise ValueError("stored evidence cannot authorize execution or production")
        if evidence_id(semantic) != row["evidence_id"]:
            raise ValueError("stored evidence identity mismatch")
        out = dict(semantic)
        out["evidence_id"] = row["evidence_id"]
        out["recorded_at"] = row["recorded_at"]
        return out

    def record_evidence(self, body: Mapping[str, Any]) -> dict[str, Any]:
        semantic = normalize_evidence(body)
        eid = evidence_id(semantic)
        recorded_at = self._utc_now()
        observed_ts = parse_utc(semantic["observed_at"], "observed_at").timestamp()
        received_ts = parse_utc(semantic["received_at"], "received_at").timestamp()
        raw = json.dumps(semantic, sort_keys=True, separators=(",", ":"), allow_nan=False)

        with self._lock, self._conn:
            cur = self._conn.execute(
                """
                INSERT OR IGNORE INTO evidence(
                    evidence_id, subject, kind, observed_at, received_at,
                    calculated_at, observed_ts, received_ts, semantic_json, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (eid, semantic["subject"], semantic["kind"], semantic["observed_at"],
                 semantic["received_at"], semantic["calculated_at"], observed_ts,
                 received_ts, raw, recorded_at),
            )
            row = self._conn.execute("SELECT * FROM evidence WHERE evidence_id = ?", (eid,)).fetchone()
        if row is None:
            raise RuntimeError("evidence write did not persist")
        evidence = self._decode_row(row)
        return {"ok": True, "idempotent": cur.rowcount == 0, "evidence": evidence, **authority_flags()}

    def evidence_as_of(self, as_of: str, *, subject: str | None = None) -> list[dict[str, Any]]:
        boundary = parse_utc(as_of, "as_of").timestamp()
        sql = "SELECT * FROM evidence WHERE observed_ts <= ? AND received_ts <= ?"
        params: list[Any] = [boundary, boundary]
        if subject is not None:
            if not isinstance(subject, str) or not subject.strip():
                raise ValueError("subject filter must be a non-empty string")
            sql += " AND subject = ?"
            params.append(subject.strip())
        sql += " ORDER BY observed_ts, received_ts, evidence_id"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                out.append(self._decode_row(row))
            except ValueError:
                continue
        return out

    def integrity_status(self) -> dict[str, Any]:
        with self._lock:
            quick = str(self._conn.execute("PRAGMA quick_check").fetchone()[0])
            rows = self._conn.execute("SELECT * FROM evidence ORDER BY evidence_id").fetchall()
        corrupt: list[str] = []
        for row in rows:
            try:
                self._decode_row(row)
            except ValueError:
                corrupt.append(str(row["evidence_id"]))
        sqlite_ok = quick.lower() == "ok"
        return {
            "schema_version": "icarus-apex-store-v1",
            "journal_mode": self.journal_mode,
            "sqlite_ok": sqlite_ok,
            "integrity_ok": sqlite_ok and not corrupt,
            "evidence_rows": len(rows),
            "corrupt_rows": len(corrupt),
            "quarantined_evidence_ids": corrupt,
            **authority_flags(),
        }
