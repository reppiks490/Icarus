from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from icarus_engine.source_reliability import SourceReliabilityStore


def _iso(dt):
    return dt.isoformat().replace("+00:00", "Z")


def _body(i=0, *, complete=True, revision=False, agreement_bps=1.0, tolerance=2.0, age=1.0):
    now = datetime.now(timezone.utc) - timedelta(minutes=5)
    retrieval = now + timedelta(seconds=i)
    event = retrieval - timedelta(seconds=age)
    observed = retrieval + timedelta(milliseconds=10)
    return {
        "source_id": "provider-a",
        "stream": "NQ-trades",
        "observed_at": _iso(observed),
        "event_time": _iso(event),
        "retrieval_time": _iso(retrieval),
        "expected_freshness_seconds": 2.0,
        "complete": complete,
        "agreement_bps": agreement_bps,
        "agreement_tolerance_bps": tolerance,
        "revision": revision,
        "evidence_hash": ("%064x" % (i + 1))[-64:],
    }


def test_observation_identity_is_idempotent_and_freshness_is_derived(tmp_path):
    store = SourceReliabilityStore(tmp_path)
    body = _body(age=1.0)
    first = store.record_observation(body)
    second = store.record_observation(body)
    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert first["fresh"] is True
    assert first["freshness_age_seconds"] == pytest.approx(1.0)


def test_stale_incomplete_revision_and_disagreement_are_measured(tmp_path):
    store = SourceReliabilityStore(tmp_path)
    store.record_observation(_body(0, age=1.0, complete=True, revision=False, agreement_bps=1.0))
    store.record_observation(_body(1, age=4.0, complete=False, revision=True, agreement_bps=5.0))
    row = store.snapshot()["sources"][0]
    assert row["sample_count"] == 2
    assert row["fresh_rate"] == 0.5
    assert row["complete_rate"] == 0.5
    assert row["agreement_rate"] == 0.5
    assert row["revision_rate"] == 0.5
    assert 0.0 < row["reliability_posterior_mean"] < 1.0
    assert row["measurement_status"] == "LOW_SAMPLE"


def test_future_and_noncausal_times_fail_closed(tmp_path):
    store = SourceReliabilityStore(tmp_path)
    body = _body()
    body["event_time"] = "2026-10-01T12:00:02Z"
    body["retrieval_time"] = "2026-10-01T12:00:01Z"
    body["observed_at"] = "2026-10-01T12:00:03Z"
    with pytest.raises(ValueError, match="event_time cannot be later"):
        store.record_observation(body)

    future = _body()
    later = datetime.now(timezone.utc) + timedelta(hours=1)
    future["retrieval_time"] = _iso(later)
    future["observed_at"] = _iso(later + timedelta(seconds=1))
    future["event_time"] = _iso(later - timedelta(seconds=1))
    with pytest.raises(ValueError, match="cannot be in the future"):
        store.record_observation(future)


def test_agreement_fields_are_optional_only_as_a_pair(tmp_path):
    store = SourceReliabilityStore(tmp_path)
    body = _body()
    body["agreement_bps"] = None
    body["agreement_tolerance_bps"] = None
    store.record_observation(body)
    row = store.snapshot()["sources"][0]
    assert row["agreement_sample_count"] == 0
    assert row["agreement_rate"] is None

    bad = _body(2)
    bad["agreement_bps"] = None
    with pytest.raises(ValueError, match="must both be set"):
        store.record_observation(bad)


def test_twenty_samples_become_measured_without_claiming_future_certainty(tmp_path):
    store = SourceReliabilityStore(tmp_path)
    for i in range(20):
        store.record_observation(_body(i, age=0.5, complete=True, revision=False, agreement_bps=0.5))
    snap = store.snapshot()
    row = snap["sources"][0]
    assert row["measurement_status"] == "MEASURED"
    assert row["sample_count"] == 20
    assert row["fresh_rate"] == 1.0
    assert row["reliability_posterior_mean"] < 1.0
    assert snap["execution_authorized"] is False
    assert snap["production_decision_authorized"] is False
