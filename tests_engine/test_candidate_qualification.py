from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from icarus_engine.candidate_qualification import (
    QualificationLedger,
    REQUIRED_GATES,
)


def candidate():
    return {
        "candidate_id": "NQ:fixture",
        "source_repo": "reppiks490/Icarus",
        "source_commit": "a" * 40,
        "regimes": ["STRONG"],
        "metrics": {"validation_score": 0.91},
        "validation": {gate: None for gate in REQUIRED_GATES},
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def receipt(gate, *, passed=True, reviewer_role="daedalus", reviewer_id=None, independent=False, evidence_hash=None):
    return {
        "candidate_id": "NQ:fixture",
        "source_repo": "reppiks490/Icarus",
        "source_commit": "a" * 40,
        "gate": gate,
        "passed": passed,
        "reviewer_role": reviewer_role,
        "reviewer_id": reviewer_id or f"{reviewer_role}-reviewer",
        "independent": independent,
        "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "evidence_hash": evidence_hash or ("b" * 64),
        "evidence": [f"{gate} deterministic fixture evidence"],
    }


def fill_all(ledger):
    for i, gate in enumerate(REQUIRED_GATES):
        if gate == "independent_verification":
            ledger.record(receipt(
                gate,
                reviewer_role="daedalus",
                reviewer_id="daedalus-1",
                independent=True,
                evidence_hash=("%064x" % (i + 1))[-64:],
            ))
            ledger.record(receipt(
                gate,
                reviewer_role="aegis",
                reviewer_id="aegis-1",
                independent=True,
                evidence_hash=("%064x" % (i + 101))[-64:],
            ))
        else:
            ledger.record(receipt(
                gate,
                evidence_hash=("%064x" % (i + 1))[-64:],
            ))


def test_candidate_fails_closed_until_every_gate_is_proven(tmp_path):
    ledger = QualificationLedger(tmp_path)
    snap = ledger.snapshot(candidate())
    assert snap["qualified_shadow_ready"] is False
    assert set(snap["blockers"]) == set(REQUIRED_GATES)

    fill_all(ledger)
    snap = ledger.snapshot(candidate())
    assert snap["qualified_shadow_ready"] is True
    assert snap["blockers"] == []
    assert len(snap["independent_reviewers"]) == 2
    assert snap["execution_authorized"] is False
    assert snap["production_decision_authorized"] is False


def test_qualification_event_is_shadow_only_and_exact_revision_bound(tmp_path):
    ledger = QualificationLedger(tmp_path)
    fill_all(ledger)
    event = ledger.qualification_event(candidate())
    assert event["stage"] == "qualified_shadow"
    assert all(event["validation"][gate] is True for gate in REQUIRED_GATES)
    assert event["source_commit"] == "a" * 40
    assert event["details"]["execution_authorized"] is False
    assert event["details"]["production_decision_authorized"] is False


def test_latest_failure_receipt_revokes_gate(tmp_path):
    ledger = QualificationLedger(tmp_path)
    fill_all(ledger)
    ledger.record(receipt("ood_drift", passed=False, evidence_hash="f" * 64))
    snap = ledger.snapshot(candidate())
    assert snap["qualified_shadow_ready"] is False
    assert "ood_drift" in snap["blockers"]


def test_later_repair_receipt_can_restore_revoked_gate(tmp_path):
    ledger = QualificationLedger(tmp_path)
    fill_all(ledger)
    ledger.record(receipt("ood_drift", passed=False, evidence_hash="e" * 64))
    ledger.record(receipt("ood_drift", passed=True, evidence_hash="d" * 64))
    assert ledger.snapshot(candidate())["qualified_shadow_ready"] is True


def test_independent_verification_requires_two_distinct_independent_reviewers(tmp_path):
    ledger = QualificationLedger(tmp_path)
    for gate in REQUIRED_GATES:
        if gate != "independent_verification":
            ledger.record(receipt(gate, evidence_hash=("%064x" % (len(gate) + 200))[-64:]))
    ledger.record(receipt(
        "independent_verification",
        reviewer_role="daedalus",
        reviewer_id="same",
        independent=True,
        evidence_hash="1" * 64,
    ))
    snap = ledger.snapshot(candidate())
    assert snap["qualified_shadow_ready"] is False
    assert "independent_verification" in snap["blockers"]

    ledger.record(receipt(
        "independent_verification",
        reviewer_role="aegis",
        reviewer_id="other",
        independent=True,
        evidence_hash="2" * 64,
    ))
    assert ledger.snapshot(candidate())["qualified_shadow_ready"] is True


def test_independent_gate_rejects_non_independent_or_untrusted_role(tmp_path):
    ledger = QualificationLedger(tmp_path)
    with pytest.raises(ValueError, match="independent"):
        ledger.record(receipt(
            "independent_verification",
            reviewer_role="daedalus",
            independent=False,
        ))
    with pytest.raises(ValueError, match="reviewer_role"):
        ledger.record(receipt(
            "causal_time",
            reviewer_role="unknown",
        ))


def test_future_receipt_time_is_rejected(tmp_path):
    ledger = QualificationLedger(tmp_path)
    body = receipt("causal_time")
    body["observed_at"] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    with pytest.raises(ValueError, match="future"):
        ledger.record(body)


def test_receipts_are_idempotent_and_hash_chained(tmp_path):
    ledger = QualificationLedger(tmp_path)
    body = receipt("causal_time")
    first = ledger.record(body)
    second = ledger.record(body)
    assert first["idempotent"] is False
    assert second["idempotent"] is True

    lines = (tmp_path / "audit" / "candidate_qualification.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["prev_hash"] == "GENESIS"
    assert row["record_hash"]


def test_tampered_ledger_blocks_qualification_and_future_append(tmp_path):
    ledger = QualificationLedger(tmp_path)
    ledger.record(receipt("causal_time"))
    path = tmp_path / "audit" / "candidate_qualification.jsonl"
    row = json.loads(path.read_text(encoding="utf-8"))
    row["passed"] = False
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    snap = ledger.snapshot(candidate())
    assert snap["qualified_shadow_ready"] is False
    assert snap["ledger_errors"]
    with pytest.raises(RuntimeError, match="integrity"):
        ledger.record(receipt("provenance", evidence_hash="c" * 64))


def test_receipt_for_other_revision_does_not_qualify_candidate(tmp_path):
    ledger = QualificationLedger(tmp_path)
    body = receipt("causal_time")
    body["source_commit"] = "c" * 40
    ledger.record(body)
    snap = ledger.snapshot(candidate())
    assert snap["receipt_count"] == 0
    assert "causal_time" in snap["blockers"]
