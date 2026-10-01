from __future__ import annotations

import pytest


def _edge(**kw):
    base={
        "source":"rates","target":"NQ","horizon_seconds":300,
        "observed_at":"2026-10-01T14:00:00Z","received_at":"2026-10-01T14:00:01Z",
        "source_precedes_target":True,"mechanism":"discount-rate transmission",
        "observational_support":0.8,"mechanistic_support":0.0,"intervention_support":0.0,
        "confounders":[],"contradictions":[],"falsifiers":["NQ fails to respond"],
        "status":"correlated","confidence":0.7,
        "execution_authorized":False,"production_decision_authorized":False,
    }
    base.update(kw); return base


def test_high_correlation_with_reversed_time_order_cannot_be_temporally_supported():
    from icarus_engine.apex.causality import causal_edge
    with pytest.raises(ValueError,match="temporal"):
        causal_edge(_edge(status="temporally_supported",source_precedes_target=False))


def test_status_promotion_requires_corresponding_support():
    from icarus_engine.apex.causality import causal_edge
    with pytest.raises(ValueError,match="mechanistic"):
        causal_edge(_edge(status="mechanistically_supported",mechanistic_support=0.0))
    with pytest.raises(ValueError,match="intervention"):
        causal_edge(_edge(status="intervention_supported",mechanistic_support=0.5,intervention_support=0.0))


def test_contradictions_survive_supportive_edge_addition_and_horizon_isolation():
    from icarus_engine.apex.causality import CausalGraph, causal_edge
    g=CausalGraph()
    g.add_edge(causal_edge(_edge(contradictions=["credit disagrees"],status="temporally_supported")))
    g.add_edge(causal_edge(_edge(horizon_seconds=900,target="ES",status="correlated")))
    rows=g.edges_as_of("2026-10-01T14:01:00Z",horizon_seconds=300)
    assert len(rows)==1 and rows[0]["contradictions"]==["credit disagrees"]


def test_pathways_are_depth_bounded_and_cycle_safe():
    from icarus_engine.apex.causality import CausalGraph, causal_edge
    g=CausalGraph()
    for s,t in [("A","B"),("B","C"),("C","A"),("C","D")]:
        g.add_edge(causal_edge(_edge(source=s,target=t,status="temporally_supported")))
    paths=g.pathways("A","D",max_depth=4)
    assert ["A","B","C","D"] in paths
    assert all(len(p)<=5 for p in paths)
