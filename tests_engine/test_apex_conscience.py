from __future__ import annotations


def _belief(kind="reconstructed"):
    return {"claim":"downside cascade","evidence_kind":kind,"evidence_ids":["e1"],"falsifiers":["reclaim"],"contradictions":[],"nominal_confidence":0.8,"execution_authorized":False,"production_decision_authorized":False}


def test_risk_veto_survives_other_judges_passing():
    from icarus_engine.apex.conscience import conscience_verdict
    out=conscience_verdict(belief_packet=_belief(),risk_context={"tail_loss":0.95,"max_tail_loss":0.4},capability_state={"consistent":True},authority_context={"production_decision_authorized":False,"execution_authorized":False})
    assert out["judges"]["Risk"]["state"]=="VETO"
    assert out["overall"]=="VETO"


def test_inferred_as_observed_triggers_truth_veto():
    from icarus_engine.apex.conscience import conscience_verdict
    b=_belief("inferred"); b["claim_representation"]="observed"
    out=conscience_verdict(belief_packet=b,risk_context={},capability_state={"consistent":True},authority_context={"production_decision_authorized":False,"execution_authorized":False})
    assert out["judges"]["Truth"]["state"]=="VETO"


def test_internal_liquidity_contradiction_triggers_consistency_objection():
    from icarus_engine.apex.conscience import conscience_verdict
    caps={"consistent":False,"contradictions":["world liquidity fragile; execution assumes normal liquidity"]}
    out=conscience_verdict(belief_packet=_belief(),risk_context={},capability_state=caps,authority_context={"production_decision_authorized":False,"execution_authorized":False})
    assert out["judges"]["Consistency"]["state"] in {"OBJECT","VETO"}


def test_missing_provenance_and_research_only_authority_are_explicit():
    from icarus_engine.apex.conscience import conscience_verdict
    b=_belief(); b["evidence_ids"]=[]
    out=conscience_verdict(belief_packet=b,risk_context={},capability_state={"consistent":True},authority_context={"production_decision_authorized":False,"execution_authorized":False})
    assert out["judges"]["Provenance"]["state"]=="OBJECT"
    assert out["judges"]["Authority"]["state"]=="PASS"
    assert out["judges"]["Authority"]["detail"]=="research_only"
