"""Proof-carrying candidate qualification for the ICARUS Adaptive Brain.

Validated research candidates may accumulate immutable gate receipts.  Only a
candidate whose exact repository revision has every required gate verified may
be transformed into a qualified_shadow event.  This module never authorizes
production decisions, strategy mutation, broker access, or execution.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping

SCHEMA_VERSION = "icarus-candidate-qualification-v1"
RECEIPT_SCHEMA = "icarus-candidate-gate-receipt-v1"

REQUIRED_GATES = (
    "causal_time",
    "provenance",
    "oos",
    "protected_holdout",
    "multiple_testing",
    "costs_slippage_latency",
    "ablation",
    "calibration",
    "ood_drift",
    "deterministic_replay",
    "independent_verification",
)

_ALLOWED_REVIEW_ROLES = {
    "aegis",
    "aion",
    "argus",
    "ascension",
    "commissioning",
    "daedalus",
    "infrastructure",
    "nexus",
    "provenance",
}

_INDEPENDENT_ROLES = {"aegis", "ascension", "daedalus"}
_LOCK = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as ex:
        raise ValueError(f"{name} must be ISO-8601") from ex
    if dt.tzinfo is None:
        raise ValueError(f"{name} must include timezone")
    dt = dt.astimezone(timezone.utc)
    if dt > _now():
        raise ValueError(f"{name} cannot be in the future")
    return dt.isoformat().replace("+00:00", "Z")


def _text(value: Any, name: str, limit: int = 240) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    out = value.strip()
    if len(out) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return out


def _sha(value: Any, name: str, size: int = 64) -> str:
    out = _text(value, name, size).lower()
    if len(out) != size or any(ch not in "0123456789abcdef" for ch in out):
        raise ValueError(f"{name} must be {size}-character hexadecimal")
    return out


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _path(base_dir: str | os.PathLike[str]) -> Path:
    return Path(base_dir) / "audit" / "candidate_qualification.jsonl"


def _candidate_identity(candidate: Mapping[str, Any]) -> tuple[str, str, str]:
    cid = _text(candidate.get("candidate_id"), "candidate_id", 180)
    repo = _text(candidate.get("source_repo"), "source_repo", 180)
    if "/" not in repo:
        raise ValueError("source_repo must be owner/repository")
    commit = _sha(candidate.get("source_commit"), "source_commit", 40)
    return cid, repo, commit


def _normalize_receipt(body: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(body, Mapping):
        raise ValueError("receipt must be an object")
    required = {
        "candidate_id", "source_repo", "source_commit", "gate", "passed",
        "reviewer_role", "reviewer_id", "independent", "observed_at",
        "evidence_hash", "evidence",
    }
    missing = required - set(body)
    extra = set(body) - required
    if missing or extra:
        raise ValueError(f"receipt fields mismatch; missing={sorted(missing)} extra={sorted(extra)}")

    gate = _text(body["gate"], "gate", 80).lower()
    if gate not in REQUIRED_GATES:
        raise ValueError("unsupported qualification gate")
    if type(body["passed"]) is not bool:
        raise ValueError("passed must be boolean")
    if type(body["independent"]) is not bool:
        raise ValueError("independent must be boolean")

    role = _text(body["reviewer_role"], "reviewer_role", 80).lower()
    if role not in _ALLOWED_REVIEW_ROLES:
        raise ValueError("reviewer_role is not allowed")
    reviewer_id = _text(body["reviewer_id"], "reviewer_id", 160)

    evidence = body["evidence"]
    if isinstance(evidence, str):
        evidence = [evidence]
    if not isinstance(evidence, list) or not evidence or len(evidence) > 32:
        raise ValueError("evidence must be a non-empty list with at most 32 items")
    clean_evidence = [_text(x, "evidence item", 700) for x in evidence]

    semantic = {
        "schema_version": RECEIPT_SCHEMA,
        "candidate_id": _text(body["candidate_id"], "candidate_id", 180),
        "source_repo": _text(body["source_repo"], "source_repo", 180),
        "source_commit": _sha(body["source_commit"], "source_commit", 40),
        "gate": gate,
        "passed": body["passed"],
        "reviewer_role": role,
        "reviewer_id": reviewer_id,
        "independent": body["independent"],
        "observed_at": _iso(body["observed_at"], "observed_at"),
        "evidence_hash": _sha(body["evidence_hash"], "evidence_hash", 64),
        "evidence": clean_evidence,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
    if gate == "independent_verification" and semantic["passed"]:
        if not semantic["independent"] or role not in _INDEPENDENT_ROLES:
            raise ValueError("independent_verification pass requires an independent AEGIS, ASCENSION, or DAEDALUS reviewer")
    return semantic


class QualificationLedger:
    def __init__(self, base_dir: str | os.PathLike[str]):
        self.base_dir = Path(base_dir)

    def record(self, body: Mapping[str, Any]) -> dict[str, Any]:
        semantic = _normalize_receipt(body)
        receipt_id = _hash(semantic)
        path = _path(self.base_dir)
        path.parent.mkdir(parents=True, exist_ok=True)

        with _LOCK:
            rows, errors = self._read_raw()
            if errors:
                raise RuntimeError("qualification ledger integrity failure; refusing append")
            for row in rows:
                if row.get("receipt_id") == receipt_id:
                    return {
                        "ok": True,
                        "idempotent": True,
                        "receipt": row,
                        "execution_authorized": False,
                        "production_decision_authorized": False,
                    }

            prev_hash = str(rows[-1]["record_hash"]) if rows else "GENESIS"
            stored = {
                **semantic,
                "receipt_id": receipt_id,
                "sequence": len(rows) + 1,
                "prev_hash": prev_hash,
            }
            stored["record_hash"] = _hash(stored)
            raw = json.dumps(stored, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
            with path.open("a", encoding="utf-8") as fh:
                fh.write(raw)
                fh.flush()
                os.fsync(fh.fileno())

        return {
            "ok": True,
            "idempotent": False,
            "receipt": stored,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def _read_raw(self) -> tuple[list[dict[str, Any]], list[str]]:
        path = _path(self.base_dir)
        if not path.is_file():
            return [], []
        rows: list[dict[str, Any]] = []
        errors: list[str] = []
        prev = "GENESIS"
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as ex:
                errors.append(f"line {line_no}: invalid JSON: {ex}")
                continue
            if not isinstance(row, dict):
                errors.append(f"line {line_no}: record is not an object")
                continue
            supplied = str(row.get("record_hash") or "")
            payload = dict(row)
            payload.pop("record_hash", None)
            expected = _hash(payload)
            if supplied != expected:
                errors.append(f"line {line_no}: record hash mismatch")
            if str(row.get("prev_hash") or "") != prev:
                errors.append(f"line {line_no}: previous hash mismatch")
            if row.get("schema_version") != RECEIPT_SCHEMA:
                errors.append(f"line {line_no}: wrong schema")
            if row.get("execution_authorized") is not False or row.get("production_decision_authorized") is not False:
                errors.append(f"line {line_no}: authority violation")
            prev = supplied or expected
            rows.append(row)
        return rows, errors

    def snapshot(self, candidate: Mapping[str, Any], *, min_independent_reviewers: int = 2) -> dict[str, Any]:
        if isinstance(min_independent_reviewers, bool) or not isinstance(min_independent_reviewers, int) or min_independent_reviewers < 1:
            raise ValueError("min_independent_reviewers must be an integer >= 1")
        cid, repo, commit = _candidate_identity(candidate)
        rows, errors = self._read_raw()
        matching = [
            row for row in rows
            if row.get("candidate_id") == cid
            and row.get("source_repo") == repo
            and row.get("source_commit") == commit
        ]

        candidate_validation = candidate.get("validation") if isinstance(candidate.get("validation"), Mapping) else {}
        # Candidate-declared validation is informational only. Qualification
        # authority comes exclusively from immutable, exact-revision receipts.
        gate_state: dict[str, bool | None] = {gate: None for gate in REQUIRED_GATES}
        evidence_by_gate: dict[str, list[str]] = {gate: [] for gate in REQUIRED_GATES}
        reviewer_sets: dict[str, set[str]] = {gate: set() for gate in REQUIRED_GATES}

        for row in matching:
            gate = str(row.get("gate") or "")
            if gate not in gate_state:
                continue
            gate_state[gate] = bool(row.get("passed"))
            evidence_by_gate[gate].append(str(row.get("record_hash") or ""))
            if row.get("independent") is True and row.get("passed") is True:
                reviewer_sets[gate].add(str(row.get("reviewer_id") or ""))

        independent_count = len(reviewer_sets["independent_verification"])
        if gate_state["independent_verification"] is True and independent_count < min_independent_reviewers:
            gate_state["independent_verification"] = False

        blockers = [gate for gate in REQUIRED_GATES if gate_state.get(gate) is not True]
        ready = not errors and not blockers
        return {
            "schema_version": SCHEMA_VERSION,
            "candidate_id": cid,
            "source_repo": repo,
            "source_commit": commit,
            "qualified_shadow_ready": ready,
            "gate_state": gate_state,
            "candidate_declared_validation": {
                gate: (candidate_validation.get(gate) if type(candidate_validation.get(gate)) is bool else None)
                for gate in REQUIRED_GATES
            },
            "gate_receipt_hashes": evidence_by_gate,
            "independent_reviewers": sorted(reviewer_sets["independent_verification"]),
            "required_independent_reviewers": min_independent_reviewers,
            "blockers": (["qualification ledger integrity failure"] if errors else []) + blockers,
            "ledger_errors": errors,
            "receipt_count": len(matching),
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def qualification_event(self, candidate: Mapping[str, Any], *, min_independent_reviewers: int = 2) -> dict[str, Any]:
        snap = self.snapshot(candidate, min_independent_reviewers=min_independent_reviewers)
        if not snap["qualified_shadow_ready"]:
            raise ValueError("candidate is not qualified_shadow ready: " + ", ".join(snap["blockers"]))
        cid, repo, commit = _candidate_identity(candidate)
        regimes = candidate.get("regimes") if isinstance(candidate.get("regimes"), list) else []
        metrics = candidate.get("metrics") if isinstance(candidate.get("metrics"), Mapping) else {}
        evidence = []
        for hashes in snap["gate_receipt_hashes"].values():
            evidence.extend(h for h in hashes if h)
        return {
            "kind": "candidate",
            "subject": cid,
            "summary": "Candidate satisfied every ICARUS proof gate with append-only exact-revision receipts and is eligible for shadow routing only.",
            "status": "qualified",
            "candidate_id": cid,
            "stage": "qualified_shadow",
            "regimes": regimes or ["UNCLASSIFIED"],
            "metrics": dict(metrics),
            "validation": {gate: True for gate in REQUIRED_GATES},
            "source_repo": repo,
            "source_commit": commit,
            "evidence": evidence[-32:],
            "details": {
                "qualification_schema": SCHEMA_VERSION,
                "receipt_count": snap["receipt_count"],
                "independent_reviewers": snap["independent_reviewers"],
                "execution_authorized": False,
                "production_decision_authorized": False,
            },
        }
