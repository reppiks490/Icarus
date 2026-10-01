from __future__ import annotations


def _ev(eid, mechanism, *, kind="observed", explicit=False, value=0.6):
    return {"evidence_id":eid,"kind":kind,"subject":"NQ:institutional","value":{"asset":"NQ","mechanism":mechanism,"rule_explicit":explicit,"pressure":value,"direction":"sell","horizon_seconds":300},"source":{"subsystem":"macro","source_repo":"reppiks490/Icarus","source_commit":"a"*40,"source_record_id":eid},"observed_at":"2026-10-01T14:00:00Z","received_at":"2026-10-01T14:00:01Z","calculated_at":"2026-10-01T14:00:01Z","confidence":0.8,"quality":0.9}


def test_explicit_rule_and_inferred_behavior_are_distinguished():
    from icarus_engine.apex.institutional import institutional_mechanics
    out=institutional_mechanics([_ev("x","expiry",explicit=True),_ev("y","cta_threshold",kind="inferred")],asset="NQ",as_of="2026-10-01T14:01:00Z",horizon_seconds=300)
    by={x["mechanism"]:x for x in out["mechanisms"]}
    assert by["expiry"]["status"] == "observed_rule"
    assert by["cta_threshold"]["status"] == "inferred_behavior"


def test_unsupported_dealer_gamma_remains_unavailable():
    from icarus_engine.apex.institutional import institutional_mechanics
    out=institutional_mechanics([],asset="NQ",as_of="2026-10-01T14:01:00Z",horizon_seconds=300)
    gamma=[x for x in out["mechanisms"] if x["mechanism"]=="dealer_gamma"][0]
    assert gamma["status"] == "unavailable" and gamma["pressure"] is None
