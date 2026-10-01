import math
import pytest

from icarus_engine.omnivision.contracts import WorldEvent, observation_from_event


def base_event(**changes):
    values = dict(
        source="noaa",
        source_event_id="wx-1",
        revision_id="v1",
        source_url="https://www.noaa.gov/example",
        domain="weather",
        entity="US_MIDWEST",
        asset_ids=("GC",),
        observed_at="2026-09-23T12:00:00Z",
        published_at="2026-09-23T12:05:00Z",
        values={"temperature_anomaly": 1.25},
        units={"temperature_anomaly": "celsius"},
        confidence=0.9,
        timing_basis="published",
    )
    values.update(changes)
    return WorldEvent(**values)


def test_world_event_preserves_domain_entity_and_availability():
    event = base_event()
    payload = event.to_advisory_event()
    assert payload["event_type"] == "world_state"
    assert payload["domain"] == "weather"
    assert payload["entity"] == "US_MIDWEST"
    assert payload["confidence"] == 0.9

    stored = {
        **payload,
        "received_at": "2026-09-23T12:06:00Z",
        "event_id": "a" * 64,
    }
    observation = observation_from_event(stored, "temperature_anomaly")
    assert observation.domain == "weather"
    assert observation.entity == "US_MIDWEST"
    assert observation.value == 1.25
    assert observation.observed_at == 1790164800
    assert observation.available_at == 1790165160
    assert observation.provenance == "https://www.noaa.gov/example"
    assert observation.evidence_id == "a" * 64


def test_first_observed_does_not_invent_publication_time():
    event = base_event(
        source="ais",
        source_event_id="port-1",
        source_url="https://ais.example/event",
        domain="logistics",
        entity="PORT_X",
        asset_ids=("NQ",),
        published_at=None,
        values={"congestion_z": 2.0},
        units={"congestion_z": "zscore"},
        confidence=0.7,
        timing_basis="first_observed",
        quality_flags=("publication_time_unknown",),
    )
    payload = event.to_advisory_event()
    assert payload["published_at"] is None
    stored = {
        **payload,
        "received_at": "2026-09-23T12:07:00Z",
        "event_id": "b" * 64,
    }
    observation = observation_from_event(stored, "congestion_z")
    assert observation.available_at == 1790165220


@pytest.mark.parametrize("changes", [
    {"domain": ""},
    {"entity": ""},
    {"confidence": -0.01},
    {"confidence": 1.01},
    {"confidence": True},
    {"values": {"x": 1.0}, "units": {}},
    {"values": {"x": float("nan")}, "units": {"x": "zscore"}},
    {"timing_basis": "guessed"},
    {"published_at": None, "timing_basis": "published"},
    {"published_at": "2026-09-23T12:05:00", "timing_basis": "published"},
])
def test_world_event_rejects_invalid_contract(changes):
    with pytest.raises(ValueError):
        base_event(**changes)


def test_observation_rejects_wrong_event_type_or_variable():
    payload = base_event().to_advisory_event()
    stored = {**payload, "received_at": "2026-09-23T12:06:00Z", "event_id": "c" * 64}
    with pytest.raises(ValueError):
        observation_from_event({**stored, "event_type": "macro"}, "temperature_anomaly")
    with pytest.raises(ValueError):
        observation_from_event(stored, "missing")


def test_world_event_rejects_nonfinite_values():
    with pytest.raises(ValueError):
        base_event(values={"x": math.inf}, units={"x": "zscore"})
