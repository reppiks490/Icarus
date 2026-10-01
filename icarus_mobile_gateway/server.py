from __future__ import annotations

import hmac
import os
import json
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .audit import GatewayAuditLog
from .auth import AuthError, SessionSigner, load_or_create_key
from .proxy import UpstreamClient, UpstreamError
from .push import ExpoPushClient, system_alerts, validate_push_token
from .store import DeviceStore


MAX_BODY = 64 * 1024
MOBILE_API_VERSION = 1
MOBILE_CAPABILITIES = [
    "pairing",
    "rotating_sessions",
    "long_poll",
    "charts",
    "trades",
    "intelligence",
    "backtest",
    "push",
]


class PairRateLimiter:
    def __init__(self, attempts: int = 6, window: int = 60) -> None:
        self.attempts = attempts
        self.window = window
        self._lock = threading.Lock()
        self._rows: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            rows = [x for x in self._rows.get(key, []) if now - x < self.window]
            if len(rows) >= self.attempts:
                self._rows[key] = rows
                return False
            rows.append(now)
            self._rows[key] = rows
            return True


class SnapshotCache:
    def __init__(self, upstream: UpstreamClient, interval: float = 2.0, on_change=None) -> None:
        self.upstream = upstream
        self.on_change = on_change
        self.interval = max(0.5, min(float(interval), 10.0))
        self._stop = threading.Event()
        self._cond = threading.Condition()
        self._payload: dict[str, Any] | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="icarus-mobile-snapshot", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        with self._cond:
            self._cond.notify_all()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                payload = self.upstream.snapshot()
            except Exception as ex:
                payload = {
                    "cursor": "error-" + str(int(time.time())),
                    "generated_at": time.time(),
                    "error": f"{type(ex).__name__}: {ex}"[:500],
                }
            prior_payload = None
            changed = False
            with self._cond:
                prior_payload = dict(self._payload) if self._payload else None
                previous = self._payload.get("cursor") if self._payload else None
                self._payload = payload
                changed = payload.get("cursor") != previous
                if changed:
                    self._cond.notify_all()
            if changed and prior_payload is not None and self.on_change:
                try:
                    self.on_change(prior_payload, payload)
                except Exception:
                    pass
            self._stop.wait(self.interval)

    def current(self) -> dict[str, Any]:
        with self._cond:
            return dict(self._payload or {
                "cursor": "starting",
                "generated_at": time.time(),
                "status": {"assets": []},
                "audit": {"status": "unknown"},
                "briefing": {},
            })

    def wait_after(self, cursor: str, timeout: float) -> dict[str, Any] | None:
        deadline = time.monotonic() + max(0.0, timeout)
        with self._cond:
            while not self._stop.is_set():
                current = self._payload
                if current and str(current.get("cursor") or "") != cursor:
                    return dict(current)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._cond.wait(timeout=min(remaining, 2.0))
        return None


@dataclass
class GatewayContext:
    pairing_secret: str
    signer: SessionSigner
    devices: DeviceStore
    upstream: UpstreamClient
    cache: SnapshotCache
    limiter: PairRateLimiter
    actions: PairRateLimiter
    audit: GatewayAuditLog


def make_server(
    host: str,
    port: int,
    *,
    data_dir: str | Path,
    engine_url: str = "http://127.0.0.1:8791",
    admin_token: str = "",
    pairing_secret: str,
    session_ttl: int = 900,
    snapshot_interval: float = 2.0,
    upstream: UpstreamClient | None = None,
    start_background: bool = True,
) -> ThreadingHTTPServer:
    if len(str(pairing_secret or "")) < 16:
        raise ValueError("ICARUS mobile pairing secret must be at least 16 characters")
    root = Path(data_dir)
    gateway_dir = root / "mobile_gateway"
    devices = DeviceStore(gateway_dir / "devices.json")
    audit = GatewayAuditLog(gateway_dir / "audit.jsonl")
    signer = SessionSigner(load_or_create_key(gateway_dir / "session.key"), ttl=session_ttl)
    upstream_client = upstream or UpstreamClient(engine_url, admin_token=admin_token)
    push_client = ExpoPushClient(access_token=os.environ.get("EXPO_ACCESS_TOKEN", ""))

    def _snapshot_notifications(previous, current):
        tokens = devices.push_targets("system")
        if not tokens:
            return
        for alert in system_alerts(previous, current):
            push_client.send(
                tokens,
                title=alert["title"],
                body=alert["body"],
                data=alert.get("data") or {},
            )

    cache = SnapshotCache(upstream_client, interval=snapshot_interval, on_change=_snapshot_notifications)
    context = GatewayContext(
        pairing_secret=str(pairing_secret),
        signer=signer,
        devices=devices,
        upstream=upstream_client,
        cache=cache,
        limiter=PairRateLimiter(),
        actions=PairRateLimiter(attempts=8, window=60),
        audit=audit,
    )

    class H(BaseHTTPRequestHandler):
        server_version = "icarus-mobile-gateway"
        sys_version = ""
        protocol_version = "HTTP/1.1"

        def log_message(self, *args: Any) -> None:
            pass

        @property
        def ctx(self) -> GatewayContext:
            return self.server.gateway_context  # type: ignore[attr-defined]

        def _send(
            self,
            code: int,
            body: bytes = b"",
            ctype: str = "application/json",
            extra: dict[str, str] | None = None,
        ) -> None:
            self.send_response(code)
            if body:
                self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text/") else ""))
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if body:
                self.wfile.write(body)

        def _json(self, code: int, value: Any, extra: dict[str, str] | None = None) -> None:
            raw = json.dumps(value, separators=(",", ":"), allow_nan=False, default=str).encode("utf-8")
            self._send(code, raw, "application/json", extra)

        def _body(self) -> dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as ex:
                raise ValueError("invalid content length") from ex
            if length <= 0 or length > MAX_BODY:
                raise ValueError("invalid request body length")
            raw = self.rfile.read(length)
            try:
                value = json.loads(raw.decode("utf-8"))
            except Exception as ex:
                raise ValueError("invalid JSON body") from ex
            if not isinstance(value, dict):
                raise ValueError("JSON body must be an object")
            return value

        def _session_device(self) -> str:
            scheme, _, token = self.headers.get("Authorization", "").partition(" ")
            if scheme.lower() != "bearer" or not token:
                raise AuthError("session required")
            payload = self.ctx.signer.verify(token)
            device_id = str(payload["sub"])
            if not self.ctx.devices.active(device_id):
                raise AuthError("device revoked")
            return device_id

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if parsed.path == "/healthz":
                upstream_ok = False
                try:
                    health = self.ctx.upstream.health()
                    upstream_ok = bool(isinstance(health, dict) and health.get("ok"))
                except Exception:
                    pass
                return self._json(200, {
                    "ok": True,
                    "gateway": "icarus-mobile",
                    "api_version": MOBILE_API_VERSION,
                    "capabilities": MOBILE_CAPABILITIES,
                    "execution_mutations": False,
                    "upstream_ok": upstream_ok,
                })

            try:
                self._session_device()
            except AuthError as ex:
                return self._json(401, {"detail": str(ex)})

            if parsed.path == "/v1/snapshot":
                return self._json(200, self.ctx.cache.current())

            if parsed.path == "/v1/notifications":
                device_id = self._session_device()
                return self._json(200, self.ctx.devices.push_status(device_id))

            if parsed.path == "/v1/events":
                cursor = str((query.get("cursor") or [""])[0])[:128]
                try:
                    wait = max(1, min(30, int((query.get("wait") or ["25"])[0])))
                except (TypeError, ValueError):
                    wait = 25
                payload = self.ctx.cache.wait_after(cursor, wait)
                if payload is None:
                    return self._send(204)
                return self._json(200, payload)

            try:
                return self._json(200, self.ctx.upstream.mobile_get(parsed.path, query))
            except UpstreamError as ex:
                return self._json(ex.status, {"detail": ex.detail})
            except Exception as ex:
                return self._json(502, {"detail": f"gateway upstream error: {type(ex).__name__}"})

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            try:
                body = self._body()
            except ValueError as ex:
                return self._json(400, {"detail": str(ex)})

            if parsed.path == "/v1/pair":
                peer = str(self.client_address[0])
                if not self.ctx.limiter.allow(peer):
                    self.ctx.audit.record("pair", status="rate_limited")
                    return self._json(429, {"detail": "too many pairing attempts"})
                supplied = str(body.get("pairing_secret") or "")
                if not hmac.compare_digest(supplied, self.ctx.pairing_secret):
                    self.ctx.audit.record("pair", status="denied")
                    return self._json(401, {"detail": "invalid pairing secret"})
                try:
                    device_id, refresh = self.ctx.devices.pair(str(body.get("device_name") or "ICARUS Mobile"))
                    session, exp = self.ctx.signer.issue(device_id)
                    self.ctx.audit.record("pair", device_id=device_id)
                    return self._json(201, {
                        "device_id": device_id,
                        "refresh_token": refresh,
                        "session_token": session,
                        "session_expires_at": exp,
                    })
                except ValueError as ex:
                    return self._json(400, {"detail": str(ex)})

            if parsed.path == "/v1/session":
                device_id = str(body.get("device_id") or "")
                refresh = str(body.get("refresh_token") or "")
                try:
                    rotated = self.ctx.devices.rotate_refresh(device_id, refresh)
                    session, exp = self.ctx.signer.issue(device_id)
                    self.ctx.audit.record("session_refresh", device_id=device_id)
                    return self._json(200, {
                        "device_id": device_id,
                        "refresh_token": rotated,
                        "session_token": session,
                        "session_expires_at": exp,
                    })
                except ValueError:
                    self.ctx.audit.record("session_refresh", status="denied", device_id=device_id)
                    return self._json(401, {"detail": "invalid device credential"})

            try:
                device_id = self._session_device()
            except AuthError as ex:
                return self._json(401, {"detail": str(ex)})

            if parsed.path == "/v1/revoke":
                self.ctx.devices.revoke(device_id)
                self.ctx.audit.record("revoke", device_id=device_id)
                return self._json(200, {"ok": True, "device_id": device_id, "revoked": True})

            if parsed.path == "/v1/notifications/register":
                try:
                    token = validate_push_token(str(body.get("expo_push_token") or ""))
                    platform = str(body.get("platform") or "").strip().lower()
                    if platform not in {"ios", "android"}:
                        raise ValueError("platform must be ios or android")
                    topics = body.get("topics", ["system"])
                    if not isinstance(topics, list) or not all(isinstance(x, str) for x in topics):
                        raise ValueError("topics must be a string array")
                    result = self.ctx.devices.set_push(device_id, token, platform, topics)
                    self.ctx.audit.record("push_register", device_id=device_id, metadata={"platform": platform, "topics": topics})
                    return self._json(200, result)
                except ValueError as ex:
                    return self._json(400, {"detail": str(ex)})

            if parsed.path == "/v1/notifications/unregister":
                self.ctx.devices.clear_push(device_id)
                self.ctx.audit.record("push_unregister", device_id=device_id)
                return self._json(200, {"enabled": False, "topics": []})

            if parsed.path == "/v1/backtest":
                if not self.ctx.actions.allow("backtest:" + device_id):
                    return self._json(429, {"detail": "backtest launch rate limit reached"})
                try:
                    result = self.ctx.upstream.mobile_post(parsed.path, body)
                    self.ctx.audit.record(
                        "backtest_start",
                        device_id=device_id,
                        metadata={
                            "asset": body.get("asset"),
                            "chart_type": body.get("chart_type"),
                            "session": body.get("session"),
                            "timeframe": body.get("timeframe"),
                            "job": result.get("job") if isinstance(result, dict) else None,
                        },
                    )
                    return self._json(200, result)
                except UpstreamError as ex:
                    self.ctx.audit.record("backtest_start", status="upstream_error", device_id=device_id, detail=ex.detail)
                    return self._json(ex.status, {"detail": ex.detail})
                except Exception as ex:
                    return self._json(502, {"detail": f"gateway upstream error: {type(ex).__name__}"})

            return self._json(404, {"detail": "unknown mobile resource"})

    class GatewayHTTPServer(ThreadingHTTPServer):
        daemon_threads = True

        def server_close(self) -> None:
            self.gateway_context.cache.close()  # type: ignore[attr-defined]
            return super().server_close()

    srv = GatewayHTTPServer((host, int(port)), H)
    srv.gateway_context = context  # type: ignore[attr-defined]
    if start_background:
        cache.start()
    return srv
