from __future__ import annotations


def _causal(status="temporally_supported"):
    return {"edges":[{"edge_id":"e1","source":"retail_stop","target":"volatility","horizon_seconds":300,"status":status,"confidence":0.8,"estimated_delay_seconds":20,"falsifiers":["no vol response"]}]}


def _forces():
    return {"cells":[{"price":25000.0,"horizon_seconds":300,"status":"ACTIVE","contributions":[{"source":"participant","participant_class":"discretionary_retail","direction":"sell","pressure":0.7,"signed_pressure":-0.7,"confidence":0.8,"evidence_id":"x"}],"net_pressure":-0.7,"confidence":0.8}]}


def test_cascade_requires_active_force_and_supported_edge():
    from icarus_engine.apex.cascade import build_cascade_graph
    g=build_cascade_graph(forces=_forces(),causal_graph=_causal(),participant_state={},liquidity_state={},as_of="2026-10-01T14:00:00Z")
    assert g["edges"][0]["active"] is True
    blocked=build_cascade_graph(forces=_forces(),causal_graph=_causal("correlated"),participant_state={},liquidity_state={},as_of="2026-10-01T14:00:00Z")
    assert blocked["edges"][0]["active"] is False


def test_cascade_delay_bounds_and_clustering_label_are_truthful():
    from icarus_engine.apex.cascade import build_cascade_graph
    g=build_cascade_graph(forces=_forces(),causal_graph=_causal(),participant_state={},liquidity_state={},as_of="2026-10-01T14:00:00Z")
    edge=g["edges"][0]
    assert 0 <= edge["estimated_delay_seconds"] <= edge["horizon_seconds"]
    assert edge["event_clustering_is_causal_proof"] is False


def test_cascade_paths_are_deterministically_ranked():
    from icarus_engine.apex.cascade import cascade_paths
    graph={"edges":[
      {"source":"A","target":"B","active":True,"confidence":0.9},
      {"source":"B","target":"D","active":True,"confidence":0.9},
      {"source":"A","target":"C","active":True,"confidence":0.5},
      {"source":"C","target":"D","active":True,"confidence":0.5},
    ]}
    paths=cascade_paths(graph,max_depth=4)
    assert paths[0]["nodes"]==["A","B","D"]
