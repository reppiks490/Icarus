from __future__ import annotations
import json

def test_apex_kernel_empty_startup_is_truthful_and_false_authority(tmp_path):
    from icarus_engine.apex.kernel import ApexKernel
    out=ApexKernel(tmp_path).snapshot(as_of="2026-10-01T14:00:00Z")
    assert out["status"]=="EMPTY" and out["participants"]["status"]=="UNAVAILABLE" and out["forces"]["status"]=="UNAVAILABLE"
    assert out["execution_authorized"] is False and out["production_decision_authorized"] is False
    json.dumps(out,allow_nan=False)

def test_apex_kernel_degraded_sibling_is_isolated(tmp_path):
    from icarus_engine.apex.kernel import ApexKernel
    bad=lambda:(_ for _ in ()).throw(RuntimeError("boom"));good=lambda:{"status":"ok","execution_authorized":False,"production_decision_authorized":False}
    out=ApexKernel(tmp_path,possibility=good,chronofold=bad).snapshot(as_of="2026-10-01T14:00:00Z")
    by={x["subsystem"]:x for x in out["siblings"]}
    assert by["psi"]["status"]=="AVAILABLE" and by["chronofold"]["status"]=="DEGRADED"

def test_apex_kernel_explicit_as_of_is_deterministic(tmp_path):
    from icarus_engine.apex.kernel import ApexKernel
    k=ApexKernel(tmp_path)
    assert k.snapshot(as_of="2026-10-01T14:00:00Z",asset="NQ")==k.snapshot(as_of="2026-10-01T14:00:00Z",asset="NQ")

def test_apex_kernel_ingest_evidence_appears_only_after_causal_boundary(tmp_path):
    from icarus_engine.apex.kernel import ApexKernel
    k=ApexKernel(tmp_path);body={"kind":"observed","subject":"NQ:trade","value":{"asset":"NQ","price":25000.0},"source":{"subsystem":"test","source_repo":"reppiks490/Icarus","source_commit":"a"*40,"source_record_id":"r1"},"observed_at":"2026-10-01T14:00:00Z","received_at":"2026-10-01T14:00:01Z","calculated_at":"2026-10-01T14:00:01Z","valid_from":"2026-10-01T14:00:00Z","valid_until":None,"confidence":1.0,"quality":1.0,"dependencies":[],"contradictions":[],"falsifiers":["source correction"]}
    k.ingest_evidence(body)
    assert k.snapshot(as_of="2026-10-01T14:00:00Z",asset="NQ")["epistemics"]["evidence_count"]==0
    assert k.snapshot(as_of="2026-10-01T14:00:01Z",asset="NQ")["epistemics"]["evidence_count"]==1

def test_apex_kernel_research_mutations_never_grant_authority(tmp_path):
    from icarus_engine.apex.kernel import ApexKernel
    k=ApexKernel(tmp_path)
    rows=[k.record_outcome({"outcome_id":"o1","as_of":"2026-10-01T14:00:00Z","status":"matured"}),k.record_model_observation({"model_id":"m1","as_of":"2026-10-01T14:00:00Z","gap":0.2,"state":"NORMAL"}),k.propose_experiment({"id":"e1","discrimination":0.8,"cost":0.1})]
    assert all(x["execution_authorized"] is False and x["production_decision_authorized"] is False for x in rows)


def test_apex_kernel_surfaces_economic_world_state(tmp_path):
    from icarus_engine.apex.kernel import ApexKernel
    k = ApexKernel(tmp_path)
    body = {
        "kind": "reconstructed",
        "subject": "macro:growth",
        "value": {"domain": "growth", "state": "slowing", "market_response": "equities_up"},
        "source": {
            "subsystem": "macro",
            "source_repo": "reppiks490/Icarus",
            "source_commit": "a" * 40,
            "source_record_id": "macro-1",
        },
        "observed_at": "2026-10-01T14:00:00Z",
        "received_at": "2026-10-01T14:00:01Z",
        "calculated_at": "2026-10-01T14:00:01Z",
        "valid_from": "2026-10-01T14:00:00Z",
        "valid_until": None,
        "confidence": 0.8,
        "quality": 0.9,
        "dependencies": [],
        "contradictions": [],
        "falsifiers": ["growth data revises"],
    }
    k.ingest_evidence(body)
    out = k.snapshot(as_of="2026-10-01T14:00:01Z")
    assert out["economic_world"]["domains"]["growth"]["state"] == "slowing"
    assert out["economic_world"]["domains"]["growth"]["market_response"] == "equities_up"
    assert out["economic_world"]["domains"]["credit"]["status"] == "UNAVAILABLE"


def _apex_evidence(*, record, observed, received, deps=()):
    return {
        "kind": "derived" if deps else "observed",
        "subject": "NQ:echo-lineage",
        "value": {"asset": "NQ", "record": record},
        "source": {
            "subsystem": "fixture",
            "source_repo": "reppiks490/Icarus",
            "source_commit": "a" * 40,
            "source_record_id": record,
        },
        "observed_at": observed,
        "received_at": received,
        "calculated_at": received,
        "valid_from": observed,
        "valid_until": None,
        "confidence": 0.9,
        "quality": 0.9,
        "dependencies": list(deps),
        "contradictions": [],
        "falsifiers": ["fixture invalidation"],
    }


def test_apex_resolves_engine_evidence_ids_to_shared_root_lineage(tmp_path):
    from icarus_engine.apex.kernel import ApexKernel
    k = ApexKernel(tmp_path)
    root = k.ingest_evidence(_apex_evidence(
        record="shared-root",
        observed="2026-10-01T13:59:58Z",
        received="2026-10-01T13:59:59Z",
    ))["evidence"]["evidence_id"]
    left = k.ingest_evidence(_apex_evidence(
        record="derived-left",
        observed="2026-10-01T14:00:00Z",
        received="2026-10-01T14:00:01Z",
        deps=(root,),
    ))["evidence"]["evidence_id"]
    right = k.ingest_evidence(_apex_evidence(
        record="derived-right",
        observed="2026-10-01T14:00:00Z",
        received="2026-10-01T14:00:01Z",
        deps=(root,),
    ))["evidence"]["evidence_id"]

    out = k.resolve_engine_evidence_lineage(
        {"oracle": [left], "athena": [right]},
        as_of="2026-10-01T14:00:02Z",
    )
    assert out["status"] == "VERIFIED"
    assert out["engine_evidence_lineage"]["oracle"] == out["engine_evidence_lineage"]["athena"]
    assert len(out["engine_evidence_lineage"]["oracle"]) == 1
    assert out["engine_support"]["oracle"]["integrity_ok"] is True
    assert out["engine_support"]["oracle"]["independence_ratio"] == 1.0
    assert out["engine_support"]["oracle"]["visible_evidence_count"] == 1
    assert out["engine_support"]["oracle"]["mean_quality"] == 0.9
    assert out["engine_support"]["oracle"]["mean_confidence"] == 0.9
    assert out["global_support"]["nominal_support"] == 2
    assert out["global_support"]["effective_independent_families"] == 1
    assert out["global_support"]["independence_ratio"] == 0.5
    assert out["execution_authorized"] is False
    assert out["production_decision_authorized"] is False


def test_apex_lineage_resolution_rejects_unknown_or_future_evidence(tmp_path):
    from icarus_engine.apex.kernel import ApexKernel
    k = ApexKernel(tmp_path)
    saved = k.ingest_evidence(_apex_evidence(
        record="future-receipt",
        observed="2026-10-01T14:00:00Z",
        received="2026-10-01T14:00:05Z",
    ))["evidence"]["evidence_id"]

    import pytest
    with pytest.raises(ValueError, match="integrity failure"):
        k.resolve_engine_evidence_lineage({"oracle": ["missing-id"]}, as_of="2026-10-01T14:00:02Z")
    with pytest.raises(ValueError, match="integrity failure"):
        k.resolve_engine_evidence_lineage({"oracle": [saved]}, as_of="2026-10-01T14:00:02Z")


def test_apex_lineage_tokens_are_compact_even_for_long_source_identity(tmp_path):
    from icarus_engine.apex.kernel import ApexKernel
    k = ApexKernel(tmp_path)
    body = _apex_evidence(
        record="r" * 120,
        observed="2026-10-01T14:00:00Z",
        received="2026-10-01T14:00:01Z",
    )
    body["source"]["source_repo"] = "repo/" + ("x" * 180)
    saved = k.ingest_evidence(body)["evidence"]["evidence_id"]
    out = k.resolve_engine_evidence_lineage(
        {"oracle": [saved]},
        as_of="2026-10-01T14:00:02Z",
    )
    token = out["engine_evidence_lineage"]["oracle"][0]
    full_root = out["engine_support"]["oracle"]["root_ids"][0]
    assert token.startswith("apex-root:")
    assert len(token) == len("apex-root:") + 32
    assert len(full_root) > len(token)
    assert out["engine_support"]["oracle"]["root_tokens"] == [token]


def test_apex_kernel_surfaces_continuous_learning_state(tmp_path):
    from icarus_engine.apex.kernel import ApexKernel

    good = lambda: {
        "status": "LEARNING",
        "scorecards": [{"producer": "sibyl", "settled": 42, "mean_brier": 0.19}],
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
    out = ApexKernel(tmp_path, learning=good).snapshot(as_of="2026-10-01T14:00:00Z")
    assert out["learning"]["status"] == "AVAILABLE"
    assert out["learning"]["snapshot"]["status"] == "LEARNING"
    assert out["learning"]["snapshot"]["scorecards"][0]["settled"] == 42
    assert out["learning"]["execution_authorized"] is False

    bad = lambda: (_ for _ in ()).throw(RuntimeError("learning unavailable"))
    degraded = ApexKernel(tmp_path, learning=bad).snapshot(as_of="2026-10-01T14:00:00Z")
    assert degraded["learning"]["status"] == "DEGRADED"
    assert "learning unavailable" in degraded["learning"]["error"]
