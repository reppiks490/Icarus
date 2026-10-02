from __future__ import annotations

import copy

import pytest

from icarus_engine.ascendancy.genome import compile_genome, normalize_genome


REGISTERED = {"nexus", "chronofold", "psi", "apex-omega"}


def _genome(**overrides):
    body = {
        "source_repo": "reppiks490/Icarus",
        "source_commit": "a" * 40,
        "parent_genome_ids": [],
        "nodes": [
            {
                "id": "data",
                "subsystem": "nexus",
                "kind": "native",
                "tier": "near",
                "config": {"mode": "causal"},
            },
            {
                "id": "time",
                "subsystem": "chronofold",
                "kind": "native",
                "tier": "research",
                "config": {"mode": "shadow"},
            },
            {
                "id": "possibility",
                "subsystem": "psi",
                "kind": "native",
                "tier": "research",
                "config": {},
            },
        ],
        "edges": [
            {"source": "data", "target": "time", "relation": "evidence"},
            {"source": "time", "target": "possibility", "relation": "derived_state"},
        ],
        "mutation": {
            "operator": "seed",
            "target": "architecture",
            "rationale": "baseline genome",
        },
        "falsifiers": [
            "protected OOS contribution is nonpositive",
            "deterministic replay diverges",
        ],
        "resource_budget": {
            "max_evaluations": 128,
            "max_wall_seconds": 3600,
            "max_cost_units": 100.0,
        },
        "evaluation_contract": {
            "objectives": [
                {"name": "incremental_information", "direction": "max"},
                {"name": "instability", "direction": "min"},
            ],
            "descriptor_keys": ["regime", "complexity_band"],
            "protected_holdout_required": True,
        },
    }
    body.update(overrides)
    return body


def test_genome_normalization_is_deterministic_and_never_grants_authority():
    first = normalize_genome(_genome())
    shuffled_body = _genome()
    shuffled_body["nodes"] = list(reversed(shuffled_body["nodes"]))
    shuffled_body["edges"] = list(reversed(shuffled_body["edges"]))
    shuffled_body["falsifiers"] = list(reversed(shuffled_body["falsifiers"]))
    second = normalize_genome(shuffled_body)

    assert first["genome_id"] == second["genome_id"]
    assert len(first["genome_id"]) == 64
    assert first["execution_authorized"] is False
    assert first["production_decision_authorized"] is False
    assert first["evaluation_contract"]["protected_holdout_required"] is True


def test_compiler_builds_deterministic_topological_layers():
    compiled = compile_genome(_genome(), available_native_subsystems=REGISTERED)
    assert compiled["status"] == "COMPILED_RESEARCH_ONLY"
    assert compiled["layers"] == [["data"], ["time"], ["possibility"]]
    assert len(compiled["runtime_hash"]) == 64
    assert compiled["execution_authorized"] is False
    assert compiled["production_decision_authorized"] is False
    assert compiled["production_bindings"] == []


def test_compiler_rejects_unknown_native_subsystem():
    body = _genome()
    body["nodes"][1]["subsystem"] = "not-registered"
    with pytest.raises(ValueError, match="unknown native subsystem"):
        compile_genome(body, available_native_subsystems=REGISTERED)


def test_genome_rejects_cycles_and_self_loops():
    cyclic = _genome()
    cyclic["edges"].append({"source": "possibility", "target": "data", "relation": "feedback"})
    with pytest.raises(ValueError, match="cycle"):
        compile_genome(cyclic, available_native_subsystems=REGISTERED)

    self_loop = _genome()
    self_loop["edges"].append({"source": "time", "target": "time", "relation": "feedback"})
    with pytest.raises(ValueError, match="self loop"):
        normalize_genome(self_loop)


def test_foreign_generated_and_hybrid_nodes_require_isolated_adapters():
    for kind in ("foreign_lens", "generated", "hybrid"):
        body = _genome()
        body["nodes"].append({
            "id": "foreign",
            "subsystem": "f4d3-time-price",
            "kind": kind,
            "tier": "research",
            "config": {},
        })
        with pytest.raises(ValueError, match="adapter"):
            normalize_genome(body)

        body["nodes"][-1]["adapter_id"] = "lens:f4d3:v1"
        body["nodes"][-1]["isolated"] = True
        normalized = normalize_genome(body)
        node = next(row for row in normalized["nodes"] if row["id"] == "foreign")
        assert node["isolated"] is True


def test_genome_requires_exact_provenance_falsifiers_and_bounded_resources():
    bad_sha = _genome(source_commit="short")
    with pytest.raises(ValueError, match="40-character Git SHA"):
        normalize_genome(bad_sha)

    no_falsifiers = _genome(falsifiers=[])
    with pytest.raises(ValueError, match="falsifier"):
        normalize_genome(no_falsifiers)

    negative_budget = _genome()
    negative_budget["resource_budget"]["max_evaluations"] = -1
    with pytest.raises(ValueError, match="max_evaluations"):
        normalize_genome(negative_budget)


def test_genome_identity_changes_when_semantics_change():
    base = normalize_genome(_genome())
    changed = copy.deepcopy(_genome())
    changed["nodes"][1]["config"]["mode"] = "alternative_shadow"
    changed = normalize_genome(changed)
    assert base["genome_id"] != changed["genome_id"]
