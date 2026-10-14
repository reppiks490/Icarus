from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from icarus_engine import intelligence_gateway as gateway


def test_default_config_is_loopback_fail_closed():
    cfg = gateway.GatewayConfig()
    assert gateway.PROTOCOL_VERSION == "icarus-intelligence-gateway-v1"
    assert cfg.host == "127.0.0.1"
    assert cfg.allow_remote is False
    assert cfg.allowed_hosts == frozenset({"127.0.0.1", "localhost", "[::1]"})
    assert cfg.allowed_origins == frozenset()
    assert cfg.default_max_inflight == 16
    assert cfg.default_lease_seconds == 30


def test_non_loopback_bind_requires_explicit_remote_enablement():
    with pytest.raises(ValueError, match="non-loopback"):
        gateway.validate_bind_host("0.0.0.0", allow_remote=False)
    with pytest.raises(ValueError, match="non-loopback"):
        gateway.validate_bind_host("192.168.1.20", allow_remote=False)
    assert gateway.validate_bind_host("127.0.0.1", allow_remote=False) == "127.0.0.1"
    assert gateway.validate_bind_host("::1", allow_remote=False) == "::1"
    assert gateway.validate_bind_host("0.0.0.0", allow_remote=True) == "0.0.0.0"


def test_host_header_rejects_unexpected_host_and_accepts_loopback_with_port():
    allowed = frozenset({"127.0.0.1", "localhost", "[::1]"})
    gateway.validate_host_header("localhost:8792", allowed)
    gateway.validate_host_header("127.0.0.1:8792", allowed)
    gateway.validate_host_header("[::1]:8792", allowed)
    with pytest.raises(gateway.GatewaySecurityError):
        gateway.validate_host_header("evil.example", allowed)
    with pytest.raises(gateway.GatewaySecurityError):
        gateway.validate_host_header(None, allowed)


def test_nonempty_origin_rejected_unless_allowlisted():
    gateway.validate_origin(None, frozenset())
    with pytest.raises(gateway.GatewaySecurityError):
        gateway.validate_origin("https://evil.example", frozenset())
    gateway.validate_origin(
        "https://operator.example",
        frozenset({"https://operator.example"}),
    )


def test_bearer_matching_uses_constant_time_helper_contract(monkeypatch):
    seen: list[tuple[str, str]] = []

    def fake_compare(left: str, right: str) -> bool:
        seen.append((left, right))
        return left == right

    monkeypatch.setattr(gateway.hmac, "compare_digest", fake_compare)
    assert gateway.bearer_matches("secret", "secret") is True
    assert gateway.bearer_matches("wrong", "secret") is False
    assert gateway.bearer_matches(None, "secret") is False
    assert seen == [("secret", "secret"), ("wrong", "secret")]


def test_redaction_removes_bearer_ticket_and_lease_values():
    bearer = "bearer-super-secret"
    ticket = "ticket-super-secret"
    lease = "lease-super-secret"
    rendered = gateway.redact_for_log(
        {
            "Authorization": f"Bearer {bearer}",
            "ticket": ticket,
            "lease_token": lease,
            "safe": "delivery-1",
        },
        secrets_to_hide=(bearer, ticket, lease),
    )
    assert "delivery-1" in rendered
    assert "[REDACTED]" in rendered
    assert bearer not in rendered
    assert ticket not in rendered
    assert lease not in rendered


@pytest.mark.parametrize(
    "kwargs",
    [
        {"default_max_inflight": 0},
        {"default_max_inflight": 257},
        {"default_lease_seconds": 4},
        {"default_lease_seconds": 301},
        {"max_sessions": 0},
        {"max_unused_tickets": 0},
        {"executor_queue_capacity": 0},
        {"ticket_ttl_seconds": 0},
        {"heartbeat_seconds": 0},
        {"max_json_body_bytes": 0},
        {"max_ws_text_bytes": 0},
    ],
)
def test_config_rejects_out_of_range_resource_limits(kwargs):
    with pytest.raises(ValueError):
        gateway.GatewayConfig(**kwargs)


class _RecordingPlane:
    def __init__(self, db_path: str, *, block: threading.Event | None = None):
        self.db_path = db_path
        self.block = block
        self.construct_thread = threading.get_ident()
        self.call_threads: list[int] = []
        self.close_thread: int | None = None

    def metrics(self, subscription_id: str, revision: int, *, as_of: str):
        self.call_threads.append(threading.get_ident())
        if self.block is not None:
            self.block.wait(timeout=5)
        return {"subscription_id": subscription_id, "revision": revision, "as_of": as_of}

    def claim(self, *args, **kwargs):
        self.call_threads.append(threading.get_ident())
        return []

    def ack(self, *args, **kwargs):
        self.call_threads.append(threading.get_ident())
        return {"state": "ACKED"}

    def nack(self, *args, **kwargs):
        self.call_threads.append(threading.get_ident())
        return {"state": "PENDING"}

    def recover_expired(self, *args, **kwargs):
        self.call_threads.append(threading.get_ident())
        return []

    def close(self):
        self.close_thread = threading.get_ident()


def test_delivery_executor_constructs_uses_and_closes_plane_on_one_worker_thread(tmp_path: Path):
    made: list[_RecordingPlane] = []

    def factory(db_path: str):
        plane = _RecordingPlane(db_path)
        made.append(plane)
        return plane

    executor = gateway.DeliveryExecutor(str(tmp_path / "fabric.db"), plane_factory=factory)
    executor.start()
    result = executor.submit("metrics", "sub", 1, as_of="2026-10-13T19:00:00Z").result(timeout=5)
    executor.close()

    assert result["subscription_id"] == "sub"
    assert len(made) == 1
    plane = made[0]
    assert plane.call_threads == [plane.construct_thread]
    assert plane.close_thread == plane.construct_thread


def test_delivery_executor_queue_is_bounded_and_reports_saturation(tmp_path: Path):
    gate = threading.Event()
    made: list[_RecordingPlane] = []

    def factory(db_path: str):
        plane = _RecordingPlane(db_path, block=gate)
        made.append(plane)
        return plane

    executor = gateway.DeliveryExecutor(
        str(tmp_path / "fabric.db"),
        plane_factory=factory,
        queue_capacity=1,
    )
    executor.start()
    first = executor.submit("metrics", "sub", 1, as_of="2026-10-13T19:00:00Z")
    second = executor.submit("metrics", "sub", 1, as_of="2026-10-13T19:00:01Z")
    with pytest.raises(gateway.GatewayBusyError):
        executor.submit("metrics", "sub", 1, as_of="2026-10-13T19:00:02Z")
    assert executor.saturation_count == 1
    assert executor.queue_depth <= 1
    gate.set()
    first.result(timeout=5)
    second.result(timeout=5)
    executor.close()


def test_delivery_executor_rejects_unknown_method_name(tmp_path: Path):
    executor = gateway.DeliveryExecutor(
        str(tmp_path / "fabric.db"),
        plane_factory=lambda path: _RecordingPlane(path),
    )
    executor.start()
    with pytest.raises(ValueError, match="unsupported delivery operation"):
        executor.submit("create_subscription").result(timeout=5)
    executor.close()


def test_delivery_executor_call_does_not_execute_phase2_on_event_loop_thread(tmp_path: Path):
    made: list[_RecordingPlane] = []

    def factory(db_path: str):
        plane = _RecordingPlane(db_path)
        made.append(plane)
        return plane

    executor = gateway.DeliveryExecutor(str(tmp_path / "fabric.db"), plane_factory=factory)
    executor.start()

    async def run():
        event_loop_thread = threading.get_ident()
        result = await executor.call("metrics", "sub", 1, as_of="2026-10-13T19:00:00Z")
        return event_loop_thread, result

    event_loop_thread, result = asyncio.run(run())
    executor.close()
    assert result["revision"] == 1
    assert made[0].call_threads[0] != event_loop_thread


def test_delivery_executor_startup_failure_propagates_without_starting_gateway_state(tmp_path: Path):
    def broken_factory(_db_path: str):
        raise RuntimeError("cannot open delivery database")

    executor = gateway.DeliveryExecutor(str(tmp_path / "missing.db"), plane_factory=broken_factory)
    with pytest.raises(RuntimeError, match="cannot open delivery database"):
        executor.start()
    assert executor.started is False
    executor.close()


class _HttpPlane:
    def __init__(self, db_path: str, *, fail_ack: bool = False):
        self.db_path = db_path
        self.fail_ack = fail_ack
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def metrics(self, subscription_id: str, revision: int, *, as_of: str):
        self.calls.append(("metrics", (subscription_id, revision), {"as_of": as_of}))
        return {
            "subscription_id": subscription_id,
            "revision": revision,
            "pending_count": 3,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def claim(self, *args, **kwargs):
        self.calls.append(("claim", args, kwargs))
        return []

    def ack(self, delivery_id, consumer_id, lease_token, *, as_of):
        self.calls.append(("ack", (delivery_id, consumer_id, lease_token), {"as_of": as_of}))
        if self.fail_ack:
            raise ValueError("SQL SELECT leaked /tmp/private-path bearer-secret")
        return {
            "delivery_id": delivery_id,
            "state": "ACKED",
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def nack(self, delivery_id, consumer_id, lease_token, *, as_of, reason):
        self.calls.append(("nack", (delivery_id, consumer_id, lease_token), {"as_of": as_of, "reason": reason}))
        return {
            "delivery_id": delivery_id,
            "state": "PENDING",
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def recover_expired(self, *, as_of, limit):
        self.calls.append(("recover_expired", (), {"as_of": as_of, "limit": limit}))
        return []

    def close(self):
        return None


def _make_app(tmp_path: Path, *, fail_ack: bool = False, config=None):
    made: list[_HttpPlane] = []

    def factory(db_path: str):
        plane = _HttpPlane(db_path, fail_ack=fail_ack)
        made.append(plane)
        return plane

    app = gateway.create_intelligence_gateway_app(
        db_path=str(tmp_path / "gateway.db"),
        bearer_token="bearer-secret",
        config=config,
        plane_factory=factory,
    )
    return app, made


def _auth_headers():
    return {"host": "localhost", "authorization": "Bearer bearer-secret"}


def _ticket_body():
    return {
        "subscription_id": "sub-live",
        "revision": 1,
        "consumer_id": "consumer-a",
        "lease_seconds": 30,
        "max_inflight": 4,
    }


def test_app_requires_nonempty_bearer_and_file_backed_db_path(tmp_path: Path):
    with pytest.raises(ValueError, match="bearer"):
        gateway.create_intelligence_gateway_app(db_path=str(tmp_path / "x.db"), bearer_token="")
    with pytest.raises(ValueError, match="file-backed"):
        gateway.create_intelligence_gateway_app(db_path=":memory:", bearer_token="secret")


def test_healthz_exposes_only_coarse_health_and_protocol(tmp_path: Path):
    app, _made = _make_app(tmp_path)
    with TestClient(app) as client:
        response = client.get("/healthz", headers={"host": "localhost"})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["protocol"] == gateway.PROTOCOL_VERSION
    assert body["delivery_store_reachable"] is True
    assert "consumer_id" not in body
    assert "subscription_id" not in body
    assert "delivery_id" not in body


def test_rejected_host_hits_no_sensitive_handler_or_phase2_operation(tmp_path: Path):
    app, made = _make_app(tmp_path)
    with TestClient(app) as client:
        response = client.get(
            "/v1/intelligence/metrics?subscription_id=sub-live&revision=1",
            headers={"host": "evil.example", "authorization": "Bearer bearer-secret"},
        )
        assert response.status_code == 400
        assert response.json()["code"] == "HOST_REJECTED"
        assert made[0].calls == []


def test_authenticated_endpoints_reject_missing_invalid_bearer_generically(tmp_path: Path):
    app, _made = _make_app(tmp_path)
    with TestClient(app) as client:
        missing = client.post("/v1/intelligence/tickets", headers={"host": "localhost"}, json=_ticket_body())
        wrong = client.post(
            "/v1/intelligence/tickets",
            headers={"host": "localhost", "authorization": "Bearer wrong"},
            json=_ticket_body(),
        )
    assert missing.status_code == wrong.status_code == 401
    assert missing.json() == wrong.json()
    assert missing.json()["code"] == "AUTH_FAILED"
    assert "subscription" not in str(missing.json()).lower()


def test_http_body_over_32k_rejected_before_durable_operation(tmp_path: Path):
    app, made = _make_app(tmp_path, config=gateway.GatewayConfig(max_json_body_bytes=128))
    with TestClient(app) as client:
        response = client.post(
            "/v1/intelligence/tickets",
            headers={**_auth_headers(), "content-type": "application/json"},
            content=b'{"padding":"' + b"x" * 200 + b'"}',
        )
    assert response.status_code == 413
    assert response.json()["code"] == "INVALID_REQUEST"
    assert made[0].calls == []


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_nan_and_infinity_json_rejected_before_durable_operation(tmp_path: Path, constant: str):
    app, made = _make_app(tmp_path)
    raw = (
        '{"subscription_id":"sub-live","revision":1,"consumer_id":"consumer-a",'
        '"lease_seconds":30,"max_inflight":4,"extra":' + constant + "}"
    )
    with TestClient(app) as client:
        response = client.post(
            "/v1/intelligence/tickets",
            headers={**_auth_headers(), "content-type": "application/json"},
            content=raw,
        )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_REQUEST"
    assert made[0].calls == []


def test_ticket_endpoint_returns_one_time_ticket_without_echoing_bearer(tmp_path: Path):
    app, _made = _make_app(tmp_path)
    with TestClient(app) as client:
        response = client.post("/v1/intelligence/tickets", headers=_auth_headers(), json=_ticket_body())
    assert response.status_code == 201
    body = response.json()
    assert body["protocol"] == gateway.PROTOCOL_VERSION
    assert isinstance(body["ticket"], str) and len(body["ticket"]) >= 20
    assert "bearer-secret" not in response.text
    assert body["execution_authorized"] is False
    assert body["production_decision_authorized"] is False


def test_metrics_delegates_phase2_and_labels_gateway_counters_ephemeral(tmp_path: Path):
    app, made = _make_app(tmp_path)
    with TestClient(app) as client:
        response = client.get(
            "/v1/intelligence/metrics?subscription_id=sub-live&revision=1",
            headers=_auth_headers(),
        )
    assert response.status_code == 200
    body = response.json()
    assert body["durable"]["pending_count"] == 3
    assert body["gateway"]["ephemeral"] is True
    assert made[0].calls[0][0] == "metrics"


def _open_sse_session(app):
    binding = gateway.SessionBinding("sub-live", 1, "consumer-a", 30, 4)
    session = app.state.gateway_service.sessions.create("sse", binding, now="2026-10-13T20:20:00Z")
    app.state.gateway_service.sessions.add_inflight(session.session_id, "delivery-1")
    return session


def test_sse_ack_requires_matching_open_sse_session_and_inflight_delivery(tmp_path: Path):
    app, _made = _make_app(tmp_path)
    with TestClient(app) as client:
        session = _open_sse_session(app)
        wrong = client.post(
            "/v1/intelligence/ack",
            headers=_auth_headers(),
            json={"session_id": session.session_id, "consumer_id": "other", "delivery_id": "delivery-1", "lease_token": "lease"},
        )
        assert wrong.status_code == 409
        assert wrong.json()["code"] == "SESSION_INVALID"
        ok = client.post(
            "/v1/intelligence/ack",
            headers=_auth_headers(),
            json={"session_id": session.session_id, "consumer_id": "consumer-a", "delivery_id": "delivery-1", "lease_token": "lease"},
        )
    assert ok.status_code == 200
    assert ok.json()["state"] == "ACKED"


def test_sse_nack_requires_matching_open_sse_session(tmp_path: Path):
    app, _made = _make_app(tmp_path)
    with TestClient(app) as client:
        session = _open_sse_session(app)
        response = client.post(
            "/v1/intelligence/nack",
            headers=_auth_headers(),
            json={
                "session_id": session.session_id,
                "consumer_id": "consumer-a",
                "delivery_id": "delivery-1",
                "lease_token": "lease",
                "reason": {"code": "failed"},
            },
        )
    assert response.status_code == 200
    assert response.json()["state"] == "PENDING"


def test_sse_ack_success_immediately_releases_inflight_slot(tmp_path: Path):
    app, _made = _make_app(tmp_path)
    with TestClient(app) as client:
        session = _open_sse_session(app)
        response = client.post(
            "/v1/intelligence/ack",
            headers=_auth_headers(),
            json={"session_id": session.session_id, "consumer_id": "consumer-a", "delivery_id": "delivery-1", "lease_token": "lease"},
        )
        assert response.status_code == 200
        assert app.state.gateway_service.sessions.get(session.session_id).inflight_delivery_ids == set()


def test_http_error_mapping_sanitizes_phase2_exception_text(tmp_path: Path):
    app, _made = _make_app(tmp_path, fail_ack=True)
    with TestClient(app) as client:
        session = _open_sse_session(app)
        response = client.post(
            "/v1/intelligence/ack",
            headers=_auth_headers(),
            json={"session_id": session.session_id, "consumer_id": "consumer-a", "delivery_id": "delivery-1", "lease_token": "lease"},
        )
    assert response.status_code >= 400
    text = response.text
    assert "SQL SELECT" not in text
    assert "/tmp/private-path" not in text
    assert "bearer-secret" not in text
    assert "lease" not in text.lower()
