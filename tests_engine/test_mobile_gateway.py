import json
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from icarus_mobile_gateway.audit import GatewayAuditLog
from icarus_mobile_gateway.auth import AuthError, SessionSigner
from icarus_mobile_gateway.proxy import UpstreamClient, UpstreamError
from icarus_mobile_gateway.push import system_alerts, validate_push_token
from icarus_mobile_gateway.server import make_server
from icarus_mobile_gateway.store import DeviceStore


def test_gateway_audit_log_records_secret_free_receipts(tmp_path):
    log = GatewayAuditLog(tmp_path / "audit.jsonl", max_bytes=65536)
    log.record("backtest_start", device_id="device-1", metadata={"asset": "NQ", "session": "rth"})
    rows = log.tail()
    assert rows[-1]["event"] == "backtest_start"
    assert rows[-1]["device_id"] == "device-1"
    assert rows[-1]["metadata"]["asset"] == "NQ"


def test_session_signer_rejects_tamper_and_expiry():
    now = [1000.0]
    signer = SessionSigner(b"x" * 32, ttl=60, clock=lambda: now[0])
    token, exp = signer.issue("device-1")
    assert exp == 1060
    assert signer.verify(token)["sub"] == "device-1"
    body, sig = token.split(".", 1)
    with pytest.raises(AuthError):
        signer.verify(body + "." + ("A" if sig[0] != "A" else "B") + sig[1:])
    now[0] = 1061.0
    with pytest.raises(AuthError):
        signer.verify(token)


def test_device_store_rotates_refresh_and_revokes(tmp_path):
    store = DeviceStore(tmp_path / "devices.json")
    device_id, refresh = store.pair("My iPhone")
    assert store.active(device_id)
    rotated = store.rotate_refresh(device_id, refresh)
    assert rotated != refresh
    with pytest.raises(ValueError):
        store.rotate_refresh(device_id, refresh)
    assert store.rotate_refresh(device_id, rotated)
    assert store.revoke(device_id)
    assert not store.active(device_id)


def test_device_store_fails_closed_on_corruption_or_disappearance(tmp_path):
    path = tmp_path / "devices.json"
    store = DeviceStore(path)
    path.write_text("{truncated", encoding="utf-8")
    with pytest.raises(ValueError, match="device store is corrupt"):
        store.list_devices()

    path.unlink()
    with pytest.raises(ValueError, match="refusing to forget paired devices"):
        store.list_devices()


def test_system_alerts_are_transition_based():
    previous = {
        "status": {"paused": False, "all_warm": True, "assets": [{"symbol": "NQ", "last_error": None}]},
        "audit": {"status": "green"},
    }
    current = {
        "status": {"paused": True, "all_warm": False, "assets": [{"symbol": "NQ", "last_error": "feed stale"}]},
        "audit": {"status": "red"},
    }
    alerts = system_alerts(previous, current)
    kinds = {row["data"]["kind"] for row in alerts}
    assert {"system_audit", "engine_paused", "warm_state_lost", "asset_error"} <= kinds
    assert system_alerts(current, current) == []


def test_push_token_validation():
    assert validate_push_token("ExpoPushToken[abcDEF_123456789]")
    with pytest.raises(ValueError):
        validate_push_token("https://example.com/not-a-token")


def test_mobile_proxy_rejects_execution_mutations_and_unknown_backtest_fields():
    client = UpstreamClient("http://127.0.0.1:1", admin_token="secret")
    with pytest.raises(UpstreamError) as denied:
        client.mobile_post("/v1/pause", {"asset": "NQ"})
    assert denied.value.status == 404

    with pytest.raises(UpstreamError) as invalid:
        client.mobile_post("/v1/backtest", {"asset": "NQ", "confirm": True})
    assert invalid.value.status == 400


def test_mobile_upstream_requires_loopback_origin():
    for url in (
        "https://engine.example:8791",
        "http://127.0.0.1.example:8791",
        "http://user@127.0.0.1:8791",
        "http://127.0.0.1:8791/other-service",
        "http://127.0.0.1:8791?redirect=1",
        "http://127.0.0.1:8791#fragment",
    ):
        with pytest.raises(ValueError, match="loopback origin"):
            UpstreamClient(url, admin_token="secret")

    assert UpstreamClient("http://127.0.0.1:8791", admin_token="secret")
    assert UpstreamClient("http://[::1]:8791", admin_token="secret")
    assert UpstreamClient("http://localhost:8791", admin_token="secret")


def test_mobile_upstream_does_not_follow_redirects_with_admin_token():
    received_local: list[str | None] = []
    received: list[str | None] = []

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            received_local.append(self.headers.get("Authorization"))
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{sink.server_port}/capture")
            self.end_headers()

        def log_message(self, *_args):
            pass

    class SinkHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append(self.headers.get("Authorization"))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_args):
            pass

    sink = ThreadingHTTPServer(("127.0.0.1", 0), SinkHandler)
    redirect = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    sink_thread = threading.Thread(target=sink.serve_forever, daemon=True)
    redirect_thread = threading.Thread(target=redirect.serve_forever, daemon=True)
    sink_thread.start()
    redirect_thread.start()
    try:
        client = UpstreamClient(f"http://127.0.0.1:{redirect.server_port}", admin_token="secret")
        with pytest.raises(UpstreamError) as denied:
            client.mobile_get("/v1/brain", {})
        assert denied.value.status == 302
        assert received_local == ["Bearer secret"]
        assert received == []
    finally:
        redirect.shutdown()
        sink.shutdown()
        redirect.server_close()
        sink.server_close()
        redirect_thread.join(timeout=3)
        sink_thread.join(timeout=3)


class FakeUpstream:
    def health(self):
        return {"ok": True}

    def snapshot(self):
        return {
            "cursor": "stable-cursor",
            "generated_at": time.time(),
            "status": {"assets": [{"symbol": "NQ", "warm": True}]},
            "audit": {"status": "green"},
            "briefing": {"summary": "ok"},
        }

    def mobile_get(self, path, query):
        if path == "/v1/status":
            return {"assets": [{"symbol": "NQ"}]}
        if path == "/v1/brain":
            return {"execution_authorized": False}
        if path.startswith("/v1/backtest/"):
            return {"id": path.rsplit("/", 1)[1], "status": "done", "result": {"asset": "NQ"}}
        raise RuntimeError(path)

    def mobile_post(self, path, body):
        if path == "/v1/backtest":
            return {"ok": True, "job": "job-123", "asset": body["asset"]}
        raise RuntimeError(path)


def _request(url, method="GET", body=None, token=None):
    raw = None if body is None else json.dumps(body).encode()
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=raw, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            payload = response.read()
            return response.status, json.loads(payload) if payload else None
    except urllib.error.HTTPError as ex:
        payload = ex.read()
        return ex.code, json.loads(payload) if payload else None


def test_gateway_pair_refresh_read_and_revoke(tmp_path):
    server = make_server(
        "127.0.0.1",
        0,
        data_dir=tmp_path,
        pairing_secret="correct-horse-battery-staple",
        upstream=FakeUpstream(),
        start_background=True,
        snapshot_interval=0.05,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        code, health = _request(base + "/healthz")
        assert code == 200 and health["upstream_ok"] is True
        assert health["api_version"] == 1
        assert health["execution_mutations"] is False
        assert "backtest" in health["capabilities"]

        code, denied = _request(base + "/v1/status")
        assert code == 401

        code, pair = _request(
            base + "/v1/pair",
            "POST",
            {"device_name": "test", "pairing_secret": "correct-horse-battery-staple"},
        )
        assert code == 201
        assert pair["device_id"]
        session = pair["session_token"]

        code, status = _request(base + "/v1/status", token=session)
        assert code == 200
        assert status["assets"][0]["symbol"] == "NQ"

        code, brain = _request(base + "/v1/brain", token=session)
        assert code == 200
        assert brain["execution_authorized"] is False

        code, push = _request(
            base + "/v1/notifications/register",
            "POST",
            {"expo_push_token": "ExpoPushToken[abcDEF_123456789]", "platform": "ios", "topics": ["system"]},
            token=session,
        )
        assert code == 200 and push["enabled"] is True

        code, push_status = _request(base + "/v1/notifications", token=session)
        assert code == 200 and push_status["enabled"] is True

        code, disabled = _request(base + "/v1/notifications/unregister", "POST", {}, token=session)
        assert code == 200 and disabled["enabled"] is False

        code, forbidden = _request(base + "/v1/pause", "POST", {"asset": "NQ"}, token=session)
        assert code == 404

        code, started = _request(
            base + "/v1/backtest",
            "POST",
            {"asset": "NQ", "chart_type": "heikin_ashi", "session": "rth", "timeframe": "20"},
            token=session,
        )
        assert code == 200
        assert started["job"] == "job-123"

        code, job = _request(base + "/v1/backtest/job-123", token=session)
        assert code == 200
        assert job["status"] == "done"

        code, refreshed = _request(
            base + "/v1/session",
            "POST",
            {"device_id": pair["device_id"], "refresh_token": pair["refresh_token"]},
        )
        assert code == 200
        assert refreshed["refresh_token"] != pair["refresh_token"]

        code, old_refresh = _request(
            base + "/v1/session",
            "POST",
            {"device_id": pair["device_id"], "refresh_token": pair["refresh_token"]},
        )
        assert code == 401

        code, revoked = _request(base + "/v1/revoke", "POST", {}, token=refreshed["session_token"])
        assert code == 200 and revoked["revoked"] is True

        code, denied = _request(base + "/v1/status", token=refreshed["session_token"])
        assert code == 401
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_gateway_response_swallows_client_disconnect(tmp_path):
    server = make_server(
        "127.0.0.1",
        0,
        data_dir=tmp_path,
        pairing_secret="correct-horse-battery-staple",
        upstream=FakeUpstream(),
        start_background=False,
    )
    handler_type = server.RequestHandlerClass
    handler = handler_type.__new__(handler_type)
    handler.close_connection = False
    handler.send_response = lambda code: None
    handler.send_header = lambda key, value: None
    handler.end_headers = lambda: None

    class DisconnectedWriter:
        def write(self, body):
            raise ConnectionAbortedError(10053, "client disconnected")

    handler.wfile = DisconnectedWriter()
    try:
        handler_type._send(handler, 200, b"response")
        assert handler.close_connection is True
    finally:
        server.server_close()
