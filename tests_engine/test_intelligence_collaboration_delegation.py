from __future__ import annotations

import pytest

from icarus_engine.intelligence_collaboration import (
    IntelligenceCollaboration,
    TransitionRequest,
    WorkRequest,
)
from icarus_engine.intelligence_fabric import IntelligenceFabric


T0 = "2026-10-14T00:00:00Z"
T1 = "2026-10-14T00:01:00Z"
T2 = "2026-10-14T00:02:00Z"
T3 = "2026-10-14T00:03:00Z"


def _parent_request(*, key: str = "parent-001") -> WorkRequest:
    return WorkRequest(
        requester_principal="parent-requester",
        requester_kind="agent",
        target_kind="principal",
        target_id="parent-worker",
        work_kind="research",
        idempotency_key=key,
        objective="Investigate the parent problem and delegate bounded subwork.",
        priority=3,
    )


def _child_request(
    parent: WorkRequest,
    parent_head: str,
    *,
    requester: str = "parent-worker",
    key: str = "child-001",
) -> WorkRequest:
    return WorkRequest(
        requester_principal=requester,
        requester_kind="agent",
        target_kind="principal",
        target_id="child-worker",
        work_kind="research",
        idempotency_key=key,
        objective="Investigate a child subproblem with explicit ancestry.",
        priority=2,
        parent_work_id=parent.work_id(),
        parent_event_id=parent_head,
    )


def _create_parent(collaboration: IntelligenceCollaboration, *, key: str = "parent-001"):
    request = _parent_request(key=key)
    root = collaboration.create_work(
        request,
        observed_at=T0,
        received_at="2026-10-14T00:00:01Z",
    )
    return request, root


def _accept_parent(
    collaboration: IntelligenceCollaboration,
    parent: WorkRequest,
    root_event_id: str,
    *,
    operation_id: str = "accept-parent",
):
    return collaboration.append_transition(
        TransitionRequest(
            work_id=parent.work_id(),
            transition="accepted",
            actor_principal="parent-worker",
            actor_kind="agent",
            operation_id=operation_id,
            expected_head_event_id=root_event_id,
        ),
        observed_at=T1,
        received_at="2026-10-14T00:01:01Z",
    )


def test_child_request_requires_parent_clean_nonterminal_assignable_state():
    open_collaboration = IntelligenceCollaboration(IntelligenceFabric())
    open_parent, open_root = _create_parent(open_collaboration, key="parent-open")
    with pytest.raises(ValueError, match="parent|assign|state"):
        open_collaboration.create_work(
            _child_request(open_parent, open_root["event_id"], key="child-open"),
            observed_at=T2,
            received_at="2026-10-14T00:02:01Z",
        )

    dirty_collaboration = IntelligenceCollaboration(IntelligenceFabric())
    dirty_parent, dirty_root = _create_parent(dirty_collaboration, key="parent-dirty")
    accepted = _accept_parent(dirty_collaboration, dirty_parent, dirty_root["event_id"])
    stale = dirty_collaboration.append_transition(
        TransitionRequest(
            work_id=dirty_parent.work_id(),
            transition="started",
            actor_principal="parent-worker",
            actor_kind="agent",
            operation_id="stale-parent-start",
            expected_head_event_id=dirty_root["event_id"],
        ),
        observed_at=T2,
        received_at="2026-10-14T00:02:01Z",
    )
    assert stale["applied"] is False
    assert dirty_collaboration.snapshot(dirty_parent.work_id()).conflicts
    with pytest.raises(ValueError, match="parent|clean|conflict"):
        dirty_collaboration.create_work(
            _child_request(dirty_parent, accepted["event_id"], key="child-dirty"),
            observed_at=T3,
            received_at="2026-10-14T00:03:01Z",
        )

    terminal_collaboration = IntelligenceCollaboration(IntelligenceFabric())
    terminal_parent, terminal_root = _create_parent(terminal_collaboration, key="parent-terminal")
    accepted = _accept_parent(terminal_collaboration, terminal_parent, terminal_root["event_id"])
    cancelled = terminal_collaboration.append_transition(
        TransitionRequest(
            work_id=terminal_parent.work_id(),
            transition="cancelled",
            actor_principal="parent-requester",
            actor_kind="agent",
            operation_id="cancel-parent",
            expected_head_event_id=accepted["event_id"],
        ),
        observed_at=T2,
        received_at="2026-10-14T00:02:01Z",
    )
    assert cancelled["state"] == "CANCELLED"
    with pytest.raises(ValueError, match="parent|terminal|state"):
        terminal_collaboration.create_work(
            _child_request(terminal_parent, cancelled["event_id"], key="child-terminal"),
            observed_at=T3,
            received_at="2026-10-14T00:03:01Z",
        )


def test_child_requester_must_be_parent_assignee():
    collaboration = IntelligenceCollaboration(IntelligenceFabric())
    parent, root = _create_parent(collaboration, key="parent-requester-check")
    accepted = _accept_parent(collaboration, parent, root["event_id"])

    with pytest.raises(ValueError, match="requester|assignee|parent"):
        collaboration.create_work(
            _child_request(
                parent,
                accepted["event_id"],
                requester="different-agent",
                key="child-wrong-requester",
            ),
            observed_at=T2,
            received_at="2026-10-14T00:02:01Z",
        )


def test_child_parent_event_must_equal_parent_current_head():
    collaboration = IntelligenceCollaboration(IntelligenceFabric())
    parent, root = _create_parent(collaboration, key="parent-head-check")
    accepted = _accept_parent(collaboration, parent, root["event_id"])
    assert accepted["event_id"] != root["event_id"]

    with pytest.raises(ValueError, match="parent_event_id|head|parent"):
        collaboration.create_work(
            _child_request(parent, root["event_id"], key="child-stale-parent-head"),
            observed_at=T2,
            received_at="2026-10-14T00:02:01Z",
        )


def test_child_root_top_level_causation_contains_parent_head():
    collaboration = IntelligenceCollaboration(IntelligenceFabric())
    parent, root = _create_parent(collaboration, key="parent-cause")
    accepted = _accept_parent(collaboration, parent, root["event_id"])
    child = _child_request(parent, accepted["event_id"], key="child-cause")

    created = collaboration.create_work(
        child,
        observed_at=T2,
        received_at="2026-10-14T00:02:01Z",
    )
    child_root = collaboration.history(child.work_id())[0]

    assert created["applied"] is True
    assert accepted["event_id"] in child_root["causation_ids"]
    assert child_root["payload"]["request"]["parent_work_id"] == parent.work_id()
    assert child_root["payload"]["request"]["parent_event_id"] == accepted["event_id"]


def test_children_discovers_parent_tagged_child_requests():
    collaboration = IntelligenceCollaboration(IntelligenceFabric())
    parent, root = _create_parent(collaboration, key="parent-discovery")
    accepted = _accept_parent(collaboration, parent, root["event_id"])
    child_a = _child_request(parent, accepted["event_id"], key="child-discovery-a")
    child_b = _child_request(parent, accepted["event_id"], key="child-discovery-b")
    collaboration.create_work(
        child_a,
        observed_at=T2,
        received_at="2026-10-14T00:02:01Z",
    )
    collaboration.create_work(
        child_b,
        observed_at=T3,
        received_at="2026-10-14T00:03:01Z",
    )

    children = collaboration.children(parent.work_id(), limit=100)

    assert [record["payload"]["work_id"] for record in children] == [
        child_a.work_id(),
        child_b.work_id(),
    ]
    assert all(record["payload"]["transition"] == "requested" for record in children)
    assert all(record["payload"]["request"]["parent_work_id"] == parent.work_id() for record in children)


def test_parent_cancel_does_not_automatically_cancel_child():
    collaboration = IntelligenceCollaboration(IntelligenceFabric())
    parent, root = _create_parent(collaboration, key="parent-independent-cancel")
    accepted = _accept_parent(collaboration, parent, root["event_id"])
    child = _child_request(parent, accepted["event_id"], key="child-independent-cancel")
    collaboration.create_work(
        child,
        observed_at=T2,
        received_at="2026-10-14T00:02:01Z",
    )

    parent_cancel = collaboration.append_transition(
        TransitionRequest(
            work_id=parent.work_id(),
            transition="cancelled",
            actor_principal="parent-requester",
            actor_kind="agent",
            operation_id="cancel-parent-after-child",
            expected_head_event_id=accepted["event_id"],
        ),
        observed_at=T3,
        received_at="2026-10-14T00:03:01Z",
    )

    assert parent_cancel["state"] == "CANCELLED"
    assert collaboration.snapshot(parent.work_id()).state == "CANCELLED"
    assert collaboration.snapshot(child.work_id()).state == "OPEN"
