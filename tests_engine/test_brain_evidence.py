from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from icarus_engine.brain_evidence import (
    BrainEvidence,
    EvidenceSource,
    RegimeSnapshot,
    validate_brain_evidence,
)

UTC = timezone.utc


def _t(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, 16, hour, minute, tzinfo=UTC)


def _source(**overrides):
    values = dict(
        source_id="databento:NQ:ohlcv-1m",
        provider="databento",
        event_time=_t(12, 0),
        retrieved_at=_t(12, 0),
        source_sha256="a" * 64,
        transformation_revision="feature-r17",
        required=True,
        status="verified",
        max_age_seconds=120,
    )
    values.update(overrides)
    return EvidenceSource(**values)


def _regime(**overrides):
    values = dict(
        label="trend_high_vol",
        confidence=0.82,
        observed_at=_t(12, 0),
        model_revision="regime-r9",
        inputs_sha256="b" * 64,
        drift_state="normal",
        ood_state="in_distribution",
    )
    values.update(overrides)
    return RegimeSnapshot(**values)


def _evidence(**overrides):
    values = dict(
        asset="NQ",
        feature_revision="feature-r17",
        evidence_sha256="c" * 64,
        sources=(_source(),),
        regime=_regime(),
        unresolved_validation_gates=(),
        decision_authorized=True,
        execution_authorized=False,
    )
    values.update(overrides)
    return BrainEvidence(**values)


def test_valid_brain_evidence_is_causal_fresh_and_provenance_complete():
    result = validate_brain_evidence(_evidence(), decision_time=_t(12, 1), now=_t(12, 1))
    assert result.valid is True
    assert result.blockers == ()


def test_regime_observed_after_decision_is_rejected_as_lookahead():
    evidence = _evidence(regime=_regime(observed_at=_t(12, 2)))
    result = validate_brain_evidence(evidence, decision_time=_t(12, 1), now=_t(12, 1))
    assert result.valid is False
    assert any("regime" in item.lower() and "decision" in item.lower() for item in result.blockers)


def test_source_event_or_retrieval_after_decision_is_rejected():
    for source in (
        _source(event_time=_t(12, 2)),
        _source(retrieved_at=_t(12, 2)),
    ):
        result = validate_brain_evidence(_evidence(sources=(source,)), decision_time=_t(12, 1), now=_t(12, 1))
        assert result.valid is False
        assert any("after decision" in item.lower() for item in result.blockers)


def test_stale_or_degraded_required_source_fails_closed():
    stale = _source(event_time=_t(11, 50), retrieved_at=_t(11, 50), max_age_seconds=120)
    degraded = _source(status="degraded")
    for source in (stale, degraded):
        result = validate_brain_evidence(_evidence(sources=(source,)), decision_time=_t(12, 1), now=_t(12, 1))
        assert result.valid is False
        assert result.blockers


def test_required_source_without_freshness_bound_fails_closed():
    source = _source(max_age_seconds=None)
    result = validate_brain_evidence(_evidence(sources=(source,)), decision_time=_t(12, 1), now=_t(12, 1))
    assert result.valid is False
    assert any("freshness bound is missing" in item.lower() for item in result.blockers)


def test_missing_provenance_hash_or_revision_is_rejected():
    bad_source = _source(source_sha256="", transformation_revision="")
    bad_evidence = _evidence(sources=(bad_source,), evidence_sha256="", feature_revision="")
    result = validate_brain_evidence(bad_evidence, decision_time=_t(12, 1), now=_t(12, 1))
    assert result.valid is False
    text = " ".join(result.blockers).lower()
    assert "hash" in text or "sha256" in text
    assert "revision" in text


def test_unresolved_validation_gates_block_decision_authorization_but_are_preserved():
    evidence = _evidence(unresolved_validation_gates=("latency_realism", "ood_robustness"))
    result = validate_brain_evidence(evidence, decision_time=_t(12, 1), now=_t(12, 1))
    assert result.valid is False
    assert any("latency_realism" in item for item in result.blockers)
    assert any("ood_robustness" in item for item in result.blockers)


def test_live_execution_cannot_be_authorized_through_brain_evidence():
    evidence = _evidence(execution_authorized=True)
    result = validate_brain_evidence(evidence, decision_time=_t(12, 1), now=_t(12, 1))
    assert result.valid is False
    assert any("live execution" in item.lower() or "owner policy" in item.lower() for item in result.blockers)


@pytest.mark.parametrize("value", [1, 0, "true", "false", "", None, [], {}])
def test_decision_authorization_requires_the_boolean_true(value):
    result = validate_brain_evidence(
        _evidence(decision_authorized=value), decision_time=_t(12, 1),
    )
    assert result.valid is False
    assert any("decision authorization" in item for item in result.blockers)


@pytest.mark.parametrize("value", [0, 1, "false", "", None, [], {}])
def test_execution_authorization_requires_the_boolean_false(value):
    result = validate_brain_evidence(
        _evidence(execution_authorized=value), decision_time=_t(12, 1),
    )
    assert result.valid is False
    assert any("execution authorization" in item for item in result.blockers)


@pytest.mark.parametrize("value", [0, 1, "false", "", None, [], {}])
def test_source_requirement_flag_must_be_a_boolean(value):
    result = validate_brain_evidence(
        _evidence(sources=(_source(required=value),)), decision_time=_t(12, 1),
    )
    assert result.valid is False
    assert any("required" in item for item in result.blockers)
