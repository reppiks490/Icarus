"""ASCENDANCY multi-fidelity evaluator cascade and resource governor.

The cascade spends cheap evidence before expensive evidence, preserves exact
candidate/evaluator provenance, prevents stage skipping, records inconclusive
work without pretending it passed, and treats protected-holdout exposure as a
consumable research event.

It never grants qualified_shadow, production-decision authority, or execution
authority. Final success means only READY_FOR_PROTECTED_QUALIFICATION.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .foundry import normalize_candidate

SCHEMA_VERSION = "icarus-ascendancy-evaluator-v1"
RECEIPT_SCHEMA_VERSION = "icarus-ascendancy-evaluator-receipt-v1"

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_LOCK = threading.RLock()

_STAGES = (
    {
        "id": "CONTRACT_VALIDATION",
        "fidelity": "contract",
        "purpose": "Validate provenance, data/evaluator contracts, falsifiers and resource bounds before spending research budget.",
    },
    {
        "id": "SMOKE_NULLS",
        "fidelity": "cheap",
        "purpose": "Cheap null, leakage, malformed-output and impossible-claim screens.",
    },
    {
        "id": "LOW_FIDELITY_REPLAY",
        "fidelity": "low",
        "purpose": "Small or reduced-fidelity causal replay for early elimination.",
    },
    {
        "id": "ABLATION",
        "fidelity": "medium",
        "purpose": "Test whether the claimed mechanism contributes under paired removal/perturbation.",
    },
    {
        "id": "WALK_FORWARD",
        "fidelity": "medium",
        "purpose": "Chronological stability screen before expensive protected evaluation.",
    },
    {
        "id": "OOS",
        "fidelity": "high",
        "purpose": "Out-of-sample evaluation under the immutable evaluator contract.",
    },
    {
        "id": "PROTECTED_HOLDOUT",
        "fidelity": "protected",
        "purpose": "Consume one named protected holdout generation exactly once per evaluator contract.",
    },
    {
        "id": "CONDITIONAL_CONTRIBUTION",
        "fidelity": "high",
        "purpose": "Measure incremental predictive information conditional on the declared ICARUS baseline.",
    },
    {
        "id": "ROBUSTNESS",
        "fidelity": "high",
        "purpose": "Stress regimes, costs, latency, calibration, OOD/drift and dependence-adjusted stability.",
    },
    {
        "id": "QUALIFICATION_PREFLIGHT",
        "fidelity": "audit",
        "purpose": "Check readiness for the independent protected qualification ledger without minting qualification.",
    },
)
_STAGE_IDS = tuple(row["id"] for row in _STAGES)
_OUTCOMES = {"PASS", "FAIL", "INCONCLUSIVE"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _text(value: Any, name: str, limit: int = 1000) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    out = value.strip()
    if not out:
        raise ValueError(f"{name} is required")
    if len(out) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return out


def _canonical(value: Any, name: str = "value", max_bytes: int = 262144) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{name} must be finite JSON") from ex
    if len(raw.encode("utf-8")) > max_bytes:
        raise ValueError(f"{name} exceeds {max_bytes} bytes")
    return raw


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value, "hash input").encode("utf-8")).hexdigest()


def _sha(value: Any, name: str, size: int) -> str:
    out = _text(value, name, size).lower()
    pattern = _SHA40 if size == 40 else _SHA64
    if not pattern.fullmatch(out):
        if size == 40:
            raise ValueError(f"{name} must be an exact 40-character Git SHA")
        raise ValueError(f"{name} must be a {size}-character hash")
    return out


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be finite")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite")
    return out


def _nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value


def _observed_at(value: Any) -> str:
    raw = _text(value, "observed_at", 80)
    probe = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        dt = datetime.fromisoformat(probe)
    except ValueError as ex:
        raise ValueError("observed_at must be ISO-8601") from ex
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("observed_at must include a timezone")
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def evaluation_stage_catalog() -> list[dict[str, Any]]:
    """Return the immutable evaluator order and fidelity labels."""
    return [
        {
            **row,
            "stage_index": idx,
            "grants_qualification": False,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }
        for idx, row in enumerate(_STAGES)
    ]


def research_priority(expected_information_gain: float, expected_cost_units: float) -> float:
    """Transparent information-gain-per-cost priority score."""
    gain = _finite(expected_information_gain, "expected_information_gain")
    cost = _finite(expected_cost_units, "expected_cost_units")
    if cost <= 0.0:
        raise ValueError("expected cost must be positive")
    return max(0.0, gain) / cost


def _normalize_usage(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("resource_usage must be an object")
    evaluations = _nonnegative_int(value.get("evaluations"), "resource_usage.evaluations")
    wall = _finite(value.get("wall_seconds"), "resource_usage.wall_seconds")
    cost = _finite(value.get("cost_units"), "resource_usage.cost_units")
    if wall < 0.0 or cost < 0.0:
        raise ValueError("resource_usage values must be nonnegative")
    return {
        "evaluations": evaluations,
        "wall_seconds": wall,
        "cost_units": cost,
    }


def _normalize_receipt(body: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(body, Mapping):
        raise ValueError("evaluation receipt must be an object")
    if body.get("execution_authorized") not in (None, False):
        raise ValueError("evaluation receipt cannot grant execution authority")
    if body.get("production_decision_authorized") not in (None, False):
        raise ValueError("evaluation receipt cannot grant production authority")

    candidate_id = _sha(body.get("candidate_id"), "candidate_id", 64)
    contract = _sha(body.get("evaluation_contract_hash"), "evaluation_contract_hash", 64)
    source_repo = _text(body.get("source_repo"), "source_repo", 180)
    source_commit = _sha(body.get("source_commit"), "source_commit", 40)
    stage = _text(body.get("stage"), "stage", 64).upper()
    if stage not in _STAGE_IDS:
        raise ValueError("unsupported evaluator stage")
    outcome = _text(body.get("outcome"), "outcome", 32).upper()
    if outcome not in _OUTCOMES:
        raise ValueError("outcome must be PASS, FAIL, or INCONCLUSIVE")

    metrics_value = body.get("metrics")
    if not isinstance(metrics_value, Mapping):
        raise ValueError("metrics must be an object")
    metrics = dict(metrics_value)
    _canonical(metrics, "metrics", 65536)

    evidence_value = body.get("evidence")
    if (
        not isinstance(evidence_value, Sequence)
        or isinstance(evidence_value, (str, bytes))
        or not evidence_value
    ):
        raise ValueError("evaluation evidence is required")
    evidence = sorted({_text(x, "evidence item", 700) for x in evidence_value})
    if len(evidence) > 128:
        raise ValueError("too many evidence items")

    usage = _normalize_usage(body.get("resource_usage"))
    observed = _observed_at(body.get("observed_at"))

    holdout_id = None
    if body.get("holdout_id") not in (None, ""):
        holdout_id = _text(body.get("holdout_id"), "holdout_id", 180)
    if stage == "PROTECTED_HOLDOUT" and holdout_id is None:
        raise ValueError("holdout_id is required for PROTECTED_HOLDOUT")

    semantic: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "evaluation_contract_hash": contract,
        "source_repo": source_repo,
        "source_commit": source_commit,
        "stage": stage,
        "outcome": outcome,
        "metrics": metrics,
        "evidence": evidence,
        "resource_usage": usage,
        "holdout_id": holdout_id,
        "observed_at": observed,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
    semantic["receipt_id"] = _hash(semantic)
    return semantic


class EvaluatorCascade:
    """Durable staged evaluator with fail-fast and holdout-consumption rules."""

    def __init__(self, base_dir: str | os.PathLike[str]):
        self.base_dir = Path(base_dir)
        self.path = self.base_dir / "research" / "ascendancy_evaluator.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path), timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        return con

    @property
    def journal_mode(self) -> str:
        with self._connect() as con:
            return str(con.execute("PRAGMA journal_mode").fetchone()[0]).lower()

    def _init(self) -> None:
        with _LOCK, self._connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS candidates (
                    candidate_id TEXT PRIMARY KEY,
                    source_repo TEXT NOT NULL,
                    source_commit TEXT NOT NULL,
                    evaluation_contract_hash TEXT NOT NULL,
                    candidate_json TEXT NOT NULL,
                    resource_budget_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    stage_index INTEGER NOT NULL,
                    used_evaluations INTEGER NOT NULL DEFAULT 0,
                    used_wall_seconds REAL NOT NULL DEFAULT 0,
                    used_cost_units REAL NOT NULL DEFAULT 0,
                    completed_stage_count INTEGER NOT NULL DEFAULT 0,
                    receipt_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS receipts (
                    receipt_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    evaluation_contract_hash TEXT NOT NULL,
                    holdout_id TEXT,
                    semantic_json TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_asc_eval_receipts_candidate
                    ON receipts(candidate_id, observed_at, receipt_id);

                CREATE TABLE IF NOT EXISTS holdout_exposures (
                    evaluation_contract_hash TEXT NOT NULL,
                    holdout_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    receipt_id TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY(evaluation_contract_hash, holdout_id)
                );
                CREATE INDEX IF NOT EXISTS idx_asc_eval_holdout_candidate
                    ON holdout_exposures(candidate_id, observed_at);
                """
            )

    def close(self) -> None:
        return None

    def _candidate_row(self, candidate_id: str, con: sqlite3.Connection | None = None) -> sqlite3.Row:
        cid = _sha(candidate_id, "candidate_id", 64)
        owns = con is None
        db = con or self._connect()
        try:
            row = db.execute(
                "SELECT * FROM candidates WHERE candidate_id=?",
                (cid,),
            ).fetchone()
        finally:
            if owns:
                db.close()
        if row is None:
            raise ValueError("unknown evaluator candidate_id")
        return row

    @staticmethod
    def _decode_candidate(row: sqlite3.Row) -> dict[str, Any]:
        try:
            candidate = json.loads(row["candidate_json"])
            budget = json.loads(row["resource_budget_json"])
        except (TypeError, json.JSONDecodeError) as ex:
            raise RuntimeError("evaluator candidate storage corruption") from ex
        if not isinstance(candidate, dict) or not isinstance(budget, dict):
            raise RuntimeError("evaluator candidate storage corruption")
        idx = int(row["stage_index"])
        state = str(row["state"])
        next_stage = _STAGE_IDS[idx] if state == "EVALUATING" and idx < len(_STAGE_IDS) else None
        used = {
            "evaluations": int(row["used_evaluations"]),
            "wall_seconds": float(row["used_wall_seconds"]),
            "cost_units": float(row["used_cost_units"]),
        }
        remaining = {
            "evaluations": max(0, int(budget["max_evaluations"]) - used["evaluations"]),
            "wall_seconds": max(0.0, float(budget["max_wall_seconds"]) - used["wall_seconds"]),
            "cost_units": max(0.0, float(budget["max_cost_units"]) - used["cost_units"]),
        }
        return {
            "candidate_id": str(row["candidate_id"]),
            "source_repo": str(row["source_repo"]),
            "source_commit": str(row["source_commit"]),
            "evaluation_contract_hash": str(row["evaluation_contract_hash"]),
            "state": state,
            "next_stage": next_stage,
            "stage_index": idx,
            "completed_stage_count": int(row["completed_stage_count"]),
            "receipt_count": int(row["receipt_count"]),
            "resource_budget": budget,
            "resource_used": used,
            "resource_remaining": remaining,
            "qualified_shadow": False,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def register_candidate(self, body: Mapping[str, Any]) -> dict[str, Any]:
        candidate = normalize_candidate(body)
        cid = str(candidate["candidate_id"])
        contract = str(candidate["evaluation_contract"]["contract_hash"])
        budget = dict(candidate["resource_budget"])
        raw = _canonical(candidate, "candidate")
        budget_raw = _canonical(budget, "resource_budget")
        now = _utc_now()

        with _LOCK, self._connect() as con:
            existing = con.execute(
                "SELECT * FROM candidates WHERE candidate_id=?",
                (cid,),
            ).fetchone()
            if existing is not None:
                if str(existing["candidate_json"]) != raw:
                    raise RuntimeError("evaluator candidate identity integrity failure")
                return {
                    "idempotent": True,
                    "candidate": self._decode_candidate(existing),
                    "execution_authorized": False,
                    "production_decision_authorized": False,
                }

            con.execute(
                """INSERT INTO candidates(
                    candidate_id,source_repo,source_commit,evaluation_contract_hash,
                    candidate_json,resource_budget_json,state,stage_index,
                    used_evaluations,used_wall_seconds,used_cost_units,
                    completed_stage_count,receipt_count,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    cid,
                    candidate["source_repo"],
                    candidate["source_commit"],
                    contract,
                    raw,
                    budget_raw,
                    "EVALUATING",
                    0,
                    0,
                    0.0,
                    0.0,
                    0,
                    0,
                    now,
                    now,
                ),
            )
            row = con.execute(
                "SELECT * FROM candidates WHERE candidate_id=?",
                (cid,),
            ).fetchone()
        if row is None:
            raise RuntimeError("evaluator candidate registration did not persist")
        return {
            "idempotent": False,
            "candidate": self._decode_candidate(row),
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def candidate(self, candidate_id: str) -> dict[str, Any]:
        return self._decode_candidate(self._candidate_row(candidate_id))

    def record(self, body: Mapping[str, Any]) -> dict[str, Any]:
        receipt = _normalize_receipt(body)
        cid = receipt["candidate_id"]
        rid = receipt["receipt_id"]
        now = _utc_now()

        with _LOCK, self._connect() as con:
            # Exact retries are idempotent even after a prior PASS advanced state.
            existing = con.execute(
                "SELECT semantic_json FROM receipts WHERE receipt_id=?",
                (rid,),
            ).fetchone()
            if existing is not None:
                if str(existing["semantic_json"]) != _canonical(receipt, "receipt"):
                    raise RuntimeError("evaluator receipt identity integrity failure")
                row = self._candidate_row(cid, con)
                return {
                    "idempotent": True,
                    "receipt": receipt,
                    "candidate": self._decode_candidate(row),
                    "execution_authorized": False,
                    "production_decision_authorized": False,
                }

            row = self._candidate_row(cid, con)
            state = str(row["state"])
            if state != "EVALUATING":
                if state == "HALTED_FAILED":
                    raise ValueError("candidate is halted after evaluator failure")
                raise ValueError("candidate evaluation is complete and cannot accept more stages")

            idx = int(row["stage_index"])
            expected = _STAGE_IDS[idx] if idx < len(_STAGE_IDS) else None
            if receipt["stage"] != expected:
                raise ValueError(
                    f"expected stage {expected}; received {receipt['stage']}"
                )
            if receipt["evaluation_contract_hash"] != str(row["evaluation_contract_hash"]):
                raise ValueError("evaluation contract does not match registered candidate")
            if receipt["source_repo"] != str(row["source_repo"]):
                raise ValueError("source_repo does not match registered candidate")
            if receipt["source_commit"] != str(row["source_commit"]):
                raise ValueError("source_commit does not match registered candidate")

            budget = json.loads(row["resource_budget_json"])
            usage = receipt["resource_usage"]
            next_evals = int(row["used_evaluations"]) + int(usage["evaluations"])
            next_wall = float(row["used_wall_seconds"]) + float(usage["wall_seconds"])
            next_cost = float(row["used_cost_units"]) + float(usage["cost_units"])
            if (
                next_evals > int(budget["max_evaluations"])
                or next_wall > float(budget["max_wall_seconds"])
                or next_cost > float(budget["max_cost_units"])
            ):
                raise ValueError("candidate resource budget would be exceeded")

            if receipt["stage"] == "PROTECTED_HOLDOUT":
                holdout_id = str(receipt["holdout_id"])
                exposure = con.execute(
                    """SELECT candidate_id,receipt_id FROM holdout_exposures
                       WHERE evaluation_contract_hash=? AND holdout_id=?""",
                    (receipt["evaluation_contract_hash"], holdout_id),
                ).fetchone()
                if exposure is not None:
                    raise ValueError(
                        "protected holdout generation has already been exposed under this evaluation contract"
                    )

            semantic_raw = _canonical(receipt, "receipt")
            con.execute(
                """INSERT INTO receipts(
                    receipt_id,candidate_id,stage,outcome,evaluation_contract_hash,
                    holdout_id,semantic_json,observed_at,recorded_at
                ) VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    rid,
                    cid,
                    receipt["stage"],
                    receipt["outcome"],
                    receipt["evaluation_contract_hash"],
                    receipt["holdout_id"],
                    semantic_raw,
                    receipt["observed_at"],
                    now,
                ),
            )
            if receipt["stage"] == "PROTECTED_HOLDOUT":
                con.execute(
                    """INSERT INTO holdout_exposures(
                        evaluation_contract_hash,holdout_id,candidate_id,
                        receipt_id,observed_at,recorded_at
                    ) VALUES(?,?,?,?,?,?)""",
                    (
                        receipt["evaluation_contract_hash"],
                        receipt["holdout_id"],
                        cid,
                        rid,
                        receipt["observed_at"],
                        now,
                    ),
                )

            new_state = "EVALUATING"
            new_index = idx
            completed = int(row["completed_stage_count"])
            if receipt["outcome"] == "PASS":
                completed += 1
                new_index += 1
                if new_index >= len(_STAGE_IDS):
                    new_state = "READY_FOR_PROTECTED_QUALIFICATION"
            elif receipt["outcome"] == "FAIL":
                new_state = "HALTED_FAILED"

            con.execute(
                """UPDATE candidates
                   SET state=?,stage_index=?,used_evaluations=?,
                       used_wall_seconds=?,used_cost_units=?,
                       completed_stage_count=?,receipt_count=receipt_count+1,
                       updated_at=?
                   WHERE candidate_id=?""",
                (
                    new_state,
                    new_index,
                    next_evals,
                    next_wall,
                    next_cost,
                    completed,
                    now,
                    cid,
                ),
            )
            updated = con.execute(
                "SELECT * FROM candidates WHERE candidate_id=?",
                (cid,),
            ).fetchone()

        if updated is None:
            raise RuntimeError("evaluator candidate state update did not persist")
        return {
            "idempotent": False,
            "receipt": receipt,
            "candidate": self._decode_candidate(updated),
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def snapshot(self) -> dict[str, Any]:
        with _LOCK, self._connect() as con:
            rows = con.execute(
                "SELECT * FROM candidates ORDER BY created_at,candidate_id"
            ).fetchall()
            receipt_rows = con.execute(
                """SELECT receipt_id,candidate_id,stage,outcome,
                          evaluation_contract_hash,holdout_id,semantic_json,
                          observed_at,recorded_at
                   FROM receipts
                   ORDER BY observed_at,receipt_id"""
            ).fetchall()
            holdouts = con.execute(
                """SELECT evaluation_contract_hash,holdout_id,candidate_id,
                          receipt_id,observed_at,recorded_at
                   FROM holdout_exposures
                   ORDER BY observed_at,holdout_id"""
            ).fetchall()

        candidates = [self._decode_candidate(row) for row in rows]
        receipts: list[dict[str, Any]] = []
        for row in receipt_rows:
            try:
                item = json.loads(row["semantic_json"])
            except (TypeError, json.JSONDecodeError) as ex:
                raise RuntimeError("evaluator receipt storage corruption") from ex
            if isinstance(item, dict):
                item["recorded_at"] = str(row["recorded_at"])
                receipts.append(item)

        state_counts: dict[str, int] = {}
        for row in candidates:
            state_counts[row["state"]] = state_counts.get(row["state"], 0) + 1

        return {
            "schema_version": SCHEMA_VERSION,
            "stage_catalog": evaluation_stage_catalog(),
            "candidate_count": len(candidates),
            "receipt_count": len(receipts),
            "holdout_exposure_count": len(holdouts),
            "state_counts": dict(sorted(state_counts.items())),
            "candidates": candidates,
            "receipts": receipts,
            "holdout_exposures": [
                {
                    "evaluation_contract_hash": str(row["evaluation_contract_hash"]),
                    "holdout_id": str(row["holdout_id"]),
                    "candidate_id": str(row["candidate_id"]),
                    "receipt_id": str(row["receipt_id"]),
                    "observed_at": str(row["observed_at"]),
                    "recorded_at": str(row["recorded_at"]),
                }
                for row in holdouts
            ],
            "truth_contract": {
                "stages_cannot_be_skipped": True,
                "inconclusive_consumes_budget_without_advancing": True,
                "failure_halts_candidate": True,
                "protected_holdout_exposure_is_consumable": True,
                "holdout_generation_reuse_blocked_per_evaluation_contract": True,
                "resource_budget_checked_before_receipt_commit": True,
                "cascade_cannot_mint_qualification": True,
                "ready_state_requires_independent_protected_qualification": True,
                "research_priority_is_expected_information_gain_per_cost": True,
            },
            "qualified_shadow": False,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }
