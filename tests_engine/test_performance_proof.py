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


def test_pending_settlement_backlog_returns_only_matured_unsettled(tmp_path):
    store = PerformanceProofStore(tmp_path)

    matured = store.register_forecast(_forecast(0))
    _, _, observed = _times(0)
    store.record_outcome({
        "forecast_id": matured["forecast_id"],
        "observed_at": observed,
        "success": True,
        "realized_value": 1.0,
        "outcome_hash": "a" * 64,
        "source": "settled fixture",
    })

    pending_body = _forecast(1)
    pending = store.register_forecast(pending_body)

    backlog = store.pending_settlements()
    assert backlog["total_matured_unsettled"] == 1
    assert backlog["returned"] == 1
    assert backlog["items"][0]["forecast_id"] == pending["forecast_id"]
    assert backlog["items"][0]["candidate_id"] == pending_body["candidate_id"]
    assert backlog["execution_authorized"] is False
    assert backlog["production_decision_authorized"] is False

    snap = store.snapshot()
    assert snap["settlement_backlog"]["count"] == 1
    assert snap["settlement_backlog"]["fully_settled"] is False


def test_pending_settlement_limit_validation(tmp_path):
    store = PerformanceProofStore(tmp_path)
    with pytest.raises(ValueError, match="limit"):
        store.pending_settlements(limit=0)


def test_settled_records_exposes_source_bound_forecast_outcome_pairs(tmp_path):
    store = PerformanceProofStore(tmp_path)
    body = _forecast(7, candidate="candidate-alpha", regime="VOLATILE")
    rec = store.register_forecast(body)
    _, _, observed = _times(7)
    store.record_outcome({
        "forecast_id": rec["forecast_id"],
        "observed_at": observed,
        "success": False,
        "realized_value": -2.5,
        "outcome_hash": "e" * 64,
        "source": "observed fixture",
    })

    rows = store.settled_records()
    assert rows["returned"] == 1
    item = rows["items"][0]
    assert item["forecast_id"] == rec["forecast_id"]
    assert item["candidate_id"] == "candidate-alpha"
    assert item["asset"] == "NQ"
    assert item["regime"] == "VOLATILE"
    assert item["probability_success"] == 0.8
    assert item["success"] is False
    assert item["realized_value"] == -2.5
    assert item["source_commit"] == "a" * 40
    assert item["dataset_hash"] == body["dataset_hash"]
    assert item["evidence_hash"] == body["evidence_hash"]
    assert rows["execution_authorized"] is False
    assert rows["production_decision_authorized"] is False


def test_settled_records_supports_stable_incremental_cursor(tmp_path):
    store = PerformanceProofStore(tmp_path)
    ids = []
    observed_times = []
    for i in range(3):
        rec = store.register_forecast(_forecast(i, candidate=f"candidate-{i}"))
        _, _, observed = _times(i)
        store.record_outcome({
            "forecast_id": rec["forecast_id"],
            "observed_at": observed,
            "success": i != 1,
            "realized_value": float(i),
            "outcome_hash": ("%064x" % (9000 + i))[-64:],
            "source": "cursor fixture",
        })
        ids.append(rec["forecast_id"])
        observed_times.append(observed)

    first = store.settled_records(limit=1)
    assert first["returned"] == 1
    cursor = first["next_cursor"]
    assert cursor["observed_at"] == first["items"][0]["observed_at"]
    assert cursor["forecast_id"] == first["items"][0]["forecast_id"]

    second = store.settled_records(
        after_observed_at=cursor["observed_at"],
        after_forecast_id=cursor["forecast_id"],
        limit=10,
    )
    assert second["returned"] == 2
    assert first["items"][0]["forecast_id"] not in {x["forecast_id"] for x in second["items"]}
