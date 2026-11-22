"""Proof of causal feature/label separation for first-passage research."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from icarus_engine.omnigenesis.contracts import identity
from icarus_engine.omnigenesis.event_bridge import bridge_first_passage
from icarus_engine.omnigenesis.first_passage import label_first_passage
from icarus_engine.omnigenesis.foundry import evaluate_dataset


def synthetic_report():
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = []
    for i in range(110):
        timestamp = t + timedelta(minutes=i)
        # Each odd bar alternates between exclusive upper/lower crossings.
        low, high = (100, 105) if i % 4 == 1 else (
            (95, 100) if i % 4 == 3 else (100, 100)
        )
        bars.append({
            "record_id": f"bar_{i:04d}",
            "observed_at": (timestamp - timedelta(seconds=2)).isoformat(),
            "received_at": (timestamp - timedelta(seconds=1)).isoformat(),
            "open_ticks": 100, "high_ticks": high,
            "low_ticks": low, "close_ticks": 100,
        })
    return label_first_passage({
        "asset": "NQ", "source_commit": "f" * 40, "bars": bars,
    }, upper_distance_ticks=4, lower_distance_ticks=4, horizon_bars=1)


def features_for(report):
    features = []
    for label in report["labels"]:
        if label["event"] not in {"UPPER", "LOWER"}:
            continue
        decision = datetime.fromisoformat(label["decision_at"])
        features.append({
            "decision_record_id": label["decision_record_id"],
            "source_record_id": "verified_derived_feature_" + label["decision_record_id"],
            "source_commit": report["source_commit"],
            "observed_at": (decision - timedelta(seconds=5)).isoformat(),
            "received_at": (decision - timedelta(seconds=2)).isoformat(),
            "feature": float(int(label["decision_record_id"].split("_")[-1]) % 4),
        })
    return features


def test_bridge_uses_only_unambiguous_mature_event_outcomes():
    report = synthetic_report()
    features = features_for(report)
    result = bridge_first_passage(report, features)
    ds, audit = result["dataset"], result["audit"]
    assert len(ds["records"]) == len(features) >= 30
    assert audit["excluded_censored"] > 0
    assert audit["eligible_records"] == len(ds["records"])
    assert audit["future_feature_used"] is False
    assert audit["qualified_edge_claim"] is False
    assert all(
        row["observed_at"] <= row["received_at"] <= row["decision_at"] < row["label_resolved_at"]
        for row in ds["records"]
    )
    assert all(type(row["outcome"]) is bool for row in ds["records"])
    assert audit["dataset_sha256"] == identity(ds)
    assert bridge_first_passage(report, features) == result
    study = evaluate_dataset(ds)
    assert study["authority"]["execution_authorized"] is False
    assert study["status"] in {"EXPLORATORY", "REJECTED"}


def test_bridge_rejects_future_feature_timestamp():
    report = synthetic_report()
    features = features_for(report)
    first = features[0]
    first["observed_at"] = first["received_at"] = (
        datetime.fromisoformat(report["labels"][0]["decision_at"])
        + timedelta(minutes=2)
    ).isoformat()
    with pytest.raises(ValueError, match="future feature"):
        bridge_first_passage(report, features)


def test_bridge_rejects_forged_report():
    report = synthetic_report()
    report["counts"]["UPPER"] += 1
    with pytest.raises(ValueError, match="tampered"):
        bridge_first_passage(report, features_for(report))


def test_bridge_rejects_source_mismatch():
    report = synthetic_report()
    features = features_for(report)
    features[0]["source_commit"] = "a" * 40
    with pytest.raises(ValueError, match="cross-revision"):
        bridge_first_passage(report, features)


def test_bridge_excludes_ambiguous_without_treating_as_negative():
    report = synthetic_report()
    labels = report["labels"]
    for row in labels:
        if row["event"] == "UPPER":
            row["event"] = "AMBIGUOUS_BOTH"
            row["label_is_ambiguous"] = True
            row["label_is_censored"] = False
            report["counts"]["UPPER"] -= 1
            report["counts"]["AMBIGUOUS_BOTH"] += 1
            break
    report["report_id"] = identity({k: v for k, v in report.items() if k != "report_id"})
    feat = features_for(report)
    result = bridge_first_passage(report, feat)
    assert result["audit"]["excluded_ambiguous"] == 1
    assert result["audit"]["eligible_records"] == len(feat)


def test_bridge_rejects_missing_or_extra_features():
    report = synthetic_report()
    feat = features_for(report)
    with pytest.raises(ValueError, match="missing source feature"):
        bridge_first_passage(report, feat[1:])
    extra = dict(feat[0])
    extra["decision_record_id"] = "unknown_extra"
    with pytest.raises(ValueError, match="unused"):
        bridge_first_passage(report, feat + [extra])
