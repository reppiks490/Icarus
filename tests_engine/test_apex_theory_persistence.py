from __future__ import annotations


def _theory():
    return {
        "claim": "fragile liquidity amplifies forced-flow cascades",
        "scope": {"asset": "NQ", "regime": "rth"},
        "source_revision": "a" * 40,
        "valid_from": "2026-10-01T14:00:00Z",
        "valid_until": None,
        "falsifiers": ["replenishment absorbs forced selling"],
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def test_theory_transitions_are_append_only_and_negative_results_are_preserved(tmp_path):
    from icarus_engine.apex.store import ApexStore
    from icarus_engine.apex.theory import TheoryLibrary
    store=ApexStore(tmp_path); lib=TheoryLibrary(store,clock=lambda:"2026-10-01T14:01:00Z")
    t=lib.record(_theory())["theory"]
    lib.clock=lambda:"2026-10-01T14:02:00Z"
    lib.transition(t["theory_id"],"supported",evidence_ids=["e1"],reason="replicated")
    lib.clock=lambda:"2026-10-01T14:03:00Z"
    lib.transition(t["theory_id"],"rejected",evidence_ids=["e2"],reason="negative result")
    rows=store._conn.execute("SELECT state, reason FROM theory_events WHERE theory_id=? ORDER BY event_ts",(t["theory_id"],)).fetchall()
    assert [r[0] for r in rows]==["unresolved","supported","rejected"]
    assert rows[-1][1]=="negative result"


def test_theory_as_of_has_no_future_transition_leakage_and_respects_validity_interval(tmp_path):
    from icarus_engine.apex.store import ApexStore
    from icarus_engine.apex.theory import TheoryLibrary
    store=ApexStore(tmp_path); lib=TheoryLibrary(store,clock=lambda:"2026-10-01T14:01:00Z")
    body=_theory(); body["valid_until"]="2026-10-01T15:00:00Z"
    t=lib.record(body)["theory"]
    lib.clock=lambda:"2026-10-01T14:45:00Z"
    lib.transition(t["theory_id"],"supported",evidence_ids=["e1"],reason="evidence")
    assert lib.as_of("2026-10-01T14:30:00Z")[0]["state"]=="unresolved"
    assert lib.as_of("2026-10-01T14:45:00Z")[0]["state"]=="supported"
    assert lib.as_of("2026-10-01T15:00:01Z")==[]


def test_model_credibility_reality_gap_and_conscience_reopen_replay(tmp_path):
    from icarus_engine.apex.store import ApexStore
    store=ApexStore(tmp_path)
    cred={"model_id":"m1","as_of":"2026-10-01T14:00:00Z","score":0.7,"status":"MEASURED","execution_authorized":False,"production_decision_authorized":False}
    gap={"model_id":"m1","as_of":"2026-10-01T14:00:00Z","gap":0.4,"state":"DRIFTING","execution_authorized":False,"production_decision_authorized":False}
    verdict={"belief_id":"b1","as_of":"2026-10-01T14:00:00Z","overall":"OBJECT","judges":{},"execution_authorized":False,"production_decision_authorized":False}
    store.record_model_credibility(cred); store.record_reality_gap(gap); store.record_conscience_verdict(verdict)
    store.close(); reopened=ApexStore(tmp_path)
    assert reopened.model_credibility_as_of("2026-10-01T14:00:00Z")[0]["model_id"]=="m1"
    assert reopened.reality_gap_as_of("2026-10-01T14:00:00Z")[0]["state"]=="DRIFTING"
    assert reopened.conscience_verdicts_as_of("2026-10-01T14:00:00Z")[0]["overall"]=="OBJECT"


def test_self_science_persistence_rejects_future_reads_and_authority_escalation(tmp_path):
    import pytest
    from icarus_engine.apex.store import ApexStore
    store=ApexStore(tmp_path)
    cred={"model_id":"m1","as_of":"2026-10-01T15:00:00Z","score":0.7,"status":"MEASURED","execution_authorized":False,"production_decision_authorized":False}
    store.record_model_credibility(cred)
    assert store.model_credibility_as_of("2026-10-01T14:59:59Z")==[]
    bad=dict(cred); bad["model_id"]="m2"; bad["execution_authorized"]=True
    with pytest.raises(ValueError,match="authority"):
        store.record_model_credibility(bad)
