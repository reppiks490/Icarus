from __future__ import annotations

import json
import time

import pytest

from icarus_engine.latency_telemetry import LatencyTelemetry


def test_latency_snapshot_reports_real_percentiles_and_budget_status():
    tel = LatencyTelemetry(
        budgets_ms={"shadow_decision_total": 25.0, "feature_update": 5.0},
        max_samples_per_stage=64,
    )
    for value in (1.0, 2.0, 3.0, 4.0, 5.0):
        tel.observe_ms("feature_update", value)
    for value in (10.0, 11.0, 12.0, 13.0, 14.0):
        tel.observe_ms("shadow_decision_total", value)

    snap = tel.snapshot()
    by_stage = {row["stage"]: row for row in snap["stages"]}
    assert by_stage["feature_update"]["p50_ms"] == 3.0
    assert by_stage["feature_update"]["p99_ms"] <= 5.0
    assert by_stage["feature_update"]["budget_status"] == "PASS_P99"
    assert by_stage["shadow_decision_total"]["budget_status"] == "PASS_P99"
    assert snap["hot_path"]["stage"] == "shadow_decision_total"
    assert snap["targets_are_measured_not_assumed"] is True
    assert snap["training_allowed_on_hot_path"] is False
    assert snap["execution_authorized"] is False
    assert snap["production_decision_authorized"] is False


def test_latency_budget_violation_is_counted_and_fails_p99():
    tel = LatencyTelemetry(budgets_ms={"feature_update": 1.0}, max_samples_per_stage=32)
    tel.observe_ms("feature_update", 0.5)
    tel.observe_ms("feature_update", 2.0)
    row = next(x for x in tel.snapshot()["stages"] if x["stage"] == "feature_update")
    assert row["budget_violations"] == 1
    assert row["budget_violation_rate"] == 0.5
    assert row["budget_status"] == "FAIL_P99"


def test_measure_context_uses_monotonic_elapsed_time():
    tel = LatencyTelemetry(max_samples_per_stage=32)
    with tel.measure("candidate_lookup"):
        time.sleep(0.001)
    row = next(x for x in tel.snapshot()["stages"] if x["stage"] == "candidate_lookup")
    assert row["total_samples"] == 1
    assert row["p50_ms"] is not None
    assert row["p50_ms"] >= 0.0
    assert tel.snapshot()["clock"] == "time.perf_counter_ns"


def test_ring_is_bounded_but_totals_remain_truthful():
    tel = LatencyTelemetry(max_samples_per_stage=32)
    for i in range(50):
        tel.observe_ms("custom_stage", float(i))
    row = next(x for x in tel.snapshot()["stages"] if x["stage"] == "custom_stage")
    assert row["retained_samples"] == 32
    assert row["total_samples"] == 50
    assert row["dropped_from_ring"] == 18
    assert row["budget_status"] == "NO_BUDGET"


def test_negative_nan_and_bad_names_fail_closed():
    tel = LatencyTelemetry(max_samples_per_stage=32)
    with pytest.raises(ValueError):
        tel.observe_ms("", 1.0)
    with pytest.raises(ValueError):
        tel.observe_ms("x", -1.0)
    with pytest.raises(ValueError):
        tel.observe_ms("x", float("nan"))


def test_snapshot_persistence_is_atomic_json(tmp_path):
    tel = LatencyTelemetry(max_samples_per_stage=32)
    tel.observe_ms("shadow_decision_total", 7.5)
    path = tel.persist_snapshot(tmp_path)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["hot_path"]["p50_ms"] == 7.5
    assert loaded["execution_authorized"] is False
