from __future__ import annotations

import pytest

from icarus_engine.ascendancy.unknowns import (
    UnknownUnknownLab,
    normalize_unknown_event,
)


def _event(
    *,
    source_engine="apex-omega",
    episode_id="ep-001",
    observed_at="2026-10-02T06:00:00Z",
    received_at="2026-10-02T06:00:01Z",
    magnitude=0.82,
    **overrides,
):
    body = {
        "source_engine": source_engine,
        "source_kind": "native",
        "source_repo": "reppiks490/Icarus",
        "source_commit": "e" * 40,
        "asset": "NQ",
        "horizon_seconds": 300,
        "observed_at": observed_at,
        "received_at": received_at,
        "episode_id": episode_id,
        "regime": "RTH_HIGH_VOL",
        "residual_family": "synchronized_reversal_underprediction",
        "residual_magnitude": magnitude,
        "evidence_class": "derived",
        "evidence_ids": [f"evidence:{source_engine}:{episode_id}"],
        "failed_systems": ["chronofold", "psi", "apex-omega"],
        "phenomenon_descriptors": {
            "session": "RTH",
            "volatility_band": "HIGH",
        },
        "context": {
            "reality_gap_state": "DEGRADED",
            "nullspace_route": "unresolved",
        },
        "cause": None,
    }
    body.update(overrides)
    return body


def test_unknown_event_is_deterministic_causal_and_unexplained():
    one = normalize_unknown_event(_event())
    two = normalize_unknown_event(_event())
    assert one["event_id"] == two["event_id"]
    assert len(one["event_id"]) == 64
    assert len(one["phenomenon_signature"]) == 64
    assert one["cause"] is None
    assert one["execution_authorized"] is False
    assert one["production_decision_authorized"] is False


def test_unknown_event_rejects_backwards_time_and_fabricated_cause():
    with pytest.raises(ValueError, match="received_at cannot precede observed_at"):
        normalize_unknown_event(_event(
            observed_at="2026-10-02T06:00:02Z",
            received_at="2026-10-02T06:00:01Z",
        ))

    with pytest.raises(ValueError, match="cause must remain null"):
        normalize_unknown_event(_event(cause="dealer hedging"))


def test_unknown_event_requires_exact_provenance_and_evidence_class():
    with pytest.raises(ValueError, match="40-character Git SHA"):
        normalize_unknown_event(_event(source_commit="short"))

    with pytest.raises(ValueError, match="evidence_class"):
        normalize_unknown_event(_event(evidence_class="magic"))


def test_same_phenomenon_can_arrive_from_different_engines():
    apex = normalize_unknown_event(_event(source_engine="apex-omega"))
    pantheon = normalize_unknown_event(_event(source_engine="pantheon", episode_id="ep-002"))
    assert apex["event_id"] != pantheon["event_id"]
    assert apex["phenomenon_signature"] == pantheon["phenomenon_signature"]


def test_lab_is_wal_idempotent_and_does_not_fake_replication(tmp_path):
    lab = UnknownUnknownLab(tmp_path)
    event = _event()
    one = lab.record_event(event)
    two = lab.record_event(event)

    assert lab.journal_mode == "wal"
    assert one["idempotent"] is False
    assert two["idempotent"] is True

    snap = lab.snapshot(min_independent_episodes=3)
    assert snap["event_count"] == 1
    assert snap["phenomenon_count"] == 1
    phenomenon = snap["phenomena"][0]
    assert phenomenon["independent_episode_count"] == 1
    assert phenomenon["status"] == "EARLY"
    assert phenomenon["cause"] is None


def test_replication_requires_independent_episodes_not_duplicate_engines(tmp_path):
    lab = UnknownUnknownLab(tmp_path)
    lab.record_event(_event(source_engine="apex-omega", episode_id="ep-001"))
    lab.record_event(_event(source_engine="pantheon", episode_id="ep-001"))
    lab.record_event(_event(source_engine="chronofold", episode_id="ep-001"))

    first = lab.snapshot(min_independent_episodes=3)["phenomena"][0]
    assert first["event_count"] == 3
    assert first["independent_episode_count"] == 1
    assert first["status"] == "EARLY"

    lab.record_event(_event(source_engine="apex-omega", episode_id="ep-002", observed_at="2026-10-02T07:00:00Z", received_at="2026-10-02T07:00:01Z"))
    second = lab.snapshot(min_independent_episodes=3)["phenomena"][0]
    assert second["independent_episode_count"] == 2
    assert second["status"] == "STRUCTURED_CANDIDATE"

    lab.record_event(_event(source_engine="psi", episode_id="ep-003", observed_at="2026-10-02T08:00:00Z", received_at="2026-10-02T08:00:01Z"))
    replicated = lab.snapshot(min_independent_episodes=3)["phenomena"][0]
    assert replicated["independent_episode_count"] == 3
    assert replicated["status"] == "REPLICATED"
    assert set(replicated["source_engines"]) >= {"apex-omega", "pantheon", "chronofold", "psi"}


def test_phenomenon_tracks_scope_failure_set_and_magnitude_statistics(tmp_path):
    lab = UnknownUnknownLab(tmp_path)
    lab.record_event(_event(episode_id="ep-001", magnitude=0.4))
    lab.record_event(_event(
        source_engine="pantheon",
        episode_id="ep-002",
        magnitude=0.8,
        observed_at="2026-10-02T07:00:00Z",
        received_at="2026-10-02T07:00:01Z",
    ))
    p = lab.snapshot()["phenomena"][0]
    assert p["assets"] == ["NQ"]
    assert p["regimes"] == ["RTH_HIGH_VOL"]
    assert p["horizons_seconds"] == [300]
    assert p["failed_systems"] == ["apex-omega", "chronofold", "psi"]
    assert p["mean_residual_magnitude"] == pytest.approx(0.6)
    assert p["median_residual_magnitude"] == pytest.approx(0.6)
    assert p["first_seen"] == "2026-10-02T06:00:00Z"
    assert p["last_seen"] == "2026-10-02T07:00:00Z"


def test_failed_explanations_are_append_only_and_do_not_assign_cause(tmp_path):
    lab = UnknownUnknownLab(tmp_path)
    saved = lab.record_event(_event())
    signature = saved["event"]["phenomenon_signature"]

    first = lab.record_explanation_test({
        "phenomenon_signature": signature,
        "explanation": "The residual is only a volatility scaling artifact.",
        "status": "FAILED",
        "evidence": ["ablation:vol-normalized:negative"],
        "source_repo": "reppiks490/Icarus",
        "source_commit": "f" * 40,
    })
    second = lab.record_explanation_test({
        "phenomenon_signature": signature,
        "explanation": "The residual is only a volatility scaling artifact.",
        "status": "FAILED",
        "evidence": ["ablation:vol-normalized:negative"],
        "source_repo": "reppiks490/Icarus",
        "source_commit": "f" * 40,
    })
    assert first["idempotent"] is False
    assert second["idempotent"] is True

    p = lab.snapshot()["phenomena"][0]
    assert p["cause"] is None
    assert p["failed_explanations"] == [
        "The residual is only a volatility scaling artifact."
    ]


def test_candidate_link_is_research_only_and_preserves_unexplained_cause(tmp_path):
    lab = UnknownUnknownLab(tmp_path)
    saved = lab.record_event(_event())
    signature = saved["event"]["phenomenon_signature"]
    candidate_id = "a" * 64

    linked = lab.link_candidate(signature, candidate_id, "Foundry candidate generated from replicated residual")
    assert linked["candidate_id"] == candidate_id
    assert linked["execution_authorized"] is False
    assert linked["production_decision_authorized"] is False

    p = lab.snapshot()["phenomena"][0]
    assert p["candidate_ids"] == [candidate_id]
    assert p["cause"] is None


def test_raw_unavailable_evidence_cannot_count_as_confirmation(tmp_path):
    lab = UnknownUnknownLab(tmp_path)
    lab.record_event(_event(
        evidence_class="unavailable",
        evidence_ids=[],
        source_engine="external-lens",
        source_kind="foreign_lens",
    ))
    p = lab.snapshot(min_independent_episodes=1)["phenomena"][0]
    assert p["confirming_event_count"] == 0
    assert p["status"] == "UNMEASURED"


def test_different_descriptors_do_not_collapse_into_same_phenomenon(tmp_path):
    lab = UnknownUnknownLab(tmp_path)
    lab.record_event(_event())
    changed = _event(
        episode_id="ep-002",
        observed_at="2026-10-02T07:00:00Z",
        received_at="2026-10-02T07:00:01Z",
        phenomenon_descriptors={"session": "ETH", "volatility_band": "HIGH"},
    )
    lab.record_event(changed)
    assert lab.snapshot()["phenomenon_count"] == 2
