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
            "agent_workflow": "icarus-omnigenesis-agent-run-v1",
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
            "agent_workflow": "run_id",
        }
        key = origins[kind]
        source = report.get(key)
        if (not isinstance(source, str) or len(source) != 64
                or any(c not in "0123456789abcdef" for c in source)):
            raise ValueError("invalid artifact identity")
        if kind in {"formal", "first_passage", "capability_plan", "agent_workflow"}:
            actual = identity({k: v for k, v in report.items() if k != key})
            if actual != source:
                raise ValueError("artifact tamper or source mismatch")
        # Independently cross-check reported conservation and scientific
        # status before accepting an opaque derived artifact.
        if kind == "synthetic_book":
            if report.get("evidence_kind") != "SYNTHETIC" or report.get("quantity_conserved") is not True:
                raise ValueError("synthetic origin or conservation was not verified")
            required = ("submitted_quantity", "resting_buy_quantity",
                        "resting_sell_quantity", "canceled_quantity",
                        "unfilled_market_quantity", "executed_quantity",
                        "trade_count")
            if any(type(report.get(k)) is not int or report[k] < 0 for k in required):
                raise ValueError("synthetic accounting metrics invalid")
            if report["submitted_quantity"] != (
                report["resting_buy_quantity"] + report["resting_sell_quantity"]
                + report["canceled_quantity"] + report["unfilled_market_quantity"]
                + 2 * report["executed_quantity"]
            ):
                raise ValueError("synthetic quantity accounting mismatch")
            trades = report.get("trades")
            if not isinstance(trades, list) or len(trades) != report["trade_count"] or (
                sum(row.get("quantity", 0) for row in trades) != report["executed_quantity"]
            ):
                raise ValueError("synthetic trade receipts inconsistent")
        elif kind == "first_passage":
            counts = report.get("counts", {})
            if not isinstance(counts, dict) or any(
                type(value) is not int or value < 0 for value in counts.values()
            ) or sum(counts.values()) != report.get("label_count"):
                raise ValueError("first-passage totals inconsistent")
        elif kind == "capability_plan":
            if report.get("status") != "PROPOSED_NOT_EXECUTED" or report.get("independent_approval_required") is not True:
                raise ValueError("unapproved autonomous plan")
        elif kind == "agent_workflow":
            if (report.get("status") not in {"RESEARCH_ONLY_COMPLETE", "RESEARCH_ONLY_REVIEW_REQUIRED"}
                    or report.get("scientific_qualification") is not False
                    or report.get("external_approval_required") is not True
                    or report.get("no_network_or_broker_operations") is not True):
                raise ValueError("workflow authority or status violation")
            receipts = report.get("receipts")
            counts = report.get("counts")
            if (not isinstance(receipts, list) or not 1 <= len(receipts) <= 24
                    or not isinstance(counts, dict)
                    or set(counts) != {"PASS", "FAIL", "BLOCKED"}
                    or any(type(x) is not int or x < 0 for x in counts.values())):
                raise ValueError("invalid workflow receipts/counts")
            prior = "0" * 64
            observed = {"PASS": 0, "FAIL": 0, "BLOCKED": 0}
            for node in receipts:
                if (not isinstance(node, dict) or
                        node.get("previous_receipt") != prior or
                        node.get("execution_authorized") is not False or
                        node.get("research_only") is not True or
                        node.get("status") not in observed):
                    raise ValueError("invalid workflow receipt chain")
                if node.get("receipt_id") != identity({
                        key: value for key, value in node.items() if key != "receipt_id"}):
                    raise ValueError("tampered workflow receipt")
                prior = node["receipt_id"]
                observed[node["status"]] += 1
            if observed != counts or report.get("final_receipt") != prior:
                raise ValueError("workflow count or chain mismatch")
            expected_status = ("RESEARCH_ONLY_COMPLETE" if not counts["FAIL"] and not counts["BLOCKED"]
                               else "RESEARCH_ONLY_REVIEW_REQUIRED")
            if report["status"] != expected_status:
                raise ValueError("workflow status inconsistent with receipts")
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
            "agent_workflow": {"title": "Research workflow execution receipts",
                               "status": "RESEARCH_ONLY" if report["status"] == "RESEARCH_ONLY_COMPLETE"
                                         else "REVIEW_REQUIRED",
                               "metric": len(report["receipts"])},
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
