from datetime import datetime, timezone

from icarus_engine.advisory import AdvisoryLedger
from icarus_engine.omnivision.ledger_bridge import ledger_observations

NOW = 1789560000.0


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def world_event(source="a", source_event_id="event-1", revision_id="v1",
                published_at=None, value=1.0):
    return {
        "schema_version": 1,
        "source": source,
        "source_event_id": source_event_id,
        "revision_id": revision_id,
        "source_url": f"https://{source}.example/event",
        "event_type": "world_state",
        "asset_ids": ["NQ"],
        "instrument_id": "PORT_X",
        "observed_at": iso(NOW - 100),
        "published_at": published_at or iso(NOW - 20),
        "values": {"shipping_stress": value},
        "units": {"shipping_stress": "zscore"},
        "domain": "logistics",
        "entity": "PORT_X",
        "confidence": 0.9,
    }


def test_bridge_projects_only_evidence_available_as_of(tmp_path):
    ledger = AdvisoryLedger(tmp_path / "research.sqlite3", {"a": ["a.example"]})
    old = ledger.ingest_event(world_event(), now=NOW - 10)
    ledger.ingest_event(
        world_event(revision_id="v2", published_at=iso(NOW + 5), value=2.0),
        now=NOW + 6,
    )

    rows = ledger_observations(ledger, "NQ", iso(NOW))
    assert len(rows) == 1
    assert rows[0].value == 1.0
    assert rows[0].provenance == old["source_url"]


def test_bridge_preserves_cross_source_contradiction(tmp_path):
    ledger = AdvisoryLedger(
        tmp_path / "research.sqlite3",
        {"a": ["a.example"], "b": ["b.example"]},
    )
    ledger.ingest_event(world_event(source="a", source_event_id="a-1", value=1.0), now=NOW)
    ledger.ingest_event(world_event(source="b", source_event_id="b-1", value=-1.0), now=NOW)

    rows = ledger_observations(ledger, "NQ", iso(NOW))
    assert sorted(row.value for row in rows) == [-1.0, 1.0]
    assert {row.source for row in rows} == {"a", "b"}


def test_bridge_ignores_non_world_state_events(tmp_path):
    ledger = AdvisoryLedger(tmp_path / "research.sqlite3", {"a": ["a.example"]})
    macro = world_event()
    macro.pop("domain")
    macro.pop("entity")
    macro.pop("confidence")
    macro["event_type"] = "macro"
    ledger.ingest_event(macro, now=NOW)
    assert ledger_observations(ledger, "NQ", iso(NOW)) == ()
