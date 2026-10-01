from __future__ import annotations


def test_safe_snapshot_isolates_failure_and_preserves_false_authority():
    from icarus_engine.apex.adapters import safe_snapshot
    ok=safe_snapshot("psi",lambda:{"value":1,"execution_authorized":False,"production_decision_authorized":False})
    assert ok["status"]=="AVAILABLE" and ok["snapshot"]["value"]==1
    bad=safe_snapshot("chronofold",lambda:(_ for _ in ()).throw(RuntimeError("boom")))
    assert bad["status"]=="DEGRADED" and "boom" in bad["error"]
    assert bad["execution_authorized"] is False


def test_sibyl_absence_degrades_gracefully_and_inputs_are_not_mutated():
    from icarus_engine.apex.adapters import sibling_evidence
    psi={"x":1,"execution_authorized":False,"production_decision_authorized":False}
    before=dict(psi)
    rows=sibling_evidence(possibility=lambda:psi,sibyl=None)
    by={r["subsystem"]:r for r in rows}
    assert by["sibyl"]["status"]=="UNAVAILABLE"
    assert psi==before


def test_malformed_or_authorizing_sibling_snapshot_is_quarantined():
    from icarus_engine.apex.adapters import safe_snapshot
    malformed=safe_snapshot("bad",lambda:[1,2,3])
    assert malformed["status"]=="DEGRADED"
    auth=safe_snapshot("bad",lambda:{"execution_authorized":True,"production_decision_authorized":False})
    assert auth["status"]=="DEGRADED"
