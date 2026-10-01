from __future__ import annotations

import sqlite3


def _world():
    return {"world_id":"w1","as_of":"2026-10-01T14:00:00Z","state":{"regime":"range"},"assumptions":["liquidity stable"],"weight":0.6,"execution_authorized":False,"production_decision_authorized":False}


def _unknown():
    return {"event_id":"u1","as_of":"2026-10-01T14:00:00Z","state":"UNKNOWN_UNKNOWN","cause":None,"unexplained_fraction":0.8,"residual_signature":"sig","evidence_ids":["e1"],"execution_authorized":False,"production_decision_authorized":False}


def test_world_state_identity_is_idempotent_and_historical(tmp_path):
    from icarus_engine.apex.store import ApexStore
    store=ApexStore(tmp_path)
    a=store.record_world_state(_world()); b=store.record_world_state(_world())
    assert a["world_record_id"]==b["world_record_id"] and b["idempotent"] is True
    assert store.world_states_as_of("2026-10-01T13:59:59Z")==[]
    assert store.world_states_as_of("2026-10-01T14:00:00Z")[0]["weight"]==0.6


def test_unknown_force_event_persists_anonymous_cause_and_reopens(tmp_path):
    from icarus_engine.apex.store import ApexStore
    store=ApexStore(tmp_path)
    a=store.record_unknown_force(_unknown()); store.close()
    reopened=ApexStore(tmp_path)
    rows=reopened.unknown_force_events_as_of("2026-10-01T14:00:00Z")
    assert rows[0]["event_id"]==a["event_id"] and rows[0]["cause"] is None


def test_corrupt_world_row_is_quarantined_from_read(tmp_path):
    from icarus_engine.apex.store import ApexStore
    store=ApexStore(tmp_path); result=store.record_world_state(_world())
    with sqlite3.connect(store.path) as conn:
        conn.execute("UPDATE world_states SET semantic_json=? WHERE world_record_id=?",('{bad',result["world_record_id"])); conn.commit()
    assert store.world_states_as_of("2026-10-01T14:01:00Z")==[]


def test_world_and_unknown_authority_escalation_rejected(tmp_path):
    import pytest
    from icarus_engine.apex.store import ApexStore
    store=ApexStore(tmp_path)
    w=_world(); w["execution_authorized"]=True
    with pytest.raises(ValueError,match="authority"): store.record_world_state(w)
    u=_unknown(); u["production_decision_authorized"]=True
    with pytest.raises(ValueError,match="authority"): store.record_unknown_force(u)
