"""Formal numeric-guard certificates, ambiguity witnesses and limits."""
from __future__ import annotations

import math
import pytest

from icarus_engine.omnigenesis.automata import compile_automaton
from icarus_engine.omnigenesis.formal import (
    guard_collision, check_guards, formal_certificate
)


def transition(src, dst, feature, op, threshold):
    return {"from": src, "to": dst, "feature": feature,
            "op": op, "threshold": threshold}


def minimal():
    return {"name":"event_machine",
            "states":["WAIT","HIT","MISS"], "initial":"WAIT",
            "terminal_states":["HIT","MISS"],
            "transitions":[
                transition("WAIT","HIT","score","gte",0.75),
                transition("WAIT","MISS","score","lt",0.75),
            ]}


def test_complete_numeric_partition_has_no_overlap():
    program=compile_automaton(minimal())
    report=formal_certificate(program)
    assert report["deterministic_for_all_finite_features"] is True
    assert report["all_states_reachable"] is True
    assert report["every_terminal_reachable"] is True
    assert report["terminal_absorbing"] is True
    assert not report["ambiguity_counterexamples"]
    assert report["reachable_terminal_paths"]["HIT"][0]["to"]=="HIT"
    assert report["execution_authorized"] is False
    assert report["liveness_proven"] is False
    assert report["feature_provenance_proven"] is False
    assert report["trading_edge_proven"] is False


def test_witness_same_feature_overlaps_exactly():
    a=transition("WAIT","HIT","score","gte",0.8)
    b=transition("WAIT","MISS","score","gt",0.6)
    clash=guard_collision(a,b)
    assert clash is not None
    assert clash["feature_value"]>=0.8
    spec=minimal()
    spec["transitions"]=[a,b]
    with pytest.raises(ValueError,match="ambiguous"):
        compile_automaton(spec)


def test_witness_independent_features_both_true():
    a=transition("WAIT","HIT","depth","gte",1)
    b=transition("WAIT","MISS","price","lt",10)
    clash=guard_collision(a,b)
    assert clash["feature"]=="depth"
    assert clash["other_feature"]=="price"
    assert clash["feature_value"]>=1
    assert clash["other_feature_value"]<10
    spec=minimal()
    spec["transitions"]=[a,b]
    with pytest.raises(ValueError,match="ambiguous"):
        compile_automaton(spec)


def test_disjoint_equalities_compile_and_have_unique_target():
    spec=minimal()
    spec["transitions"]=[
        transition("WAIT","HIT","score","eq",0.0),
        transition("WAIT","MISS","score","eq",1.0),
    ]
    report=formal_certificate(compile_automaton(spec))
    assert report["deterministic_for_all_finite_features"] is True


def test_unreachable_beyond_float_extreme_is_not_false_collision():
    a=transition("WAIT","HIT","score","gt",float.fromhex("0x1.fffffffffffffp+1023"))
    b=transition("WAIT","MISS","score","gte",0)
    assert guard_collision(a,b) is None


def test_nequality_guard_and_exact_threshold_partition():
    a=transition("WAIT","HIT","score","neq",5)
    b=transition("WAIT","MISS","score","eq",5)
    assert guard_collision(a,b) is None
    c=transition("WAIT","MISS","score","gt",5)
    assert guard_collision(a,c) is not None


def test_certificate_refuses_tampered_program():
    program=compile_automaton(minimal())
    program["transitions"][0]["threshold"]=0.05
    with pytest.raises(ValueError,match="tampered"):
        formal_certificate(program)


@pytest.mark.parametrize("x",[-1e3,-1,0,0.75,1,1e3])
def test_comparator_exactness(x):
    a=transition("A","B","f","gt",0.75)
    b=transition("A","C","f","lte",0.75)
    assert (x>0.75) != (x<=0.75)
    assert guard_collision(a,b) is None
