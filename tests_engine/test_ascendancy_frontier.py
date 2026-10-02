from __future__ import annotations

import copy

import pytest

from icarus_engine.ascendancy.frontier import (
    build_frontier,
    dominates,
    niche_id,
)
from icarus_engine.ascendancy.genome import normalize_genome


def _genome(commit, *, mode, descriptors=("regime", "complexity_band")):
    return normalize_genome({
        "source_repo": "reppiks490/Icarus",
        "source_commit": commit,
        "parent_genome_ids": [],
        "nodes": [
            {"id": "nexus", "subsystem": "nexus", "kind": "native", "tier": "near", "config": {}},
            {"id": "time", "subsystem": "chronofold", "kind": "native", "tier": "research", "config": {"mode": mode}},
        ],
        "edges": [{"source": "nexus", "target": "time", "relation": "evidence"}],
        "mutation": {"operator": "seed", "target": "architecture", "rationale": mode},
        "falsifiers": ["protected OOS contribution is nonpositive"],
        "resource_budget": {"max_evaluations": 32, "max_wall_seconds": 900, "max_cost_units": 20.0},
        "evaluation_contract": {
            "objectives": [
                {"name": "incremental_information", "direction": "max"},
                {"name": "instability", "direction": "min"},
            ],
            "descriptor_keys": list(descriptors),
            "protected_holdout_required": True,
        },
    })


def _eval(genome, info, instability, regime, band, *, observed="2026-10-02T03:00:00Z", suffix="a"):
    return {
        "evaluation_id": (suffix * 64)[:64],
        "genome_id": genome["genome_id"],
        "evaluation_contract_hash": genome["evaluation_contract"]["contract_hash"],
        "metrics": {
            "incremental_information": info,
            "instability": instability,
        },
        "descriptors": {
            "regime": regime,
            "complexity_band": band,
        },
        "evidence": ["fixture"],
        "observed_at": observed,
        "status": "VALIDATED_RESEARCH",
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def _snapshot(genomes, evaluations, lineage=None):
    return {
        "genomes": genomes,
        "evaluations": evaluations,
        "lineage": list(lineage or []),
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def test_pareto_dominance_respects_explicit_objective_directions():
    objectives = [
        {"name": "incremental_information", "direction": "max"},
        {"name": "instability", "direction": "min"},
    ]
    assert dominates(
        {"incremental_information": 0.20, "instability": 0.05},
        {"incremental_information": 0.10, "instability": 0.08},
        objectives,
    ) is True
    assert dominates(
        {"incremental_information": 0.20, "instability": 0.10},
        {"incremental_information": 0.10, "instability": 0.08},
        objectives,
    ) is False


def test_niche_id_is_exact_contract_scoped_and_descriptor_order_independent():
    descriptors_a = {"regime": "RTH_HIGH_VOL", "complexity_band": "MEDIUM"}
    descriptors_b = {"complexity_band": "MEDIUM", "regime": "RTH_HIGH_VOL"}
    one = niche_id("a" * 64, descriptors_a, ["regime", "complexity_band"])
    two = niche_id("a" * 64, descriptors_b, ["complexity_band", "regime"])
    assert one == two
    assert len(one) == 64
    assert niche_id("b" * 64, descriptors_a, ["regime", "complexity_band"]) != one


def test_frontier_preserves_global_pareto_set_and_niche_elites():
    g1 = _genome("1" * 40, mode="stable")
    g2 = _genome("2" * 40, mode="novel")
    g3 = _genome("3" * 40, mode="fragile")

    e1 = _eval(g1, 0.20, 0.05, "RTH", "LOW", suffix="1")
    e2 = _eval(g2, 0.25, 0.08, "RTH", "HIGH", suffix="2")
    e3 = _eval(g3, 0.10, 0.12, "RTH", "LOW", suffix="3")

    out = build_frontier(_snapshot([g1, g2, g3], [e1, e2, e3]))
    group = out["contracts"][0]

    assert set(group["pareto_genome_ids"]) == {g1["genome_id"], g2["genome_id"]}
    niches = {row["descriptor_values"]["complexity_band"]: row for row in group["niches"]}
    assert niches["LOW"]["elite_genome_ids"] == [g1["genome_id"]]
    assert niches["HIGH"]["elite_genome_ids"] == [g2["genome_id"]]
    assert g3["genome_id"] in group["dominated_genome_ids"]
    assert out["execution_authorized"] is False
    assert out["production_decision_authorized"] is False


def test_frontier_never_compares_different_evaluation_contracts():
    g1 = _genome("4" * 40, mode="one")
    g2 = _genome("5" * 40, mode="two", descriptors=("regime",))
    e1 = _eval(g1, 0.2, 0.1, "RTH", "LOW", suffix="4")
    e2 = {
        "evaluation_id": "5" * 64,
        "genome_id": g2["genome_id"],
        "evaluation_contract_hash": g2["evaluation_contract"]["contract_hash"],
        "metrics": {"incremental_information": 0.9, "instability": 0.01},
        "descriptors": {"regime": "RTH"},
        "evidence": ["fixture"],
        "observed_at": "2026-10-02T03:00:00Z",
        "status": "VALIDATED_RESEARCH",
        "execution_authorized": False,
        "production_decision_authorized": False,
    }

    out = build_frontier(_snapshot([g1, g2], [e1, e2]))
    assert len(out["contracts"]) == 2
    for group in out["contracts"]:
        assert group["pareto_count"] == 1


def test_frontier_uses_latest_evaluation_per_genome_not_best_cherry_pick():
    g = _genome("6" * 40, mode="drifting")
    older = _eval(g, 0.50, 0.01, "RTH", "LOW", observed="2026-10-02T02:00:00Z", suffix="6")
    newer = _eval(g, 0.05, 0.20, "RTH", "LOW", observed="2026-10-02T03:00:00Z", suffix="7")

    out = build_frontier(_snapshot([g], [older, newer]))
    candidate = out["contracts"][0]["candidates"][0]
    assert candidate["evaluation_id"] == newer["evaluation_id"]
    assert candidate["metrics"]["incremental_information"] == 0.05
    assert out["selection_policy"] == "latest_evaluation_per_genome_per_contract"


def test_frontier_preserves_retired_or_failed_ancestors_as_stepping_stones():
    parent = _genome("7" * 40, mode="parent")
    child = copy.deepcopy(_genome("8" * 40, mode="child"))
    child_input = {
        k: v for k, v in child.items()
        if k not in {"genome_id", "schema_version", "execution_authorized", "production_decision_authorized"}
    }
    child_input["parent_genome_ids"] = [parent["genome_id"]]
    child = normalize_genome(child_input)
    parent["state"] = "RETIRED"
    child["state"] = "REGISTERED_RESEARCH"

    e_parent = _eval(parent, 0.02, 0.30, "RTH", "LOW", suffix="8")
    e_child = _eval(child, 0.25, 0.05, "RTH", "LOW", suffix="9")
    out = build_frontier(_snapshot(
        [parent, child],
        [e_parent, e_child],
        [{"parent_genome_id": parent["genome_id"], "child_genome_id": child["genome_id"]}],
    ))

    stones = out["stepping_stones"]
    assert any(
        row["genome_id"] == parent["genome_id"]
        and row["descendant_genome_ids"] == [child["genome_id"]]
        for row in stones
    )


def test_frontier_rejects_contract_or_metric_integrity_mismatch():
    g = _genome("9" * 40, mode="integrity")
    bad = _eval(g, 0.1, 0.1, "RTH", "LOW", suffix="a")
    bad["evaluation_contract_hash"] = "f" * 64
    with pytest.raises(ValueError, match="contract"):
        build_frontier(_snapshot([g], [bad]))

    bad_metric = _eval(g, 0.1, 0.1, "RTH", "LOW", suffix="b")
    del bad_metric["metrics"]["instability"]
    with pytest.raises(ValueError, match="metrics"):
        build_frontier(_snapshot([g], [bad_metric]))
