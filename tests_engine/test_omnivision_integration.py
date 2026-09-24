from datetime import datetime, timezone

from icarus_engine.advisory import AdvisoryLedger
from icarus_engine.omnivision.candidates import build_candidate
from icarus_engine.omnivision.contracts import WorldEvent
from icarus_engine.omnivision.falsification import placebo_shift_test, walk_forward_correlation
from icarus_engine.omnivision.hypotheses import forge_hypotheses
from icarus_engine.omnivision.ledger_bridge import ledger_observations
from icarus_engine.omnivision.novelty import screen_novelty
from icarus_engine.world_state import Transmission, WorldStateGraph

NOW = 1789560000
DATASET_HASH = "a" * 64


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def event(source="source_a", source_event_id="event-1", revision_id="v1",
          published_at=None, value=2.0):
    host = "source-a.example" if source == "source_a" else "source-b.example"
    return WorldEvent(
        source=source,
        source_event_id=source_event_id,
        revision_id=revision_id,
        source_url=f"https://{host}/{source_event_id}",
        domain="logistics",
        entity="PORT_X",
        asset_ids=("NQ",),
        observed_at=iso(NOW - 100),
        published_at=published_at or iso(NOW - 20),
        values={"shipping_stress": value},
        units={"shipping_stress": "zscore"},
        confidence=0.9,
        timing_basis="published",
    )


def test_authorized_evidence_flows_to_research_only_candidate(tmp_path):
    ledger = AdvisoryLedger(
        tmp_path / "research.sqlite3",
        {
            "source_a": ["source-a.example"],
            "source_b": ["source-b.example"],
        },
    )

    accepted = ledger.ingest_event(event().to_advisory_event(), now=NOW - 10)

    # A later revision may exist in the ledger but cannot leak into an earlier replay.
    ledger.ingest_event(
        event(revision_id="v2", published_at=iso(NOW + 5), value=9.0).to_advisory_event(),
        now=NOW + 6,
    )
    observations = ledger_observations(ledger, "NQ", iso(NOW))
    assert len(observations) == 1
    assert observations[0].value == 2.0
    assert observations[0].evidence_id == accepted["event_id"]

    transmission = Transmission(
        "shipping_stress",
        "inflation_pressure",
        0,
        1,
        0.9,
        0.9,
        "freight-to-goods",
    )
    graph = WorldStateGraph(observations, (transmission,))
    gap = graph.gap_map(["inflation_pressure"], NOW)
    assert gap["latent"]["inflation_pressure"]["evidence_ids"] == [accepted["event_id"]]

    hypothesis = forge_hypotheses(gap, asset="NQ", decision_at=NOW)[0]
    assert hypothesis.evidence_ids == (accepted["event_id"],)

    candidate_series = [(i, float(i % 7)) for i in range(1, 100)]
    existing_series = [(i, float((i * 3) % 11)) for i in range(1, 100)]
    novelty = screen_novelty(candidate_series, {"existing": existing_series}, min_pairs=20)
    assert novelty["status"] == "novel"

    feature_rows = [(i, i, float(i % 7)) for i in range(1, 100)]
    outcome_rows = [(i + 1, i + 1, float(i % 7)) for i in range(1, 100)]
    placebo = placebo_shift_test(
        feature_rows,
        outcome_rows,
        decision_cutoff=100,
        lag_seconds=1,
        placebo_shift_seconds=5,
        min_pairs=20,
    )
    walk = walk_forward_correlation(
        feature_rows,
        outcome_rows,
        cutoffs=(40, 70, 100),
        lag_seconds=1,
        min_pairs=20,
    )
    assert placebo["passed"] is True
    assert walk["passed"] is True

    artifact = build_candidate(
        hypothesis=hypothesis,
        novelty=novelty,
        placebo=placebo,
        walk_forward=walk,
        dataset_hash=DATASET_HASH,
        known_failure_modes=("source_revision", "regime_break"),
        rollback_conditions=("source_invalidated", "walk_forward_sign_breaks"),
    )
    assert artifact["artifact_type"] == "omnivision_research_candidate"
    assert artifact["integration_ready"] is True
    assert artifact["execution_authorized"] is False
    assert artifact["evidence_ids"] == [accepted["event_id"]]


def test_cross_source_disagreement_survives_into_graph(tmp_path):
    ledger = AdvisoryLedger(
        tmp_path / "research.sqlite3",
        {
            "source_a": ["source-a.example"],
            "source_b": ["source-b.example"],
        },
    )
    left = ledger.ingest_event(
        event(source="source_a", source_event_id="a-1", value=1.0).to_advisory_event(),
        now=NOW,
    )
    right = ledger.ingest_event(
        event(source="source_b", source_event_id="b-1", value=-1.0).to_advisory_event(),
        now=NOW,
    )
    graph = WorldStateGraph(ledger_observations(ledger, "NQ", iso(NOW)))
    contradictions = graph.contradictions(NOW)
    assert len(contradictions) == 1
    assert {contradictions[0]["left_id"], contradictions[0]["right_id"]} == {
        left["event_id"],
        right["event_id"],
    }
