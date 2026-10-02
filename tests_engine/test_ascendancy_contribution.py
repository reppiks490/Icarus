from __future__ import annotations

import math

import pytest

from icarus_engine.ascendancy.contribution import (
    ContributionLab,
    normalize_contribution_observation,
)


CID = "a" * 64
CONTRACT = "b" * 64


def _binary(**overrides):
    body = {
        "contributor_id": CID,
        "contributor_kind": "candidate",
        "source_repo": "reppiks490/Icarus",
        "source_commit": "c" * 40,
        "evaluation_contract_hash": CONTRACT,
        "conditioning_set": ["apex-omega", "chronofold", "psi"],
        "baseline_model_id": "icarus-without-candidate",
        "augmented_model_id": "icarus-plus-candidate",
        "target_kind": "binary",
        "target_key": "reversal_within_horizon",
        "horizon_seconds": 300,
        "baseline_prediction": {"probability": 0.55},
        "augmented_prediction": {"probability": 0.75},
        "observed_outcome": 1,
        "context": {"asset": "NQ", "regime": "RTH_HIGH_VOL"},
        "episode_id": "ep-1",
        "evidence": ["paired-oos:fixture"],
        "observed_at": "2026-10-02T07:00:00Z",
    }
    body.update(overrides)
    return body


def _continuous(**overrides):
    body = _binary(
        target_kind="continuous",
        target_key="forward_return",
        baseline_prediction={"mean": 0.0, "sigma": 2.0},
        augmented_prediction={"mean": 1.0, "sigma": 1.0},
        observed_outcome=1.2,
    )
    body.update(overrides)
    return body


def test_binary_gain_is_paired_log_score_improvement_in_nats():
    row = normalize_contribution_observation(_binary())
    expected = math.log(0.75) - math.log(0.55)
    assert row["information_gain_nats"] == pytest.approx(expected)
    assert row["estimator"] == "paired_predictive_log_score_gain"
    assert row["exact_conditional_mutual_information"] is False
    assert row["execution_authorized"] is False
    assert row["production_decision_authorized"] is False


def test_continuous_gain_uses_gaussian_predictive_log_density():
    row = normalize_contribution_observation(_continuous())

    def logpdf(y, mu, sigma):
        return -0.5 * math.log(2.0 * math.pi) - math.log(sigma) - ((y - mu) ** 2) / (2.0 * sigma ** 2)

    expected = logpdf(1.2, 1.0, 1.0) - logpdf(1.2, 0.0, 2.0)
    assert row["information_gain_nats"] == pytest.approx(expected)
    assert row["target_kind"] == "continuous"


def test_observation_requires_exact_provenance_conditioning_and_evidence():
    with pytest.raises(ValueError, match="40-character Git SHA"):
        normalize_contribution_observation(_binary(source_commit="short"))

    with pytest.raises(ValueError, match="conditioning_set"):
        normalize_contribution_observation(_binary(conditioning_set=[]))

    with pytest.raises(ValueError, match="evidence"):
        normalize_contribution_observation(_binary(evidence=[]))


def test_binary_predictions_are_bounded_and_continuous_sigma_is_positive():
    bad = _binary()
    bad["augmented_prediction"] = {"probability": 1.2}
    with pytest.raises(ValueError, match="probability"):
        normalize_contribution_observation(bad)

    bad_cont = _continuous()
    bad_cont["augmented_prediction"] = {"mean": 1.0, "sigma": 0.0}
    with pytest.raises(ValueError, match="sigma"):
        normalize_contribution_observation(bad_cont)


def test_lab_is_wal_idempotent_and_prevents_duplicate_episode_inflation(tmp_path):
    lab = ContributionLab(tmp_path)
    one = lab.record(_binary())
    two = lab.record(_binary())

    assert lab.journal_mode == "wal"
    assert one["idempotent"] is False
    assert two["idempotent"] is True

    changed = _binary()
    changed["augmented_prediction"] = {"probability": 0.8}
    with pytest.raises(ValueError, match="episode"):
        lab.record(changed)

    snap = lab.snapshot()
    assert snap["observation_count"] == 1
    assert snap["execution_authorized"] is False
    assert snap["production_decision_authorized"] is False


def test_positive_incremental_information_requires_replicated_independent_episodes(tmp_path):
    lab = ContributionLab(tmp_path)
    for i in range(12):
        lab.record(_binary(
            baseline_prediction={"probability": 0.52},
            augmented_prediction={"probability": 0.78},
            episode_id=f"ep-{i}",
            observed_at=f"2026-10-02T07:{i:02d}:00Z",
        ))

    snap = lab.snapshot(contributor_id=CID)
    group = snap["groups"][0]
    assert group["n"] == 12
    assert group["mean_information_gain_nats"] > 0
    assert group["ci95_low"] > 0
    assert group["classification"] == "SUPPORTED_INCREMENTAL"
    assert group["bits_per_observation"] > 0
    assert group["exact_conditional_mutual_information"] is False


def test_harmful_incremental_information_is_detected(tmp_path):
    lab = ContributionLab(tmp_path)
    for i in range(12):
        lab.record(_binary(
            baseline_prediction={"probability": 0.80},
            augmented_prediction={"probability": 0.52},
            episode_id=f"harm-{i}",
            observed_at=f"2026-10-02T08:{i:02d}:00Z",
        ))

    group = lab.snapshot(contributor_id=CID)["groups"][0]
    assert group["mean_information_gain_nats"] < 0
    assert group["ci95_high"] < 0
    assert group["classification"] == "SUPPORTED_HARMFUL_OR_REDUNDANT"


def test_contract_context_horizon_and_conditioning_sets_are_never_pooled(tmp_path):
    lab = ContributionLab(tmp_path)
    lab.record(_binary(
        episode_id="a",
        evaluation_contract_hash="1" * 64,
        conditioning_set=["apex-omega", "psi"],
        context={"asset": "NQ", "regime": "RTH"},
        horizon_seconds=300,
    ))
    lab.record(_binary(
        episode_id="b",
        evaluation_contract_hash="2" * 64,
        conditioning_set=["apex-omega", "chronofold"],
        context={"asset": "NQ", "regime": "ETH"},
        horizon_seconds=600,
    ))

    snap = lab.snapshot(contributor_id=CID)
    assert len(snap["groups"]) == 2
    assert {g["evaluation_contract_hash"] for g in snap["groups"]} == {"1" * 64, "2" * 64}
    assert {g["horizon_seconds"] for g in snap["groups"]} == {300, 600}
    assert len({g["conditioning_set_hash"] for g in snap["groups"]}) == 2


def test_insufficient_evidence_stays_unmeasured_not_zero_edge(tmp_path):
    lab = ContributionLab(tmp_path)
    for i in range(3):
        lab.record(_binary(
            episode_id=f"few-{i}",
            observed_at=f"2026-10-02T09:{i:02d}:00Z",
        ))

    group = lab.snapshot(contributor_id=CID)["groups"][0]
    assert group["classification"] == "INSUFFICIENT_EVIDENCE"
    assert group["n"] == 3
    assert group["mean_information_gain_nats"] is not None
    assert lab.snapshot()["truth_contract"]["standalone_performance_is_not_incremental_information"] is True
