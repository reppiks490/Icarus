from __future__ import annotations


def test_reflexive_loop_detection_is_canonical_and_finite():
    from icarus_engine.apex.cascade import reflexive_loops
    graph={"edges":[
      {"source":"A","target":"B","active":True,"confidence":0.8,"status":"temporally_supported"},
      {"source":"B","target":"C","active":True,"confidence":0.7,"status":"temporally_supported"},
      {"source":"C","target":"A","active":True,"confidence":0.6,"status":"temporally_supported"},
    ]}
    loops=reflexive_loops(graph,max_cycle=5)
    assert len(loops)==1
    assert set(loops[0]["nodes"])=={"A","B","C"}
    assert 0 <= loops[0]["gain"] <= 1


def test_contradicted_edge_damps_reflexive_gain():
    from icarus_engine.apex.cascade import reflexive_loops
    base=[{"source":"A","target":"B","active":True,"confidence":0.8,"status":"temporally_supported"},{"source":"B","target":"A","active":True,"confidence":0.8,"status":"temporally_supported"}]
    normal=reflexive_loops({"edges":base})[0]["gain"]
    contrad=[dict(base[0]),dict(base[1],status="contradicted")]
    damped=reflexive_loops({"edges":contrad})[0]["gain"]
    assert damped < normal
