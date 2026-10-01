from __future__ import annotations

from icarus_engine.evidence_graph import build_evidence_graph


def event(event_id, *, source_commit="a"*40, evidence=None, candidate_id="", status="observed"):
    return {
        "id": event_id,
        "kind": "candidate" if candidate_id else "finding",
        "subject": candidate_id or "market-structure",
        "summary": "fixture",
        "status": status,
        "recorded_at": "2026-10-01T12:00:00Z",
        "source_repo": "reppiks490/Icarus",
        "source_commit": source_commit,
        "evidence": list(evidence or []),
        "candidate_id": candidate_id,
        "stage": "qualified_shadow" if candidate_id else "",
        "regimes": ["TREND"] if candidate_id else [],
        "validation": {"causal_time": True, "provenance": True} if candidate_id else {},
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def test_repeated_evidence_from_same_revision_is_duplicate_not_independent():
    graph = build_evidence_graph([
        event("e1", evidence=["same observation"]),
        event("e2", evidence=["same observation"]),
    ])
    assert graph["metrics"]["duplicate_evidence_count"] == 1
    assert graph["metrics"]["independently_corroborated_evidence_count"] == 0
    row = graph["evidence"][0]
    assert row["event_count"] == 2
    assert row["source_revision_count"] == 1
    assert row["duplicate_reference"] is True
    assert row["independently_corroborated"] is False


def test_same_evidence_from_two_exact_source_revisions_is_independent_corroboration():
    graph = build_evidence_graph([
        event("e1", source_commit="a"*40, evidence=["same observation"]),
        event("e2", source_commit="b"*40, evidence=["same observation"]),
    ])
    assert graph["metrics"]["independently_corroborated_evidence_count"] == 1
    assert graph["evidence"][0]["source_revision_count"] == 2
    assert graph["evidence"][0]["independently_corroborated"] is True


def test_candidate_provenance_regimes_and_verified_gates_are_projected():
    graph = build_evidence_graph([
        event("c1", candidate_id="nq-trend-v1", evidence=["walk-forward"]),
    ])
    row = graph["candidates"][0]
    assert row["candidate_id"] == "nq-trend-v1"
    assert row["event_count"] == 1
    assert row["source_revision_count"] == 1
    assert row["evidence_count"] == 1
    assert row["regimes"] == ["TREND"]
    assert row["verified_gates"] == ["causal_time", "provenance"]
    assert graph["execution_authorized"] is False
    assert graph["production_decision_authorized"] is False


def test_performance_proof_scope_links_to_candidate_without_minting_authority():
    proof = {
        "candidate_statistics": [{
            "candidate_id": "nq-trend-v1",
            "asset": "NQ",
            "regime": "TREND",
            "success_definition": "positive net outcome after costs",
            "horizon_seconds": 300,
            "settled": 30,
            "successes": 24,
            "success_rate": 0.8,
            "brier_score": 0.16,
            "outcome_coverage": 1.0,
            "closed_regime_sample": True,
        }]
    }
    graph = build_evidence_graph([], proof)
    assert graph["metrics"]["candidate_count"] == 1
    scopes = [n for n in graph["nodes"] if n["kind"] == "proof_scope"]
    assert len(scopes) == 1
    assert scopes[0]["success_rate"] == 0.8
    assert any(e["relation"] == "MEASURED_IN" for e in graph["edges"])
    assert graph["execution_authorized"] is False


def test_graph_output_is_deterministic_for_same_inputs():
    rows = [
        event("e2", source_commit="b"*40, evidence=["beta"]),
        event("e1", source_commit="a"*40, evidence=["alpha"]),
    ]
    assert build_evidence_graph(rows) == build_evidence_graph(rows)
