from __future__ import annotations


def _e(eid, value, *, kind="observed", received="2026-10-01T14:00:01Z"):
    return {"evidence_id":eid,"kind":kind,"subject":"NQ:liquidity","value":{"asset":"NQ",**value},"source":{"subsystem":"argus","source_repo":"reppiks490/Icarus","source_commit":"a"*40,"source_record_id":eid},"observed_at":"2026-10-01T14:00:00Z","received_at":received,"calculated_at":received,"confidence":0.8,"quality":0.9}


def test_true_depth_is_exposed_only_from_observed_depth_evidence():
    from icarus_engine.apex.liquidity import liquidity_topology
    out=liquidity_topology([_e("d",{"price":25000.0,"depth":120.0,"spread":0.25})],asset="NQ",as_of="2026-10-01T14:01:00Z",price_grid=[25000.0])
    assert out["depth_status"] == "OBSERVED"
    assert out["cells"][0]["depth"] == 120.0


def test_proxy_only_evidence_never_manufactures_depth():
    from icarus_engine.apex.liquidity import liquidity_topology
    out=liquidity_topology([_e("p",{"price":25000.0,"fragility":0.7,"proxy":True},kind="derived")],asset="NQ",as_of="2026-10-01T14:01:00Z",price_grid=[25000.0])
    assert out["depth_status"] == "UNAVAILABLE"
    assert out["cells"][0]["depth"] is None
    assert "fragility" in out["proxy_fields"]


def test_stale_future_receipt_is_excluded():
    from icarus_engine.apex.liquidity import liquidity_topology
    out=liquidity_topology([_e("d",{"price":25000.0,"depth":120.0},received="2026-10-01T15:00:00Z")],asset="NQ",as_of="2026-10-01T14:01:00Z",price_grid=[25000.0])
    assert out["cells"][0]["depth"] is None
