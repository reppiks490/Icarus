"""Safe internal executor for ASCENDANCY governor plans.

This executor applies only administrative research-state transitions whose truth
is already established elsewhere. It deliberately refuses to execute actions
that require scientific evidence, mechanism review, protected holdouts,
hypothesis generation, architecture mutation, or independent qualification.

Executor receipts are bookkeeping receipts only. They are never evaluator
receipts, scientific evidence, qualification receipts, or trading authority.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

SCHEMA_VERSION = "icarus-ascendancy-safe-executor-v1"
RECEIPT_SCHEMA_VERSION = "icarus-ascendancy-safe-executor-receipt-v1"

SAFE_INTERNAL_ACTION_KINDS = frozenset({
    "REGISTER_WITH_EVALUATOR",
    "PROMOTE_BLUEPRINT_TO_FOUNDRY",
    "REJECT_FAILED_CANDIDATE",
})

_EXTERNAL_AUTHORITY = frozenset({
    "REQUEST_PROTECTED_HOLDOUT",
    "SUBMIT_FOR_INDEPENDENT_QUALIFICATION",
})
_EXTERNAL_EVIDENCE = frozenset({
    "RUN_EVALUATOR_STAGE",
})
_EXTERNAL_RESEARCH = frozenset({
    "INCUBATE_CANDIDATE",
    "GENERATE_UNKNOWN_HYPOTHESES",
    "SPAWN_GENOME_DESCENDANT",
    "MINE_FEDERATED_CONTEXT",
})
_EXTERNAL_REVIEW = frozenset({
    "REVIEW_RESOURCE_EXHAUSTION",
})

_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_LOCK = threading.RLock()


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


def _sha64(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a 64-character hash")
    out = value.strip().lower()
    if not _SHA64.fullmatch(out):
        raise ValueError(f"{name} must be a 64-character hash")
    return out


def _validate_authority(value: Mapping[str, Any], label: str) -> None:
    for key in (
        "execution_authorized",
        "production_decision_authorized",
        "broker_authority",
    ):
        if value.get(key) is True:
            raise ValueError(f"{label} authority escalation is forbidden")
    if value.get("qualified_shadow") is True:
        raise ValueError(f"{label} qualification authority is forbidden")
    if value.get("can_mint_qualification") is True:
        raise ValueError(f"{label} qualification authority is forbidden")
    if value.get("can_mint_evaluator_receipts") is True:
        raise ValueError(f"{label} evaluator receipt authority is forbidden")


def _validate_action(action: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(action, Mapping):
        raise ValueError("governor action must be an object")
    row = dict(action)
    _validate_authority(row, "governor action")
    action_id = _sha64(row.get("action_id"), "action_id")
    unsigned = {k: v for k, v in row.items() if k != "action_id"}
    if _hash(unsigned) != action_id:
        raise ValueError("action_id integrity mismatch")
    if row.get("priority_basis") != "scheduler_heuristic_not_edge_score":
        raise ValueError("governor action priority basis mismatch")
    kind = str(row.get("kind") or "").strip().upper()
    if not kind:
        raise ValueError("governor action kind is required")
    row["kind"] = kind
    return row


def _validate_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, Mapping):
        raise ValueError("governor plan must be an object")
    row = dict(plan)
    _validate_authority(row, "governor plan")
    if row.get("schema_version") != "icarus-ascendancy-governor-plan-v1":
        raise ValueError("unsupported governor plan schema_version")
    if row.get("can_mint_evaluator_receipts") is not False:
        raise ValueError("governor plan evaluator receipt authority must be false")
    if row.get("can_mint_qualification") is not False:
        raise ValueError("governor plan qualification authority must be false")

    plan_id = _sha64(row.get("plan_id"), "plan_id")
    unsigned = {k: v for k, v in row.items() if k != "plan_id"}
    if _hash(unsigned) != plan_id:
        raise ValueError("plan_id integrity mismatch")

    raw_actions = row.get("actions")
    if not isinstance(raw_actions, Sequence) or isinstance(raw_actions, (str, bytes)):
        raise ValueError("governor plan actions must be a list")
    actions = [_validate_action(x) for x in raw_actions]
    action_ids = [x["action_id"] for x in actions]
    if len(action_ids) != len(set(action_ids)):
        raise ValueError("duplicate action_id in governor plan")
    if int(row.get("action_count") or 0) != len(actions):
        raise ValueError("governor plan action_count mismatch")
    row["actions"] = actions
    return row


def _validate_handler_result(result: Any, kind: str) -> tuple[str, list[str]]:
    if result is None:
        value: Mapping[str, Any] = {}
    elif isinstance(result, Mapping):
        value = result
    else:
        raise ValueError(f"{kind} internal handler result must be an object")

    _validate_authority(value, f"{kind} handler result")
    forbidden = {
        "receipt",
        "evaluator_receipt",
        "qualification_receipt",
        "evaluation_outcome",
    }
    present = sorted(forbidden.intersection(value))
    if present:
        if "receipt" in present or "evaluator_receipt" in present:
            raise ValueError(
                f"{kind} internal handler cannot emit an evaluator receipt"
            )
        raise ValueError(f"{kind} internal handler cannot emit scientific authority")

    # Persist only a digest and top-level key list. The safe executor does not
    # convert administrative callback output into evidence.
    canonical = _canonical(value, "internal handler result", max_bytes=262144)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest(), sorted(
        str(k) for k in value.keys()
    )


def _external_status(kind: str) -> str:
    if kind in _EXTERNAL_AUTHORITY:
        return "AWAITING_EXTERNAL_AUTHORITY"
    if kind in _EXTERNAL_EVIDENCE:
        return "AWAITING_EXTERNAL_EVIDENCE"
    if kind in _EXTERNAL_RESEARCH:
        return "AWAITING_EXTERNAL_RESEARCH"
    if kind in _EXTERNAL_REVIEW:
        return "AWAITING_EXTERNAL_REVIEW"
    return "AWAITING_EXTERNAL_REVIEW"


def _receipt_semantic(
    plan_id: str,
    action: Mapping[str, Any],
    status: str,
    *,
    result_digest: str | None = None,
    result_keys: Sequence[str] | None = None,
    detail: str | None = None,
) -> dict[str, Any]:
    semantic: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "plan_id": plan_id,
        "action_id": action["action_id"],
        "kind": action["kind"],
        "subject_id": str(action.get("subject_id") or ""),
        "status": status,
        "result_digest": result_digest,
        "result_keys": list(result_keys or []),
        "detail": detail,
        "scientific_evidence": False,
        "evaluator_receipt": False,
        "qualification_receipt": False,
        "trading_authority": False,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
    semantic["receipt_id"] = _hash(semantic)
    return semantic


class GovernorExecutor:
    """Append-only executor for the governor's narrow safe-internal action set."""

    def __init__(self, base_dir: str | os.PathLike[str]):
        self.base_dir = Path(base_dir)
        self.path = self.base_dir / "research" / "ascendancy_executor.sqlite3"
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
                CREATE TABLE IF NOT EXISTS action_receipts (
                    receipt_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    action_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    semantic_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    UNIQUE(plan_id, action_id)
                );
                CREATE INDEX IF NOT EXISTS idx_asc_executor_plan
                    ON action_receipts(plan_id, recorded_at, action_id);
                CREATE INDEX IF NOT EXISTS idx_asc_executor_status
                    ON action_receipts(status, recorded_at);
                """
            )

    def close(self) -> None:
        return None

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        try:
            receipt = json.loads(row["semantic_json"])
        except (TypeError, json.JSONDecodeError) as ex:
            raise RuntimeError("governor executor receipt storage corruption") from ex
        if not isinstance(receipt, dict):
            raise RuntimeError("governor executor receipt storage corruption")
        receipt["recorded_at"] = str(row["recorded_at"])
        return receipt

    def _existing(self, plan_id: str, action_id: str) -> sqlite3.Row | None:
        with self._connect() as con:
            return con.execute(
                """SELECT * FROM action_receipts
                   WHERE plan_id=? AND action_id=?""",
                (plan_id, action_id),
            ).fetchone()

    def _persist(self, receipt: Mapping[str, Any]) -> dict[str, Any]:
        raw = _canonical(receipt, "executor receipt")
        now = _utc_now()
        with _LOCK, self._connect() as con:
            existing = con.execute(
                """SELECT * FROM action_receipts
                   WHERE plan_id=? AND action_id=?""",
                (receipt["plan_id"], receipt["action_id"]),
            ).fetchone()
            if existing is not None:
                prior = self._decode(existing)
                prior.pop("recorded_at", None)
                if _canonical(prior, "stored executor receipt") != raw:
                    raise RuntimeError("governor executor action identity integrity failure")
                out = dict(prior)
                out["recorded_at"] = str(existing["recorded_at"])
                out["idempotent"] = True
                return out

            con.execute(
                """INSERT INTO action_receipts(
                    receipt_id,plan_id,action_id,kind,status,semantic_json,recorded_at
                ) VALUES(?,?,?,?,?,?,?)""",
                (
                    receipt["receipt_id"],
                    receipt["plan_id"],
                    receipt["action_id"],
                    receipt["kind"],
                    receipt["status"],
                    raw,
                    now,
                ),
            )
        out = dict(receipt)
        out["recorded_at"] = now
        out["idempotent"] = False
        return out

    def execute(
        self,
        plan: Mapping[str, Any],
        handlers: Mapping[str, Callable[[Mapping[str, Any]], Any]] | None = None,
    ) -> dict[str, Any]:
        normalized = _validate_plan(plan)
        handler_map = dict(handlers or {})
        receipts: list[dict[str, Any]] = []

        for action in normalized["actions"]:
            plan_id = normalized["plan_id"]
            action_id = action["action_id"]
            existing = self._existing(plan_id, action_id)
            if existing is not None:
                row = self._decode(existing)
                row["idempotent"] = True
                receipts.append(row)
                continue

            kind = action["kind"]
            if kind not in SAFE_INTERNAL_ACTION_KINDS:
                receipt = _receipt_semantic(
                    plan_id,
                    action,
                    _external_status(kind),
                    detail=(
                        "Action requires evidence, review, hypothesis construction, "
                        "architecture mutation, protected authority, or independent qualification."
                    ),
                )
                receipts.append(self._persist(receipt))
                continue

            handler = handler_map.get(kind)
            if not callable(handler):
                receipt = _receipt_semantic(
                    plan_id,
                    action,
                    "BLOCKED_INTERNAL_HANDLER",
                    detail=f"No approved internal handler is installed for {kind}.",
                )
                receipts.append(self._persist(receipt))
                continue

            # All three whitelisted operations are expected to be idempotent at
            # their domain boundary. The executor never calls evidence-producing
            # or qualification-producing functions.
            result = handler(action)
            digest, keys = _validate_handler_result(result, kind)
            receipt = _receipt_semantic(
                plan_id,
                action,
                "APPLIED_INTERNAL",
                result_digest=digest,
                result_keys=keys,
                detail="Administrative research-state transition applied.",
            )
            receipts.append(self._persist(receipt))

        applied = sum(1 for x in receipts if x["status"] == "APPLIED_INTERNAL")
        failed = sum(1 for x in receipts if x["status"].startswith("BLOCKED_"))
        external = len(receipts) - applied - failed
        return {
            "schema_version": SCHEMA_VERSION,
            "plan_id": normalized["plan_id"],
            "receipt_count": len(receipts),
            "applied_count": applied,
            "external_count": external,
            "failed_count": failed,
            "receipts": receipts,
            "truth_contract": {
                "safe_internal_action_kinds": sorted(SAFE_INTERNAL_ACTION_KINDS),
                "executor_receipts_are_not_scientific_evidence": True,
                "executor_cannot_emit_evaluator_receipts": True,
                "executor_cannot_emit_qualification_receipts": True,
                "evidence_producing_actions_are_never_auto_applied": True,
                "protected_authority_actions_are_never_auto_applied": True,
            },
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def snapshot(self) -> dict[str, Any]:
        with _LOCK, self._connect() as con:
            rows = con.execute(
                """SELECT * FROM action_receipts
                   ORDER BY recorded_at,receipt_id"""
            ).fetchall()
        receipts = [self._decode(row) for row in rows]
        counts: dict[str, int] = {}
        for row in receipts:
            status = str(row["status"])
            counts[status] = counts.get(status, 0) + 1
        return {
            "schema_version": SCHEMA_VERSION,
            "journal_mode": self.journal_mode,
            "receipt_count": len(receipts),
            "applied_internal_count": counts.get("APPLIED_INTERNAL", 0),
            "awaiting_external_count": sum(
                count for status, count in counts.items()
                if status.startswith("AWAITING_")
            ),
            "blocked_count": sum(
                count for status, count in counts.items()
                if status.startswith("BLOCKED_")
            ),
            "status_counts": dict(sorted(counts.items())),
            "receipts": receipts,
            "truth_contract": {
                "safe_internal_action_kinds": sorted(SAFE_INTERNAL_ACTION_KINDS),
                "executor_receipts_are_not_scientific_evidence": True,
                "executor_cannot_emit_evaluator_receipts": True,
                "executor_cannot_emit_qualification_receipts": True,
                "evidence_producing_actions_are_never_auto_applied": True,
                "protected_authority_actions_are_never_auto_applied": True,
                "receipts_are_append_only": True,
            },
            "execution_authorized": False,
            "production_decision_authorized": False,
        }
