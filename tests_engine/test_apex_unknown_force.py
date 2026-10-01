from __future__ import annotations


def test_unknown_force_event_never_invents_cause():
    from icarus_engine.apex.unknown_force import unknown_force_event
    out=unknown_force_event(observed={"magnitude":1.0},explained={"magnitude":0.25,"envelope":0.2},evidence_ids=["e1"],as_of="2026-10-01T14:00:00Z")
    assert out["state"] in {"KNOWN_UNKNOWN","UNKNOWN_UNKNOWN"}
    assert out["cause"] is None
    assert 0<=out["unexplained_fraction"]<=1


def test_residual_inside_calibrated_envelope_emits_known_known():
    from icarus_engine.apex.unknown_force import unknown_force_event
    out=unknown_force_event(observed={"magnitude":1.0},explained={"magnitude":0.95,"envelope":0.1},evidence_ids=["e1"],as_of="2026-10-01T14:00:00Z")
    assert out["state"]=="KNOWN_KNOWN"
    assert out["event_id"]


def test_unknown_force_identity_is_reproducible():
    from icarus_engine.apex.unknown_force import unknown_force_event
    kw=dict(observed={"magnitude":2.0},explained={"magnitude":0.5,"envelope":0.2},evidence_ids=["a","b"],as_of="2026-10-01T14:00:00Z")
    assert unknown_force_event(**kw)["event_id"]==unknown_force_event(**kw)["event_id"]
