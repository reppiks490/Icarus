from __future__ import annotations


def _edge(status="temporally_supported", horizon=300):
    return {
        "edge_id":"e1","source":"rates","target":"NQ","horizon_seconds":horizon,
        "observed_at":"2026-10-01T14:00:00Z","received_at":"2026-10-01T14:00:01Z",
        "source_precedes_target":True,"mechanism":"discounting",
        "observational_support":0.8,"mechanistic_support":0.0,"intervention_support":0.0,
        "confounders":[],"contradictions":["credit disagrees"],"falsifiers":["no response"],
        "status":status,"confidence":0.7,"execution_authorized":False,"production_decision_authorized":False,
    }


def _cascade():
    return {
        "edge_id":"c1","source":"retail_stop","target":"volatility","horizon_seconds":300,
        "estimated_delay_seconds":20.0,"status":"temporally_supported","confidence":0.7,
        "active":True,"falsifiers":["no response"],"event_clustering_is_causal_proof":False,
        "as_of":"2026-10-01T14:00:01Z","execution_authorized":False,"production_decision_authorized":False,
    }


def test_causal_edge_persistence_is_idempotent_and_preserves_contradictions(tmp_path):
    from icarus_engine.apex.store import ApexStore
    store=ApexStore(tmp_path)
    a=store.record_causal_edge(_edge()); b=store.record_causal_edge(_edge())
    assert a["edge_id"]==b["edge_id"] and b["idempotent"] is True
    rows=store.causal_edges_as_of("2026-10-01T14:00:01Z",horizon_seconds=300)
    assert rows[0]["contradictions"]==["credit disagrees"]


def test_causal_horizon_and_as_of_are_isolated(tmp_path):
    from icarus_engine.apex.store import ApexStore
    store=ApexStore(tmp_path)
    e=_edge(horizon=900); e["edge_id"]="e900"
    store.record_causal_edge(e)
    assert store.causal_edges_as_of("2026-10-01T13:59:59Z")==[]
    assert store.causal_edges_as_of("2026-10-01T14:01:00Z",horizon_seconds=300)==[]
    assert len(store.causal_edges_as_of("2026-10-01T14:01:00Z",horizon_seconds=900))==1


def test_cascade_edge_persistence_reopens_deterministically(tmp_path):
    from icarus_engine.apex.store import ApexStore
    store=ApexStore(tmp_path)
    a=store.record_cascade_edge(_cascade())
    store.close()
    reopened=ApexStore(tmp_path)
    rows=reopened.cascade_edges_as_of("2026-10-01T14:00:01Z")
    assert len(rows)==1 and rows[0]["edge_id"]==a["edge_id"]


def test_causal_and_cascade_authority_escalation_rejected(tmp_path):
    import pytest
    from icarus_engine.apex.store import ApexStore
    store=ApexStore(tmp_path)
    bad=_edge(); bad["execution_authorized"]=True
    with pytest.raises(ValueError,match="authority"):
        store.record_causal_edge(bad)
    badc=_cascade(); badc["production_decision_authorized"]=True
    with pytest.raises(ValueError,match="authority"):
        store.record_cascade_edge(badc)
