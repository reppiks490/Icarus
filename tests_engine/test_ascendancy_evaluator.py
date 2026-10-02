from __future__ import annotations

import pytest

from icarus_engine.ascendancy.evaluator import (
    EvaluatorCascade,
    evaluation_stage_catalog,
    research_priority,
)
from icarus_engine.ascendancy.foundry import normalize_candidate


def _candidate(**overrides):
    body = {
        "origin": "generated_math",
        "source_repo": "reppiks490/Icarus",
        "source_commit": "a" * 40,
        "title": "Evaluator fixture",
        "hypothesis": "A bounded candidate survives the staged evaluator.",
        "mechanism": {
            "type": "representation_mutation",
            "inputs": ["price"],
            "transform": "fixture",
            "outputs": ["state"],
        },
        "expected_advantage": {
            "target": "incremental_information",
            "direction": "increase",
            "scope": "NQ:RTH",
        },
        "required_observations": [
            {"name": "price", "evidence_class": "observed"},
        ],
        "falsifiers": [
            "protected OOS incremental information is nonpositive",
        ],
        "parent_candidate_ids": [],
        "parent_genome_ids": [],
        "evaluation_contract": {
            "objectives": [
                {"name": "incremental_information", "direction": "max"},
                {"name": "instability", "direction": "min"},
            ],
            "descriptor_keys": ["regime", "complexity_band"],
            "protected_holdout_required": True,
        },
        "resource_budget": {
            "max_evaluations": 100,
            "max_wall_seconds": 1000,
            "max_cost_units": 100.0,
        },
        "metadata": {},
    }
    body.update(overrides)
    return normalize_candidate(body)


def _receipt(candidate, stage, **overrides):
    body = {
        "candidate_id": candidate["candidate_id"],
        "evaluation_contract_hash": candidate["evaluation_contract"]["contract_hash"],
        "source_repo": candidate["source_repo"],
        "source_commit": candidate["source_commit"],
        "stage": stage,
        "outcome": "PASS",
        "metrics": {"signal": 1.0},
        "evidence": [f"evidence:{stage}"],
        "resource_usage": {
            "evaluations": 1,
            "wall_seconds": 2.0,
            "cost_units": 1.0,
        },
        "observed_at": "2026-10-02T08:00:00Z",
    }
    body.update(overrides)
    return body


def test_stage_catalog_is_ordered_multifidelity_and_research_only():
    rows = evaluation_stage_catalog()
    ids = [row["id"] for row in rows]
    assert ids == [
        "CONTRACT_VALIDATION",
        "SMOKE_NULLS",
        "LOW_FIDELITY_REPLAY",
        "ABLATION",
        "WALK_FORWARD",
        "OOS",
        "PROTECTED_HOLDOUT",
        "CONDITIONAL_CONTRIBUTION",
        "ROBUSTNESS",
        "QUALIFICATION_PREFLIGHT",
    ]
    assert rows[0]["fidelity"] == "contract"
    assert rows[2]["fidelity"] == "low"
    assert rows[6]["fidelity"] == "protected"
    assert rows[-1]["grants_qualification"] is False
    assert all(row["execution_authorized"] is False for row in rows)


def test_research_priority_is_information_gain_per_cost_and_fail_closed():
    assert research_priority(2.0, 4.0) == pytest.approx(0.5)
    assert research_priority(0.0, 4.0) == 0.0
    with pytest.raises(ValueError, match="cost"):
        research_priority(1.0, 0.0)
    with pytest.raises(ValueError, match="finite"):
        research_priority(float("nan"), 1.0)


def test_cascade_is_wal_and_starts_at_contract_validation(tmp_path):
    cascade = EvaluatorCascade(tmp_path)
    candidate = _candidate()
    saved = cascade.register_candidate(candidate)

    assert cascade.journal_mode == "wal"
    assert saved["idempotent"] is False
    snap = cascade.candidate(candidate["candidate_id"])
    assert snap["state"] == "EVALUATING"
    assert snap["next_stage"] == "CONTRACT_VALIDATION"
    assert snap["completed_stage_count"] == 0
    assert snap["execution_authorized"] is False
    assert snap["production_decision_authorized"] is False


def test_passes_advance_exactly_one_stage_and_cannot_skip(tmp_path):
    cascade = EvaluatorCascade(tmp_path)
    candidate = _candidate()
    cascade.register_candidate(candidate)

    with pytest.raises(ValueError, match="expected stage"):
        cascade.record(_receipt(candidate, "LOW_FIDELITY_REPLAY"))

    one = cascade.record(_receipt(candidate, "CONTRACT_VALIDATION"))
    assert one["candidate"]["next_stage"] == "SMOKE_NULLS"

    two = cascade.record(_receipt(candidate, "SMOKE_NULLS"))
    assert two["candidate"]["next_stage"] == "LOW_FIDELITY_REPLAY"


def test_failure_halts_candidate_and_blocks_future_stages(tmp_path):
    cascade = EvaluatorCascade(tmp_path)
    candidate = _candidate()
    cascade.register_candidate(candidate)
    failed = cascade.record(_receipt(
        candidate,
        "CONTRACT_VALIDATION",
        outcome="FAIL",
        evidence=["falsifier:contract"],
    ))
    assert failed["candidate"]["state"] == "HALTED_FAILED"
    assert failed["candidate"]["next_stage"] is None

    with pytest.raises(ValueError, match="halted"):
        cascade.record(_receipt(candidate, "SMOKE_NULLS"))


def test_inconclusive_does_not_advance_but_consumes_budget(tmp_path):
    cascade = EvaluatorCascade(tmp_path)
    candidate = _candidate()
    cascade.register_candidate(candidate)

    first = cascade.record(_receipt(
        candidate,
        "CONTRACT_VALIDATION",
        outcome="INCONCLUSIVE",
        resource_usage={"evaluations": 3, "wall_seconds": 5.0, "cost_units": 2.0},
    ))
    assert first["candidate"]["next_stage"] == "CONTRACT_VALIDATION"
    assert first["candidate"]["resource_used"]["evaluations"] == 3

    second = cascade.record(_receipt(
        candidate,
        "CONTRACT_VALIDATION",
        observed_at="2026-10-02T08:01:00Z",
        evidence=["evidence:retry"],
        resource_usage={"evaluations": 1, "wall_seconds": 1.0, "cost_units": 1.0},
    ))
    assert second["candidate"]["next_stage"] == "SMOKE_NULLS"
    assert second["candidate"]["resource_used"]["evaluations"] == 4


def test_budget_is_enforced_before_receipt_is_committed(tmp_path):
    tiny = _candidate(resource_budget={
        "max_evaluations": 2,
        "max_wall_seconds": 4,
        "max_cost_units": 2.0,
    })
    cascade = EvaluatorCascade(tmp_path)
    cascade.register_candidate(tiny)

    with pytest.raises(ValueError, match="resource budget"):
        cascade.record(_receipt(
            tiny,
            "CONTRACT_VALIDATION",
            resource_usage={"evaluations": 3, "wall_seconds": 1.0, "cost_units": 1.0},
        ))
    assert cascade.candidate(tiny["candidate_id"])["receipt_count"] == 0


def test_protected_holdout_requires_id_and_cannot_be_adaptively_reused(tmp_path):
    cascade = EvaluatorCascade(tmp_path)
    first = _candidate(title="first")
    second = _candidate(title="second", hypothesis="Second candidate.")
    cascade.register_candidate(first)
    cascade.register_candidate(second)

    pre_holdout = [
        "CONTRACT_VALIDATION",
        "SMOKE_NULLS",
        "LOW_FIDELITY_REPLAY",
        "ABLATION",
        "WALK_FORWARD",
        "OOS",
    ]
    for idx, stage in enumerate(pre_holdout):
        cascade.record(_receipt(
            first, stage,
            observed_at=f"2026-10-02T08:{10+idx:02d}:00Z",
        ))
        cascade.record(_receipt(
            second, stage,
            observed_at=f"2026-10-02T09:{10+idx:02d}:00Z",
        ))

    with pytest.raises(ValueError, match="holdout_id"):
        cascade.record(_receipt(first, "PROTECTED_HOLDOUT"))

    passed = cascade.record(_receipt(
        first,
        "PROTECTED_HOLDOUT",
        holdout_id="holdout-generation-001",
        observed_at="2026-10-02T08:30:00Z",
    ))
    assert passed["candidate"]["next_stage"] == "CONDITIONAL_CONTRIBUTION"

    with pytest.raises(ValueError, match="holdout"):
        cascade.record(_receipt(
            second,
            "PROTECTED_HOLDOUT",
            holdout_id="holdout-generation-001",
            observed_at="2026-10-02T09:30:00Z",
        ))


def test_full_pass_stops_at_preflight_without_granting_qualification(tmp_path):
    cascade = EvaluatorCascade(tmp_path)
    candidate = _candidate()
    cascade.register_candidate(candidate)

    for idx, stage in enumerate([
        "CONTRACT_VALIDATION",
        "SMOKE_NULLS",
        "LOW_FIDELITY_REPLAY",
        "ABLATION",
        "WALK_FORWARD",
        "OOS",
        "PROTECTED_HOLDOUT",
        "CONDITIONAL_CONTRIBUTION",
        "ROBUSTNESS",
        "QUALIFICATION_PREFLIGHT",
    ]):
        extra = {}
        if stage == "PROTECTED_HOLDOUT":
            extra["holdout_id"] = "holdout-generation-final"
        result = cascade.record(_receipt(
            candidate,
            stage,
            observed_at=f"2026-10-02T10:{idx:02d}:00Z",
            **extra,
        ))

    state = result["candidate"]
    assert state["state"] == "READY_FOR_PROTECTED_QUALIFICATION"
    assert state["next_stage"] is None
    assert state["qualified_shadow"] is False
    assert state["execution_authorized"] is False
    assert state["production_decision_authorized"] is False
    assert cascade.snapshot()["truth_contract"]["cascade_cannot_mint_qualification"] is True


def test_receipts_are_idempotent_and_contract_bound(tmp_path):
    cascade = EvaluatorCascade(tmp_path)
    candidate = _candidate()
    cascade.register_candidate(candidate)
    receipt = _receipt(candidate, "CONTRACT_VALIDATION")
    one = cascade.record(receipt)
    two = cascade.record(receipt)
    assert one["idempotent"] is False
    assert two["idempotent"] is True

    bad = _receipt(candidate, "SMOKE_NULLS")
    bad["evaluation_contract_hash"] = "f" * 64
    with pytest.raises(ValueError, match="contract"):
        cascade.record(bad)
