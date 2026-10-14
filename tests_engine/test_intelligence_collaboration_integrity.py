from __future__ import annotations

from copy import deepcopy

import pytest

from icarus_engine.intelligence_collaboration import (
    COLLABORATION_PROTOCOL,
    CollaborationIntegrityError,
    WorkRequest,
    build_request_event,
    load_complete_work_history,
    project_work,
    project_work_from_fabric,
)


def _root(*, idempotency_key: str = "integrity-001") -> dict:
    request = WorkRequest(
        requester_principal="requester-agent",
        requester_kind="agent",
        target_kind="principal",
        target_id="worker-agent",
        work_kind="research",
        idempotency_key=idempotency_key,
        objective="Verify the reserved collaboration thread without truncation.",
        priority=3,
        constraints={"asset": "NQ"},
        required_capabilities=("research",),
        reviewer_principals=("reviewer-agent",),
        deadline="2026-10-14T08:00:00Z",
        result_contract={"result_kind": "json", "required_fields": ["conclusion"]},
    )
    normalized = build_request_event(
        request,
        observed_at="2026-10-14T05:00:00Z",
        received_at="2026-10-14T05:00:01Z",
        actor_kind="agent",
        assets=("NQ",),
    ).normalized()
    return {"sequence": 1, "event_id": "root-event", "attention_score": 36.0, **normalized}


def _transition(
    root: dict,
    *,
    sequence: int,
    event_id: str,
    transition: str = "evidence_added",
    expected_head: str = "root-event",
    actor: str = "requester-agent",
    actor_kind: str = "agent",
    data: object | None = None,
    event_type: str = "agent_note",
) -> dict:
    work_id = root["payload"]["work_id"]
    return {
        "sequence": sequence,
        "event_id": event_id,
        "attention_score": 0.0,
        "schema_version": root["schema_version"],
        "event_type": event_type,
        "source": actor,
        "source_kind": actor_kind,
        "channel": "collaboration",
        "thread_key": f"work:{work_id}",
        "title": transition,
        "body": transition,
        "observed_at": f"2026-10-14T05:{sequence % 60:02d}:00Z",
        "received_at": f"2026-10-14T05:{sequence % 60:02d}:01Z",
        "severity": 0,
        "urgency": 0.0,
        "confidence": None,
        "expires_at": None,
        "assets": [],
        "correlation_id": work_id,
        "causation_ids": [expected_head],
        "evidence_ids": [],
        "tags": ["collaboration:v1", f"transition:{transition}"],
        "payload": {
            "protocol": COLLABORATION_PROTOCOL,
            "work_id": work_id,
            "transition": transition,
            "actor_principal": actor,
            "actor_kind": actor_kind,
            "operation_id": f"op-{event_id}",
            "expected_head_event_id": expected_head,
            "data": {} if data is None else data,
        },
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def _record(sequence: int, *, thread_key: str, work_id: str, event_id: str | None = None) -> dict:
    return {
        "sequence": sequence,
        "event_id": event_id or f"event-{sequence}",
        "thread_key": thread_key,
        "correlation_id": work_id,
        "payload": {"protocol": COLLABORATION_PROTOCOL, "work_id": work_id},
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


class FakeFabric:
    def __init__(self, *, thread_records: list[dict], replay_pages: dict[int, list[dict]] | None = None):
        self.thread_records = list(thread_records)
        self.replay_pages = dict(replay_pages or {})
        self.thread_calls: list[tuple[str, int]] = []
        self.replay_calls: list[tuple[int, int]] = []

    def thread(self, thread_key: str, *, limit: int = 100):
        self.thread_calls.append((thread_key, limit))
        return list(self.thread_records[:limit])

    def replay(self, *, after_sequence: int = 0, limit: int = 100):
        self.replay_calls.append((after_sequence, limit))
        page = self.replay_pages.get(after_sequence, [])
        if isinstance(page, Exception):
            raise page
        return list(page[:limit])


def test_mismatched_thread_correlation_or_payload_work_id_fails_closed():
    root = _root()
    work_id = root["payload"]["work_id"]

    wrong_thread = deepcopy(root)
    wrong_thread["thread_key"] = "work:" + ("0" * 64)
    with pytest.raises(CollaborationIntegrityError):
        project_work([wrong_thread])

    wrong_correlation = deepcopy(root)
    wrong_correlation["correlation_id"] = "0" * 64
    with pytest.raises(CollaborationIntegrityError):
        project_work([wrong_correlation])

    wrong_payload = deepcopy(root)
    wrong_payload["payload"]["work_id"] = "0" * 64
    wrong_payload["thread_key"] = f"work:{work_id}"
    with pytest.raises(CollaborationIntegrityError):
        project_work([wrong_payload])


def test_foreign_event_inside_reserved_work_thread_fails_closed():
    root = _root()
    foreign = _transition(root, sequence=2, event_id="foreign")
    foreign["channel"] = "research"
    with pytest.raises(CollaborationIntegrityError, match="foreign|collaboration"):
        project_work([root, foreign])


def test_unsupported_protocol_claiming_reserved_thread_fails_closed():
    root = _root()
    bad = _transition(root, sequence=2, event_id="bad-protocol")
    bad["payload"]["protocol"] = "icarus-collaboration-v999"
    with pytest.raises(CollaborationIntegrityError, match="protocol"):
        project_work([root, bad])


def test_authority_true_in_history_fails_closed():
    root = _root()
    event = _transition(root, sequence=2, event_id="authority")
    event["execution_authorized"] = True
    with pytest.raises(CollaborationIntegrityError, match="authority"):
        project_work([root, event])


def test_malformed_payload_cannot_change_semantic_state():
    root = _root()
    malformed = _transition(root, sequence=2, event_id="malformed", data=["not", "a", "mapping"])
    with pytest.raises(CollaborationIntegrityError, match="data"):
        project_work([root, malformed])


def test_history_under_1000_uses_thread_fast_path_only():
    root = _root()
    work_id = root["payload"]["work_id"]
    records = [_record(i, thread_key=f"work:{work_id}", work_id=work_id) for i in range(1, 4)]
    fabric = FakeFabric(thread_records=records)

    result = load_complete_work_history(fabric, work_id)

    assert [item["sequence"] for item in result] == [1, 2, 3]
    assert fabric.thread_calls == [(f"work:{work_id}", 1000)]
    assert fabric.replay_calls == []


def test_exactly_1000_thread_records_triggers_global_replay_fallback():
    root = _root()
    work_id = root["payload"]["work_id"]
    target = f"work:{work_id}"
    first_page = [_record(i, thread_key=target, work_id=work_id) for i in range(1, 1001)]
    fabric = FakeFabric(
        thread_records=first_page,
        replay_pages={
            0: first_page,
            1000: [],
        },
    )

    result = load_complete_work_history(fabric, work_id)

    assert len(result) == 1000
    assert result[-1]["sequence"] == 1000
    assert fabric.replay_calls == [(0, 1000), (1000, 1000)]


def test_over_1000_history_filters_work_thread_and_preserves_global_sequence_order():
    root = _root()
    work_id = root["payload"]["work_id"]
    target = f"work:{work_id}"
    other_work = "f" * 64
    first_page = [_record(i, thread_key=target, work_id=work_id) for i in range(1, 1001)]
    second_page = [
        _record(1001, thread_key="work:" + other_work, work_id=other_work, event_id="foreign-1001"),
        _record(1002, thread_key=target, work_id=work_id),
        _record(1003, thread_key=target, work_id=work_id),
    ]
    fabric = FakeFabric(
        thread_records=first_page,
        replay_pages={
            0: first_page,
            1000: second_page,
        },
    )

    result = load_complete_work_history(fabric, work_id)

    assert len(result) == 1002
    assert [item["sequence"] for item in result[-3:]] == [1000, 1002, 1003]
    assert all(item["thread_key"] == target for item in result)
    assert fabric.replay_calls == [(0, 1000), (1000, 1000)]


def test_history_retrieval_failure_does_not_return_truncated_projection():
    root = _root()
    work_id = root["payload"]["work_id"]
    target = f"work:{work_id}"
    first_page = [_record(i, thread_key=target, work_id=work_id) for i in range(1, 1001)]
    fabric = FakeFabric(
        thread_records=first_page,
        replay_pages={0: RuntimeError("replay unavailable")},
    )

    with pytest.raises(RuntimeError, match="replay unavailable"):
        load_complete_work_history(fabric, work_id)


def test_project_work_from_fabric_projects_only_complete_history():
    root = _root()
    work_id = root["payload"]["work_id"]
    fabric = FakeFabric(thread_records=[root])

    snapshot = project_work_from_fabric(fabric, work_id)

    assert snapshot.work_id == work_id
    assert snapshot.state == "OPEN"
    assert snapshot.execution_authorized is False
    assert snapshot.production_decision_authorized is False


def test_collaboration_payload_rejects_over_30_kib_before_publish():
    request = WorkRequest(
        requester_principal="requester-agent",
        requester_kind="agent",
        target_kind="principal",
        target_id="worker-agent",
        work_kind="research",
        idempotency_key="oversize",
        objective="Oversize payload test",
        constraints={"blob": "x" * (31 * 1024)},
    )
    with pytest.raises(ValueError, match="30 KiB|payload"):
        build_request_event(
            request,
            observed_at="2026-10-14T05:00:00Z",
            received_at="2026-10-14T05:00:01Z",
            actor_kind="agent",
        )


def test_every_snapshot_and_public_record_hard_false_authority():
    root = _root()
    work_id = root["payload"]["work_id"]
    fabric = FakeFabric(thread_records=[root])

    history = load_complete_work_history(fabric, work_id)
    snapshot = project_work(history)

    assert history[0]["execution_authorized"] is False
    assert history[0]["production_decision_authorized"] is False
    assert snapshot.execution_authorized is False
    assert snapshot.production_decision_authorized is False


def test_nonfinite_transition_material_is_rejected():
    root = _root()
    event = _transition(root, sequence=2, event_id="nan", data={"score": float("nan")})
    with pytest.raises(CollaborationIntegrityError, match="finite JSON"):
        project_work([root, event])
