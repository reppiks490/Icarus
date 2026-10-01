"""Low-overhead measured latency telemetry for ICARUS hot/near paths.

Targets are budgets, never assumed achievements. Measurements use
perf_counter_ns() so wall-clock adjustments cannot corrupt elapsed time.
No training, strategy mutation, production authority, or broker authority lives here.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Deque, Iterator, Mapping

DEFAULT_STAGE_BUDGET_MS: dict[str, float] = {
    "feed_to_normalized": 5.0,
    "feature_update": 5.0,
    "regime_lookup": 3.0,
    "candidate_lookup": 3.0,
    "brain_arbitration": 5.0,
    "risk_abstention": 4.0,
    "shadow_decision_total": 25.0,
}

_MAX_STAGE_LEN = 80


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def _stage(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("stage is required")
    out = value.strip().lower()
    if len(out) > _MAX_STAGE_LEN:
        raise ValueError(f"stage exceeds {_MAX_STAGE_LEN} characters")
    return out


def _percentile(sorted_values: list[float], q: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = (len(sorted_values) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_values[lo]
    w = pos - lo
    return sorted_values[lo] * (1.0 - w) + sorted_values[hi] * w


@dataclass(frozen=True)
class LatencySample:
    stage: str
    elapsed_ms: float
    budget_ms: float | None
    budget_met: bool | None
    monotonic_ns: int


class LatencyTelemetry:
    """Bounded in-memory latency sampler with truthful percentile snapshots.

    The collector is intentionally separate from training. It can be called from
    the hot path, but its own work is bounded: append to a fixed-size deque under
    one lock and defer percentile sorting to snapshot time.
    """

    def __init__(
        self,
        *,
        budgets_ms: Mapping[str, float] | None = None,
        max_samples_per_stage: int = 4096,
    ) -> None:
        if isinstance(max_samples_per_stage, bool) or not isinstance(max_samples_per_stage, int):
            raise ValueError("max_samples_per_stage must be an integer")
        if not 32 <= max_samples_per_stage <= 1_000_000:
            raise ValueError("max_samples_per_stage must be between 32 and 1000000")
        raw = dict(DEFAULT_STAGE_BUDGET_MS)
        if budgets_ms:
            for key, value in budgets_ms.items():
                raw[_stage(key)] = _finite(value, f"budget[{key}]")
        for key, value in raw.items():
            if value <= 0:
                raise ValueError(f"budget[{key}] must be > 0")
        self._budgets = raw
        self._max = max_samples_per_stage
        self._samples: dict[str, Deque[LatencySample]] = {}
        self._totals: dict[str, int] = {}
        self._violations: dict[str, int] = {}
        self._lock = threading.Lock()

    def budget_ms(self, stage: str) -> float | None:
        return self._budgets.get(_stage(stage))

    def observe_ms(self, stage: str, elapsed_ms: float) -> LatencySample:
        name = _stage(stage)
        elapsed = _finite(elapsed_ms, "elapsed_ms")
        if elapsed < 0:
            raise ValueError("elapsed_ms cannot be negative")
        budget = self._budgets.get(name)
        met = None if budget is None else elapsed <= budget
        sample = LatencySample(
            stage=name,
            elapsed_ms=elapsed,
            budget_ms=budget,
            budget_met=met,
            monotonic_ns=time.perf_counter_ns(),
        )
        with self._lock:
            ring = self._samples.get(name)
            if ring is None:
                ring = deque(maxlen=self._max)
                self._samples[name] = ring
            ring.append(sample)
            self._totals[name] = self._totals.get(name, 0) + 1
            if met is False:
                self._violations[name] = self._violations.get(name, 0) + 1
        return sample

    def observe_ns(self, stage: str, elapsed_ns: int) -> LatencySample:
        if isinstance(elapsed_ns, bool) or not isinstance(elapsed_ns, int):
            raise ValueError("elapsed_ns must be an integer")
        if elapsed_ns < 0:
            raise ValueError("elapsed_ns cannot be negative")
        return self.observe_ms(stage, elapsed_ns / 1_000_000.0)

    @contextmanager
    def measure(self, stage: str) -> Iterator[None]:
        name = _stage(stage)
        start = time.perf_counter_ns()
        try:
            yield
        finally:
            self.observe_ns(name, time.perf_counter_ns() - start)

    def _stage_snapshot(self, stage: str, rows: list[LatencySample], total: int, violations: int) -> dict[str, Any]:
        values = sorted(x.elapsed_ms for x in rows)
        budget = self._budgets.get(stage)
        measured = len(values)
        violation_rate = (violations / total) if total else None
        return {
            "stage": stage,
            "budget_ms": budget,
            "retained_samples": measured,
            "total_samples": total,
            "dropped_from_ring": max(0, total - measured),
            "p50_ms": _percentile(values, 0.50),
            "p95_ms": _percentile(values, 0.95),
            "p99_ms": _percentile(values, 0.99),
            "min_ms": values[0] if values else None,
            "max_ms": values[-1] if values else None,
            "mean_ms": (sum(values) / measured) if measured else None,
            "budget_violations": violations,
            "budget_violation_rate": violation_rate,
            "budget_status": (
                "UNMEASURED" if not values else
                "NO_BUDGET" if budget is None else
                "PASS_P99" if (_percentile(values, 0.99) or 0.0) <= budget else
                "FAIL_P99"
            ),
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            stage_names = sorted(set(self._budgets) | set(self._samples))
            copies = {
                stage: list(self._samples.get(stage, ()))
                for stage in stage_names
            }
            totals = {stage: self._totals.get(stage, 0) for stage in stage_names}
            violations = {stage: self._violations.get(stage, 0) for stage in stage_names}

        stages = [
            self._stage_snapshot(stage, copies[stage], totals[stage], violations[stage])
            for stage in stage_names
        ]
        hot = next((x for x in stages if x["stage"] == "shadow_decision_total"), None)
        return {
            "schema_version": "icarus-latency-telemetry-v1",
            "clock": "time.perf_counter_ns",
            "measurement_type": "LOCAL_PROCESSING_ELAPSED_TIME",
            "targets_are_measured_not_assumed": True,
            "hot_path": hot,
            "stages": stages,
            "execution_authorized": False,
            "production_decision_authorized": False,
            "training_allowed_on_hot_path": False,
        }

    def persist_snapshot(self, base_dir: str | os.PathLike[str]) -> Path:
        """Atomically persist a telemetry snapshot outside the measured section."""
        root = Path(base_dir) / "audit"
        root.mkdir(parents=True, exist_ok=True)
        path = root / "latency_telemetry.json"
        raw = json.dumps(self.snapshot(), sort_keys=True, indent=2, allow_nan=False) + "\n"
        with NamedTemporaryFile("w", encoding="utf-8", dir=root, prefix=".latency-", delete=False) as fh:
            tmp = Path(fh.name)
            fh.write(raw)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        return path
