from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from icarus_engine.qualification_receipts import QualificationReceiptStore


GATES = ("causal_time", "provenance", "independent_verification")


def _time(i=0):
    return (datetime.now(timezone.utc) - timedelta(minutes=5) + timedelta(seconds=i)).isoformat().replace("+00:00", "Z")


def _receipt(gate, *, passed=True, verifier_commit="b"*40, i=0):
    return {
        "candidate_id": "nq-trend-v1",
        "candidate_source_repo": "reppiks490/Icarus",
        "candidate_source_commit": "a" * 40,
        "gate": gate,
        "passed": passed,
        "verifier_id": "daedalus",
        "verifier_source_repo": "reppiks490/Icarus",
        "verifier_source_commit": verifier_commit,
        "observed_at": _time(i),
        "evidence_hash": ("%064x" % (100 + i))[-64:],
    }


def test_receipts_are_idempotent_for_exact_semantic_payload(tmp_path):
    store = QualificationReceiptStore(tmp_path, GATES)
    body = _receipt("causal_time")
    first = store.record(body)
    second = store.record(body)
    assert first["idempotent"] is False
    assert second["idempotent"] is True


def test_latest_negative_receipt_reopens_gate(tmp_path):
    store = QualificationReceiptStore(tmp_path, GATES)
    store.record(_receipt("causal_time", passed=True, i=0))
    store.record(_receipt("causal_time", passed=False, i=1))
    state = store.candidate_status("nq-trend-v1", "reppiks490/Icarus", "a"*40)
    assert state["validation"]["causal_time"] is False
    assert "causal_time gate not verified" in state["blockers"]


def test_all_required_gates_produce_qualified_shadow_readiness_only(tmp_path):
    store = QualificationReceiptStore(tmp_path, GATES)
    store.record(_receipt("causal_time", i=0))
    store.record(_receipt("provenance", i=1))
    store.record(_receipt("independent_verification", i=2))
    state = store.candidate_status("nq-trend-v1", "reppiks490/Icarus", "a"*40)
    assert state["qualification_ready"] is True
    assert state["recommended_stage"] == "qualified_shadow"
    assert state["blockers"] == []
    assert state["execution_authorized"] is False
    assert state["production_decision_authorized"] is False


def test_independent_gate_rejects_same_exact_candidate_revision(tmp_path):
    store = QualificationReceiptStore(tmp_path, GATES)
    with pytest.raises(ValueError, match="exact source revision"):
        store.record(_receipt("independent_verification", verifier_commit="a"*40))


def test_candidate_revision_scopes_do_not_mix(tmp_path):
    store = QualificationReceiptStore(tmp_path, GATES)
    store.record(_receipt("causal_time"))
    other = _receipt("provenance")
    other["candidate_source_commit"] = "c" * 40
    store.record(other)
    first = store.candidate_status("nq-trend-v1", "reppiks490/Icarus", "a"*40)
    second = store.candidate_status("nq-trend-v1", "reppiks490/Icarus", "c"*40)
    assert first["validation"]["causal_time"] is True
    assert first["validation"]["provenance"] is False
    assert second["validation"]["causal_time"] is False
    assert second["validation"]["provenance"] is True
