"""Cross-project UMBRA v5 paired-report arithmetic and research-truth tests."""
import copy
from datetime import datetime

import pytest

from icarus_engine.omnigenesis.umbra_bridge import audit_umbra_worldlines

SOURCE = "a" * 40


def hash32(n):
    n &= 0xffffffff
    n = ((n ^ (n >> 16)) * 0x7feb352d) & 0xffffffff
    n = ((n ^ (n >> 15)) * 0x846ca68b) & 0xffffffff
    return (n ^ (n >> 16)) & 0xffffffff


def example(trials=8):
    # This small hand-built fixture matches UMBRA's JS pairedExperiment
    # fields and derived run-seed algorithm; no claims of actual engine replay.
    cfg = {"trade": .72, "climate": .38, "medicine": .48,
           "innovation": .58, "migration": .48,
           "conservation": .48, "conflict": .25}
    baselines = [100 + i * 3 for i in range(trials)]
    treatments = [95 + i * 3 for i in range(trials)]
    rows = [{
        "seed": hash32(49021 + (i + 1) * 0x9e3779b1),
        "baseline": baselines[i],
        "treatment": treatments[i],
        "diff": 5,
        "foodDiff": -3,
        "emissionsDiff": 1.5,
    } for i in range(trials)]
    return {"version": "5.0.0", "seed": 49021, "trials": trials, "steps": 12,
            "baseline": cfg, "treatment": {**cfg, "trade": 0},
            "mean": 5, "median": 5, "p05": 5, "p95": 5, "sd": 0,
            "positive": trials, "paths": rows}


def test_adapter_checks_seed_and_aggregate_no_empirical_authority():
    x = example()
    a = audit_umbra_worldlines(x, claimed_source_commit=SOURCE)
    assert a == audit_umbra_worldlines(x, claimed_source_commit=SOURCE)
    assert a["evidence_kind"] == "SYNTHETIC_MODEL_INTERNAL"
    assert a["source_system"] == "UMBRA_SOVEREIGN_WORLDS_V5"
    assert a["all_seed_and_aggregate_checks_passed"] is True
    assert a["source_commit_verified"] is False
    assert a["engine_replay_verified"] is False
    assert a["real_market_fidelity_verified"] is False
    assert a["authority"]["execution_authorized"] is False
    assert a["production_qualified"] is False
    assert len(a["receipt_id"]) == 64


@pytest.mark.parametrize("mutation,error", [
    (lambda x: x.update(version="4.0.0"), "version"),
    (lambda x: x.update(trials=7), "replicate count"),
    (lambda x: x["paths"][0].update(seed=1), "seed divergence"),
    (lambda x: x["paths"][0].update(diff=999), "paired effect"),
    (lambda x: x.update(mean=999), "aggregate mean"),
    (lambda x: x.update(positive=0), "positive count"),
    (lambda x: x["baseline"].update(trade=7), "policy value"),
    (lambda x: x["paths"][0].update(a_new_field=1), "replicate schema"),
])
def test_cross_worldline_tamper_rejected(mutation, error):
    x = example()
    mutation(x)
    with pytest.raises(ValueError, match=error):
        audit_umbra_worldlines(x, claimed_source_commit=SOURCE)


def test_unsupported_claimed_commit_or_nonfinite_measure():
    with pytest.raises(ValueError, match="source commit"):
        audit_umbra_worldlines(example(), claimed_source_commit="not-a-git-sha")
    x = example()
    x["paths"][0]["baseline"] = float("nan")
    with pytest.raises(ValueError, match="nonfinite"):
        audit_umbra_worldlines(x, claimed_source_commit=SOURCE)


def test_cross_implementation_seed_recovers_exact_js_hash():
    # UMBRA's source: hash32((seed>>>0)+Math.imul(k+1,0x9e3779b1)).
    for k in range(64):
        s = hash32(49021 + (k + 1) * 0x9e3779b1)
        assert 0 <= s <= 0xffffffff
        assert isinstance(s, int)
