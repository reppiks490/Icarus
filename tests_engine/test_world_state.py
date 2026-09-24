from icarus_engine.world_state import Observation, Transmission, WorldStateGraph


def obs(source, variable, value, available=100, confidence=1.0):
    return Observation(source, "macro", "GLOBAL", variable, value, 90, available, confidence, f"https://{source}.example/e")


def test_asof_prevents_future_knowledge():
    g = WorldStateGraph([obs("a", "x", 1, available=101)])
    assert g.as_of(100) == ()
    assert len(g.as_of(101)) == 1


def test_latent_is_explicitly_inferred_not_observed():
    g = WorldStateGraph(
        [obs("a", "shipping_stress", 2.0, confidence=0.8)],
        [Transmission("shipping_stress", "inflation_pressure", 0, 1, 0.9, 0.9, "freight-to-goods")]
    )
    result = g.gap_map(["inflation_pressure"], 100)
    latent = result["latent"]["inflation_pressure"]
    assert latent["status"] == "latent_estimate"
    assert latent["estimate"] == 2.0
    assert 0 < latent["confidence"] <= 1
    assert result["execution_authorized"] is False


def test_missing_without_transmission_stays_unresolved():
    g = WorldStateGraph([obs("a", "x", 1)])
    assert g.gap_map(["unknown"], 100)["unresolved"] == ["unknown"]


def test_cross_source_sign_conflict_is_preserved():
    g = WorldStateGraph([obs("a", "risk", 1), obs("b", "risk", -1)])
    conflicts = g.contradictions(100)
    assert len(conflicts) == 1
    assert conflicts[0]["confidence_floor"] == 1.0


def test_bad_time_and_confidence_rejected():
    import pytest
    with pytest.raises(ValueError):
        Observation("a", "d", "e", "v", 1, 100, 99, 1, "p")
    with pytest.raises(ValueError):
        Observation("a", "d", "e", "v", 1, 100, 100, 1.1, "p")
