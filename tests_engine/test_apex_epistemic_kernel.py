from __future__ import annotations

import json

import pytest


def test_authority_invariant_rejects_true_execution_or_production_flag():
    from icarus_engine.apex.epistemics import validate_authority_invariants
    validate_authority_invariants({"execution_authorized": False, "production_decision_authorized": False})
    with pytest.raises(ValueError, match="execution"):
        validate_authority_invariants({"execution_authorized": True, "production_decision_authorized": False})
    with pytest.raises(ValueError, match="production"):
        validate_authority_invariants({"execution_authorized": False, "production_decision_authorized": True})


def test_independence_adjustment_never_increases_nominal_confidence():
    from icarus_engine.apex.epistemics import confidence_after_independence
    support = {"nominal_support": 4, "effective_independent_families": 2, "integrity_ok": True}
    adjusted = confidence_after_independence(0.8, support)
    assert 0.0 <= adjusted <= 0.8
    assert adjusted == pytest.approx(0.4)
    assert confidence_after_independence(0.8, {**support, "integrity_ok": False}) == 0.0


def test_unmeasured_calibration_remains_unmeasured_not_perfect():
    from icarus_engine.apex.credibility import credibility_score
    result = credibility_score(calibration=None, data_quality=0.9, independence=0.8, reality_gap=None)
    assert result["status"] == "UNMEASURED"
    assert result["score"] is None
    assert result["calibration"] is None


def test_epistemic_snapshot_is_json_finite_and_false_authority(tmp_path):
    from icarus_engine.apex.epistemics import epistemic_kernel_snapshot
    from icarus_engine.apex.store import ApexStore
    store = ApexStore(tmp_path)
    snap = epistemic_kernel_snapshot(store, as_of="2026-10-01T14:00:00Z")
    json.dumps(snap, allow_nan=False)
    assert snap["execution_authorized"] is False
    assert snap["production_decision_authorized"] is False
    assert snap["as_of"] == "2026-10-01T14:00:00Z"


def test_empty_store_snapshot_is_truthful_not_error(tmp_path):
    from icarus_engine.apex.epistemics import epistemic_kernel_snapshot
    from icarus_engine.apex.store import ApexStore
    store = ApexStore(tmp_path)
    snap = epistemic_kernel_snapshot(store, as_of="2026-10-01T14:00:00Z")
    assert snap["evidence_count"] == 0
    assert snap["belief_count"] == 0
    assert snap["store"]["integrity_ok"] is True
    assert snap["status"] == "EMPTY"


def test_credibility_is_bounded_and_reality_gap_only_reduces_it():
    from icarus_engine.apex.credibility import credibility_score
    base = credibility_score(calibration=0.9, data_quality=0.8, independence=0.75, reality_gap=0.0)
    degraded = credibility_score(calibration=0.9, data_quality=0.8, independence=0.75, reality_gap=0.5)
    assert 0.0 <= degraded["score"] <= base["score"] <= 1.0
