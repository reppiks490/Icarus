from __future__ import annotations

import pytest


def test_capability_graph_degrades_transitively_on_missing_prerequisite():
    from icarus_engine.apex.self_model import CapabilityGraph
    g=CapabilityGraph(); g.register("depth_analysis",["depth_feed"]); g.register("cascade_analysis",["depth_analysis","participant_state"])
    out=g.status({"depth_feed":False,"participant_state":True})
    assert out["depth_analysis"]["available"] is False
    assert out["cascade_analysis"]["available"] is False


def test_capability_graph_rejects_cycle():
    from icarus_engine.apex.self_model import CapabilityGraph
    g=CapabilityGraph(); g.register("a",["b"])
    with pytest.raises(ValueError,match="cycle"):
        g.register("b",["a"])


def test_self_model_binds_revision_and_preserves_unmeasured_latency():
    from icarus_engine.apex.self_model import self_model_snapshot
    out=self_model_snapshot(source_commit="a"*40,capabilities={"x":{"available":True}},model_health={},compute={},latency={})
    assert out["source_commit"]=="a"*40
    assert out["latency"]["status"]=="UNMEASURED"
    assert out["execution_authorized"] is False
