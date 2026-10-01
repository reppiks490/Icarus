"""Immutable gate receipts for rigorous ICARUS candidate qualification.

A receipt can prove or falsify one gate for one exact candidate source revision.
The store never mutates strategy state or grants production/execution authority.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


_ALLOWED = {
    "candidate_id",
    "candidate_source_repo",
    "candidate_source_commit",
    "gate",
    "passed",
    "verifier_id",
    "verifier_source_repo",
    "verifier_source_commit",
    "observed_at",
    "evidence_hash",
}


def _text(value: Any, name: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    out = value.strip()
    if len(out) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return out


def _sha(value: Any, name: str, length: int) -> str:
    out = _text(value, name, length).lower()
    if len(out) != length or any(ch not in "0123456789abcdef" for ch in out):
        raise ValueError(f"{name} must be an exact {length}-character lowercase hex digest")
    return out


def _iso(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a timezone-aware ISO-8601 timestamp")
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as ex:
        raise ValueError(f"{name} must be a timezone-aware ISO-8601 timestamp") from ex
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    utc = dt.astimezone(timezone.utc)
    if utc > datetime.now(timezone.utc):
        raise ValueError(f"{name} cannot be in the future")
    return utc.isoformat().replace("+00:00", "Z")


def _semantic_hash(value: Mapping[str, Any]) -> str:
    raw = json.dumps(dict(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_shadow_promotion_event(
    candidate: Mapping[str, Any],
    qualification: Mapping[str, Any],
) -> dict[str, Any]:
    """Build one deterministic qualified-shadow Brain event from exact receipts.

    This helper does not write the event. It proves that the durable candidate
    revision and receipt scope match, then returns an event suitable for
    record_brain_event(). The resulting event remains research/shadow-only.
    """
    if not isinstance(candidate, Mapping) or not isinstance(qualification, Mapping):
        raise ValueError("candidate and qualification must be objects")
    candidate_id = _text(candidate.get("candidate_id"), "candidate.candidate_id", 180)
    source_repo = _text(candidate.get("source_repo"), "candidate.source_repo", 180)
    source_commit = _sha(candidate.get("source_commit"), "candidate.source_commit", 40)
    if qualification.get("qualification_ready") is not True:
        blockers = qualification.get("blockers")
        detail = "; ".join(str(x) for x in blockers) if isinstance(blockers, list) else "qualification gates incomplete"
        raise ValueError("candidate is not qualification-ready: " + detail)
    if _text(qualification.get("candidate_id"), "qualification.candidate_id", 180) != candidate_id:
        raise ValueError("qualification candidate_id does not match candidate")
    q_repo = _text(qualification.get("candidate_source_repo"), "qualification.candidate_source_repo", 180)
    q_commit = _sha(qualification.get("candidate_source_commit"), "qualification.candidate_source_commit", 40)
    if (q_repo, q_commit) != (source_repo, source_commit):
        raise ValueError("qualification source revision does not match candidate")

    stage = _text(candidate.get("stage"), "candidate.stage", 40)
    if stage not in {"validated", "qualified_shadow"}:
        raise ValueError("candidate must be validated before qualified-shadow promotion")
    regimes = candidate.get("regimes")
    if not isinstance(regimes, list) or not regimes:
        raise ValueError("candidate regimes are required")
    metrics = candidate.get("metrics")
    if not isinstance(metrics, Mapping):
        raise ValueError("candidate metrics are required")
    validation = qualification.get("validation")
    if not isinstance(validation, Mapping) or not validation or not all(value is True for value in validation.values()):
        raise ValueError("qualification validation map must contain only verified gates")

    receipts = qualification.get("latest_gate_receipts")
    if not isinstance(receipts, list) or not receipts:
        raise ValueError("qualification receipts are required")
    receipt_ids = []
    receipt_provenance = []
    for row in receipts:
        if not isinstance(row, Mapping) or row.get("passed") is not True:
            raise ValueError("every latest qualification receipt must pass")
        receipt_id = _sha(row.get("receipt_id"), "receipt_id", 64)
        receipt_ids.append(receipt_id)
        receipt_provenance.append({
            "gate": _text(row.get("gate"), "receipt.gate", 96),
            "receipt_id": receipt_id,
            "verifier_id": _text(row.get("verifier_id"), "receipt.verifier_id", 180),
            "verifier_source_revision": _text(
                row.get("verifier_source_revision"), "receipt.verifier_source_revision", 260
            ),
            "evidence_hash": _sha(row.get("evidence_hash"), "receipt.evidence_hash", 64),
        })

    return {
        "kind": "candidate",
        "subject": candidate_id,
        "summary": "candidate qualified for regime-specific shadow routing by immutable gate receipts",
        "status": "qualified",
        "evidence": [f"qualification-receipt:{receipt_id}" for receipt_id in receipt_ids],
        "details": {
            "promotion_plane": "QUALIFICATION_RECEIPTS",
            "promoted_from_stage": stage,
            "candidate_source_revision": f"{source_repo}@{source_commit}",
            "gate_receipts": receipt_provenance,
            "execution_authorized": False,
            "production_decision_authorized": False,
        },
        "candidate_id": candidate_id,
        "stage": "qualified_shadow",
        "regimes": list(regimes),
        "metrics": dict(metrics),
        "validation": dict(validation),
        "source_repo": source_repo,
        "source_commit": source_commit,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


class QualificationReceiptStore:
    """Append-only verification receipts keyed to exact candidate revisions."""

    def __init__(self, base_dir: str | Path, required_gates: Iterable[str]):
        gates = tuple(dict.fromkeys(str(x).strip() for x in required_gates if str(x).strip()))
        if not gates:
            raise ValueError("required_gates cannot be empty")
        self.required_gates = gates
        self.required_gate_set = set(gates)
        self.root = Path(base_dir) / "audit"
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "candidate_qualification.sqlite3"
        self._lock = threading.RLock()
        with self._connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS receipts (
                    receipt_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    candidate_source_repo TEXT NOT NULL,
                    candidate_source_commit TEXT NOT NULL,
                    gate_name TEXT NOT NULL,
                    passed INTEGER NOT NULL CHECK(passed IN (0,1)),
                    verifier_id TEXT NOT NULL,
                    verifier_source_repo TEXT NOT NULL,
                    verifier_source_commit TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    evidence_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS qualification_candidate_scope
                    ON receipts(candidate_id, candidate_source_repo, candidate_source_commit, gate_name, observed_at);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path), timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def record(self, body: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(body, Mapping) or set(body) != _ALLOWED:
            raise ValueError("qualification receipt requires exactly: " + ", ".join(sorted(_ALLOWED)))

        gate = _text(body["gate"], "gate", 96)
        if gate not in self.required_gate_set:
            raise ValueError(f"unknown qualification gate: {gate}")
        if type(body["passed"]) is not bool:
            raise ValueError("passed must be Boolean")

        semantic = {
            "candidate_id": _text(body["candidate_id"], "candidate_id", 180),
            "candidate_source_repo": _text(body["candidate_source_repo"], "candidate_source_repo", 180),
            "candidate_source_commit": _sha(body["candidate_source_commit"], "candidate_source_commit", 40),
            "gate": gate,
            "passed": body["passed"],
            "verifier_id": _text(body["verifier_id"], "verifier_id", 180),
            "verifier_source_repo": _text(body["verifier_source_repo"], "verifier_source_repo", 180),
            "verifier_source_commit": _sha(body["verifier_source_commit"], "verifier_source_commit", 40),
            "observed_at": _iso(body["observed_at"], "observed_at"),
            "evidence_hash": _sha(body["evidence_hash"], "evidence_hash", 64),
        }
        if "/" not in semantic["candidate_source_repo"] or "/" not in semantic["verifier_source_repo"]:
            raise ValueError("source repositories must use owner/repository form")

        candidate_revision = semantic["candidate_source_repo"] + "@" + semantic["candidate_source_commit"]
        verifier_revision = semantic["verifier_source_repo"] + "@" + semantic["verifier_source_commit"]
        if gate == "independent_verification" and semantic["passed"] and verifier_revision == candidate_revision:
            raise ValueError("independent_verification cannot be proved by the candidate's exact source revision")

        receipt_id = _semantic_hash(semantic)
        created = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with self._lock, self._connect() as con:
            prior = con.execute("SELECT receipt_id FROM receipts WHERE receipt_id=?", (receipt_id,)).fetchone()
            if prior is None:
                con.execute(
                    "INSERT INTO receipts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        receipt_id,
                        semantic["candidate_id"],
                        semantic["candidate_source_repo"],
                        semantic["candidate_source_commit"],
                        gate,
                        1 if semantic["passed"] else 0,
                        semantic["verifier_id"],
                        semantic["verifier_source_repo"],
                        semantic["verifier_source_commit"],
                        semantic["observed_at"],
                        semantic["evidence_hash"],
                        created,
                    ),
                )
                idempotent = False
            else:
                idempotent = True

        return {
            "ok": True,
            "receipt_id": receipt_id,
            "idempotent": idempotent,
            "gate": gate,
            "passed": semantic["passed"],
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def candidate_status(
        self,
        candidate_id: str,
        candidate_source_repo: str,
        candidate_source_commit: str,
    ) -> dict[str, Any]:
        cid = _text(candidate_id, "candidate_id", 180)
        repo = _text(candidate_source_repo, "candidate_source_repo", 180)
        commit = _sha(candidate_source_commit, "candidate_source_commit", 40)

        with self._lock, self._connect() as con:
            rows = [dict(x) for x in con.execute(
                "SELECT * FROM receipts WHERE candidate_id=? AND candidate_source_repo=? "
                "AND candidate_source_commit=? ORDER BY observed_at, receipt_id",
                (cid, repo, commit),
            ).fetchall()]

        latest: dict[str, dict[str, Any]] = {}
        for row in rows:
            latest[row["gate_name"]] = row

        validation = {}
        gate_receipts = []
        blockers = []
        for gate in self.required_gates:
            row = latest.get(gate)
            passed = bool(row and row["passed"])
            validation[gate] = passed
            if not passed:
                blockers.append(f"{gate} gate not verified")
            gate_receipts.append({
                "gate": gate,
                "passed": passed,
                "receipt_id": row["receipt_id"] if row else None,
                "observed_at": row["observed_at"] if row else None,
                "verifier_id": row["verifier_id"] if row else None,
                "verifier_source_revision": (
                    row["verifier_source_repo"] + "@" + row["verifier_source_commit"]
                    if row else None
                ),
                "evidence_hash": row["evidence_hash"] if row else None,
            })

        ready = not blockers
        return {
            "candidate_id": cid,
            "candidate_source_repo": repo,
            "candidate_source_commit": commit,
            "candidate_source_revision": repo + "@" + commit,
            "receipt_count": len(rows),
            "latest_gate_receipts": gate_receipts,
            "validation": validation,
            "qualification_ready": ready,
            "recommended_stage": "qualified_shadow" if ready else "validated",
            "blockers": blockers,
            "execution_authorized": False,
            "production_decision_authorized": False,
            "rule": "Qualification readiness is evidence-only. Promotion must be recorded separately and cannot authorize production or execution.",
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock, self._connect() as con:
            scopes = con.execute(
                "SELECT DISTINCT candidate_id, candidate_source_repo, candidate_source_commit "
                "FROM receipts ORDER BY candidate_id, candidate_source_repo, candidate_source_commit"
            ).fetchall()

        candidates = [
            self.candidate_status(row["candidate_id"], row["candidate_source_repo"], row["candidate_source_commit"])
            for row in scopes
        ]
        return {
            "schema_version": "icarus-qualification-receipts-v1",
            "required_gates": list(self.required_gates),
            "candidate_revision_count": len(candidates),
            "qualification_ready_count": sum(1 for x in candidates if x["qualification_ready"]),
            "candidates": candidates,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }
