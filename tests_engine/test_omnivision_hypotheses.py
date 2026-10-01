from icarus_engine.omnivision.hypotheses import Hypothesis, forge_hypotheses


def test_gap_forge_is_deterministic_and_hash_bound():
    gap = {
        "latent": {
            "inflation_pressure": {
                "status": "latent_estimate",
                "estimate": 1.2,
                "confidence": 0.6,
                "evidence_ids": ["a" * 64],
                "mechanisms": ["freight-to-goods"],
            }
        },
        "unresolved": [],
        "contradictions": [],
        "execution_authorized": False,
    }
    left = forge_hypotheses(gap, asset="NQ", decision_at=100)
    right = forge_hypotheses(gap, asset="NQ", decision_at=100)
    assert left == right
    assert len(left) == 1
    assert left[0].kind == "latent_gap"
    assert left[0].target == "inflation_pressure"
    assert left[0].hypothesis_id == right[0].hypothesis_id
    assert left[0].execution_authorized is False


def test_unresolved_gap_without_evidence_does_not_become_hypothesis():
    gap = {
        "latent": {},
        "unresolved": ["mystery"],
        "contradictions": [],
        "execution_authorized": False,
    }
    assert forge_hypotheses(gap, asset="NQ", decision_at=100) == ()


def test_contradiction_hypothesis_binds_both_sources():
    gap = {
        "latent": {},
        "unresolved": [],
        "contradictions": [{
            "entity": "PORT_X",
            "variable": "shipping_stress",
            "left_id": "a" * 64,
            "right_id": "b" * 64,
            "delta": 2.0,
            "confidence_floor": 0.8,
        }],
        "execution_authorized": False,
    }
    items = forge_hypotheses(gap, asset="NQ", decision_at=100)
    assert len(items) == 1
    item = items[0]
    assert item.kind == "contradiction"
    assert item.evidence_ids == ("a" * 64, "b" * 64)
    assert item.falsification_rules == (
        "source_disagreement_must_resolve_or_predict_distinct_outcomes",
    )
    assert item.execution_authorized is False


def test_hypothesis_rejects_bad_identity_or_negative_time():
    import pytest
    with pytest.raises(ValueError):
        Hypothesis(
            hypothesis_id="a" * 64,
            kind="latent_gap",
            asset="",
            target="x",
            mechanism="m",
            expected_lag_seconds=0,
            horizon_seconds=0,
            required_variables=("x",),
            evidence_ids=("b" * 64,),
            falsification_rules=("walk_forward_must_hold",),
            eligible_regimes=("all",),
            decision_at=1,
        )
    with pytest.raises(ValueError):
        forge_hypotheses({
            "latent": {},
            "unresolved": [],
            "contradictions": [],
            "execution_authorized": False,
        }, asset="NQ", decision_at=-1)
