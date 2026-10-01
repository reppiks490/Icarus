from __future__ import annotations


def test_unavailable_and_redundant_observations_are_deprioritized():
    from icarus_engine.apex.information_gain import rank_observations
    rows=[{"id":"new","uncertainty_reduction":0.8,"decision_improvement":0.8,"redundancy":0.0},{"id":"dup","uncertainty_reduction":0.9,"decision_improvement":0.9,"redundancy":0.95},{"id":"missing","uncertainty_reduction":1.0,"decision_improvement":1.0,"redundancy":0.0}]
    out=rank_observations(rows,uncertainty_state={},acquisition_costs={"new":0.1,"dup":0.1,"missing":0.0},availability={"new":True,"dup":True,"missing":False})
    assert [x["id"] for x in out][0]=="new"
    assert [x for x in out if x["id"]=="missing"][0]["status"]=="UNAVAILABLE"


def test_experiment_ranking_rewards_discrimination_and_is_deterministic():
    from icarus_engine.apex.information_gain import rank_experiments
    hypotheses=["H1","H2"]
    experiments=[{"id":"weak","discrimination":0.2,"cost":0.1},{"id":"strong","discrimination":0.9,"cost":0.2}]
    a=rank_experiments(hypotheses,experiments); b=rank_experiments(hypotheses,experiments)
    assert a==b and a[0]["id"]=="strong"


def test_expensive_low_value_compute_job_is_deprioritized():
    from icarus_engine.apex.information_gain import rank_compute_jobs
    jobs=[{"id":"huge"},{"id":"small"}]
    out=rank_compute_jobs(jobs,opportunity={"huge":0.2,"small":0.8},uncertainty_reduction={"huge":0.2,"small":0.8},impact={"huge":0.2,"small":0.8},urgency={"huge":0.2,"small":0.8},compute_cost={"huge":1.0,"small":0.2})
    assert out[0]["id"]=="small"


def test_scientific_governor_preserves_unresolved_hypotheses():
    from icarus_engine.apex.information_gain import scientific_governor_snapshot
    out=scientific_governor_snapshot(unresolved_hypotheses=[{"id":"H1"}],anomalies=[],experiments=[],compute_jobs=[])
    assert out["unresolved_hypotheses"]==[{"id":"H1"}]
