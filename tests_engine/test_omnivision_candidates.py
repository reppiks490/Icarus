import pytest

from icarus_engine.omnivision.candidates import build_candidate
from icarus_engine.omnivision.hypotheses import Hypothesis


def qualified_hypothesis():
    return Hypothesis(
        hypothesis_id="b" * 64,
        kind="latent_gap",
        asset="NQ",
        target="inflation_pressure",
        mechanism="freight-to-goods",
        expected_lag_seconds=0,
        horizon_seconds=0,
        required_variables=("inflation_pressure",),
        evidence_ids=("c" * 64,),
        falsification_rules=("placebo_shift_must_not_match", "walk_forward_must_hold"),
        eligible_regimes=("all",),
        decision_at=100,
    )


def good_inputs():
    return {
        "hypothesis": qualified_hypothesis(),
        "novelty": {"status": "novel", "max_abs_correlation": 0.2},
        "placebo": {"status": "complete", "passed": True},
        "walk_forward": {"passed": True, "folds_qualified": 3},
        "dataset_hash": "a" * 64,
        "known_failure_modes": ("source_stale",),
        "rollback_conditions": ("walk_forward_sign_breaks",),
    }


def test_candidate_never_authorizes_execution():
    artifact = build_candidate(**good_inputs())
    assert artifact["integration_ready"] is True
    assert artifact["execution_authorized"] is False
    assert artifact["artifact_type"] == "omnivision_research_candidate"
    assert len(artifact["candidate_hash"]) == 64


def test_any_failed_gate_blocks_integration_readiness():
    values = good_inputs()
    values["novelty"] = {"status": "redundant", "max_abs_correlation": 0.99}
    artifact = build_candidate(**values)
    assert artifact["integration_ready"] is False
    assert artifact["execution_authorized"] is False


def test_candidate_hash_changes_with_validation():
    left = build_candidate(**good_inputs())
    values = good_inputs()
    values["walk_forward"] = {"passed": False, "folds_qualified": 2}
    right = build_candidate(**values)
    assert left["candidate_hash"] != right["candidate_hash"]


@pytest.mark.parametrize("dataset_hash", ["", "A" * 64, "a" * 63, "g" * 64])
def test_invalid_dataset_hash_rejected(dataset_hash):
    values = good_inputs()
    values["dataset_hash"] = dataset_hash
    with pytest.raises(ValueError):
        build_candidate(**values)


@pytest.mark.parametrize("field", ["known_failure_modes", "rollback_conditions"])
def test_candidate_requires_failure_and_rollback_metadata(field):
    values = good_inputs()
    values[field] = ()
    with pytest.raises(ValueError):
        build_candidate(**values)


def test_execution_authority_is_not_an_input_parameter():
    values = good_inputs()
    values["execution_authorized"] = True
    with pytest.raises(TypeError):
        build_candidate(**values)
