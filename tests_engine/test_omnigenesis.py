"""OMNIGENESIS phase 1–3 safety, math, reproducibility and provenance tests."""
from __future__ import annotations

import copy
import json
import math
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from icarus_engine.omnigenesis import (
    AUTHORITY, ResearchLedger, evaluate_dataset, first_event_offset, next_prime
)
from icarus_engine.omnigenesis.arithmetic import floor_divides
from icarus_engine.omnigenesis.contracts import normalize_dataset


def sample(n=100, outcome_mode="informative"):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    out = []
    for i in range(n):
        decision = start + timedelta(minutes=i)
        feature = float((i * 17) % 19 - 9)
        outcome = feature >= 1 if outcome_mode == "informative" else False
        out.append({
            "record_id": f"event-{i:04d}",
            "asset": "NQ",
            "decision_at": decision.isoformat(),
            "observed_at": (decision - timedelta(seconds=2)).isoformat(),
            "received_at": (decision - timedelta(seconds=1)).isoformat(),
            "label_resolved_at": (decision + timedelta(seconds=30)).isoformat(),
            "feature": feature,
            "outcome": outcome,
            "source_record_id": f"feed-{i}",
        })
    return {"dataset_id": "fixture-nq-v1", "source_commit": "a" * 40, "records": out}


@pytest.mark.parametrize("n,expected", [
    (1, 2), (2, 3), (3, 5), (4, 5), (7, 11), (8, 11), (14, 17),
    (24, 29), (89, 97), (100, 101), (1000, 1009)
])
def test_next_prime_exact(n, expected):
    assert next_prime(n) == expected


def test_floor_indicator_matches_divisibility():
    for n in range(2, 50):
        for k in range(2, 20):
            assert floor_divides(n, k) == int(n % k == 0)


def test_strict_prime_inputs():
    for item in (False, True, 0, -1, 1.2, "7"):
        with pytest.raises((ValueError, TypeError)):
            next_prime(item)


def test_historical_first_passage_and_sentinel():
    assert first_event_offset([False, False, True, True], 4) == 3
    assert first_event_offset([False, False, False], 3) == 4
    assert first_event_offset([True, False], 1) == 1
    with pytest.raises(ValueError, match="incomplete"):
        first_event_offset([True], 2)
    with pytest.raises(ValueError, match="boolean"):
        first_event_offset([1, False], 2)


def test_foundry_reproducible_and_no_authority():
    report = evaluate_dataset(sample())
    assert report == evaluate_dataset(sample())
    assert report["status"] == "EXPLORATORY"
    assert report["authority"] == AUTHORITY
    assert report["search"]["candidate_count"] > 0
    assert report["data_counts"]["train_mature"] >= 8
    assert report["data_counts"]["holdout"] == 20
    assert report["hypothesis"]["holdout_brier_improvement"] > 0
    assert "independent forward data" in report["validation_required"]


def test_holdout_labels_cannot_select_hypothesis():
    data = sample()
    original = evaluate_dataset(data)
    changed = copy.deepcopy(data)
    for row in changed["records"][80:]:
        row["outcome"] = not row["outcome"]
    revised = evaluate_dataset(changed)
    for field in ("operation", "threshold", "p_ge", "p_lt",
                  "validation_brier"):
        assert original["hypothesis"][field] == revised["hypothesis"][field]
    assert original["hypothesis"]["holdout_brier"] != revised["hypothesis"]["holdout_brier"]


def test_record_order_does_not_influence_result():
    data = sample()
    first = evaluate_dataset(data)
    data["records"].reverse()
    second = evaluate_dataset(data)
    assert first == second


def test_provenance_and_causal_availability_fail_closed():
    invalid = sample()
    invalid["records"][0]["received_at"] = "2027-01-01T00:00:00Z"
    with pytest.raises(ValueError, match="not available"):
        evaluate_dataset(invalid)
    invalid = sample()
    invalid["records"][0]["label_resolved_at"] = "2026-01-01T00:00:00Z"
    with pytest.raises(ValueError, match="label not future"):
        evaluate_dataset(invalid)
    invalid = sample()
    invalid["records"][0]["record_id"] = invalid["records"][1]["record_id"]
    with pytest.raises(ValueError, match="duplicate"):
        evaluate_dataset(invalid)
    invalid = sample()
    invalid["records"][0]["feature"] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        evaluate_dataset(invalid)


def test_immature_boundary_outcomes_are_purged():
    data = sample()
    # Entire train segment's labels only resolve after validation begins.
    for row in data["records"][:60]:
        row["label_resolved_at"] = "2027-01-01T00:00:00Z"
    with pytest.raises(ValueError, match="insufficient mature data"):
        evaluate_dataset(data)


def test_uninformative_features_do_not_gain_false_execution_authority():
    report = evaluate_dataset(sample(outcome_mode="no_events"))
    assert report["status"] in {"REJECTED", "EXPLORATORY"}
    assert report["authority"]["execution_authorized"] is False
    assert report["authority"]["auto_promote"] is False


def test_sqlite_immutable_idempotent_and_readonly_snapshot(tmp_path):
    report = evaluate_dataset(sample())
    store = ResearchLedger(tmp_path)
    assert store.append(report) == report["study_id"]
    assert store.append(report) == report["study_id"]
    assert store.get(report["study_id"]) == report
    snap = store.snapshot()
    assert snap["study_count"] == 1
    assert snap["status"] == "RESEARCH_ONLY"
    assert snap["authority"]["execution_authorized"] is False
    assert snap["recent_studies"][0]["study_id"] == report["study_id"]
    assert "records" not in json.dumps(snap)
    modified = copy.deepcopy(report)
    modified["hypothesis"]["p_lt"] = 0.999
    with pytest.raises(ValueError, match="identity mismatch"):
        store.append(modified)
    with pytest.raises(ValueError, match="authority"):
        store.append({**report, "authority": {"execution_authorized": True}})


def test_cli_prime_and_status(tmp_path):
    command = [sys.executable, "-m", "icarus_engine.omnigenesis"]
    result = subprocess.run(command + ["prime", "100"], capture_output=True,
                            text=True, check=True)
    assert json.loads(result.stdout)["next_prime"] == 101
    status = subprocess.run(command + ["status", "--root", str(tmp_path)],
                            capture_output=True, text=True, check=True)
    assert json.loads(status.stdout)["study_count"] == 0
