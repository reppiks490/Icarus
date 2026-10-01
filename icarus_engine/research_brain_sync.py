"""Promote durable local research outcomes into Adaptive Brain evidence.

This bridge does not train, approve, or activate a strategy. It watches completed
bounded-research study artifacts and records either:
- a partially validated Brain candidate with only gates the local workflow truly
  proves; or
- a durable negative/degraded learning event.

Unknown source revision, missing evidence, or unproven validation gates fail closed.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping

from .brain import REQUIRED_CANDIDATE_GATES, record_brain_event

_TERMINAL = {"complete", "no_candidate", "cancelled", "time_limit", "error", "interrupted"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _hex(value: Any, size: int) -> bool:
    return isinstance(value, str) and len(value) == size and all(c in "0123456789abcdef" for c in value.lower())


def _state_path(base_dir: str | os.PathLike[str]) -> Path:
    return Path(base_dir) / "audit" / "brain_research_sync.json"


def _default_state(interval_seconds: int) -> dict[str, Any]:
    return {
        "schema_version": "icarus-brain-research-sync-v1",
        "enabled": True,
        "interval_seconds": interval_seconds,
        "status": "not_started",
        "last_attempt_at": None,
        "last_success_at": None,
        "last_error": None,
        "studies_seen": 0,
        "candidates_recorded": 0,
        "negative_results_recorded": 0,
        "blocked_revision_count": 0,
        "processed": {},
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def _read_state(base_dir: str | os.PathLike[str], interval_seconds: int) -> dict[str, Any]:
    path = _state_path(base_dir)
    state = _default_state(interval_seconds)
    if not path.is_file():
        return state
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state["status"] = "degraded"
        state["last_error"] = "local research-sync state is unreadable; study events will replay idempotently"
        return state
    if not isinstance(raw, dict) or raw.get("execution_authorized") is not False:
        state["status"] = "degraded"
        state["last_error"] = "local research-sync state failed authority validation"
        return state
    state.update(raw)
    state["interval_seconds"] = interval_seconds
    state["execution_authorized"] = False
    state["production_decision_authorized"] = False
    return state


def _write_state(base_dir: str | os.PathLike[str], state: Mapping[str, Any]) -> None:
    path = _state_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(state)
    payload["execution_authorized"] = False
    payload["production_decision_authorized"] = False
    raw = json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n"
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=".brain-research-", delete=False) as fh:
        tmp = Path(fh.name)
        fh.write(raw)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _job_digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _number(value: Any) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return value


def _study_evidence(job: Mapping[str, Any], result: Mapping[str, Any] | None = None) -> list[str]:
    result = result if isinstance(result, Mapping) else {}
    out = [
        f"study_id:{job.get('id', '')}",
        f"asset:{job.get('asset', '')}",
        f"dataset_sha256:{job.get('dataset_hash', '')}",
        f"baseline_sha256:{job.get('baseline_hash', '')}",
        f"study_sha256:{result.get('study_hash', '')}",
        f"status:{job.get('status', '')}",
    ]
    selection = result.get("selection")
    if isinstance(selection, Mapping) and selection.get("selection_sha256"):
        out.append(f"selection_sha256:{selection.get('selection_sha256')}")
    holdout = result.get("holdout_evidence")
    if isinstance(holdout, Mapping) and holdout.get("result_sha256"):
        out.append(f"holdout_result_sha256:{holdout.get('result_sha256')}")
    stress = result.get("stress")
    if isinstance(stress, Mapping):
        stress_holdout = stress.get("holdout_evidence")
        if isinstance(stress_holdout, Mapping) and stress_holdout.get("result_sha256"):
            out.append(f"stress_holdout_result_sha256:{stress_holdout.get('result_sha256')}")
    return [str(x)[:700] for x in out if x and not x.endswith(":")][:32]


def _provenance_ok(job: Mapping[str, Any], result: Mapping[str, Any]) -> bool:
    if not all(_hex(job.get(key), 64) for key in ("dataset_hash", "baseline_hash")):
        return False
    if not _hex(result.get("study_hash"), 64):
        return False
    if result.get("manifest", {}).get("dataset_hash") != job.get("dataset_hash"):
        return False
    if result.get("manifest", {}).get("baseline_hash") != job.get("baseline_hash"):
        return False
    return True


def _has_replay_evidence(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    return all(_hex(value.get(key), 64) for key in ("result_sha256", "source_config_sha256", "subbars_sha256", "deep_sha256"))


def _oos_ok(result: Mapping[str, Any]) -> bool:
    selected = result.get("selected")
    if not isinstance(selected, Mapping) or not selected:
        return False
    trial = next((x for x in result.get("trials", []) if isinstance(x, Mapping) and x.get("inputs") == selected), None)
    if not isinstance(trial, Mapping):
        return False
    evidence = trial.get("result_evidence")
    if not isinstance(evidence, Mapping):
        return False
    return _has_replay_evidence(evidence.get("train")) and _has_replay_evidence(evidence.get("validation"))


def _holdout_ok(result: Mapping[str, Any]) -> bool:
    comparison = result.get("holdout_comparison")
    return (
        result.get("holdout_consumed") is True
        and isinstance(comparison, Mapping)
        and comparison.get("passed") is True
        and _has_replay_evidence(result.get("holdout_evidence"))
    )


def _stress_cost_ok(result: Mapping[str, Any]) -> bool:
    stress = result.get("stress")
    return (
        isinstance(stress, Mapping)
        and stress.get("status") == "enabled"
        and isinstance(stress.get("holdout_comparison"), Mapping)
        and stress["holdout_comparison"].get("passed") is True
        and _has_replay_evidence(stress.get("holdout_evidence"))
    )


def _metrics(result: Mapping[str, Any]) -> dict[str, Any]:
    holdout = result.get("holdout") if isinstance(result.get("holdout"), Mapping) else {}
    stress = result.get("stress") if isinstance(result.get("stress"), Mapping) else {}
    stress_holdout = stress.get("holdout") if isinstance(stress.get("holdout"), Mapping) else {}
    return {
        "search_trials": len(result.get("trials", [])) if isinstance(result.get("trials"), list) else None,
        "total_combinations": result.get("total_combinations") if type(result.get("total_combinations")) is int else None,
        "holdout_entries": holdout.get("entries") if type(holdout.get("entries")) is int else None,
        "holdout_win_rate": _number(holdout.get("win_rate")),
        "holdout_net_after_costs": _number(holdout.get("net_after_costs")),
        "holdout_expectancy_after_costs": _number(holdout.get("expectancy_after_costs")),
        "holdout_max_drawdown_pct": _number(holdout.get("max_drawdown_pct")),
        "stress_holdout_net_after_costs": _number(stress_holdout.get("net_after_costs")),
        "stress_holdout_expectancy_after_costs": _number(stress_holdout.get("expectancy_after_costs")),
        "stress_holdout_max_drawdown_pct": _number(stress_holdout.get("max_drawdown_pct")),
    }


def _validation(result: Mapping[str, Any]) -> dict[str, bool | None]:
    # The local research workflow proves provenance, disjoint OOS evaluation,
    # one protected holdout, and cost/slippage stress. It does NOT independently
    # prove feature causality, latency realism, multiple-testing correction,
    # ablation, calibration, OOD/drift robustness, deterministic rerun equality,
    # or independent verification. Those remain explicitly unresolved.
    out: dict[str, bool | None] = {gate: None for gate in REQUIRED_CANDIDATE_GATES}
    out["provenance"] = _provenance_ok_placeholder = True  # overwritten by caller
    out["oos"] = _oos_ok(result)
    out["protected_holdout"] = _holdout_ok(result)
    # Cost and slippage are stressed, but the combined gate includes latency.
    out["costs_slippage_latency"] = None if _stress_cost_ok(result) else False
    return out


def _candidate_event(job: Mapping[str, Any], result: Mapping[str, Any], stage: str) -> dict[str, Any] | None:
    repo = job.get("source_repo")
    commit = job.get("source_commit")
    revision_eligible = job.get("source_revision_eligible") is True
    if not revision_eligible or not isinstance(repo, str) or "/" not in repo or not _hex(commit, 40):
        return None

    validation = _validation(result)
    validation["provenance"] = _provenance_ok(job, result)
    candidate_id = f"{job.get('asset', 'UNKNOWN')}:{result.get('study_hash', job.get('id', 'unknown'))}"
    qualified = result.get("research_qualified") is True
    summary = (
        "Local bounded research candidate passed its preregistered train/validation/holdout and stress workflow; "
        "unproven causal, multiple-testing, latency, ablation, calibration, OOD, deterministic-rerun and independent-review gates remain closed."
        if qualified
        else "Local research selected a candidate but final qualification failed; rejection is retained as learning evidence."
    )
    details = {
        "study_id": job.get("id"),
        "selected_inputs": result.get("selected"),
        "qualification_reasons": result.get("qualification_reasons", []),
        "research_qualified": qualified,
        "source_revision_status": job.get("source_revision_status"),
        "accuracy_guaranteed": result.get("accuracy_guaranteed"),
        "execution_authorized": False,
    }
    return {
        "kind": "candidate",
        "subject": candidate_id,
        "summary": summary,
        "status": "verified" if qualified else "rejected",
        "candidate_id": candidate_id,
        "stage": stage,
        "regimes": ["UNCLASSIFIED"],
        "metrics": _metrics(result),
        "validation": validation,
        "source_repo": repo,
        "source_commit": commit,
        "evidence": _study_evidence(job, result),
        "details": details,
    }


class BrainResearchSync:
    """Continuously retain local research candidates and negative results."""

    def __init__(self, base_dir: str | os.PathLike[str], *, interval_seconds: int = 30):
        self.base_dir = Path(base_dir)
        self.interval_seconds = max(10, min(3600, int(interval_seconds)))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def status(self) -> dict[str, Any]:
        state = _read_state(self.base_dir, self.interval_seconds)
        state.pop("processed", None)
        return state

    def _learning_event(self, job: Mapping[str, Any], result: Mapping[str, Any] | None, summary: str, status: str) -> None:
        record_brain_event(
            self.base_dir,
            {
                "kind": "learning",
                "subject": f"research:{job.get('id', 'unknown')}",
                "summary": summary,
                "status": status,
                "evidence": _study_evidence(job, result),
                "details": {
                    "asset": job.get("asset"),
                    "study_id": job.get("id"),
                    "job_status": job.get("status"),
                    "error": job.get("error"),
                    "source_repo": job.get("source_repo"),
                    "source_commit": job.get("source_commit"),
                    "source_revision_status": job.get("source_revision_status"),
                    "qualification_reasons": (result or {}).get("qualification_reasons", []) if isinstance(result, Mapping) else [],
                },
            },
        )

    def _process(self, job: Mapping[str, Any], state: dict[str, Any]) -> None:
        status = str(job.get("status") or "")
        result = job.get("result") if isinstance(job.get("result"), Mapping) else None

        if status == "complete" and result is not None and result.get("selected"):
            stage = "validated" if result.get("research_qualified") is True else "rejected"
            event = _candidate_event(job, result, stage)
            if event is None:
                state["blocked_revision_count"] = int(state.get("blocked_revision_count", 0)) + 1
                self._learning_event(
                    job,
                    result,
                    "Research outcome was not admitted as a Brain candidate because an exact clean source revision was not captured at study start.",
                    "blocked",
                )
                return
            record_brain_event(self.base_dir, event)
            state["candidates_recorded"] = int(state.get("candidates_recorded", 0)) + 1
            return

        if status == "no_candidate":
            self._learning_event(
                job,
                result,
                "No candidate survived the bounded train/validation/stress search. The negative result is retained to prevent repeated rediscovery.",
                "rejected",
            )
            state["negative_results_recorded"] = int(state.get("negative_results_recorded", 0)) + 1
            return

        if status in {"cancelled", "time_limit", "error", "interrupted"}:
            self._learning_event(
                job,
                result,
                f"Research study ended as {status}; incomplete evidence is retained but cannot become a candidate.",
                "degraded",
            )
            state["negative_results_recorded"] = int(state.get("negative_results_recorded", 0)) + 1

    def sync_once(self) -> dict[str, Any]:
        with self._lock:
            state = _read_state(self.base_dir, self.interval_seconds)
            state["last_attempt_at"] = _utc_now()
            errors: list[str] = []
            processed = dict(state.get("processed") or {})
            studies = self.base_dir / "research" / "studies"
            paths = sorted(studies.glob("*.json")) if studies.is_dir() else []
            state["studies_seen"] = len(paths)

            for path in paths[-5000:]:
                try:
                    raw = path.read_bytes()
                    digest = _job_digest(raw)
                    if processed.get(path.name) == digest:
                        continue
                    job = json.loads(raw)
                    if not isinstance(job, Mapping):
                        raise ValueError("study artifact is not an object")
                    if str(job.get("status") or "") not in _TERMINAL:
                        continue
                    self._process(job, state)
                    processed[path.name] = digest
                except Exception as ex:
                    errors.append(f"{path.name}: {type(ex).__name__}: {ex}")

            if len(processed) > 5000:
                keep = {path.name for path in paths[-5000:]}
                processed = {k: v for k, v in processed.items() if k in keep}
            state["processed"] = processed
            state["last_success_at"] = _utc_now()
            state["last_error"] = " | ".join(errors[-10:])[:3000] if errors else None
            state["status"] = "degraded" if errors else "green"
            _write_state(self.base_dir, state)
            return self.status()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.sync_once()
            except Exception:
                pass
            self._stop.wait(self.interval_seconds)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="icarus-adaptive-brain-research-sync", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=2.0)
