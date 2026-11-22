"""Phase 6 research-planning and authority-boundary verification."""
import copy

import pytest

from icarus_engine.omnigenesis.evolution import (
    compile_proposal, plan_capabilities
)


def proposal(name, budget=100, cost=0.0, deps=None, gain=0.8):
    return compile_proposal({
        "name": name, "kind": "verification_tool",
        "objective": "Build a new independent falsification instrument for ICARUS.",
        "falsifier": "The new instrument reproduces no previously undetected failures.",
        "evidence_ids": ["a" * 64],
        "depends_on": deps or [],
        "estimated_compute_seconds": budget,
        "estimated_cost_usd": cost,
        "estimated_information_gain": gain,
    })


def test_budgeted_plans_reproducible_and_nonexecuting():
    p1 = proposal("check_1", 100, 1, gain=0.9)
    p2 = proposal("check_2", 800, 10, gain=0.2)
    a = plan_capabilities([p1, p2], max_compute_seconds=200,
                          max_cost_usd=5, max_projects=2)
    b = plan_capabilities([p1, p2], max_compute_seconds=200,
                          max_cost_usd=5, max_projects=2)
    assert a == b
    assert a["selected_proposal_ids"] == [p1["proposal_id"]]
    assert a["estimated_compute_seconds"] == 100
    assert a["estimated_cost_usd"] == 1
    assert a["status"] == "PROPOSED_NOT_EXECUTED"
    assert a["authority"]["execution_authorized"] is False
    assert a["independent_approval_required"] is True


def test_dependency_ordering_and_resource_limits():
    parent = proposal("parent", 100)
    child = proposal("child", 200, deps=[parent["proposal_id"]])
    result = plan_capabilities([child, parent], max_compute_seconds=500,
                               max_cost_usd=0)
    assert result["selected_proposal_ids"] == [
        parent["proposal_id"], child["proposal_id"]
    ]
    small = plan_capabilities([child, parent], max_compute_seconds=50,
                              max_cost_usd=0)
    assert small["selected_proposal_ids"] == []


def test_proposals_refuse_unsafe_mutation():
    p = proposal("another")
    attack = copy.deepcopy(p)
    attack["authority"]["execution_authorized"] = True
    with pytest.raises(ValueError, match="authority"):
        plan_capabilities([attack], max_compute_seconds=100,
                          max_cost_usd=0)
    attack = copy.deepcopy(p)
    attack["estimated_information_gain"] = 1.0
    with pytest.raises(ValueError, match="tampered"):
        plan_capabilities([attack], max_compute_seconds=100,
                          max_cost_usd=0)


def test_duplicate_and_unknown_dependency_refused():
    p = proposal("unique")
    with pytest.raises(ValueError, match="duplicate"):
        plan_capabilities([p, p], max_compute_seconds=100,
                          max_cost_usd=0)
    unknown = proposal("unknown", deps=["b" * 64])
    with pytest.raises(ValueError, match="dependencies"):
        plan_capabilities([unknown], max_compute_seconds=100,
                          max_cost_usd=0)


def test_constraints_and_falsifiability():
    with pytest.raises(ValueError, match="falsifier"):
        compile_proposal({
            "name": "something", "kind": "algorithm",
            "objective": "This objective is long enough.",
            "falsifier": "short", "evidence_ids": ["a" * 64],
            "depends_on": [], "estimated_compute_seconds": 10,
            "estimated_cost_usd": 0, "estimated_information_gain": 1,
        })
    with pytest.raises(ValueError, match="cost budget"):
        plan_capabilities([proposal("check_1")],
                          max_compute_seconds=500, max_cost_usd=-1)
