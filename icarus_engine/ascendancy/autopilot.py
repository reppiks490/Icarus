"""Bounded continuous ASCENDANCY research autopilot.

The autopilot repeatedly asks the Evolution Governor for a plan and passes that
plan to the Safe Internal Executor.  It re-plans only after a genuinely new
safe administrative transition.  The moment progress requires scientific
evidence, review, protected holdout authority, architecture mutation work, or
independent qualification, the internal loop stops.

This is autonomous research bookkeeping and scheduling, not autonomous truth
creation and not autonomous trading.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

SCHEMA_VERSION = "icarus-ascendancy-autopilot-v1"
CYCLE_SCHEMA_VERSION = "icarus-ascendancy-autopilot-cycle-v1"
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


def _authority_false(value: Mapping[str, Any], label: str) -> None:
    if value.get("execution_authorized") is not False:
        raise ValueError(f"{label} execution_authorized must be false")
    if value.get("production_decision_authorized") is not False:
        raise ValueError(f"{label} production_decision_authorized must be false")
    if value.get("can_mint_qualification") is True:
        raise ValueError(f"{label} cannot mint qualification")
    if value.get("can_mint_evaluator_receipts") is True:
        raise ValueError(f"{label} cannot mint evaluator receipts")


class GovernorAutopilot:
    """Persisted quiescence-seeking loop over governor planning and safe execution."""

    def __init__(
        self,
        base_dir: str | os.PathLike[str],
        *,
        plan_callback: Callable[[], Mapping[str, Any]],
        execute_callback: Callable[[Mapping[str, Any]], Mapping[str, Any]],
        interval_seconds: int = 300,
        max_internal_iterations: int = 4,
        enabled: bool = True,
    ):
        if isinstance(interval_seconds, bool) or not isinstance(interval_seconds, int):
            raise ValueError("interval_seconds must be an integer")
        if interval_seconds < 1 or interval_seconds > 86_400:
            raise ValueError("interval_seconds must be between 1 and 86400")
        if isinstance(max_internal_iterations, bool) or not isinstance(max_internal_iterations, int):
            raise ValueError("max_internal_iterations must be an integer")
        if max_internal_iterations < 1 or max_internal_iterations > 100:
            raise ValueError("max_internal_iterations must be between 1 and 100")
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be Boolean")
        if not callable(plan_callback) or not callable(execute_callback):
            raise ValueError("autopilot callbacks must be callable")

        self.base_dir = Path(base_dir)
        self.path = self.base_dir / "research" / "ascendancy_autopilot.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.plan_callback = plan_callback
        self.execute_callback = execute_callback
        self.interval_seconds = interval_seconds
        self.max_internal_iterations = max_internal_iterations
        self.enabled = enabled
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._cycle_lock = threading.Lock()
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
                CREATE TABLE IF NOT EXISTS cycles (
                    cycle_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    stop_reason TEXT NOT NULL,
                    iteration_count INTEGER NOT NULL,
                    new_internal_transition_count INTEGER NOT NULL,
                    awaiting_external_count INTEGER NOT NULL,
                    blocked_count INTEGER NOT NULL,
                    semantic_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_asc_autopilot_recorded
                    ON cycles(recorded_at, cycle_id);
                CREATE TABLE IF NOT EXISTS latest_observation (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    cycle_id TEXT NOT NULL,
                    observed_at TEXT NOT NULL
                );
                """
            )

    def _persist(self, semantic: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        raw = _canonical(semantic, "autopilot cycle")
        now = _utc_now()
        cycle_id = str(semantic["cycle_id"])
        with _LOCK, self._connect() as con:
            existing = con.execute(
                "SELECT semantic_json,recorded_at FROM cycles WHERE cycle_id=?",
                (cycle_id,),
            ).fetchone()
            if existing is not None:
                if str(existing["semantic_json"]) != raw:
                    raise RuntimeError("autopilot cycle identity integrity failure")
            else:
                con.execute(
                    """INSERT INTO cycles(
                        cycle_id,status,stop_reason,iteration_count,
                        new_internal_transition_count,awaiting_external_count,
                        blocked_count,semantic_json,recorded_at
                    ) VALUES(?,?,?,?,?,?,?,?,?)""",
                    (
                        cycle_id,
                        semantic["status"],
                        semantic["stop_reason"],
                        semantic["iteration_count"],
                        semantic["new_internal_transition_count"],
                        semantic["awaiting_external_count"],
                        semantic["blocked_count"],
                        raw,
                        now,
                    ),
                )
            # Current state follows the latest observation, while immutable
            # cycle receipts retain their original timestamps and progress.
            con.execute(
                """INSERT INTO latest_observation VALUES(1,?,?)
                   ON CONFLICT(singleton) DO UPDATE SET
                       cycle_id=excluded.cycle_id, observed_at=excluded.observed_at""",
                (cycle_id, now),
            )
        out = dict(semantic)
        out["recorded_at"] = str(existing["recorded_at"]) if existing else now
        return out, existing is not None

    def run_cycle(self) -> dict[str, Any]:
        with self._cycle_lock:
            steps: list[dict[str, Any]] = []
            new_transitions = 0
            awaiting_external = 0
            blocked = 0
            status = "GREEN"
            stop_reason = "AWAITING_EXTERNAL_OR_QUIESCENT"
            last_error: str | None = None

            try:
                for iteration in range(1, self.max_internal_iterations + 1):
                    planned = self.plan_callback()
                    if not isinstance(planned, Mapping):
                        raise ValueError("autopilot plan callback must return an object")
                    _authority_false(planned, "autopilot plan callback")
                    plan = planned.get("plan")
                    if not isinstance(plan, Mapping):
                        raise ValueError("autopilot plan callback must return a plan object")
                    _authority_false(plan, "autopilot governor plan")
                    plan_id = str(plan.get("plan_id") or "").strip()
                    if not plan_id:
                        raise ValueError("autopilot governor plan_id is required")

                    executed = self.execute_callback(plan)
                    if not isinstance(executed, Mapping):
                        raise ValueError("autopilot execute callback must return an object")
                    _authority_false(executed, "autopilot safe executor")
                    if str(executed.get("plan_id") or "") != plan_id:
                        raise ValueError("autopilot executor plan_id mismatch")

                    newly = int(executed.get("newly_applied_count") or 0)
                    external = int(executed.get("external_count") or 0)
                    failed = int(executed.get("failed_count") or 0)
                    if min(newly, external, failed) < 0:
                        raise ValueError("autopilot executor counts must be nonnegative")

                    steps.append({
                        "iteration": iteration,
                        "plan_id": plan_id,
                        "action_count": int(plan.get("action_count") or 0),
                        "newly_applied_count": newly,
                        "awaiting_external_count": external,
                        "blocked_count": failed,
                    })
                    new_transitions += newly
                    awaiting_external += external
                    blocked += failed

                    if failed > 0:
                        status = "DEGRADED"
                        stop_reason = "BLOCKED_INTERNAL"
                        break
                    if newly == 0:
                        stop_reason = "AWAITING_EXTERNAL_OR_QUIESCENT"
                        break
                else:
                    status = "DEGRADED"
                    stop_reason = "INTERNAL_ITERATION_LIMIT"
            except Exception as ex:
                status = "DEGRADED"
                stop_reason = "ERROR"
                last_error = f"{type(ex).__name__}: {ex}"[:2000]

            semantic: dict[str, Any] = {
                "schema_version": CYCLE_SCHEMA_VERSION,
                "status": status,
                "stop_reason": stop_reason,
                "iteration_count": len(steps),
                "new_internal_transition_count": new_transitions,
                "awaiting_external_count": awaiting_external,
                "blocked_count": blocked,
                "last_error": last_error,
                "steps": steps,
                "truth_contract": {
                    "autopilot_only_executes_safe_internal_actions": True,
                    "external_evidence_stops_internal_progression": True,
                    "protected_holdout_authority_remains_external": True,
                    "qualification_authority_remains_external": True,
                    "autopilot_cannot_fabricate_evaluator_receipts": True,
                    "autopilot_cannot_trade": True,
                },
                "execution_authorized": False,
                "production_decision_authorized": False,
            }
            semantic["cycle_id"] = _hash(semantic)
            out, idempotent = self._persist(semantic)
            out["idempotent"] = idempotent
            return out

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_cycle()
            except Exception:
                # run_cycle itself records ordinary failures. This guard is only
                # for an unexpected persistence/runtime failure; the worker must
                # remain fail-closed rather than die into an unknown state.
                pass
            self._stop.wait(self.interval_seconds)

    def start(self) -> None:
        if not self.enabled:
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="icarus-ascendancy-autopilot",
            daemon=True,
        )
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if (
            self._thread
            and self._thread.is_alive()
            and self._thread is not threading.current_thread()
        ):
            self._thread.join(timeout=2.0)

    def status(self) -> dict[str, Any]:
        with _LOCK, self._connect() as con:
            rows = con.execute(
                """SELECT semantic_json,recorded_at
                   FROM cycles ORDER BY recorded_at,cycle_id"""
            ).fetchall()
            observation = con.execute(
                "SELECT cycle_id,observed_at FROM latest_observation WHERE singleton=1"
            ).fetchone()

        cycles: list[dict[str, Any]] = []
        for row in rows:
            try:
                item = json.loads(row["semantic_json"])
            except (TypeError, json.JSONDecodeError) as ex:
                raise RuntimeError("autopilot cycle storage corruption") from ex
            if not isinstance(item, dict):
                raise RuntimeError("autopilot cycle storage corruption")
            item["recorded_at"] = str(row["recorded_at"])
            cycles.append(item)
        latest = cycles[-1] if cycles else None
        if observation is not None:
            latest = next((row for row in cycles
                           if row.get("cycle_id") == observation["cycle_id"]), None)
            if latest is None:
                raise RuntimeError("autopilot observation storage corruption")

        return {
            "schema_version": SCHEMA_VERSION,
            "enabled": self.enabled,
            "worker_running": bool(self._thread and self._thread.is_alive()),
            "interval_seconds": self.interval_seconds,
            "max_internal_iterations": self.max_internal_iterations,
            "journal_mode": self.journal_mode,
            "cycle_count": len(cycles),
            "latest_cycle_id": latest.get("cycle_id") if latest else None,
            "latest_cycle": latest,
            "latest_observed_at": str(observation["observed_at"]) if observation else None,
            "status": latest.get("status") if latest else "NOT_RUN",
            "stop_reason": latest.get("stop_reason") if latest else None,
            "last_error": latest.get("last_error") if latest else None,
            "truth_contract": {
                "autopilot_only_executes_safe_internal_actions": True,
                "external_evidence_stops_internal_progression": True,
                "protected_holdout_authority_remains_external": True,
                "qualification_authority_remains_external": True,
                "autopilot_cannot_fabricate_evaluator_receipts": True,
                "autopilot_cannot_trade": True,
                "cycles_are_append_only": True,
                "same_quiescent_cycle_is_idempotent": True,
            },
            "execution_authorized": False,
            "production_decision_authorized": False,
        }
