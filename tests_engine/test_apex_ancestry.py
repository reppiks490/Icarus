from __future__ import annotations

import pytest


def _e(eid, *, deps=(), record=None, subsystem="argus"):
    return {
        "evidence_id": eid,
        "dependencies": list(deps),
        "source": {
            "subsystem": subsystem,
            "source_repo": "reppiks490/Icarus",
            "source_commit": "a" * 40,
            "source_record_id": record if record is not None else eid,
        },
    }


def test_shared_root_counts_as_one_effective_family():
    from icarus_engine.apex.ancestry import EvidenceAncestry
    dag = EvidenceAncestry()
    dag.add(_e("root", record="raw-1"))
    dag.add(_e("derived-a", deps=["root"]))
    dag.add(_e("derived-b", deps=["root"]))
    support = dag.effective_support(["derived-a", "derived-b"])
    assert support["nominal_support"] == 2
    assert support["effective_independent_families"] == 1
    assert support["overlap_ratio"] == 0.5
    assert support["integrity_ok"] is True


def test_independent_roots_increase_effective_support():
    from icarus_engine.apex.ancestry import EvidenceAncestry
    dag = EvidenceAncestry()
    dag.add(_e("a", record="raw-a", subsystem="argus"))
    dag.add(_e("b", record="raw-b", subsystem="macro"))
    support = dag.effective_support(["a", "b"])
    assert support["effective_independent_families"] == 2
    assert len(support["root_ids"]) == 2
    assert support["overlap_ratio"] == 0.0


def test_semantic_duplicate_root_does_not_inflate_support():
    from icarus_engine.apex.ancestry import EvidenceAncestry
    dag = EvidenceAncestry()
    dag.add(_e("copy-a", record="same-raw"))
    dag.add(_e("copy-b", record="same-raw"))
    support = dag.effective_support(["copy-a", "copy-b"])
    assert support["nominal_support"] == 2
    assert support["effective_independent_families"] == 1
    assert support["semantic_duplicate_count"] == 1


def test_ancestry_cycle_fails_closed_without_infinite_traversal():
    from icarus_engine.apex.ancestry import EvidenceAncestry
    dag = EvidenceAncestry()
    dag.add(_e("a", deps=["b"]))
    dag.add(_e("b", deps=["a"]))
    assert dag.detect_cycle("a") is True
    with pytest.raises(ValueError, match="cycle"):
        dag.roots("a")
    support = dag.effective_support(["a", "b"])
    assert support["integrity_ok"] is False
    assert set(support["cycle_evidence_ids"]) == {"a", "b"}


def test_missing_dependency_marks_integrity_false_and_does_not_count_as_independent_support():
    from icarus_engine.apex.ancestry import EvidenceAncestry
    dag = EvidenceAncestry()
    dag.add(_e("derived", deps=["missing-root"]))
    support = dag.effective_support(["derived"])
    assert support["integrity_ok"] is False
    assert support["effective_independent_families"] == 0
    assert support["missing_dependencies"] == ["missing-root"]
