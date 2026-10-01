from __future__ import annotations


def _ev(eid, cls, metric, value, *, direction="long", deps=(), conf=0.8, horizon=300, kind="reconstructed"):
    return {
        "evidence_id": eid,
        "kind": kind,
        "subject": "NQ:participant",
        "value": {
            "asset": "NQ",
            "participant_class": cls,
            "metric": metric,
            "direction": direction,
            "price_low": 24990.0,
            "price_high": 25010.0,
            "value": value,
            "horizon_seconds": horizon,
        },
        "source": {"subsystem":"psi","source_repo":"reppiks490/Icarus","source_commit":"a"*40,"source_record_id": eid if not deps else ""},
        "observed_at":"2026-10-01T14:00:00Z","received_at":"2026-10-01T14:00:01Z","calculated_at":"2026-10-01T14:00:02Z",
        "valid_from":"2026-10-01T14:00:00Z","valid_until":None,"confidence":conf,"quality":0.9,
        "dependencies":list(deps),"contradictions":[],"falsifiers":["response fails"],
        "execution_authorized":False,"production_decision_authorized":False,
    }


def test_empty_evidence_produces_unavailable_not_zero_position():
    from icarus_engine.apex.participants import participant_state
    out=participant_state([],asset="NQ",as_of="2026-10-01T14:01:00Z",horizon_seconds=300)
    assert out["status"] == "UNAVAILABLE"
    assert out["classes"] == []


def test_participant_state_separates_long_and_short_evidence():
    from icarus_engine.apex.participants import participant_state
    ev=[_ev("a","discretionary_retail","entry_density",0.7,direction="long"),_ev("b","discretionary_retail","entry_density",0.4,direction="short")]
    out=participant_state(ev,asset="NQ",as_of="2026-10-01T14:01:00Z",horizon_seconds=300)
    cls=out["classes"][0]
    assert cls["long_support"] == 1
    assert cls["short_support"] == 1
    assert {x["direction"] for x in cls["components"]} == {"long","short"}


def test_shared_ancestry_discounts_participant_confidence():
    from icarus_engine.apex.participants import participant_state
    root=_ev("root","discretionary_retail","entry_density",0.7,kind="observed")
    a=_ev("a","discretionary_retail","stop_density",0.5,deps=["root"])
    b=_ev("b","discretionary_retail","forced_action_propensity",0.6,deps=["root"])
    out=participant_state([root,a,b],asset="NQ",as_of="2026-10-01T14:01:00Z",horizon_seconds=300)
    cls=out["classes"][0]
    assert cls["nominal_evidence_count"] == 3
    assert cls["effective_independent_families"] == 1
    assert cls["confidence"] < 0.8


def test_future_or_wrong_horizon_evidence_is_excluded():
    from icarus_engine.apex.participants import participant_state
    future=_ev("future","discretionary_retail","entry_density",0.7)
    future["received_at"]="2026-10-01T15:00:00Z"
    wrong=_ev("wrong","discretionary_retail","entry_density",0.5,horizon=900)
    out=participant_state([future,wrong],asset="NQ",as_of="2026-10-01T14:30:00Z",horizon_seconds=300)
    assert out["classes"] == []


def test_unknown_participant_class_is_preserved_as_unknown():
    from icarus_engine.apex.participants import participant_state
    out=participant_state([_ev("x","mystery_fund","entry_density",0.5)],asset="NQ",as_of="2026-10-01T14:01:00Z",horizon_seconds=300)
    assert out["classes"][0]["participant_class"] == "unknown"
    assert out["classes"][0]["reported_class"] == "mystery_fund"
