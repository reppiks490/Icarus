from __future__ import annotations

import sqlite3

import pytest

from icarus_engine.ascendancy.archive import GenomeArchive
from icarus_engine.ascendancy.genome import compile_genome, normalize_genome


REGISTERED = {"nexus", "chronofold", "psi", "apex-omega"}


def _genome(*, parent_ids=None, source_commit=None, mode="shadow"):
    return {
        "source_repo": "reppiks490/Icarus",
        "source_commit": source_commit or ("b" * 40),
        "parent_genome_ids": list(parent_ids or []),
        "nodes": [
            {"id": "data", "subsystem": "nexus", "kind": "native", "tier": "near", "config": {}},
            {"id": "time", "subsystem": "chronofold", "kind": "native", "tier": "research", "config": {"mode": mode}},
            {"id": "psi", "subsystem": "psi", "kind": "native", "tier": "research", "config": {}},
        ],
        "edges": [
            {"source": "data", "target": "time", "relation": "evidence"},
            {"source": "time", "target": "psi", "relation": "derived_state"},
        ],
        "mutation": {"operator": "seed", "target": "architecture", "rationale": "archive fixture"},
        "falsifiers": ["protected OOS contribution is nonpositive"],
        "resource_budget": {"max_evaluations": 64, "max_wall_seconds": 1800, "max_cost_units": 50.0},
        "evaluation_contract": {
            "objectives": [
                {"name": "incremental_information", "direction": "max"},
                {"name": "instability", "direction": "min"},
            ],
            "descriptor_keys": ["regime", "complexity_band"],
            "protected_holdout_required": True,
        },
    }


def _evaluation(genome, **overrides):
    body = {
        "genome_id": genome["genome_id"],
        "evaluation_contract_hash": genome["evaluation_contract"]["contract_hash"],
        "metrics": {"incremental_information": 0.18, "instability": 0.07},
        "descriptors": {"regime": "RTH_HIGH_VOL", "complexity_band": "MEDIUM"},
        "evidence": ["holdout:fixture", "replay:fixture"],
        "observed_at": "2026-10-02T03:20:00Z",
        "status": "VALIDATED_RESEARCH",
    }
    body.update(overrides)
    return body


def test_archive_is_wal_idempotent_and_reopens_deterministically(tmp_path):
    store = GenomeArchive(tmp_path)
    genome = normalize_genome(_genome())
    first = store.register(genome)
    second = store.register(genome)

    assert store.journal_mode == "wal"
    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert first["genome"]["genome_id"] == genome["genome_id"]
    snap = store.snapshot()
    assert snap["genome_count"] == 1
    assert snap["execution_authorized"] is False
    assert snap["production_decision_authorized"] is False

    store.close()
    reopened = GenomeArchive(tmp_path)
    assert reopened.snapshot()["genomes"][0]["genome_id"] == genome["genome_id"]
    reopened.close()


def test_archive_preserves_parent_child_lineage_through_retirement(tmp_path):
    store = GenomeArchive(tmp_path)
    parent = normalize_genome(_genome(mode="parent"))
    store.register(parent)
    child = normalize_genome(_genome(parent_ids=[parent["genome_id"]], mode="child"))
    store.register(child)

    before = store.snapshot()
    assert before["lineage"] == [{"parent_genome_id": parent["genome_id"], "child_genome_id": child["genome_id"]}]

    retired = store.retire(child["genome_id"], "dominated after protected evaluation")
    assert retired["state"] == "RETIRED"
    after = store.snapshot()
    by_id = {row["genome_id"]: row for row in after["genomes"]}
    assert by_id[child["genome_id"]]["state"] == "RETIRED"
    assert after["lineage"] == before["lineage"]
    assert after["lifecycle_events"][-1]["reason"] == "dominated after protected evaluation"


def test_archive_records_compile_receipts_idempotently(tmp_path):
    store = GenomeArchive(tmp_path)
    genome = normalize_genome(_genome())
    store.register(genome)
    compiled = compile_genome(genome, available_native_subsystems=REGISTERED)

    one = store.record_compile(compiled)
    two = store.record_compile(compiled)
    assert one["idempotent"] is False
    assert two["idempotent"] is True
    assert one["compile_receipt"]["runtime_hash"] == compiled["runtime_hash"]
    assert store.snapshot()["compile_count"] == 1


def test_evaluations_are_append_only_contract_bound_and_finite(tmp_path):
    store = GenomeArchive(tmp_path)
    genome = normalize_genome(_genome())
    store.register(genome)

    first = store.record_evaluation(_evaluation(genome))
    second_body = _evaluation(
        genome,
        metrics={"incremental_information": 0.21, "instability": 0.06},
        observed_at="2026-10-02T03:30:00Z",
    )
    second = store.record_evaluation(second_body)
    assert first["evaluation"]["evaluation_id"] != second["evaluation"]["evaluation_id"]
    assert store.snapshot()["evaluation_count"] == 2

    wrong = _evaluation(genome, evaluation_contract_hash="0" * 64)
    with pytest.raises(ValueError, match="evaluation contract"):
        store.record_evaluation(wrong)

    nonfinite = _evaluation(genome, metrics={"incremental_information": float("nan"), "instability": 0.1})
    with pytest.raises(ValueError, match="finite"):
        store.record_evaluation(nonfinite)


def test_evaluation_requires_exact_objectives_and_descriptors(tmp_path):
    store = GenomeArchive(tmp_path)
    genome = normalize_genome(_genome())
    store.register(genome)

    missing_metric = _evaluation(genome, metrics={"incremental_information": 0.1})
    with pytest.raises(ValueError, match="objective metrics"):
        store.record_evaluation(missing_metric)

    missing_descriptor = _evaluation(genome, descriptors={"regime": "RTH"})
    with pytest.raises(ValueError, match="descriptor"):
        store.record_evaluation(missing_descriptor)


def test_parent_identity_is_immutable_for_existing_genome(tmp_path):
    store = GenomeArchive(tmp_path)
    parent = normalize_genome(_genome(mode="parent"))
    store.register(parent)
    child = normalize_genome(_genome(parent_ids=[parent["genome_id"]], mode="child"))
    store.register(child)

    with sqlite3.connect(store.path) as con:
        con.execute(
            "DELETE FROM lineage WHERE parent_genome_id=? AND child_genome_id=?",
            (parent["genome_id"], child["genome_id"]),
        )
        con.commit()

    with pytest.raises(RuntimeError, match="lineage integrity"):
        store.register(child)


def test_retirement_does_not_delete_evaluations_or_allow_authority_escalation(tmp_path):
    store = GenomeArchive(tmp_path)
    genome = normalize_genome(_genome())
    store.register(genome)
    store.record_evaluation(_evaluation(genome))
    store.retire(genome["genome_id"], "superseded")

    snap = store.snapshot()
    assert snap["evaluation_count"] == 1
    assert snap["genomes"][0]["state"] == "RETIRED"
    assert snap["execution_authorized"] is False
    assert snap["production_decision_authorized"] is False
