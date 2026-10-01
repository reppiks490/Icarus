from __future__ import annotations


def _state():
    return {"asset":"NQ","as_of":"2026-10-01T14:01:00Z","horizon_seconds":300,"classes":[{
        "participant_class":"discretionary_retail","reported_class":"discretionary_retail","confidence":0.6,
        "components":[
            {"metric":"entry_density","direction":"long","price_low":24990.0,"price_high":25010.0,"value":0.8,"confidence":0.7,"evidence_id":"e1"},
            {"metric":"stop_density","direction":"long","price_low":24970.0,"price_high":24990.0,"value":0.5,"confidence":0.6,"evidence_id":"e2"},
            {"metric":"trapped_position_density","direction":"short","price_low":25020.0,"price_high":25040.0,"value":0.4,"confidence":0.5,"evidence_id":"e3"},
        ]}]}


def test_crowd_map_keeps_long_short_and_stop_surfaces_separate():
    from icarus_engine.apex.crowdhunt import crowd_map
    out=crowd_map(_state(),price_grid=[24980.0,25000.0,25030.0])
    assert out["cells"][1]["entry_long_density"] > 0
    assert out["cells"][0]["stop_density_below"] > 0
    assert out["cells"][2]["trapped_short_density"] > 0


def test_stop_density_is_not_inferred_from_entry_density_alone():
    from icarus_engine.apex.crowdhunt import crowd_map
    state=_state(); state["classes"][0]["components"]=[state["classes"][0]["components"][0]]
    out=crowd_map(state,price_grid=[25000.0])
    assert out["cells"][0]["entry_long_density"] > 0
    assert out["cells"][0]["stop_density_below"] is None


def test_crowd_map_has_false_authority_and_explicit_falsifiers():
    from icarus_engine.apex.crowdhunt import crowd_map
    out=crowd_map(_state(),price_grid=[25000.0])
    assert out["execution_authorized"] is False and out["production_decision_authorized"] is False
    assert out["falsifiers"]
