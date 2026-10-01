from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from icarus_engine.performance_proof import PerformanceProofStore


def _times(i=0):
    now = datetime.now(timezone.utc) - timedelta(hours=3)
    decision = now + timedelta(seconds=i)
    maturity = decision + timedelta(minutes=1)
    observed = maturity + timedelta(seconds=1)
    iso = lambda x: x.isoformat().replace("+00:00", "Z")
    return iso(decision), iso(maturity), iso(observed)


def _forecast(i=0, candidate="nq-trend-v1", regime="TREND"):
    decision, maturity, _ = _times(i)
    return {
        "candidate_id": candidate,
        "asset": "NQ",
        "regime": regime,
        "decision_at": decision,
        "matures_at": maturity,
        "probability_success": 0.8,
        "success_definition": "positive net outcome after configured costs at the declared horizon",
        "source_repo": "reppiks490/Icarus",
        "source_commit": "a" * 40,
        "dataset_hash": ("%064x" % (i + 1))[-64:],
        "evidence_hash": ("%064x" % (i + 1001))[-64:],
    }


def test_closed_sample_can_establish_exact_historical_100_percent_without_future_guarantee(tmp_path):
    store = PerformanceProofStore(tmp_path)
    for i in range(30):
        rec = store.register_forecast(_forecast(i))
        _, _, observed = _times(i)
        store.record_outcome({
            "forecast_id": rec["forecast_id"],
            "observed_at": observed,
            "success": True,
            "realized_value": 1.0,
            "outcome_hash": ("%064x" % (i + 2001))[-64:],
            "source": "deterministic test outcome",
        })
    snap = store.snapshot()
    assert snap["metrics"]["outcome_coverage"] == 1.0
    assert snap["metrics"]["success_rate"] == 1.0
    assert snap["closed_sample"]["complete"] is True
    assert snap["closed_sample"]["historical_100_percent_established"] is True
    assert snap["closed_sample"]["future_guarantee"] is False
    assert snap["closed_sample"]["generalization_claim"] is False


def test_one_failure_prevents_100_percent_claim(tmp_path):
    store = PerformanceProofStore(tmp_path)
    for i in range(30):
        rec = store.register_forecast(_forecast(i))
        _, _, observed = _times(i)
        store.record_outcome({
            "forecast_id": rec["forecast_id"],
            "observed_at": observed,
            "success": i != 17,
            "realized_value": 1.0 if i != 17 else -1.0,
            "outcome_hash": ("%064x" % (i + 3001))[-64:],
            "source": "deterministic test outcome",
        })
    snap = store.snapshot()
    assert snap["metrics"]["success_rate"] == 29 / 30
    assert snap["closed_sample"]["historical_100_percent_established"] is False


def test_incomplete_outcome_coverage_fails_closed(tmp_path):
    store = PerformanceProofStore(tmp_path)
    for i in range(30):
        rec = store.register_forecast(_forecast(i))
        if i < 29:
            _, _, observed = _times(i)
            store.record_outcome({
                "forecast_id": rec["forecast_id"],
                "observed_at": observed,
                "success": True,
                "realized_value": None,
                "outcome_hash": ("%064x" % (i + 4001))[-64:],
                "source": "deterministic test outcome",
            })
    snap = store.snapshot()
    assert snap["metrics"]["outcome_coverage"] == 29 / 30
    assert snap["closed_sample"]["complete"] is False
    assert snap["closed_sample"]["historical_100_percent_established"] is False


def test_outcome_before_maturity_is_rejected_and_outcome_is_immutable(tmp_path):
    store = PerformanceProofStore(tmp_path)
    body = _forecast()
    rec = store.register_forecast(body)
    decision, _, observed = _times()
    with pytest.raises(ValueError, match="before forecast maturity"):
        store.record_outcome({
            "forecast_id": rec["forecast_id"], "observed_at": decision, "success": True,
            "realized_value": 1.0, "outcome_hash": "b" * 64, "source": "test",
        })
    first = store.record_outcome({
        "forecast_id": rec["forecast_id"], "observed_at": observed, "success": True,
        "realized_value": 1.0, "outcome_hash": "b" * 64, "source": "test",
    })
    assert first["idempotent"] is False
    second = store.record_outcome({
        "forecast_id": rec["forecast_id"], "observed_at": observed, "success": True,
        "realized_value": 1.0, "outcome_hash": "b" * 64, "source": "test",
    })
    assert second["idempotent"] is True
    with pytest.raises(ValueError, match="immutable"):
        store.record_outcome({
            "forecast_id": rec["forecast_id"], "observed_at": observed, "success": False,
            "realized_value": -1.0, "outcome_hash": "c" * 64, "source": "test",
        })


def test_replay_determinism_requires_a_real_sample(tmp_path):
    store = PerformanceProofStore(tmp_path)
    observed = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    for i in range(10):
        row = store.record_replay({
            "subject": f"candidate-{i}",
            "source_commit": "a" * 40,
            "input_hash": ("%064x" % (i + 1))[-64:],
            "first_output_hash": ("%064x" % (i + 101))[-64:],
            "second_output_hash": ("%064x" % (i + 101))[-64:],
            "observed_at": observed,
        })
        assert row["passed"] is True
    snap = store.snapshot()
    assert snap["replay"]["determinism_rate"] == 1.0
    assert snap["replay"]["historical_100_percent_established"] is True


def test_future_outcome_is_rejected(tmp_path):
    store = PerformanceProofStore(tmp_path)
    rec = store.register_forecast(_forecast())
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    with pytest.raises(ValueError, match="observed_at cannot be in the future"):
        store.record_outcome({
            "forecast_id": rec["forecast_id"],
            "observed_at": future,
            "success": True,
            "realized_value": 1.0,
            "outcome_hash": "d" * 64,
            "source": "future-test",
        })


def test_mixed_success_definitions_do_not_establish_one_global_100_percent_claim(tmp_path):
    store = PerformanceProofStore(tmp_path)
    for i in range(30):
        body = _forecast(i)
        if i >= 15:
            body["success_definition"] = "different outcome definition"
        rec = store.register_forecast(body)
        _, _, observed = _times(i)
        store.record_outcome({
            "forecast_id": rec["forecast_id"],
            "observed_at": observed,
            "success": True,
            "realized_value": 1.0,
            "outcome_hash": ("%064x" % (i + 5001))[-64:],
            "source": "deterministic test outcome",
        })
    snap = store.snapshot()
    assert snap["metrics"]["success_rate"] == 1.0
    assert snap["closed_sample"]["scope_coherent"] is False
    assert snap["closed_sample"]["scope_count"] == 2
    assert snap["closed_sample"]["historical_100_percent_established"] is False
