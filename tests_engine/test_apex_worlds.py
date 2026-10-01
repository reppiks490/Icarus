from __future__ import annotations


def _world(i,w=0.5,state="range"):
    return {"world_id":i,"state":{"regime":state},"assumptions":[i],"weight":w,"execution_authorized":False,"production_decision_authorized":False}


def test_world_weights_normalize_and_update_deterministically():
    from icarus_engine.apex.worlds import WorldPopulation
    p=WorldPopulation(); p.seed([_world("a",0.7),_world("b",0.3,"trend")])
    a=p.update({"likelihoods":{"a":0.2,"b":0.8}}); b=p.snapshot()
    assert abs(sum(x["weight"] for x in a["worlds"])-1)<1e-12
    assert a==b


def test_all_impossible_worlds_become_unresolved_not_divide_by_zero():
    from icarus_engine.apex.worlds import WorldPopulation
    p=WorldPopulation(); p.seed([_world("a"),_world("b")])
    out=p.update({"likelihoods":{"a":0.0,"b":0.0}})
    assert out["status"]=="UNRESOLVED"
    assert all(x["weight"]==0 for x in out["worlds"])


def test_world_split_is_bounded_and_equivalent_worlds_merge():
    from icarus_engine.apex.worlds import WorldPopulation
    p=WorldPopulation(max_worlds=4); p.seed([_world("a",1.0)])
    ids=p.split("a",[{"state":{"regime":"trend"},"weight_share":0.5},{"state":{"regime":"trend"},"weight_share":0.5}])
    assert len(ids)==2
    assert p.merge_equivalent()==1
