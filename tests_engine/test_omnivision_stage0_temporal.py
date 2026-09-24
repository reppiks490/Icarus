from datetime import datetime, timezone

from icarus_engine.advisory import AdvisoryLedger
from icarus_engine.omnivision.contracts import WorldEvent, observation_from_event
from icarus_engine.omnivision.ledger_bridge import ledger_observations
from icarus_engine.world_state import WorldStateGraph


def iso(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def world_event(*, revision_id="v1", published_at, value=1.0) -> WorldEvent:
    return WorldEvent(
        source="provider",
        source_event_id="macro-1",
        revision_id=revision_id,
        source_url="https://provider.example/macro-1",
        domain="macro",
        entity="GLOBAL",
        asset_ids=("NQ",),
        observed_at=iso(100),
        published_at=iso(published_at),
        values={"x": value},
        units={"x": "index"},
        confidence=0.9,
        timing_basis="published",
    )


def test_published_event_is_not_available_before_receipt():
    payload = world_event(published_at=105).to_advisory_event()
    stored = {
        **payload,
        "received_at": iso(120),
        "event_id": "a" * 64,
    }

    observation = observation_from_event(stored, "x")

    assert observation.available_at == 120
    graph = WorldStateGraph([observation])
    assert graph.as_of(119) == ()
    assert len(graph.as_of(120)) == 1


def test_subsecond_receipt_never_rounds_availability_backward():
    payload = world_event(published_at=105).to_advisory_event()
    stored = {
        **payload,
        "received_at": datetime.fromtimestamp(120.5, timezone.utc).isoformat(),
        "event_id": "f" * 64,
    }

    observation = observation_from_event(stored, "x")
    graph = WorldStateGraph([observation])

    assert observation.available_at == 121
    assert graph.as_of(120) == ()
    assert len(graph.as_of(121)) == 1


def test_revision_replay_respects_publication_and_receipt(tmp_path):
    ledger = AdvisoryLedger(
        tmp_path / "research.sqlite3",
        {"provider": ["provider.example"]},
    )

    first = ledger.ingest_event(
        world_event(revision_id="v1", published_at=105, value=1.0).to_advisory_event(),
        now=110,
    )
    second = ledger.ingest_event(
        world_event(revision_id="v2", published_at=115, value=2.0).to_advisory_event(),
        now=130,
    )

    before_second_receipt = ledger_observations(ledger, "NQ", iso(129))
    at_second_receipt = ledger_observations(ledger, "NQ", iso(130))

    assert len(before_second_receipt) == 1
    assert before_second_receipt[0].value == 1.0
    assert before_second_receipt[0].evidence_id == first["event_id"]
    assert before_second_receipt[0].available_at == 110

    assert len(at_second_receipt) == 1
    assert at_second_receipt[0].value == 2.0
    assert at_second_receipt[0].evidence_id == second["event_id"]
    assert at_second_receipt[0].available_at == 130
