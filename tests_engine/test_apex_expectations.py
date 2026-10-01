from __future__ import annotations


def _e(a,b,conf=0.8):
    return {"believer":a,"about":b,"belief":"will_buy","confidence":conf,"evidence_ids":[f"{a}-{b}"]}


def test_expectation_graph_caps_depth_and_decays_confidence():
    from icarus_engine.apex.expectations import expectation_graph, expectation_paths
    graph=expectation_graph([_e("macro","dealer"),_e("dealer","cta"),_e("cta","retail")],max_depth=2,depth_penalty=0.5)
    paths=expectation_paths(graph,participant="macro")
    assert max(x["depth"] for x in paths)<=2
    deep=[x for x in paths if x["depth"]==2][0]
    assert deep["confidence"] < paths[0]["confidence"]


def test_missing_root_evidence_is_withheld_and_disagreement_preserved():
    from icarus_engine.apex.expectations import expectation_graph
    rows=[{"believer":"macro","about":"dealer","belief":"buy","confidence":0.8,"evidence_ids":[]},
          {"believer":"macro","about":"dealer","belief":"sell","confidence":0.7,"evidence_ids":["e2"]}]
    graph=expectation_graph(rows)
    assert len(graph["edges"])==1
    assert graph["edges"][0]["belief"]=="sell"


def test_expectation_cycle_is_truncated_not_recursive_forever():
    from icarus_engine.apex.expectations import expectation_graph, expectation_paths
    g=expectation_graph([_e("A","B"),_e("B","A")],max_depth=5)
    paths=expectation_paths(g,participant="A")
    assert len(paths)<=2
