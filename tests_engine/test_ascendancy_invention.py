from __future__ import annotations

import pytest

from icarus_engine.ascendancy.foundry import normalize_candidate
from icarus_engine.ascendancy.invention import (
    InventionLab,
    generate_blueprints,
    primitive_catalog,
    to_foundry_candidate,
)


def _seed(**overrides):
    body = {
        "source_repo": "reppiks490/Icarus",
        "source_commit": "d" * 40,
        "research_question": "Can a transformed market clock expose reversal states not represented by current ICARUS?",
        "target_outcome": "incremental_information",
        "observations": [
            {"role": "price_series", "name": "price", "evidence_class": "observed"},
            {"role": "returns", "name": "returns", "evidence_class": "derived"},
            {"role": "volatility", "name": "realized_volatility", "evidence_class": "derived"},
            {"role": "information_rate", "name": "information_rate", "evidence_class": "derived"},
        ],
        "target_roles": ["phase_state", "topology_state"],
        "parent_candidate_ids": [],
        "constraints": {
            "max_depth": 3,
            "max_candidates": 32,
            "max_cost_units": 7.0,
        },
        "evaluation_contract": {
            "objectives": [
                {"name": "incremental_information", "direction": "max"},
                {"name": "instability", "direction": "min"},
            ],
            "descriptor_keys": ["regime", "complexity_band"],
            "protected_holdout_required": True,
        },
        "resource_budget": {
            "max_evaluations": 128,
            "max_wall_seconds": 3600,
            "max_cost_units": 100.0,
        },
        "context": {"asset": "NQ", "session": "RTH"},
    }
    body.update(overrides)
    return body


def test_primitive_catalog_spans_multiple_math_families_and_is_research_only():
    catalog = primitive_catalog()
    families = {row["family"] for row in catalog}
    assert {
        "market_clock",
        "dynamical_systems",
        "signal_processing",
        "topology",
        "information_geometry",
        "state_space",
    } <= families
    assert all(row["execution_authorized"] is False for row in catalog)
    assert all(row["production_decision_authorized"] is False for row in catalog)


def test_blueprint_generation_is_deterministic_bounded_and_typed():
    one = generate_blueprints(_seed())
    two = generate_blueprints(_seed())
    assert one == two
    assert 0 < len(one) <= 32

    for row in one:
        assert 1 <= row["depth"] <= 3
        assert row["estimated_cost_units"] <= 7.0
        assert row["target_role"] in {"phase_state", "topology_state"}
        assert row["status"] == "UNTESTED_HYPOTHESIS"
        assert row["edge_claim_established"] is False
        assert row["execution_authorized"] is False
        assert row["production_decision_authorized"] is False
        assert row["falsifiers"]

    phase = [row for row in one if row["target_role"] == "phase_state"]
    chains = {tuple(row["primitive_ids"]) for row in phase}
    assert ("information_clock", "phase_embedding") in chains
    assert ("volatility_clock", "phase_embedding") in chains


def test_unavailable_observations_cannot_satisfy_transform_requirements():
    seed = _seed()
    seed["observations"] = [
        {"role": "price_series", "name": "price", "evidence_class": "observed"},
        {"role": "information_rate", "name": "information_rate", "evidence_class": "unavailable"},
    ]
    seed["target_roles"] = ["phase_state"]
    rows = generate_blueprints(seed)
    assert rows == []


def test_blueprint_can_be_converted_to_falsifiable_foundry_candidate():
    blueprint = next(
        row for row in generate_blueprints(_seed())
        if row["primitive_ids"] == ["information_clock", "phase_embedding"]
    )
    candidate = to_foundry_candidate(blueprint)
    normalized = normalize_candidate(candidate)

    assert normalized["origin"] == "generated_math"
    assert normalized["mechanism"]["type"] == "typed_composition"
    assert normalized["mechanism"]["primitive_ids"] == ["information_clock", "phase_embedding"]
    assert normalized["falsifiers"]
    assert normalized["evaluation_contract"]["protected_holdout_required"] is True
    assert normalized["execution_authorized"] is False


def test_invention_lab_persists_blueprints_idempotently_in_wal(tmp_path):
    lab = InventionLab(tmp_path)
    one = lab.generate(_seed())
    two = lab.generate(_seed())

    assert lab.journal_mode == "wal"
    assert one["generated_count"] > 0
    assert two["new_count"] == 0
    snap = lab.snapshot()
    assert snap["blueprint_count"] == one["generated_count"]
    assert snap["execution_authorized"] is False
    assert snap["production_decision_authorized"] is False
    assert snap["truth_contract"]["generated_blueprint_is_not_validated_edge"] is True


def test_invention_generation_rejects_unbounded_search_requests():
    too_deep = _seed()
    too_deep["constraints"]["max_depth"] = 99
    with pytest.raises(ValueError, match="max_depth"):
        generate_blueprints(too_deep)

    too_many = _seed()
    too_many["constraints"]["max_candidates"] = 100000
    with pytest.raises(ValueError, match="max_candidates"):
        generate_blueprints(too_many)

    bad_cost = _seed()
    bad_cost["constraints"]["max_cost_units"] = float("inf")
    with pytest.raises(ValueError, match="finite"):
        generate_blueprints(bad_cost)


def test_blueprints_preserve_parent_candidate_lineage():
    seed = _seed(parent_candidate_ids=["e" * 64])
    rows = generate_blueprints(seed)
    assert rows
    assert all(row["parent_candidate_ids"] == ["e" * 64] for row in rows)
