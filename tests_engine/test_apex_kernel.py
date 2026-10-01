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
