"""ASCENDANCY external research work-order board.

The board converts governor actions that stopped at an external boundary into
typed, durable work orders.  It routes work to the appropriate research owner
but does not execute the work and does not accept a work-order claim as
scientific completion.

A work order is coordination metadata, not evidence. Domain-specific receipts
(evaluator, holdout, qualification, Foundry, genome lineage, etc.) remain the
only way to establish the corresponding scientific/research state.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .evaluator import EvaluatorCascade, _normalize_receipt

SCHEMA_VERSION = "icarus-ascendancy-work-order-board-v1"
ORDER_SCHEMA_VERSION = "icarus-ascendancy-work-order-v1"
CLAIM_SCHEMA_VERSION = "icarus-ascendancy-work-order-claim-v1"
_LOCK = threading.RLock()

_STAGE_OWNER = {
    "CONTRACT_VALIDATION": "daedalus",
    "SMOKE_NULLS": "daedalus",
    "LOW_FIDELITY_REPLAY": "aion",
    "ABLATION": "daedalus",
    "WALK_FORWARD": "aion",
    "OOS": "aion",
    "PROTECTED_HOLDOUT": "protected-qualification",
    "CONDITIONAL_CONTRIBUTION": "daedalus",
    "ROBUSTNESS": "daedalus",
    "QUALIFICATION_PREFLIGHT": "daedalus",
}

_ROUTING = {
    "REQUEST_PROTECTED_HOLDOUT": ("protected-qualification", "PROTECTED_HOLDOUT_REQUEST"),
    "SUBMIT_FOR_INDEPENDENT_QUALIFICATION": ("protected-qualification", "QUALIFICATION_REVIEW"),
    "INCUBATE_CANDIDATE": ("daedalus", "CANDIDATE_REVIEW"),
    "GENERATE_UNKNOWN_HYPOTHESES": ("aion", "HYPOTHESIS_SYNTHESIS"),
    "SPAWN_GENOME_DESCENDANT": ("omega", "ARCHITECTURE_MUTATION"),
    "MINE_FEDERATED_CONTEXT": ("omega", "FEDERATED_CONTEXT_ANALYSIS"),
    "REVIEW_RESOURCE_EXHAUSTION": ("omega", "RESOURCE_REVIEW"),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: Any, name: str = "value", max_bytes: int = 2_000_000) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{name} must be finite JSON") from ex
    if len(raw.encode("utf-8")) > max_bytes:
        raise ValueError(f"{name} exceeds {max_bytes} bytes")
    return raw


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value, "hash input").encode("utf-8")).hexdigest()


def _authority_false(value: Mapping[str, Any], label: str) -> None:
    if value.get("execution_authorized") is not False:
        raise ValueError(f"{label} authority boundary requires execution_authorized=false")
    if value.get("production_decision_authorized") is not False:
        raise ValueError(
            f"{label} authority boundary requires production_decision_authorized=false"
        )
    if value.get("trading_authority") is True:
        raise ValueError(f"{label} trading authority escalation is forbidden")
    if value.get("qualified_shadow") is True:
        raise ValueError(f"{label} qualification authority escalation is forbidden")


def _route(action: Mapping[str, Any]) -> tuple[str, str, str | None]:
    kind = str(action.get("kind") or "").strip().upper()
    details = action.get("details")
    details = details if isinstance(details, Mapping) else {}
    if kind == "RUN_EVALUATOR_STAGE":
        stage = str(details.get("stage") or "").strip().upper()
        if stage not in _STAGE_OWNER:
            raise ValueError(f"unsupported evaluator work-order stage: {stage}")
        return _STAGE_OWNER[stage], "EVALUATOR_EVIDENCE", stage
    if kind not in _ROUTING:
        raise ValueError(f"unsupported external work-order action kind: {kind}")
    owner, work_type = _ROUTING[kind]
    return owner, work_type, None


def _required_artifacts(kind: str, stage: str | None) -> list[str]:
    if kind == "RUN_EVALUATOR_STAGE":
        return [
            f"domain:evaluator-receipt:{stage}",
            "immutable-evaluation-contract",
            "provenance-bound-evidence",
        ]
    if kind == "REQUEST_PROTECTED_HOLDOUT":
        return ["externally-named-protected-holdout", "domain:evaluator-receipt:PROTECTED_HOLDOUT"]
    if kind == "SUBMIT_FOR_INDEPENDENT_QUALIFICATION":
        return ["domain:protected-qualification-receipt"]
    if kind == "INCUBATE_CANDIDATE":
        return ["domain:foundry-stage-review"]
    if kind == "GENERATE_UNKNOWN_HYPOTHESES":
        return ["falsifiable-hypothesis-proposal", "domain:foundry-candidate-link"]
    if kind == "SPAWN_GENOME_DESCENDANT":
        return ["falsifiable-genome-mutation", "domain:genome-lineage-receipt"]
    if kind == "MINE_FEDERATED_CONTEXT":
        return ["bounded-context-derived-hypothesis", "domain:foundry-admission-if-pursued"]
    if kind == "REVIEW_RESOURCE_EXHAUSTION":
        return ["resource-governance-review"]
    return ["domain-receipt"]


def _build_order(plan_id: str, action: Mapping[str, Any], receipt: Mapping[str, Any]) -> dict[str, Any]:
    _authority_false(action, "governor action")
    _authority_false(receipt, "executor receipt")
    kind = str(action.get("kind") or "").strip().upper()
    if str(receipt.get("kind") or "").strip().upper() != kind:
        raise ValueError("executor receipt kind does not match governor action")
    if str(receipt.get("action_id") or "") != str(action.get("action_id") or ""):
        raise ValueError("executor receipt action_id does not match governor action")
    status = str(receipt.get("status") or "").strip().upper()
    if not status.startswith("AWAITING_"):
        raise ValueError("work order requires an AWAITING_* executor receipt")

    owner, work_type, stage = _route(action)
    semantic: dict[str, Any] = {
        "schema_version": ORDER_SCHEMA_VERSION,
        "plan_id": str(plan_id),
        "action_id": str(action.get("action_id") or ""),
        "kind": kind,
        "subject_id": str(action.get("subject_id") or ""),
        "niche_key": str(action.get("niche_key") or ""),
        "owner_subsystem": owner,
        "work_type": work_type,
        "evaluator_stage": stage,
        "source_executor_status": status,
        "priority_score": action.get("priority_score"),
        "priority_basis": action.get("priority_basis"),
        "estimated_cost_units": action.get("estimated_cost_units"),
        "reason": action.get("reason"),
        "required_artifacts": _required_artifacts(kind, stage),
        "completion_requires_domain_receipt": True,
        "order_itself_is_evidence": False,
        "scientific_evidence": False,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
    semantic["order_id"] = _hash(semantic)
    return semantic


class ResearchWorkOrderBoard:
    """Durable queue of external research work required by governor plans."""

    def __init__(self, base_dir: str | os.PathLike[str], *, evaluator: EvaluatorCascade | None = None):
        self.base_dir = Path(base_dir)
        if evaluator is not None and evaluator.base_dir.resolve() != self.base_dir.resolve():
            raise ValueError("work orders and evaluator must share a base directory")
        self.evaluator = evaluator
        self.path = self.base_dir / "research" / "ascendancy_work_orders.sqlite3"
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
                CREATE TABLE IF NOT EXISTS work_orders (
                    order_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    action_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    owner_subsystem TEXT NOT NULL,
                    work_type TEXT NOT NULL,
                    semantic_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(plan_id, action_id)
                );
                CREATE INDEX IF NOT EXISTS idx_asc_work_order_owner
                    ON work_orders(owner_subsystem, created_at, order_id);

                CREATE TABLE IF NOT EXISTS claims (
                    order_id TEXT PRIMARY KEY,
                    claim_id TEXT NOT NULL UNIQUE,
                    worker_id TEXT NOT NULL,
                    owner_subsystem TEXT NOT NULL,
                    semantic_json TEXT NOT NULL,
                    claimed_at TEXT NOT NULL
                );
                """
            )

    def close(self) -> None:
        return None

    @staticmethod
    def _decode_order(row: sqlite3.Row) -> dict[str, Any]:
        try:
            item = json.loads(row["semantic_json"])
        except (TypeError, json.JSONDecodeError) as ex:
            raise RuntimeError("work-order storage corruption") from ex
        if not isinstance(item, dict):
            raise RuntimeError("work-order storage corruption")
        item["created_at"] = str(row["created_at"])
        return item

    def dispatch(
        self,
        plan: Mapping[str, Any],
        executor_result: Mapping[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(plan, Mapping) or not isinstance(executor_result, Mapping):
            raise ValueError("work-order dispatch requires plan and executor result objects")
        _authority_false(plan, "governor plan")
        _authority_false(executor_result, "executor result")
        plan_id = str(plan.get("plan_id") or "")
        if not plan_id:
            raise ValueError("governor plan_id is required")
        if str(executor_result.get("plan_id") or "") != plan_id:
            raise ValueError("executor result plan_id does not match governor plan")

        actions = {
            str(row.get("action_id") or ""): row
            for row in (plan.get("actions") or [])
            if isinstance(row, Mapping) and row.get("action_id")
        }
        receipts = [
            row for row in (executor_result.get("receipts") or [])
            if isinstance(row, Mapping)
        ]

        orders: list[dict[str, Any]] = []
        created_count = 0
        for receipt in receipts:
            status = str(receipt.get("status") or "").upper()
            if not status.startswith("AWAITING_"):
                continue
            action_id = str(receipt.get("action_id") or "")
            action = actions.get(action_id)
            if action is None:
                raise ValueError("executor receipt references unknown governor action")
            order = _build_order(plan_id, action, receipt)
            raw = _canonical(order, "work order")
            now = _utc_now()
            with _LOCK, self._connect() as con:
                existing = con.execute(
                    "SELECT * FROM work_orders WHERE plan_id=? AND action_id=?",
                    (plan_id, action_id),
                ).fetchone()
                if existing is not None:
                    prior = self._decode_order(existing)
                    prior.pop("created_at", None)
                    if _canonical(prior, "stored work order") != raw:
                        raise RuntimeError("work-order identity integrity failure")
                    out = dict(prior)
                    out["created_at"] = str(existing["created_at"])
                    out["idempotent"] = True
                    orders.append(out)
                    continue

                con.execute(
                    """INSERT INTO work_orders(
                        order_id,plan_id,action_id,kind,owner_subsystem,
                        work_type,semantic_json,created_at
                    ) VALUES(?,?,?,?,?,?,?,?)""",
                    (
                        order["order_id"],
                        plan_id,
                        action_id,
                        order["kind"],
                        order["owner_subsystem"],
                        order["work_type"],
                        raw,
                        now,
                    ),
                )
            out = dict(order)
            out["created_at"] = now
            out["idempotent"] = False
            orders.append(out)
            created_count += 1

        return {
            "schema_version": SCHEMA_VERSION,
            "plan_id": plan_id,
            "order_count": len(orders),
            "created_count": created_count,
            "orders": orders,
            "truth_contract": {
                "work_order_is_not_scientific_evidence": True,
                "domain_receipt_required_before_completion": True,
                "claim_is_coordination_not_completion": True,
                "work_orders_cannot_grant_trading_authority": True,
            },
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def claim(
        self,
        order_id: str,
        *,
        worker_id: str,
        owner_subsystem: str,
    ) -> dict[str, Any]:
        oid = str(order_id or "").strip()
        worker = str(worker_id or "").strip()
        owner = str(owner_subsystem or "").strip().lower()
        if not oid or not worker or not owner:
            raise ValueError("order_id, worker_id, and owner_subsystem are required")

        with _LOCK, self._connect() as con:
            order_row = con.execute(
                "SELECT * FROM work_orders WHERE order_id=?",
                (oid,),
            ).fetchone()
            if order_row is None:
                raise ValueError("unknown work order")
            order = self._decode_order(order_row)
            expected_owner = str(order["owner_subsystem"]).lower()
            if owner != expected_owner:
                raise ValueError(
                    f"work order owner mismatch; expected {expected_owner}"
                )

            existing = con.execute(
                "SELECT * FROM claims WHERE order_id=?",
                (oid,),
            ).fetchone()
            if existing is not None:
                if (
                    str(existing["worker_id"]) != worker
                    or str(existing["owner_subsystem"]).lower() != owner
                ):
                    raise ValueError("work order is already claimed by another worker")
                claim = json.loads(existing["semantic_json"])
                return {
                    "order_id": oid,
                    "status": "CLAIMED",
                    "claim_receipt": claim,
                    "idempotent": True,
                    "execution_authorized": False,
                    "production_decision_authorized": False,
                }

            semantic = {
                "schema_version": CLAIM_SCHEMA_VERSION,
                "order_id": oid,
                "worker_id": worker,
                "owner_subsystem": owner,
                "scientific_evidence": False,
                "completion": False,
                "execution_authorized": False,
                "production_decision_authorized": False,
            }
            semantic["claim_id"] = _hash(semantic)
            now = _utc_now()
            con.execute(
                """INSERT INTO claims(
                    order_id,claim_id,worker_id,owner_subsystem,
                    semantic_json,claimed_at
                ) VALUES(?,?,?,?,?,?)""",
                (
                    oid,
                    semantic["claim_id"],
                    worker,
                    owner,
                    _canonical(semantic, "claim receipt"),
                    now,
                ),
            )
        claim = dict(semantic)
        claim["claimed_at"] = now
        return {
            "order_id": oid,
            "status": "CLAIMED",
            "claim_receipt": claim,
            "idempotent": False,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def snapshot(self) -> dict[str, Any]:
        ledger = (self.evaluator or EvaluatorCascade(self.base_dir)).snapshot()
        candidates = {row["candidate_id"]: row for row in ledger["candidates"]}
        domain_results: dict[tuple[str, str], dict[str, Any]] = {}
        for receipt in ledger["receipts"]:
            try:
                normalized = _normalize_receipt(receipt)
            except (ValueError, TypeError) as ex:
                raise RuntimeError("work-order evaluator receipt corruption") from ex
            candidate = candidates.get(normalized["candidate_id"])
            if (
                candidate is None or normalized["receipt_id"] != receipt.get("receipt_id")
                or any(normalized[key] != candidate[key] for key in (
                    "source_repo", "source_commit", "evaluation_contract_hash"
                ))
            ):
                raise RuntimeError("work-order evaluator receipt identity mismatch")
            key = (normalized["candidate_id"], normalized["stage"])
            previous = domain_results.get(key)
            # An accepted conclusive result cannot be replaced by an earlier
            # inconclusive attempt merely because its observation time differs.
            if previous is None or normalized["outcome"] != "INCONCLUSIVE":
                domain_results[key] = normalized
        with _LOCK, self._connect() as con:
            order_rows = con.execute(
                "SELECT * FROM work_orders ORDER BY created_at,order_id"
            ).fetchall()
            claim_rows = con.execute(
                "SELECT order_id,semantic_json,claimed_at FROM claims ORDER BY claimed_at,order_id"
            ).fetchall()

        claims: dict[str, dict[str, Any]] = {}
        for row in claim_rows:
            try:
                item = json.loads(row["semantic_json"])
            except (TypeError, json.JSONDecodeError) as ex:
                raise RuntimeError("work-order claim storage corruption") from ex
            if not isinstance(item, dict):
                raise RuntimeError("work-order claim storage corruption")
            item["claimed_at"] = str(row["claimed_at"])
            claims[str(row["order_id"])] = item

        orders: list[dict[str, Any]] = []
        for row in order_rows:
            order = self._decode_order(row)
            claim = claims.get(str(order["order_id"]))
            order["status"] = "CLAIMED" if claim else "OPEN"
            order["claim"] = claim
            lookup_stage = "PROTECTED_HOLDOUT" if order["kind"] == "REQUEST_PROTECTED_HOLDOUT" else order.get("evaluator_stage")
            result = domain_results.get((order["subject_id"], lookup_stage))
            order["domain_result"] = None
            if result is not None and order["kind"] in {"RUN_EVALUATOR_STAGE", "REQUEST_PROTECTED_HOLDOUT"}:
                order["domain_result"] = {
                    key: result[key] for key in (
                        "receipt_id", "stage", "outcome", "observed_at",
                        "source_repo", "source_commit", "evaluation_contract_hash",
                    )
                }
                if result["outcome"] in {"PASS", "FAIL"}:
                    order["status"] = "COMPLETED"
            orders.append(order)

        open_count = sum(1 for x in orders if x["status"] == "OPEN")
        claimed_count = sum(1 for x in orders if x["status"] == "CLAIMED")
        owner_counts: dict[str, int] = {}
        for row in orders:
            owner = str(row["owner_subsystem"])
            owner_counts[owner] = owner_counts.get(owner, 0) + 1

        return {
            "schema_version": SCHEMA_VERSION,
            "journal_mode": self.journal_mode,
            "order_count": len(orders),
            "open_count": open_count,
            "claimed_count": claimed_count,
            "completed_count": sum(x["status"] == "COMPLETED" for x in orders),
            "owner_counts": dict(sorted(owner_counts.items())),
            "orders": orders,
            "truth_contract": {
                "work_order_is_not_scientific_evidence": True,
                "domain_receipt_required_before_completion": True,
                "claim_is_coordination_not_completion": True,
                "completion_state_is_not_minted_by_work_order_board": True,
                "work_orders_cannot_grant_trading_authority": True,
            },
            "execution_authorized": False,
            "production_decision_authorized": False,
        }
