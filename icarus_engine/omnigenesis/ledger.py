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
            db.execute(
                """CREATE TABLE IF NOT EXISTS artifacts (
                  artifact_id TEXT PRIMARY KEY,
                  artifact_kind TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  summary_json TEXT NOT NULL
                )"""
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_omega_artifact_kind ON artifacts(artifact_kind)")

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

    def append_artifact(self, kind: str, report: dict) -> str:
        """Persist *only derived summary metadata*, never a full event tape.

        Each family has a strict schema/authority gate. Unknown artifacts fail
        closed. The digest binds the generated report to its precise lineage.
        """
        schemas = {
            "formal": "icarus-omnigenesis-formal-v1",
            "synthetic_book": "icarus-omnigenesis-synthetic-book-v1",
            "first_passage": "icarus-omnigenesis-first-passage-v1",
            "capability_plan": "icarus-omnigenesis-plan-v1",
        }
        if kind not in schemas or not isinstance(report, dict):
            raise ValueError("unsupported research artifact")
        if report.get("schema_version") != schemas[kind]:
            raise ValueError("unexpected artifact schema")
        if kind == "formal":
            if report.get("execution_authorized") is not False:
                raise ValueError("formal certificate cannot authorize execution")
        elif report.get("authority") != _AUTHORITY:
            raise ValueError("research authority escalation")
        origins = {
            "formal": "certificate_id",
            "synthetic_book": "scenario_id",
            "first_passage": "report_id",
            "capability_plan": "plan_id",
        }
        key = origins[kind]
        source = report.get(key)
        if (not isinstance(source, str) or len(source) != 64
                or any(c not in "0123456789abcdef" for c in source)):
            raise ValueError("invalid artifact identity")
        if kind in {"formal", "first_passage", "capability_plan"}:
            actual = identity({k: v for k, v in report.items() if k != key})
            if actual != source:
                raise ValueError("artifact tamper or source mismatch")
        # Synthetic scenario_id identifies input events, not the summary;
        # tie the immutable artifact identity to the entire derived report.
        digest = identity(report)
        details = {
            "formal": {"title": "Formal automaton certificate",
                       "status": "DETERMINISTIC" if report.get("deterministic_for_all_finite_features") else "CONTRADICTED",
                       "metric": len(report.get("ambiguity_counterexamples", []))},
            "synthetic_book": {"title": "Synthetic exchange experiment",
                               "status": "SYNTHETIC",
                               "metric": report.get("trade_count")},
            "first_passage": {"title": "Historical first-passage label study",
                              "status": "DERIVED",
                              "metric": report.get("label_count")},
            "capability_plan": {"title": "Capability expansion research proposal",
                                "status": "PROPOSED",
                                "metric": len(report.get("selected_proposal_ids", []))},
        }[kind]
        if type(details["metric"]) is not int or not 0 <= details["metric"] <= 100000:
            raise ValueError("artifact metric out of bounds")
        summary = {"artifact_id": digest, "kind": kind, "source_id": source,
                   "title": details["title"], "status": details["status"],
                   "metric": details["metric"], "research_only": True}
        payload = canonical_bytes(summary).decode("utf-8")
        with self._connect() as db:
            found = db.execute(
                "SELECT summary_json FROM artifacts WHERE artifact_id=?", (digest,)
            ).fetchone()
            if found:
                if found[0] != payload:
                    raise ValueError("immutable artifact collision")
                return digest
            now = datetime.now(timezone.utc).isoformat()
            db.execute("INSERT INTO artifacts VALUES (?, ?, ?, ?)",
                       (digest, kind, now, payload))
        return digest

    def snapshot(self, limit: int = 20) -> dict:
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
            raise ValueError("limit must be an integer between 1 and 100")
        with self._connect() as db:
            total = db.execute("SELECT COUNT(*) FROM studies").fetchone()[0]
            artifact_total = db.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
            artifacts = db.execute(
                "SELECT summary_json FROM artifacts ORDER BY created_at DESC, artifact_id LIMIT ?",
                (limit,),
            ).fetchall()
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
            "artifact_count": artifact_total,
            "recent_artifacts": [json.loads(row[0]) for row in artifacts],
            "recent_studies": [{
                "study_id": report["study_id"],
                "dataset_id": report["dataset_id"],
                "asset": report["asset"],
                "status": report["status"],
                "holdout_brier_improvement":
                    report["hypothesis"]["holdout_brier_improvement"],
            } for report in reports],
        }
