"""Bounded native CONTRACT_VALIDATION service backed by the existing evaluator."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from ..process_launch import background_kwargs
from .contract_worker import implementation_hash
from .evaluator import EvaluatorCascade

_LOCK = threading.RLock()
_STAGE = "CONTRACT_VALIDATION"


def _json(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(raw.encode()) > 262144:
        raise ValueError("native validation document exceeds bound")
    return raw


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _artifact_hash(report: str, receipt: str) -> str:
    return hashlib.sha256(_json({"report": report, "receipt": receipt}).encode()).hexdigest()


class NativeContractValidator:
    def __init__(self, base_dir, *, evaluator: EvaluatorCascade, checkout_root=None,
                 max_candidates=4, worker_timeout=2.0, interval_seconds=300, enabled=True):
        if isinstance(max_candidates, bool) or not isinstance(max_candidates, int) or not 1 <= max_candidates <= 16:
            raise ValueError("max_candidates must be between 1 and 16")
        if isinstance(worker_timeout, bool) or not isinstance(worker_timeout, (int, float)) or not math.isfinite(worker_timeout) or not 0 < worker_timeout <= 5:
            raise ValueError("worker_timeout must be between zero and five seconds")
        if isinstance(interval_seconds, bool) or not isinstance(interval_seconds, int) or not 1 <= interval_seconds <= 86400:
            raise ValueError("interval_seconds must be between 1 and 86400")
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be Boolean")
        self.base_dir = Path(base_dir)
        if evaluator.base_dir.resolve() != self.base_dir.resolve():
            raise ValueError("native validator and evaluator must share a base directory")
        self.evaluator = evaluator
        self.package_root = Path(__file__).resolve().parents[2]
        self.checkout_root = Path(checkout_root or self.package_root).resolve()
        self.max_candidates, self.worker_timeout = max_candidates, float(worker_timeout)
        self.interval_seconds, self.enabled = interval_seconds, enabled
        self.path = self.base_dir / "research" / "ascendancy_native_validation.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._stop = threading.Event()
        self._thread = None
        self.last_error = None
        self._cursor = ""
        with self._connect() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS runs(
                run_id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL,
                state TEXT NOT NULL, report_json TEXT, receipt_json TEXT,
                error TEXT, created_at TEXT NOT NULL, artifact_sha256 TEXT)""")
            if "artifact_sha256" not in {row[1] for row in con.execute("PRAGMA table_info(runs)")}:
                con.execute("ALTER TABLE runs ADD COLUMN artifact_sha256 TEXT")
            con.execute("CREATE INDEX IF NOT EXISTS idx_native_runs_recovery ON runs(state,created_at,run_id)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_native_runs_candidate ON runs(candidate_id,state)")

    def _connect(self):
        con = sqlite3.connect(str(self.path), timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def _source_check(self, candidate, deadline):
        def git(*args):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return ""
            try:
                result = subprocess.run(["git", "-C", str(self.checkout_root), *args],
                    capture_output=True, text=True, timeout=remaining, **background_kwargs())
                return result.stdout.strip() if result.returncode == 0 else ""
            except (OSError, subprocess.TimeoutExpired):
                return ""
        remote = git("remote", "get-url", "origin")
        match = re.fullmatch(r"(?:https://github\.com/|git@github\.com:)([^/]+/[^/]+?)(?:\.git)?", remote)
        return {
            "local_remote_matches_declared_repo": bool(match and match[1] == candidate["source_repo"]),
            "source_revision_present_locally": git("rev-parse", "--verify", candidate["source_commit"] + "^{commit}") == candidate["source_commit"],
        }

    def _claim(self, run_id, candidate_id):
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            if con.execute("SELECT 1 FROM runs WHERE run_id=?", (run_id,)).fetchone():
                return False
            if con.execute("SELECT 1 FROM runs WHERE candidate_id=? AND state IN ('RUNNING','PENDING','BLOCKED')", (candidate_id,)).fetchone():
                return False
            con.execute("INSERT INTO runs(run_id,candidate_id,state,created_at) VALUES(?,?,'RUNNING',?)",
                        (run_id, candidate_id, _now()))
        return True

    def _submit(self, run_id, raw):
        with self._connect() as con:
            row = con.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if (row is None or raw != row["receipt_json"] or not row["report_json"]
            or _artifact_hash(row["report_json"], raw) != row["artifact_sha256"]):
            raise RuntimeError("native validation artifact integrity failure")
        try:
            result = self.evaluator.record(json.loads(raw))
        except ValueError as ex:
            with self._connect() as con:
                con.execute("UPDATE runs SET state='BLOCKED',error=? WHERE run_id=?", (str(ex), run_id))
            return False
        with self._connect() as con:
            con.execute("UPDATE runs SET state='SUBMITTED',error=NULL WHERE run_id=?", (run_id,))
        return not result["idempotent"]

    def _execute(self, candidate, run_id, source, code_hash, started, deadline):
        payload = {"candidate": candidate, "run_id": run_id,
                   "source_check": source, "implementation_sha256": code_hash}
        env = dict(os.environ)
        env["PYTHONPATH"] = str(self.package_root) + os.pathsep + env.get("PYTHONPATH", "")
        try:
            result = subprocess.run([sys.executable, "-m", "icarus_engine.ascendancy.contract_worker"],
                input=_json(payload), capture_output=True, text=True, env=env,
                cwd=str(self.package_root), timeout=max(.001, deadline-time.monotonic()),
                **background_kwargs())
            if result.returncode or len(result.stdout.encode()) > 65536:
                raise ValueError("native worker did not return a bounded successful report")
            report = json.loads(result.stdout)
            if (not isinstance(report, dict) or report.get("run_id") != run_id or report.get("candidate_id") != candidate["candidate_id"]
                or report.get("evaluation_contract_hash") != candidate["evaluation_contract"]["contract_hash"]
                or report.get("stage") != _STAGE or report.get("outcome") not in {"PASS", "FAIL", "INCONCLUSIVE"}
                or report.get("execution_authorized") is not False or report.get("production_decision_authorized") is not False):
                raise ValueError("native worker report identity mismatch")
        except (OSError, ValueError, TypeError, subprocess.TimeoutExpired) as ex:
            report = {"run_id": run_id, "candidate_id": candidate["candidate_id"],
                      "stage": _STAGE, "outcome": "INCONCLUSIVE",
                      "metrics": {"worker_error": type(ex).__name__, "scientific_performance_evaluated": False},
                      "execution_authorized": False, "production_decision_authorized": False}
        usage = {"evaluations": 1, "wall_seconds": max(0.0, time.monotonic()-started), "cost_units": 0.0}
        report["resource_usage"] = usage
        report["implementation_sha256"] = code_hash
        receipt = {"candidate_id": candidate["candidate_id"],
                   "evaluation_contract_hash": candidate["evaluation_contract"]["contract_hash"],
                   "source_repo": candidate["source_repo"], "source_commit": candidate["source_commit"],
                   "stage": _STAGE, "outcome": report["outcome"], "metrics": report["metrics"],
                   "evidence": ["native-contract-run:"+run_id, "worker-code-sha256:"+code_hash],
                   "resource_usage": usage, "observed_at": _now(),
                   "execution_authorized": False, "production_decision_authorized": False}
        # Commit the exact retryable receipt before touching the separate ledger.
        report_raw, receipt_raw = _json(report), _json(receipt)
        with self._connect() as con:
            con.execute("UPDATE runs SET state='PENDING',report_json=?,receipt_json=?,artifact_sha256=? WHERE run_id=?",
                        (report_raw, receipt_raw, _artifact_hash(report_raw, receipt_raw), run_id))
        return self._submit(run_id, receipt_raw)

    def run_once(self):
        submitted = attempted = checked = 0
        with _LOCK:
            with self._connect() as con:
                # BLOCKED receipts require review. Repeatedly retrying them
                # would monopolize the bounded recovery window indefinitely.
                pending = con.execute("SELECT run_id,receipt_json FROM runs WHERE state='PENDING' ORDER BY created_at,run_id LIMIT ?", (self.max_candidates,)).fetchall()
            for row in pending:
                submitted += self._submit(row["run_id"], row["receipt_json"])
            window = self.evaluator.pending_contract_candidates(after_id=self._cursor, limit=self.max_candidates)
            if window:
                self._cursor = window[-1]["candidate_id"]
            for state in window:
                if self._stop.is_set():
                    break
                checked += 1
                remaining = state["resource_remaining"]
                if remaining["evaluations"] < 1 or remaining["wall_seconds"] <= 0:
                    continue
                candidate = self.evaluator.candidate_definition(state["candidate_id"])
                started = time.monotonic()
                deadline = started + min(self.worker_timeout, remaining["wall_seconds"])
                source = self._source_check(candidate, deadline)
                code_hash = implementation_hash()
                run_id = hashlib.sha256(_json({"candidate_id": candidate["candidate_id"],
                    "stage": _STAGE, "implementation_sha256": code_hash, "source_check": source}).encode()).hexdigest()
                if not self._claim(run_id, candidate["candidate_id"]):
                    continue
                attempted += 1
                submitted += self._execute(candidate, run_id, source, code_hash, started, deadline)
        return {"submitted_count": submitted, "attempted_count": attempted, "checked_count": checked,
                "execution_authorized": False, "production_decision_authorized": False}

    def snapshot(self):
        with self._connect() as con:
            rows = con.execute("SELECT * FROM runs ORDER BY created_at,run_id").fetchall()
        runs = []
        for row in rows:
            if row["report_json"] and (not row["receipt_json"] or
                _artifact_hash(row["report_json"], row["receipt_json"]) != row["artifact_sha256"]):
                raise RuntimeError("native validation artifact integrity failure")
            report = json.loads(row["report_json"]) if row["report_json"] else {
                "run_id": row["run_id"], "candidate_id": row["candidate_id"],
                "outcome": None, "execution_authorized": False, "production_decision_authorized": False}
            report.update({"submission_state": row["state"], "error": row["error"], "created_at": row["created_at"]})
            runs.append(report)
        return {"run_count": len(runs), "runs": runs, "enabled": self.enabled,
                "worker_running": bool(self._thread and self._thread.is_alive()), "last_error": self.last_error,
                "execution_authorized": False, "production_decision_authorized": False}

    def start(self):
        if not self.enabled or (self._thread and self._thread.is_alive()):
            return
        self._stop.clear()
        def loop():
            while not self._stop.is_set():
                try:
                    self.run_once()
                    self.last_error = None
                except Exception as ex:
                    self.last_error = type(ex).__name__ + ": " + str(ex)
                self._stop.wait(self.interval_seconds)
        self._thread = threading.Thread(target=loop, name="ascendancy-native-contracts", daemon=True)
        self._thread.start()

    def close(self):
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=self.worker_timeout + 1)
