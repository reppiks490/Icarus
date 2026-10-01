import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from icarus_mobile_gateway.auth import AuthError, SessionSigner
from icarus_mobile_gateway.server import make_server
from icarus_mobile_gateway.store import DeviceStore


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

        code, started = _request(base + "/v1/backtest", "POST", {"asset": "NQ"}, token=session)
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
