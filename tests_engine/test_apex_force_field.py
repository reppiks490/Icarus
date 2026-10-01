from __future__ import annotations


def test_pressure_tensor_preserves_opposing_forces_and_net_as_derived_view():
    from icarus_engine.apex.force_field import pressure_tensor
    participants={"classes":[{"participant_class":"discretionary_retail","components":[{"metric":"forced_action_propensity","direction":"sell","price_low":24990.0,"price_high":25010.0,"value":0.7,"confidence":0.8,"evidence_id":"a"},{"metric":"forced_action_propensity","direction":"buy","price_low":24990.0,"price_high":25010.0,"value":0.4,"confidence":0.7,"evidence_id":"b"}]}]}
    out=pressure_tensor(participants=participants,crowd={},institutional={},liquidity={},price_grid=[25000.0],horizons=[300])
    cell=out["cells"][0]
    assert {x["direction"] for x in cell["contributions"]} == {"buy","sell"}
    assert cell["net_pressure"] == -0.3


def test_no_evidence_cell_remains_unavailable():
    from icarus_engine.apex.force_field import pressure_tensor
    out=pressure_tensor(participants={"classes":[]},crowd={},institutional={},liquidity={},price_grid=[25000.0],horizons=[300])
    assert out["cells"][0]["status"] == "UNAVAILABLE"
    assert out["cells"][0]["net_pressure"] is None
