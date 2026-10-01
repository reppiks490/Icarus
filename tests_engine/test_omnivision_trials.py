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


import sqlite3
from icarus_engine.omnivision.trials import TrialLedger


def test_trial_ledger_preserves_hidden_search_and_all_outcomes(tmp_path):
    ledger = TrialLedger(tmp_path / "trials.sqlite3")
    records = (
        trial(status="passed", feature_config_hash="1" * 64, decision_at=40),
        trial(status="rejected", rejection_reason="weak", feature_config_hash="2" * 64, decision_at=41),
        trial(status="rejected", rejection_reason="unstable", feature_config_hash="3" * 64, decision_at=42),
        trial(status="duplicate", rejection_reason="duplicate", feature_config_hash="1" * 64, decision_at=43),
        trial(status="failed", rejection_reason="exception", feature_config_hash="4" * 64, decision_at=44),
    )
    for record in records:
        ledger.record(record, recorded_at=record.decision_at)

    summary = ledger.family("b" * 64)
    assert len(summary) == 5
    counts = ledger.family_summary("b" * 64)
    assert counts["attempts_total"] == 5
    assert counts["passed"] == 1
    assert counts["rejected"] == 2
    assert counts["failed"] == 1
    assert counts["duplicate"] == 1
    assert counts["deferred"] == 0
    assert counts["invalidated"] == 0
    burden = ledger.search_burden("b" * 64)
    assert burden["correction_required"] is True
    assert burden["distinct_configs"] == 4
    assert burden["attempts_total"] == 5

    passed_only = tuple(item for item in ledger.family("b" * 64) if item.status == "passed")
    assert len(passed_only) == 1
    assert ledger.family_summary("b" * 64)["attempts_total"] == 5


def test_trial_ledger_is_append_only_through_direct_sql(tmp_path):
    path = tmp_path / "trials.sqlite3"
    ledger = TrialLedger(path)
    item = trial()
    ledger.record(item, recorded_at=40)
    connection = sqlite3.connect(path)
    with pytest.raises(sqlite3.DatabaseError):
        connection.execute("UPDATE omnivision_trials SET status='rejected'")
    connection.rollback()
    with pytest.raises(sqlite3.DatabaseError):
        connection.execute("DELETE FROM omnivision_trials")
    connection.close()


def test_trial_ledger_restart_and_family_order_are_deterministic(tmp_path):
    path = tmp_path / "trials.sqlite3"
    first = TrialLedger(path)
    later = trial(feature_config_hash="2" * 64, decision_at=50)
    earlier = trial(feature_config_hash="1" * 64, decision_at=40)
    first.record(later, recorded_at=50)
    first.record(earlier, recorded_at=40)
    second = TrialLedger(path)
    expected = tuple(sorted((earlier, later), key=lambda item: (item.decision_at, item.trial_id)))
    assert first.family("b" * 64) == expected
    assert second.family("b" * 64) == expected
    assert first.family_summary("b" * 64) == second.family_summary("b" * 64)


def test_trial_ledger_single_attempt_needs_no_search_correction(tmp_path):
    ledger = TrialLedger(tmp_path / "trials.sqlite3")
    item = trial()
    assert ledger.record(item, recorded_at=40) == item.trial_id
    assert ledger.record(item, recorded_at=40) == item.trial_id
    assert ledger.get(item.trial_id) == item
    assert ledger.search_burden("b" * 64) == {
        "attempts_total": 1,
        "distinct_configs": 1,
        "distinct_datasets": 1,
        "correction_required": False,
        "reason": "single_recorded_attempt",
    }


def test_trial_ledger_rejects_backdated_recording(tmp_path):
    ledger = TrialLedger(tmp_path / "trials.sqlite3")
    with pytest.raises(ValueError):
        ledger.record(trial(decision_at=50), recorded_at=49)
