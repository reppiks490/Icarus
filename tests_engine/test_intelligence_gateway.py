from __future__ import annotations

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
