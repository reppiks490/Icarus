from __future__ import annotations

import pytest


def _evidence(record_id="raw-1", *, deps=()):
    return {
        "kind": "observed" if not deps else "derived",
        "subject": "NQ:pressure",
        "value": {"pressure": -0.4},
        "source": {
            "subsystem": "argus",
            "source_repo": "reppiks490/Icarus",
            "source_commit": "a" * 40,
            "source_record_id": record_id,
        },
        "observed_at": "2026-10-01T14:00:00Z",
        "received_at": "2026-10-01T14:00:01Z",
        "calculated_at": "2026-10-01T14:00:01Z",
        "valid_from": "2026-10-01T14:00:00Z",
        "valid_until": None,
        "confidence": 0.8,
        "quality": 0.9,
        "dependencies": list(deps),
        "contradictions": [],
        "falsifiers": ["source correction"],
    }


def _belief(*, falsifiers=None):
    return {
        "claim": "downside pressure is elevated",
        "scope": {"asset": "NQ", "horizon_seconds": 300},
        "source_revision": "b" * 40,
        "assumptions": ["market open"],
        "contradictions": ["liquidity replenishment"],
        "falsifiers": ["rapid reclaim"] if falsifiers is None else falsifiers,
        "nominal_confidence": 0.72,
        "epistemic_uncertainty": 0.35,
        "aleatoric_uncertainty": 0.45,
    }


class Clock:
    def __init__(self, value): self.value = value
    def __call__(self): return self.value


def _setup(tmp_path):
    from icarus_engine.apex.ancestry import EvidenceAncestry
    from icarus_engine.apex.beliefs import BeliefLedger
    from icarus_engine.apex.store import ApexStore
    store = ApexStore(tmp_path)
    ancestry = EvidenceAncestry()
    rec = store.record_evidence(_evidence())["evidence"]
    ancestry.add(rec)
    clock = Clock("2026-10-01T14:01:00Z")
    ledger = BeliefLedger(store, ancestry=ancestry, clock=clock)
    return store, ancestry, ledger, clock, rec


def test_belief_transition_history_is_append_only(tmp_path):
    store, ancestry, ledger, clock, rec = _setup(tmp_path)
    proposed = ledger.propose(_belief())
    bid = proposed["belief"]["belief_id"]
    clock.value = "2026-10-01T14:02:00Z"
    ledger.transition(bid, "supported", evidence_ids=[rec["evidence_id"]], reason="independent evidence")
    clock.value = "2026-10-01T14:03:00Z"
    ledger.transition(bid, "contradicted", evidence_ids=[rec["evidence_id"]], reason="reclaim observed")
    rows = store._conn.execute("SELECT state FROM belief_events WHERE belief_id=? ORDER BY event_ts", (bid,)).fetchall()
    assert [r[0] for r in rows] == ["proposed", "supported", "contradicted"]
    assert ledger.as_of("2026-10-01T14:03:00Z")[0]["state"] == "contradicted"


def test_supported_belief_requires_complete_evidence_ancestry_and_falsifier(tmp_path):
    store, ancestry, ledger, clock, rec = _setup(tmp_path)
    bid = ledger.propose(_belief(falsifiers=[]))["belief"]["belief_id"]
    clock.value = "2026-10-01T14:02:00Z"
    with pytest.raises(ValueError, match="falsifier"):
        ledger.transition(bid, "supported", evidence_ids=[rec["evidence_id"]], reason="not enough")


def test_incomplete_proof_packet_cannot_transition_to_supported(tmp_path):
    from icarus_engine.apex.ancestry import EvidenceAncestry
    from icarus_engine.apex.beliefs import BeliefLedger
    from icarus_engine.apex.store import ApexStore
    store = ApexStore(tmp_path)
    ancestry = EvidenceAncestry()
    missing_dep_record = store.record_evidence(_evidence("derived", deps=["missing-root"]))["evidence"]
    ancestry.add(missing_dep_record)
    clock = Clock("2026-10-01T14:01:00Z")
    ledger = BeliefLedger(store, ancestry=ancestry, clock=clock)
    bid = ledger.propose(_belief())["belief"]["belief_id"]
    clock.value = "2026-10-01T14:02:00Z"
    with pytest.raises(ValueError, match="ancestry"):
        ledger.transition(bid, "supported", evidence_ids=[missing_dep_record["evidence_id"]], reason="bad proof")


def test_belief_as_of_does_not_leak_future_transition(tmp_path):
    store, ancestry, ledger, clock, rec = _setup(tmp_path)
    bid = ledger.propose(_belief())["belief"]["belief_id"]
    clock.value = "2026-10-01T15:00:00Z"
    ledger.transition(bid, "supported", evidence_ids=[rec["evidence_id"]], reason="later evidence")
    assert ledger.as_of("2026-10-01T14:30:00Z")[0]["state"] == "proposed"
    assert ledger.as_of("2026-10-01T15:00:00Z")[0]["state"] == "supported"


def test_proof_packet_preserves_contradictions_and_false_authority(tmp_path):
    store, ancestry, ledger, clock, rec = _setup(tmp_path)
    bid = ledger.propose(_belief())["belief"]["belief_id"]
    clock.value = "2026-10-01T14:02:00Z"
    ledger.transition(bid, "supported", evidence_ids=[rec["evidence_id"]], reason="qualified evidence")
    packet = ledger.proof_packet(bid, as_of="2026-10-01T14:02:00Z")
    assert packet["contradictions"] == ["liquidity replenishment"]
    assert packet["falsifiers"] == ["rapid reclaim"]
    assert packet["evidence_ids"] == [rec["evidence_id"]]
    assert packet["effective_support"]["integrity_ok"] is True
    assert packet["execution_authorized"] is False
    assert packet["production_decision_authorized"] is False
