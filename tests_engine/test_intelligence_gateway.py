from __future__ import annotations

import asyncio
import itertools

import pytest

from icarus_engine import intelligence_gateway as gateway


def _binding(*, consumer: str = "consumer-a", max_inflight: int = 4) -> gateway.SessionBinding:
    return gateway.SessionBinding(
        subscription_id="sub-live",
        revision=1,
        consumer_id=consumer,
        lease_seconds=30,
        max_inflight=max_inflight,
    )


def _token_factory(prefix: str = "ticket"):
    counter = itertools.count(1)
    return lambda: f"{prefix}-{next(counter)}-opaque-value"


def test_ticket_is_one_use_and_returns_exact_binding():
    store = gateway.TicketStore(max_tickets=4, ttl_seconds=30, token_factory=_token_factory())
    binding = _binding()
    ticket = store.issue(binding, now_monotonic=100.0)
    assert store.consume(ticket, now_monotonic=101.0) == binding
    with pytest.raises(gateway.GatewaySecurityError):
        store.consume(ticket, now_monotonic=102.0)


def test_ticket_expires_at_configured_ttl():
    store = gateway.TicketStore(max_tickets=4, ttl_seconds=30, token_factory=_token_factory())
    ticket = store.issue(_binding(), now_monotonic=100.0)
    with pytest.raises(gateway.GatewaySecurityError):
        store.consume(ticket, now_monotonic=130.0)
    assert store.count(now_monotonic=130.0) == 0


def test_ticket_store_purges_expired_before_capacity_check():
    tokens = iter(("first-opaque-ticket", "second-opaque-ticket"))
    store = gateway.TicketStore(max_tickets=1, ttl_seconds=5, token_factory=lambda: next(tokens))
    first = store.issue(_binding(), now_monotonic=10.0)
    assert first == "first-opaque-ticket"
    second = store.issue(_binding(), now_monotonic=15.0)
    assert second == "second-opaque-ticket"
    assert store.count(now_monotonic=15.0) == 1


def test_ticket_store_never_evicts_valid_ticket_when_full():
    tokens = iter(("first-opaque-ticket", "second-opaque-ticket"))
    store = gateway.TicketStore(max_tickets=1, ttl_seconds=30, token_factory=lambda: next(tokens))
    first = store.issue(_binding(), now_monotonic=10.0)
    with pytest.raises(gateway.GatewayBusyError):
        store.issue(_binding(), now_monotonic=11.0)
    assert store.consume(first, now_monotonic=12.0) == _binding()


def test_ticket_values_are_opaque_and_not_present_in_count_or_repr():
    store = gateway.TicketStore(max_tickets=4, ttl_seconds=30, token_factory=lambda: "highly-secret-ticket-value")
    ticket = store.issue(_binding(), now_monotonic=100.0)
    assert ticket == "highly-secret-ticket-value"
    assert store.count(now_monotonic=101.0) == 1
    assert ticket not in repr(store)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"subscription_id": "", "revision": 1, "consumer_id": "c", "lease_seconds": 30, "max_inflight": 1},
        {"subscription_id": "s", "revision": 0, "consumer_id": "c", "lease_seconds": 30, "max_inflight": 1},
        {"subscription_id": "s", "revision": 1, "consumer_id": "", "lease_seconds": 30, "max_inflight": 1},
        {"subscription_id": "s", "revision": 1, "consumer_id": "c", "lease_seconds": 4, "max_inflight": 1},
        {"subscription_id": "s", "revision": 1, "consumer_id": "c", "lease_seconds": 301, "max_inflight": 1},
        {"subscription_id": "s", "revision": 1, "consumer_id": "c", "lease_seconds": 30, "max_inflight": 0},
        {"subscription_id": "s", "revision": 1, "consumer_id": "c", "lease_seconds": 30, "max_inflight": 257},
    ],
)
def test_session_binding_rejects_invalid_identity_or_bounds(kwargs):
    with pytest.raises(ValueError):
        gateway.SessionBinding(**kwargs)


def test_session_registry_enforces_max_sessions_without_evicting_live_session():
    ids = iter(("session-1", "session-2"))
    registry = gateway.SessionRegistry(max_sessions=1, session_id_factory=lambda: next(ids))
    first = registry.create("websocket", _binding(), now="2026-10-13T20:00:00Z")
    assert first.session_id == "session-1"
    with pytest.raises(gateway.GatewayBusyError):
        registry.create("sse", _binding(), now="2026-10-13T20:00:01Z")
    assert registry.get("session-1") is first


def test_session_close_returns_inflight_ids_without_ack_or_nack_side_effect():
    registry = gateway.SessionRegistry(max_sessions=4, session_id_factory=lambda: "session-1")
    session = registry.create("websocket", _binding(), now="2026-10-13T20:00:00Z")
    registry.add_inflight(session.session_id, "delivery-1")
    registry.add_inflight(session.session_id, "delivery-2")
    closed = registry.close(session.session_id)
    assert closed == ("delivery-1", "delivery-2")
    assert registry.get(session.session_id) is None


def test_same_consumer_may_have_two_sessions_with_independent_inflight_sets():
    ids = iter(("session-1", "session-2"))
    registry = gateway.SessionRegistry(max_sessions=4, session_id_factory=lambda: next(ids))
    one = registry.create("websocket", _binding(), now="2026-10-13T20:00:00Z")
    two = registry.create("sse", _binding(), now="2026-10-13T20:00:01Z")
    registry.add_inflight(one.session_id, "delivery-a")
    registry.add_inflight(two.session_id, "delivery-b")
    assert registry.get(one.session_id).inflight_delivery_ids == {"delivery-a"}
    assert registry.get(two.session_id).inflight_delivery_ids == {"delivery-b"}


def test_remove_inflight_everywhere_reconciles_expired_delivery():
    ids = iter(("session-1", "session-2"))
    registry = gateway.SessionRegistry(max_sessions=4, session_id_factory=lambda: next(ids))
    one = registry.create("websocket", _binding(), now="2026-10-13T20:00:00Z")
    two = registry.create("sse", _binding(), now="2026-10-13T20:00:01Z")
    registry.add_inflight(one.session_id, "delivery-x")
    registry.add_inflight(two.session_id, "delivery-x")
    assert registry.remove_inflight_everywhere("delivery-x") == 2
    assert registry.get(one.session_id).inflight_delivery_ids == set()
    assert registry.get(two.session_id).inflight_delivery_ids == set()


def test_snapshot_counts_transport_and_inflight_without_secrets():
    ids = iter(("session-1", "session-2"))
    registry = gateway.SessionRegistry(max_sessions=4, session_id_factory=lambda: next(ids))
    one = registry.create("websocket", _binding(), now="2026-10-13T20:00:00Z")
    two = registry.create("sse", _binding(), now="2026-10-13T20:00:01Z")
    registry.add_inflight(one.session_id, "delivery-a")
    registry.add_inflight(two.session_id, "delivery-b")
    snapshot = registry.snapshot()
    assert snapshot == {
        "active_sessions": 2,
        "websocket_sessions": 1,
        "sse_sessions": 1,
        "inflight_total": 2,
    }
    assert "delivery-a" not in repr(snapshot)
    assert "consumer-a" not in repr(snapshot)


class _FakeExecutor:
    def __init__(self):
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
        self.responses: list[object] = []
        self.errors: list[BaseException] = []
        self.started = False
        self.closed = False
        self.queue_depth = 0
        self.saturation_count = 0

    def start(self):
        self.started = True

    def close(self):
        self.closed = True

    async def call(self, method: str, /, *args: object, **kwargs: object):
        self.calls.append((method, args, kwargs))
        if self.errors:
            raise self.errors.pop(0)
        if self.responses:
            return self.responses.pop(0)
        return []


def _service(*, ids=("session-1", "session-2", "session-3"), config=None):
    executor = _FakeExecutor()
    session_ids = iter(ids)
    sessions = gateway.SessionRegistry(max_sessions=8, session_id_factory=lambda: next(session_ids))
    tickets = gateway.TicketStore(max_tickets=8, ttl_seconds=30, token_factory=_token_factory())
    service = gateway.IntelligenceGatewayService(
        executor=executor,
        config=config or gateway.GatewayConfig(max_sessions=8, max_unused_tickets=8),
        session_registry=sessions,
        ticket_store=tickets,
    )
    return service, executor, sessions


def test_claim_for_session_calls_phase2_with_exact_binding_and_free_slot_limit():
    service, executor, sessions = _service()
    session = service.create_ws_session(_binding(max_inflight=4), now="2026-10-13T20:10:00Z")
    sessions.add_inflight(session.session_id, "existing")
    executor.responses.append(
        [
            {"delivery_id": "delivery-1", "event_id": "event-1", "event": {"title": "one"}},
            {"delivery_id": "delivery-2", "event_id": "event-2", "event": {"title": "two"}},
        ]
    )
    result = asyncio.run(service.claim_for_session(session.session_id, now="2026-10-13T20:10:01Z"))
    assert executor.calls == [
        (
            "claim",
            ("sub-live", 1, "consumer-a"),
            {"as_of": "2026-10-13T20:10:01Z", "lease_seconds": 30, "limit": 3},
        )
    ]
    assert [item["delivery_id"] for item in result] == ["delivery-1", "delivery-2"]
    assert sessions.get(session.session_id).inflight_delivery_ids == {"existing", "delivery-1", "delivery-2"}


def test_claim_for_session_does_not_call_phase2_when_inflight_full():
    service, executor, sessions = _service()
    session = service.create_ws_session(_binding(max_inflight=2), now="2026-10-13T20:10:00Z")
    sessions.add_inflight(session.session_id, "delivery-a")
    sessions.add_inflight(session.session_id, "delivery-b")
    assert asyncio.run(service.claim_for_session(session.session_id, now="2026-10-13T20:10:01Z")) == []
    assert executor.calls == []


def test_claim_result_preserves_phase2_delivery_and_event_identity():
    service, executor, _sessions = _service()
    session = service.create_ws_session(_binding(), now="2026-10-13T20:10:00Z")
    event = {"schema_version": "icarus-intelligence-fabric-v1", "event_id": "inside-event"}
    delivery = {
        "delivery_id": "delivery-identity",
        "event_id": "event-identity",
        "journal_sequence": 42,
        "attempt": 1,
        "event": event,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
    executor.responses.append([delivery])
    result = asyncio.run(service.claim_for_session(session.session_id, now="2026-10-13T20:10:01Z"))
    assert result == [delivery]
    assert result[0]["event"] is event


def test_claim_rejects_unknown_session_before_phase2():
    service, executor, _sessions = _service()
    with pytest.raises(gateway.GatewaySessionError):
        asyncio.run(service.claim_for_session("missing-session", now="2026-10-13T20:10:01Z"))
    assert executor.calls == []


def test_ack_calls_phase2_with_exact_consumer_delivery_token_and_frees_slot():
    service, executor, sessions = _service()
    session = service.create_ws_session(_binding(), now="2026-10-13T20:10:00Z")
    sessions.add_inflight(session.session_id, "delivery-1")
    executor.responses.append({"delivery_id": "delivery-1", "state": "ACKED"})
    result = asyncio.run(
        service.ack_for_session(
            session.session_id,
            "delivery-1",
            "lease-secret",
            now="2026-10-13T20:10:02Z",
        )
    )
    assert result["state"] == "ACKED"
    assert executor.calls == [
        (
            "ack",
            ("delivery-1", "consumer-a", "lease-secret"),
            {"as_of": "2026-10-13T20:10:02Z"},
        )
    ]
    assert sessions.get(session.session_id).inflight_delivery_ids == set()


def test_nack_calls_phase2_with_exact_fields_reason_and_frees_slot():
    service, executor, sessions = _service()
    session = service.create_ws_session(_binding(), now="2026-10-13T20:10:00Z")
    sessions.add_inflight(session.session_id, "delivery-1")
    reason = {"code": "consumer_processing_failed"}
    executor.responses.append({"delivery_id": "delivery-1", "state": "PENDING"})
    result = asyncio.run(
        service.nack_for_session(
            session.session_id,
            "delivery-1",
            "lease-secret",
            now="2026-10-13T20:10:02Z",
            reason=reason,
        )
    )
    assert result["state"] == "PENDING"
    assert executor.calls == [
        (
            "nack",
            ("delivery-1", "consumer-a", "lease-secret"),
            {"as_of": "2026-10-13T20:10:02Z", "reason": reason},
        )
    ]
    assert sessions.get(session.session_id).inflight_delivery_ids == set()


def test_cross_session_ack_rejected_before_phase2_even_same_consumer_and_valid_token():
    service, executor, sessions = _service()
    one = service.create_ws_session(_binding(), now="2026-10-13T20:10:00Z")
    two = service.create_ws_session(_binding(), now="2026-10-13T20:10:01Z")
    sessions.add_inflight(one.session_id, "delivery-1")
    with pytest.raises(gateway.GatewaySessionError, match="delivery"):
        asyncio.run(service.ack_for_session(two.session_id, "delivery-1", "valid-token", now="2026-10-13T20:10:02Z"))
    assert executor.calls == []


def test_cross_session_nack_rejected_before_phase2():
    service, executor, sessions = _service()
    one = service.create_ws_session(_binding(), now="2026-10-13T20:10:00Z")
    two = service.create_ws_session(_binding(), now="2026-10-13T20:10:01Z")
    sessions.add_inflight(one.session_id, "delivery-1")
    with pytest.raises(gateway.GatewaySessionError, match="delivery"):
        asyncio.run(service.nack_for_session(two.session_id, "delivery-1", "valid-token", now="2026-10-13T20:10:02Z"))
    assert executor.calls == []


def test_failed_phase2_ack_keeps_inflight_membership_for_reconciliation():
    service, executor, sessions = _service()
    session = service.create_ws_session(_binding(), now="2026-10-13T20:10:00Z")
    sessions.add_inflight(session.session_id, "delivery-1")
    executor.errors.append(ValueError("lease has expired"))
    with pytest.raises(ValueError, match="expired"):
        asyncio.run(service.ack_for_session(session.session_id, "delivery-1", "lease", now="2026-10-13T20:10:02Z"))
    assert sessions.get(session.session_id).inflight_delivery_ids == {"delivery-1"}


def test_failed_phase2_nack_keeps_inflight_membership_for_reconciliation():
    service, executor, sessions = _service()
    session = service.create_ws_session(_binding(), now="2026-10-13T20:10:00Z")
    sessions.add_inflight(session.session_id, "delivery-1")
    executor.errors.append(RuntimeError("store unavailable"))
    with pytest.raises(RuntimeError, match="unavailable"):
        asyncio.run(service.nack_for_session(session.session_id, "delivery-1", "lease", now="2026-10-13T20:10:02Z"))
    assert sessions.get(session.session_id).inflight_delivery_ids == {"delivery-1"}


def test_lost_ack_response_retry_does_not_synthesize_success():
    service, executor, sessions = _service()
    session = service.create_ws_session(_binding(), now="2026-10-13T20:10:00Z")
    sessions.add_inflight(session.session_id, "delivery-1")
    executor.errors.extend([RuntimeError("response lost after durable commit"), ValueError("delivery is not leased")])
    with pytest.raises(RuntimeError, match="response lost"):
        asyncio.run(service.ack_for_session(session.session_id, "delivery-1", "lease", now="2026-10-13T20:10:02Z"))
    with pytest.raises(ValueError, match="not leased"):
        asyncio.run(service.ack_for_session(session.session_id, "delivery-1", "lease", now="2026-10-13T20:10:03Z"))
    assert sessions.get(session.session_id).inflight_delivery_ids == {"delivery-1"}
    assert len(executor.calls) == 2


def test_recovery_delegates_to_phase2_and_removes_recovered_ids_from_all_sessions():
    service, executor, sessions = _service()
    one = service.create_ws_session(_binding(), now="2026-10-13T20:10:00Z")
    two = service.create_ws_session(_binding(), now="2026-10-13T20:10:01Z")
    sessions.add_inflight(one.session_id, "delivery-x")
    sessions.add_inflight(two.session_id, "delivery-x")
    executor.responses.append([{"delivery_id": "delivery-x", "state": "PENDING"}])
    result = asyncio.run(service.recover_expired(now="2026-10-13T20:10:30Z"))
    assert result[0]["delivery_id"] == "delivery-x"
    assert executor.calls == [
        ("recover_expired", (), {"as_of": "2026-10-13T20:10:30Z", "limit": 100})
    ]
    assert sessions.get(one.session_id).inflight_delivery_ids == set()
    assert sessions.get(two.session_id).inflight_delivery_ids == set()


def test_disconnect_drops_ephemeral_state_without_phase2_ack_or_nack():
    service, executor, sessions = _service()
    session = service.create_ws_session(_binding(), now="2026-10-13T20:10:00Z")
    sessions.add_inflight(session.session_id, "delivery-1")
    assert service.close_session(session.session_id) == ("delivery-1",)
    assert sessions.get(session.session_id) is None
    assert executor.calls == []


def test_reconnect_has_no_gateway_cursor_and_asks_phase2_again():
    service, executor, _sessions = _service()
    first = service.create_ws_session(_binding(), now="2026-10-13T20:10:00Z")
    service.close_session(first.session_id)
    second = service.create_ws_session(_binding(), now="2026-10-13T20:10:05Z")
    executor.responses.append([])
    assert asyncio.run(service.claim_for_session(second.session_id, now="2026-10-13T20:10:06Z")) == []
    assert executor.calls == [
        (
            "claim",
            ("sub-live", 1, "consumer-a"),
            {"as_of": "2026-10-13T20:10:06Z", "lease_seconds": 30, "limit": 4},
        )
    ]


def test_service_start_close_and_ticket_binding_are_ephemeral_only():
    service, executor, _sessions = _service()
    asyncio.run(service.start())
    assert executor.started is True
    ticket = service.create_sse_ticket(_binding(), now_monotonic=100.0)
    session = service.consume_sse_ticket(ticket, now_monotonic=101.0, now="2026-10-13T20:10:00Z")
    assert session.transport == "sse"
    assert session.binding == _binding()
    asyncio.run(service.close())
    assert executor.closed is True
