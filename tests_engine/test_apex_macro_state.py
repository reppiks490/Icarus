from __future__ import annotations


def _e(domain,state,conf=0.8,received="2026-10-01T14:00:01Z",market_response=None):
    v={"domain":domain,"state":state}
    if market_response is not None: v["market_response"]=market_response
    return {"evidence_id":f"{domain}-{state}","value":v,"observed_at":"2026-10-01T14:00:00Z","received_at":received,"confidence":conf,"kind":"reconstructed"}


def test_economic_state_and_market_response_remain_separate():
    from icarus_engine.apex.macro_state import economic_world_state
    out=economic_world_state([_e("growth","slowing",market_response="equities_up")],as_of="2026-10-01T14:01:00Z")
    assert out["domains"]["growth"]["state"]=="slowing"
    assert out["domains"]["growth"]["market_response"]=="equities_up"


def test_contradictory_macro_evidence_is_preserved_not_forced_to_consensus():
    from icarus_engine.apex.macro_state import economic_world_state
    out=economic_world_state([_e("inflation","sticky",0.8),_e("inflation","falling",0.7)],as_of="2026-10-01T14:01:00Z")
    assert out["domains"]["inflation"]["status"]=="CONTESTED"
    assert {x["state"] for x in out["domains"]["inflation"]["hypotheses"]}=={"sticky","falling"}


def test_future_received_macro_evidence_is_excluded_and_missing_domain_unavailable():
    from icarus_engine.apex.macro_state import economic_world_state
    out=economic_world_state([_e("growth","strong",received="2026-10-01T15:00:00Z")],as_of="2026-10-01T14:01:00Z")
    assert out["domains"]["growth"]["status"]=="UNAVAILABLE"
    assert out["domains"]["credit"]["status"]=="UNAVAILABLE"
