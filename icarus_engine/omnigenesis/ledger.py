"""Append-only, content-addressed scientific result store.

Research artifacts are derived only. Raw historical market rows remain local
to the caller and are not written to this store.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .contracts import canonical_bytes, identity

_AUTHORITY = {"research_only": True, "execution_authorized": False,
              "production_decision_authorized": False, "auto_promote": False}


class ResearchLedger:
    def __init__(self, root: str | Path):
        self.path = Path(root) / "research" / "omnigenesis.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS studies (
                  study_id TEXT PRIMARY KEY,
                  dataset_sha256 TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  report_json TEXT NOT NULL
                )"""
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_omega_dataset ON studies(dataset_sha256)")

    @contextmanager
    def _connect(self):
        con = sqlite3.connect(self.path, timeout=15)
        try:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA busy_timeout=15000")
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def append(self, report: dict) -> str:
        if not isinstance(report, dict) or report.get("authority") != _AUTHORITY:
            raise ValueError("invalid research-only authority")
        if report.get("schema_version") != "icarus-omnigenesis-study-v1":
            raise ValueError("invalid study schema")
        if report.get("status") not in {"EXPLORATORY", "REJECTED"}:
            raise ValueError("unsupported scientific status")
        expected_id = identity({k: v for k, v in report.items()
                                if k != "study_id"})
        if report.get("study_id") != expected_id:
            raise ValueError("study identity mismatch")
        payload = canonical_bytes(report).decode("utf-8")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            existing = db.execute("SELECT report_json FROM studies WHERE study_id=?",
                                  (expected_id,)).fetchone()
            if existing is not None:
                if existing[0] != payload:
                    raise ValueError("immutable study collision")
                return expected_id
            db.execute("INSERT INTO studies VALUES (?, ?, ?, ?)",
                       (expected_id, report["dataset_sha256"], now, payload))
        return expected_id

    def get(self, study_id: str) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT report_json FROM studies WHERE study_id=?",
                             (study_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def snapshot(self, limit: int = 20) -> dict:
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
            raise ValueError("limit must be an integer between 1 and 100")
        with self._connect() as db:
            total = db.execute("SELECT COUNT(*) FROM studies").fetchone()[0]
            rows = db.execute(
                "SELECT report_json FROM studies ORDER BY created_at DESC, study_id LIMIT ?",
                (limit,),
            ).fetchall()
        reports = [json.loads(row[0]) for row in rows]
        return {
            "schema_version": "icarus-omnigenesis-snapshot-v1",
            "authority": dict(_AUTHORITY),
            "status": "RESEARCH_ONLY",
            "study_count": total,
            "recent_studies": [{
                "study_id": report["study_id"],
                "dataset_id": report["dataset_id"],
                "asset": report["asset"],
                "status": report["status"],
                "holdout_brier_improvement":
                    report["hypothesis"]["holdout_brier_improvement"],
            } for report in reports],
        }
