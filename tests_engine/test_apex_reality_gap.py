from __future__ import annotations


def test_reality_gap_degrades_current_credibility_even_after_historical_strength():
    from icarus_engine.apex.reality_gap import reality_gap
    from icarus_engine.apex.credibility import credibility_score
    gap=reality_gap(predictions=[1.0,1.0,1.0],observations=[0.0,0.0,0.0],calibration_contract={"scale":1.0})
    assert gap["state"] in {"DEGRADED","INVALID","QUARANTINED"}
    good=credibility_score(calibration=0.95,data_quality=0.9,independence=0.9,reality_gap=0.0)
    bad=credibility_score(calibration=0.95,data_quality=0.9,independence=0.9,reality_gap=gap["gap"])
    assert bad["score"] < good["score"]


def test_reality_gap_missing_evidence_is_unmeasured():
    from icarus_engine.apex.reality_gap import reality_gap
    out=reality_gap(predictions=[],observations=[],calibration_contract={"scale":1.0})
    assert out["state"]=="UNMEASURED" and out["gap"] is None


def test_model_monoculture_reduces_effective_diversity():
    from icarus_engine.apex.credibility import effective_model_diversity
    same=[{"model_id":str(i),"data_families":["same"],"features":["x"],"architecture":"tree","residual_signature":"r"} for i in range(10)]
    out=effective_model_diversity(same)
    assert out["nominal_model_count"]==10
    assert out["effective_model_count"]==1
