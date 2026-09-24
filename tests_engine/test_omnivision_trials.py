import math
import pytest

from icarus_engine.omnivision.trials import TrialRecord


def trial(**changes):
    values = dict(
        hypothesis_id="a" * 64,
        hypothesis_family_id="b" * 64,
        parent_trial_ids=(),
        generation_method="manual_hypothesis",
        feature_config_hash="c" * 64,
        dataset_snapshot_hashes=("d" * 64,),
        train_start=10,
        train_end=20,
        validation_start=20,
        validation_end=30,
        holdout_start=30,
        holdout_end=40,
        code_hash="e" * 64,
        config_hash="f" * 64,
        decision_at=40,
        metrics=(("correlation", 0.2),),
        cost_assumptions=(("slippage_bps", 1.0),),
        status="passed",
        rejection_reason=None,
        family_memberships=("search-family-a",),
        execution_authorized=False,
    )
    values.update(changes)
    return TrialRecord.build(**values)


def test_trial_identity_is_deterministic_and_research_only():
    left = trial(); right = trial()
    assert left == right
    assert len(left.trial_id) == 64
    assert left.execution_authorized is False


@pytest.mark.parametrize("field", [
    "hypothesis_id", "hypothesis_family_id", "feature_config_hash", "code_hash", "config_hash",
])
def test_trial_rejects_bad_required_hashes(field):
    with pytest.raises(ValueError):
        trial(**{field: "bad"})


def test_trial_rejects_bad_dataset_hash_and_nonfinite_metrics():
    with pytest.raises(ValueError):
        trial(dataset_snapshot_hashes=("bad",))
    with pytest.raises(ValueError):
        trial(metrics=(("x", math.inf),))
    with pytest.raises(ValueError):
        trial(cost_assumptions=(("x", math.nan),))


@pytest.mark.parametrize("changes", [
    {"train_end": 10},
    {"validation_start": 19},
    {"validation_end": 20},
    {"holdout_start": 29},
    {"holdout_end": 30},
])
def test_trial_rejects_overlapping_or_empty_time_boundaries(changes):
    with pytest.raises(ValueError):
        trial(**changes)


def test_completed_trial_cannot_decide_before_holdout_end():
    with pytest.raises(ValueError):
        trial(decision_at=39)
    planned = trial(status="planned", decision_at=15, metrics=())
    assert planned.status == "planned"


@pytest.mark.parametrize("status", ["rejected", "failed", "duplicate", "invalidated"])
def test_unsuccessful_completed_status_requires_reason(status):
    with pytest.raises(ValueError):
        trial(status=status, rejection_reason=None)
    item = trial(status=status, rejection_reason="did_not_survive_gate")
    assert item.rejection_reason == "did_not_survive_gate"


def test_trial_rejects_unknown_status_duplicate_parents_and_authorization():
    with pytest.raises(ValueError):
        trial(status="winner")
    with pytest.raises(ValueError):
        trial(parent_trial_ids=("1" * 64, "1" * 64))
    with pytest.raises(ValueError):
        trial(execution_authorized=True)


def test_trial_rejects_duplicate_metric_names_and_empty_family_membership():
    with pytest.raises(ValueError):
        trial(metrics=(("x", 1.0), ("x", 2.0)))
    with pytest.raises(ValueError):
        trial(family_memberships=())
