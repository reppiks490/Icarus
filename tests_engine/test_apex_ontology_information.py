from __future__ import annotations


def test_latent_candidate_requires_independent_episodes_and_stays_anonymous():
    from icarus_engine.apex.unknown_force import latent_candidate
    one=[{"episode_id":"ep1","event_id":str(i),"residual_signature":"sig","unexplained_fraction":0.8} for i in range(5)]
    early=latent_candidate(one,min_independent_episodes=3)
    assert early["status"]=="EARLY"
    rows=one+[{"episode_id":"ep2","event_id":"x","residual_signature":"sig","unexplained_fraction":0.7},{"episode_id":"ep3","event_id":"y","residual_signature":"sig","unexplained_fraction":0.75}]
    ready=latent_candidate(rows,min_independent_episodes=3)
    assert ready["status"]=="REPLICATED"
    assert ready["interpretation"] is None and ready["latent_id"].startswith("latent_")


def test_information_wave_is_depth_bounded_and_keeps_contradictions():
    from icarus_engine.apex.causality import information_wave
    edges=[{"source":"rates","target":"fx","confidence":0.8,"status":"temporally_supported","contradictions":[]},{"source":"fx","target":"equities","confidence":0.7,"status":"temporally_supported","contradictions":["credit"]},{"source":"equities","target":"rates","confidence":0.5,"status":"temporally_supported","contradictions":[]}]
    out=information_wave(edges,origin="rates",as_of="2026-10-01T14:00:00Z",max_depth=2)
    assert max(x["depth"] for x in out["paths"])<=2
    assert any("credit" in x["contradictions"] for x in out["paths"])
