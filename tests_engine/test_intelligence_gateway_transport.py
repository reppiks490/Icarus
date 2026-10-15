from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from icarus_engine import intelligence_gateway as gateway


class _TransportPlane:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
        self.claim_batches: list[list[dict[str, object]]] = []

    def claim(self, subscription_id, revision, consumer_id, *, as_of, lease_seconds, limit):
        self.calls.append(
            (
                "claim",
                (subscription_id, revision, consumer_id),
                {"as_of": as_of, "lease_seconds": lease_seconds, "limit": limit},
            )
        )
        if self.claim_batches:
            return self.claim_batches.pop(0)
        return []

    def ack(self, delivery_id, consumer_id, lease_token, *, as_of):
        self.calls.append(("ack", (delivery_id, consumer_id, lease_token), {"as_of": as_of}))
        return {
            "delivery_id": delivery_id,
            "state": "ACKED",
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def nack(self, delivery_id, consumer_id, lease_token, *, as_of, reason):
        self.calls.append(
            (
                "nack",
                (delivery_id, consumer_id, lease_token),
                {"as_of": as_of, "reason": reason},
            )
        )
        return {
            "delivery_id": delivery_id,
            "state": "PENDING",
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def recover_expired(self, *, as_of, limit):
        self.calls.append(("recover_expired", (), {"as_of": as_of, "limit": limit}))
        return []

    def metrics(self, subscription_id, revision, *, as_of):
        self.calls.append(("metrics", (subscription_id, revision), {"as_of": as_of}))
        return {
            "subscription_id": subscription_id,
            "revision": revision,
            "sequence_lag": 0,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def close(self):
        return None


def _delivery(delivery_id: str = "delivery-1") -> dict[str, object]:
    return {
        "delivery_id": delivery_id,
        "subscription_id": "sub-live",
        "revision": 1,
        "target_kind": "consumer",
        "target_id": "consumer-a",
        "event_id": "event-1",
        "journal_sequence": 42,
        "state": "LEASED",
        "attempt": 1,
        "lease_owner": "consumer-a",
        "lease_token": "lease-token-1",
        "leased_at": "2026-10-13T20:30:00Z",
        "lease_expires_at": "2026-10-13T20:30:30Z",
        "event": {
            "schema_version": "icarus-intelligence-fabric-v1",
            "event_type": "alert",
            "source": "test-source",
            "title": "test event",
            "execution_authorized": False,
            "production_decision_authorized": False,
        },
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def _make_app(tmp_path: Path, *, config: gateway.GatewayConfig | None = None):
    made: list[_TransportPlane] = []

    def factory(db_path: str):
        plane = _TransportPlane(db_path)
        made.append(plane)
        return plane

    app = gateway.create_intelligence_gateway_app(
        db_path=str(tmp_path / "gateway.db"),
        bearer_token="bearer-secret",
        config=config,
        plane_factory=factory,
    )
    return app, made


def _auth_frame(**overrides):
    frame = {
        "type": "authenticate",
        "protocol": gateway.PROTOCOL_VERSION,
        "token": "bearer-secret",
        "subscription_id": "sub-live",
        "revision": 1,
        "consumer_id": "consumer-a",
        "lease_seconds": 30,
        "max_inflight": 4,
    }
    frame.update(overrides)
    return frame


def test_websocket_rejects_unexpected_host_before_authentication(tmp_path: Path):
    app, made = _make_app(tmp_path)
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/v1/intelligence/ws", headers={"host": "evil.example"}) as ws:
                ws.send_json(_auth_frame())
                ws.receive_json()
        assert made[0].calls == []


def test_websocket_rejects_nonallowlisted_origin_before_authentication(tmp_path: Path):
    app, made = _make_app(tmp_path)
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "/v1/intelligence/ws",
                headers={"host": "localhost", "origin": "https://evil.example"},
            ) as ws:
                ws.send_json(_auth_frame())
                ws.receive_json()
        assert made[0].calls == []


def test_websocket_auth_timeout_closes_with_zero_claim_calls(tmp_path: Path):
    config = gateway.GatewayConfig(auth_timeout_seconds=0.05)
    app, made = _make_app(tmp_path, config=config)
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/v1/intelligence/ws", headers={"host": "localhost"}) as ws:
                ws.receive_json()
        assert [call for call in made[0].calls if call[0] == "claim"] == []


def test_websocket_invalid_token_closes_with_zero_claim_calls_and_no_secret_echo(tmp_path: Path):
    app, made = _make_app(tmp_path)
    with TestClient(app) as client:
        with client.websocket_connect("/v1/intelligence/ws", headers={"host": "localhost"}) as ws:
            ws.send_json(_auth_frame(token="wrong-secret-value"))
            error = ws.receive_json()
            assert error["type"] == "error"
            assert error["code"] == "AUTH_FAILED"
            assert "wrong-secret-value" not in str(error)
            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()
        assert [call for call in made[0].calls if call[0] == "claim"] == []


def test_websocket_unsupported_protocol_rejected_before_claim(tmp_path: Path):
    app, made = _make_app(tmp_path)
    with TestClient(app) as client:
        with client.websocket_connect("/v1/intelligence/ws", headers={"host": "localhost"}) as ws:
            ws.send_json(_auth_frame(protocol="future-protocol"))
            error = ws.receive_json()
            assert error["code"] == "PROTOCOL_UNSUPPORTED"
            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()
        assert [call for call in made[0].calls if call[0] == "claim"] == []


def test_websocket_auth_does_not_auto_register_consumer(tmp_path: Path):
    app, made = _make_app(tmp_path)
    with TestClient(app) as client:
        with client.websocket_connect("/v1/intelligence/ws", headers={"host": "localhost"}) as ws:
            ws.send_json(_auth_frame())
            hello = ws.receive_json()
            assert hello["type"] == "hello"
            assert hello["consumer_id"] == "consumer-a"
        assert all(call[0] != "register_consumer" for call in made[0].calls)


def test_websocket_delivery_frame_preserves_phase2_delivery_and_phase1_event_identity(tmp_path: Path):
    app, made = _make_app(tmp_path)
    with TestClient(app) as client:
        made[0].claim_batches.append([_delivery()])
        with client.websocket_connect("/v1/intelligence/ws", headers={"host": "localhost"}) as ws:
            ws.send_json(_auth_frame())
            hello = ws.receive_json()
            frame = ws.receive_json()
            assert hello["type"] == "hello"
            assert frame["type"] == "delivery"
            assert frame["delivery_id"] == "delivery-1"
            assert frame["event_id"] == "event-1"
            assert frame["journal_sequence"] == 42
            assert frame["event"]["title"] == "test event"
            assert frame["execution_authorized"] is False
            assert frame["production_decision_authorized"] is False


def test_websocket_never_claims_above_free_inflight_capacity(tmp_path: Path):
    app, made = _make_app(tmp_path)
    with TestClient(app) as client:
        made[0].claim_batches.append([_delivery()])
        with client.websocket_connect("/v1/intelligence/ws", headers={"host": "localhost"}) as ws:
            ws.send_json(_auth_frame(max_inflight=1))
            ws.receive_json()
            ws.receive_json()
            ws.send_json({"type": "ping", "request_id": "ping-1"})
            ws.receive_json()
            claim_calls = [call for call in made[0].calls if call[0] == "claim"]
            assert claim_calls[0][2]["limit"] == 1
            assert len(claim_calls) == 1


def test_websocket_ack_and_nack_delegate_exactly_and_emit_result_frames(tmp_path: Path):
    app, made = _make_app(tmp_path)
    with TestClient(app) as client:
        made[0].claim_batches.append([_delivery("delivery-ack")])
        with client.websocket_connect("/v1/intelligence/ws", headers={"host": "localhost"}) as ws:
            ws.send_json(_auth_frame(max_inflight=1))
            ws.receive_json()
            delivery = ws.receive_json()
            ws.send_json(
                {
                    "type": "ack",
                    "request_id": "ack-1",
                    "delivery_id": "delivery-ack",
                    "lease_token": delivery["lease_token"],
                }
            )
            ack = ws.receive_json()
            assert ack["type"] == "ack_result"
            assert ack["state"] == "ACKED"
            assert ack["request_id"] == "ack-1"
        ack_calls = [call for call in made[0].calls if call[0] == "ack"]
        assert ack_calls[0][1] == ("delivery-ack", "consumer-a", "lease-token-1")

    app2, made2 = _make_app(tmp_path / "nack")
    with TestClient(app2) as client:
        made2[0].claim_batches.append([_delivery("delivery-nack")])
        with client.websocket_connect("/v1/intelligence/ws", headers={"host": "localhost"}) as ws:
            ws.send_json(_auth_frame(max_inflight=1))
            ws.receive_json()
            delivery = ws.receive_json()
            ws.send_json(
                {
                    "type": "nack",
                    "request_id": "nack-1",
                    "delivery_id": "delivery-nack",
                    "lease_token": delivery["lease_token"],
                    "reason": {"code": "consumer_processing_failed"},
                }
            )
            nack = ws.receive_json()
            assert nack["type"] == "nack_result"
            assert nack["state"] == "PENDING"
        nack_calls = [call for call in made2[0].calls if call[0] == "nack"]
        assert nack_calls[0][2]["reason"] == {"code": "consumer_processing_failed"}


def test_websocket_ping_returns_heartbeat_and_authority_is_always_false(tmp_path: Path):
    app, _made = _make_app(tmp_path)
    with TestClient(app) as client:
        with client.websocket_connect("/v1/intelligence/ws", headers={"host": "localhost"}) as ws:
            ws.send_json(_auth_frame())
            hello = ws.receive_json()
            ws.send_json({"type": "ping", "request_id": "ping-1"})
            heartbeat = ws.receive_json()
            assert heartbeat["type"] == "heartbeat"
            for frame in (hello, heartbeat):
                assert frame["execution_authorized"] is False
                assert frame["production_decision_authorized"] is False


def test_websocket_disconnect_never_auto_acks_or_nacks(tmp_path: Path):
    app, made = _make_app(tmp_path)
    with TestClient(app) as client:
        made[0].claim_batches.append([_delivery()])
        with client.websocket_connect("/v1/intelligence/ws", headers={"host": "localhost"}) as ws:
            ws.send_json(_auth_frame(max_inflight=1))
            ws.receive_json()
            ws.receive_json()
        assert all(call[0] not in {"ack", "nack"} for call in made[0].calls)
