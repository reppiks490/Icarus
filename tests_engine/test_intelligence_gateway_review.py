from __future__ import annotations

import asyncio
import sqlite3
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from icarus_engine import intelligence_gateway as gateway


class _ReviewPlane:
    def __init__(self, db_path: str, *, fail_ack: bool = False):
        self.db_path = db_path
        self.fail_ack = fail_ack

    def metrics(self, subscription_id: str, revision: int, *, as_of: str):
        return {"subscription_id": subscription_id, "revision": revision, "sequence_lag": 0,
                "execution_authorized": False, "production_decision_authorized": False}

    def claim(self, *args, **kwargs):
        return []

    def ack(self, delivery_id, consumer_id, lease_token, *, as_of):
        if self.fail_ack:
            raise sqlite3.OperationalError("database disk image unavailable /tmp/private bearer-secret")
        return {"delivery_id": delivery_id, "state": "ACKED",
                "execution_authorized": False, "production_decision_authorized": False}

    def nack(self, delivery_id, consumer_id, lease_token, *, as_of, reason):
        return {"delivery_id": delivery_id, "state": "PENDING",
                "execution_authorized": False, "production_decision_authorized": False}

    def recover_expired(self, *, as_of, limit):
        return []

    def close(self):
        return None


def test_delivery_executor_async_call_does_not_block_event_loop_during_submit(tmp_path: Path, monkeypatch):
    executor = gateway.DeliveryExecutor(
        str(tmp_path / "gateway.db"),
        plane_factory=lambda path: _ReviewPlane(path),
    )
    executor.start()
    original_submit = executor.submit
    ticker_ran = {"value": False}
    observed_during_submit: list[bool] = []

    def deliberately_slow_submit(*args, **kwargs):
        time.sleep(0.05)
        observed_during_submit.append(ticker_ran["value"])
        return original_submit(*args, **kwargs)

    monkeypatch.setattr(executor, "submit", deliberately_slow_submit)

    async def scenario():
        async def ticker():
            await asyncio.sleep(0.005)
            ticker_ran["value"] = True

        tick = asyncio.create_task(ticker())
        result = await executor.call("metrics", "sub", 1, as_of="2026-10-13T23:15:00Z")
        await tick
        return result

    try:
        result = asyncio.run(scenario())
    finally:
        executor.close()

    assert result["revision"] == 1
    assert observed_during_submit == [True]


def test_delivery_executor_caller_cancellation_does_not_kill_worker(tmp_path: Path):
    entered = threading.Event()
    release = threading.Event()

    class _BlockingPlane(_ReviewPlane):
        def metrics(self, subscription_id: str, revision: int, *, as_of: str):
            entered.set()
            release.wait(timeout=2)
            return super().metrics(subscription_id, revision, as_of=as_of)

    executor = gateway.DeliveryExecutor(
        str(tmp_path / "gateway.db"),
        plane_factory=lambda path: _BlockingPlane(path),
    )
    executor.start()

    async def scenario():
        first = asyncio.create_task(
            executor.call("metrics", "sub", 1, as_of="2026-10-13T23:30:00Z")
        )
        assert await asyncio.to_thread(entered.wait, 1.0)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        release.set()
        await asyncio.sleep(0.05)
        assert executor._thread is not None and executor._thread.is_alive()
        return await asyncio.wait_for(
            executor.call("metrics", "sub", 2, as_of="2026-10-13T23:30:01Z"),
            timeout=1.0,
        )

    try:
        result = asyncio.run(scenario())
    finally:
        release.set()
        executor.close()

    assert result["revision"] == 2


def test_http_sqlite_store_failure_maps_to_retryable_store_unavailable(tmp_path: Path):
    made: list[_ReviewPlane] = []

    def factory(path: str):
        plane = _ReviewPlane(path, fail_ack=True)
        made.append(plane)
        return plane

    app = gateway.create_intelligence_gateway_app(
        db_path=str(tmp_path / "gateway.db"),
        bearer_token="bearer-secret",
        plane_factory=factory,
    )
    with TestClient(app) as client:
        binding = gateway.SessionBinding("sub-live", 1, "consumer-a", 30, 4)
        session = app.state.gateway_service.sessions.create("sse", binding, now="2026-10-13T23:15:00Z")
        app.state.gateway_service.sessions.add_inflight(session.session_id, "delivery-1")
        response = client.post(
            "/v1/intelligence/ack",
            headers={"host": "localhost", "authorization": "Bearer bearer-secret"},
            json={
                "session_id": session.session_id,
                "consumer_id": "consumer-a",
                "delivery_id": "delivery-1",
                "lease_token": "lease-1",
            },
        )

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "DELIVERY_STORE_UNAVAILABLE"
    assert body["retryable"] is True
    assert "database disk image" not in response.text
    assert "/tmp/private" not in response.text
    assert "bearer-secret" not in response.text


def test_managed_launcher_pushes_websocket_frame_cap_into_uvicorn(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ICARUS_INTELLIGENCE_GATEWAY_TOKEN", "secret")
    seen: dict[str, object] = {}

    def fake_run(app, **kwargs):
        seen["app"] = app
        seen.update(kwargs)

    monkeypatch.setattr(gateway, "_run_uvicorn", fake_run)
    assert gateway.main(["--db", str(tmp_path / "gateway.db")]) == 0
    assert seen["ws_max_size"] == gateway.GatewayConfig().max_ws_text_bytes == 64 * 1024
    assert seen["access_log"] is False
