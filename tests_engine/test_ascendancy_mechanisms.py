from __future__ import annotations

import math

import pytest

from icarus_engine.ascendancy.mechanisms import MechanismLab, normalize_experiment


CID = "a" * 64
CONTRACT = "b" * 64


def _experiment(
    *,
    kind="ablation",
    mechanism="time_price_phase",
    baseline=0.20,
    perturbed=0.10,
    direction="max",
    episode="ep-1",
    observed_at="2026-10-02T06:30:00Z",
    contract=CONTRACT,
    related=None,
):
    return {
        "candidate_id": CID,
        "source_repo": "reppiks490/Icarus",
        "source_commit": "c" * 40,
        "evaluation_contract_hash": contract,
        "mechanism_key": mechanism,
        "experiment_kind": kind,
        "target_metric": "incremental_information",
        "direction": direction,
        "baseline_value": baseline,
        "perturbed_value": perturbed,
        "context": {"asset": "NQ", "regime": "RTH_HIGH_VOL"},
        "episode_id": episode,
        "related_mechanisms": list(related or []),
        "evidence": ["paired-replay:fixture"],
        "observed_at": observed_at,
    }


def test_mechanism_experiment_normalizes_directional_effect_and_authority():
    row = normalize_experiment(_experiment())
    assert row["effect"] == pytest.approx(0.10)
    assert len(row["experiment_id"]) == 64
    assert row["execution_authorized"] is False
    assert row["production_decision_authorized"] is False
    assert row["causal_proof"] is False

    lower_is_better = normalize_experiment(
        _experiment(direction="min", baseline=0.05, perturbed=0.12)
    )
    assert lower_is_better["effect"] == pytest.approx(0.07)


def test_mechanism_experiment_requires_exact_provenance_evidence_and_finite_values():
    bad_sha = _experiment()
    bad_sha["source_commit"] = "short"
    with pytest.raises(ValueError, match="40-character Git SHA"):
        normalize_experiment(bad_sha)

    no_evidence = _experiment()
    no_evidence["evidence"] = []
    with pytest.raises(ValueError, match="evidence"):
        normalize_experiment(no_evidence)

    nonfinite = _experiment()
    nonfinite["baseline_value"] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        normalize_experiment(nonfinite)


def test_mechanism_lab_is_wal_idempotent_and_append_only(tmp_path):
    lab = MechanismLab(tmp_path)
    body = _experiment()
    one = lab.record(body)
    two = lab.record(body)

    assert lab.journal_mode == "wal"
    assert one["idempotent"] is False
    assert two["idempotent"] is True
    snap = lab.snapshot()
    assert snap["experiment_count"] == 1
    assert snap["execution_authorized"] is False
    assert snap["production_decision_authorized"] is False


def test_direct_ablation_support_classifies_direct_contributor(tmp_path):
    lab = MechanismLab(tmp_path)
    effects = [
        (0.20, 0.10),
        (0.23, 0.11),
        (0.19, 0.10),
        (0.25, 0.12),
        (0.22, 0.11),
        (0.24, 0.10),
    ]
    for i, (baseline, perturbed) in enumerate(effects):
        lab.record(_experiment(
            baseline=baseline,
            perturbed=perturbed,
            episode=f"ep-{i}",
            observed_at=f"2026-10-02T06:{30+i:02d}:00Z",
        ))

    snap = lab.snapshot(candidate_id=CID)
    mech = next(x for x in snap["mechanisms"] if x["mechanism_key"] == "time_price_phase")
    assert mech["classification"] == "DIRECT_CONTRIBUTOR"
    direct = next(x for x in mech["groups"] if x["experiment_kind"] == "ablation")
    assert direct["n"] == 6
    assert direct["ci95_low"] > 0
    assert direct["sign_agreement"] == 1.0
    assert mech["causal_proof"] is False


def test_interaction_support_without_direct_support_is_interaction_dependent(tmp_path):
    lab = MechanismLab(tmp_path)
    direct_pairs = [
        (0.20, 0.199),
        (0.20, 0.201),
        (0.20, 0.200),
        (0.20, 0.202),
        (0.20, 0.198),
        (0.20, 0.200),
    ]
    for i, (baseline, perturbed) in enumerate(direct_pairs):
        lab.record(_experiment(
            baseline=baseline,
            perturbed=perturbed,
            episode=f"d-{i}",
            observed_at=f"2026-10-02T07:{i:02d}:00Z",
        ))

    for i in range(6):
        lab.record(_experiment(
            kind="interaction_ablation",
            baseline=0.24 + (i * 0.001),
            perturbed=0.10 + (i * 0.001),
            episode=f"i-{i}",
            observed_at=f"2026-10-02T08:{i:02d}:00Z",
            related=["chronofold_temporal_shear"],
        ))

    snap = lab.snapshot(candidate_id=CID)
    mech = next(x for x in snap["mechanisms"] if x["mechanism_key"] == "time_price_phase")
    assert mech["classification"] == "INTERACTION_DEPENDENT"
    assert "chronofold_temporal_shear" in mech["related_mechanisms"]


def test_mechanism_lab_never_pools_different_evaluator_contracts_or_contexts(tmp_path):
    lab = MechanismLab(tmp_path)
    for i in range(5):
        lab.record(_experiment(
            episode=f"a-{i}",
            observed_at=f"2026-10-02T09:{i:02d}:00Z",
            contract="1" * 64,
        ))
    for i in range(5):
        body = _experiment(
            episode=f"b-{i}",
            observed_at=f"2026-10-02T10:{i:02d}:00Z",
            contract="2" * 64,
        )
        body["context"] = {"asset": "NQ", "regime": "ETH_LOW_VOL"}
        lab.record(body)

    snap = lab.snapshot(candidate_id=CID)
    groups = [
        g
        for m in snap["mechanisms"]
        for g in m["groups"]
        if m["mechanism_key"] == "time_price_phase"
    ]
    assert len(groups) == 2
    assert {g["evaluation_contract_hash"] for g in groups} == {"1" * 64, "2" * 64}
    assert {g["context"]["regime"] for g in groups} == {"RTH_HIGH_VOL", "ETH_LOW_VOL"}


def test_insufficient_samples_remain_unresolved_and_not_causal(tmp_path):
    lab = MechanismLab(tmp_path)
    for i in range(3):
        lab.record(_experiment(
            episode=f"few-{i}",
            observed_at=f"2026-10-02T11:{i:02d}:00Z",
        ))

    snap = lab.snapshot(candidate_id=CID)
    mech = snap["mechanisms"][0]
    assert mech["classification"] == "UNRESOLVED"
    assert mech["groups"][0]["status"] == "INSUFFICIENT_EVIDENCE"
    assert snap["truth_contract"]["mechanism_attribution_is_not_causal_proof"] is True
    assert snap["truth_contract"]["contracts_and_contexts_are_never_pooled"] is True
