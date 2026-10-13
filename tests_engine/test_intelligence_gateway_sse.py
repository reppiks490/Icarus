from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest

from icarus_engine import intelligence_gateway as gateway


class _SsePlane:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.claimed = False
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def claim(self, subscription_id, revision, consumer_id, *, as_of, lease_seconds, limit):
        self.calls.append(("claim", (subscription_id, revision, consumer_id), {"as_of": as_of, "lease_seconds": lease_seconds, "limit": limit}))
        if self.claimed:
            return []
        self.claimed = True
        return [{
            "delivery_id": "delivery-sse-1",
            "event_id": "event-sse-1",
            "journal_sequence": 7,
            "attempt": 1,
            "lease_token": "lease-sse-1",
            "lease_expires_at": "2026-10-13T22:00:30Z",
            "event": {
                "schema_version": "icarus-intelligence-fabric-v1",
                "title": "SSE test event",
                "execution_authorized": False,
                "production_decision_authorized": False,
            },
            "execution_authorized": False,
            "production_decision_authorized": False,
        }]

    def ack(self, *args, **kwargs):
        self.calls.append(("ack", args, kwargs))
        return {"delivery_id": args[0], "state": "ACKED", "execution_authorized": False, "production_decision_authorized": False}

    def nack(self, *args, **kwargs):
        self.calls.append(("nack", args, kwargs))
        return {"delivery_id": args[0], "state": "PENDING", "execution_authorized": False, "production_decision_authorized": False}

    def metrics(self, subscription_id, revision, *, as_of):
        self.calls.append(("metrics", (subscription_id, revision), {"as_of": as_of}))
        return {"subscription_id": subscription_id, "revision": revision, "sequence_lag": 0,
                "execution_authorized": False, "production_decision_authorized": False}

    def recover_expired(self, *, as_of, limit):
        self.calls.append(("recover_expired", (), {"as_of": as_of, "limit": limit}))
        return []

    def close(self):
        return None


def _app(tmp_path: Path, *, config: gateway.GatewayConfig | None = None):
    made: list[_SsePlane] = []

    def factory(db_path: str):
        plane = _SsePlane(db_path)
        made.append(plane)
        return plane

    app = gateway.create_intelligence_gateway_app(
        db_path=str(tmp_path / "gateway.db"),
        bearer_token="bearer-secret",
        config=config or gateway.GatewayConfig(idle_poll_seconds=0.01, heartbeat_seconds=0.02, recovery_seconds=0.02),
        plane_factory=factory,
    )
    return app, made


def _binding() -> gateway.SessionBinding:
    return gateway.SessionBinding("sub-live", 1, "consumer-a", 30, 1)


async def _raw_sse_request(app, ticket: str, *, stop_after_event: str | None):
    """Drive ASGI directly so a deliberate long-lived SSE stream can disconnect finitely.

    Starlette TestClient buffers the whole response body before returning, so it
    cannot be used to assert an infinite text/event-stream without deadlocking.
    """
    sent: list[dict[str, object]] = []
    disconnect = asyncio.Event()
    request_sent = False
    marker = f"event: {stop_after_event}\n".encode() if stop_after_event else None

    async def receive():
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await disconnect.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(dict(message))
        if marker is not None and message.get("type") == "http.response.body" and marker in message.get("body", b""):
            disconnect.set()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/v1/intelligence/stream",
        "raw_path": b"/v1/intelligence/stream",
        "query_string": f"ticket={ticket}".encode(),
        "headers": [(b"host", b"localhost")],
        "client": ("testclient", 50000),
        "server": ("localhost", 80),
        "root_path": "",
        "state": {},
    }
    await asyncio.wait_for(app(scope, receive, send), timeout=2.0)
    start = next(message for message in sent if message.get("type") == "http.response.start")
    body = b"".join(message.get("body", b"") for message in sent if message.get("type") == "http.response.body")
    return int(start["status"]), body


def _drive_sse(app, *, stop_after_event: str):
    service = app.state.gateway_service

    async def scenario():
        await service.start()
        try:
            ticket = service.create_sse_ticket(_binding(), now_monotonic=time.monotonic())
            status, body = await _raw_sse_request(app, ticket, stop_after_event=stop_after_event)
            reused_status, reused_body = await _raw_sse_request(app, ticket, stop_after_event=None)
            return ticket, status, body, reused_status, reused_body
        finally:
            await service.close()

    return asyncio.run(scenario())


def test_encode_sse_emits_named_event_with_compact_finite_json():
    payload = gateway._authority_payload(type="heartbeat", server_time="2026-10-13T22:00:00Z")
    encoded = gateway.encode_sse("heartbeat", payload)
    assert encoded.startswith(b"event: heartbeat\n")
    assert b"data: " in encoded
    assert encoded.endswith(b"\n\n")
    data_line = next(line for line in encoded.splitlines() if line.startswith(b"data: "))
    decoded = json.loads(data_line[6:])
    assert decoded["execution_authorized"] is False
    assert decoded["production_decision_authorized"] is False


def test_sse_stream_route_is_registered(tmp_path: Path):
    app, _made = _app(tmp_path)
    assert any(getattr(route, "path", None) == "/v1/intelligence/stream" for route in app.routes)


def test_sse_stream_consumes_ticket_once_and_emits_hello_then_delivery(tmp_path: Path):
    app, _made = _app(tmp_path)
    _ticket, status, body, reused_status, reused_body = _drive_sse(app, stop_after_event="delivery")
    assert status == 200
    assert b"event: hello" in body
    assert b"event: delivery" in body
    assert b"delivery-sse-1" in body
    assert b"event-sse-1" in body
    assert reused_status in {401, 403}
    assert b"AUTH_FAILED" in reused_body


def test_sse_full_inflight_window_stops_additional_claims(tmp_path: Path):
    app, made = _app(tmp_path)
    _ticket, status, body, _reused_status, _reused_body = _drive_sse(app, stop_after_event="flow")
    assert status == 200
    claim_calls = [item for item in made[0].calls if item[0] == "claim"]
    assert len(claim_calls) == 1
    assert b"inflight_window_full" in body


def test_transport_payload_identity_is_shared_between_websocket_and_sse_helpers():
    binding = gateway.SessionBinding("sub-live", 1, "consumer-a", 30, 1)
    session = gateway.GatewaySession(
        "session-1", "sse", binding,
        "2026-10-13T22:00:00Z", "2026-10-13T22:00:00Z", "2026-10-13T22:00:00Z", set(), False,
    )
    delivery = {
        "delivery_id": "delivery-same",
        "event_id": "event-same",
        "journal_sequence": 9,
        "attempt": 2,
        "lease_token": "lease-same",
        "lease_expires_at": "2026-10-13T22:00:30Z",
        "event": {"schema_version": "icarus-intelligence-fabric-v1", "title": "same"},
    }
    frame = gateway.delivery_frame(session, delivery)
    wire = gateway.encode_sse("delivery", frame)
    decoded = json.loads(next(line for line in wire.splitlines() if line.startswith(b"data: "))[6:])
    for key in ("delivery_id", "event_id", "journal_sequence", "attempt", "lease_expires_at", "event"):
        assert decoded[key] == frame[key]
    assert decoded["execution_authorized"] is False
    assert decoded["production_decision_authorized"] is False


def test_periodic_recovery_runs_and_reconciles_session_inflight():
    class Executor:
        def __init__(self):
            self.calls = []
            self.started = False
            self.closed = False
            self.queue_depth = 0
            self.saturation_count = 0
        def start(self): self.started = True
        def close(self): self.closed = True
        async def call(self, method, /, *args, **kwargs):
            self.calls.append((method, args, kwargs))
            if method == "recover_expired":
                return [{"delivery_id": "delivery-expired", "state": "PENDING"}]
            return []

    executor = Executor()
    cfg = gateway.GatewayConfig(recovery_seconds=0.01, idle_poll_seconds=0.01)
    sessions = gateway.SessionRegistry(max_sessions=4, session_id_factory=lambda: "session-recovery")
    service = gateway.IntelligenceGatewayService(executor=executor, config=cfg, session_registry=sessions)
    session = service.create_ws_session(gateway.SessionBinding("sub-live", 1, "consumer-a", 30, 2), now="2026-10-13T22:00:00Z")
    sessions.add_inflight(session.session_id, "delivery-expired")

    async def run():
        await service.start()
        await asyncio.sleep(0.04)
        remaining = set(sessions.get(session.session_id).inflight_delivery_ids)
        await service.close()
        return remaining

    remaining = asyncio.run(run())
    assert remaining == set()
    assert any(call[0] == "recover_expired" for call in executor.calls)
    assert executor.closed is True


def test_main_requires_gateway_token_environment_variable_before_uvicorn_start(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("ICARUS_INTELLIGENCE_GATEWAY_TOKEN", raising=False)
    called = []
    monkeypatch.setattr(gateway, "_run_uvicorn", lambda *args, **kwargs: called.append((args, kwargs)))
    with pytest.raises(SystemExit):
        gateway.main(["--db", str(tmp_path / "gateway.db")])
    assert called == []


def test_main_rejects_in_memory_database_path(monkeypatch):
    monkeypatch.setenv("ICARUS_INTELLIGENCE_GATEWAY_TOKEN", "secret")
    monkeypatch.setattr(gateway, "_run_uvicorn", lambda *args, **kwargs: None)
    with pytest.raises(ValueError, match="file-backed"):
        gateway.main(["--db", ":memory:"])


def test_main_rejects_remote_bind_without_allow_remote(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ICARUS_INTELLIGENCE_GATEWAY_TOKEN", "secret")
    monkeypatch.setattr(gateway, "_run_uvicorn", lambda *args, **kwargs: None)
    with pytest.raises(ValueError, match="non-loopback"):
        gateway.main(["--db", str(tmp_path / "gateway.db"), "--host", "0.0.0.0"])


def test_main_passes_loopback_host_port_and_disables_access_log(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ICARUS_INTELLIGENCE_GATEWAY_TOKEN", "super-secret-token")
    seen = {}
    def fake_run(app, **kwargs):
        seen["app"] = app
        seen.update(kwargs)
    monkeypatch.setattr(gateway, "_run_uvicorn", fake_run)
    assert gateway.main(["--db", str(tmp_path / "gateway.db"), "--host", "127.0.0.1", "--port", "8899"]) == 0
    assert seen["host"] == "127.0.0.1"
    assert seen["port"] == 8899
    assert seen["access_log"] is False
    assert "super-secret-token" not in repr(seen)
