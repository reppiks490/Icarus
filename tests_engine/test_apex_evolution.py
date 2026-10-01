from __future__ import annotations


def _proposal(**kw):
    p={"proposal_id":"p1","independent_information_gain":0.2,"reliability_gain":0.2,"compute_cost":0.1,"dependency_cost":0.1,"failure_surface_cost":0.1,"reversible":True,"requested_authority":"research_only"}
    p.update(kw); return p


def test_authority_escalation_is_rejected_even_with_high_performance_gain():
    from icarus_engine.apex.evolution import evaluate_architecture_proposal
    out=evaluate_architecture_proposal(_proposal(independent_information_gain=1.0,reliability_gain=1.0,requested_authority="production"))
    assert out["decision"]=="REJECT" and "authority" in out["reasons"]


def test_complexity_dominated_proposal_is_rejected():
    from icarus_engine.apex.evolution import evaluate_architecture_proposal
    out=evaluate_architecture_proposal(_proposal(independent_information_gain=0.01,reliability_gain=0.01,compute_cost=1.0,dependency_cost=1.0,failure_surface_cost=1.0))
    assert out["decision"]=="REJECT"


def test_missing_information_gain_is_withheld_and_no_deploy_api_exists():
    import icarus_engine.apex.evolution as evo
    out=evo.evaluate_architecture_proposal({"proposal_id":"p","requested_authority":"research_only","reversible":True})
    assert out["decision"]=="WITHHOLD"
    assert not hasattr(evo,"deploy") and not hasattr(evo,"promote")
