"""Authenticated live transport over the durable ICARUS intelligence delivery plane."""
from __future__ import annotations

import argparse
import asyncio
import hmac
import ipaddress
import json
import math
import os
import queue
import secrets
import sqlite3
import threading
import time
from concurrent.futures import Future
from contextlib import asynccontextmanager
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.websockets import WebSocketDisconnect

from .intelligence_delivery import IntelligenceDeliveryPlane

PROTOCOL_VERSION = "icarus-intelligence-gateway-v1"
_ALLOWED_DELIVERY_METHODS = frozenset({"claim", "ack", "nack", "recover_expired", "metrics"})
_SENSITIVE_KEYS = frozenset({"authorization", "bearer", "bearer_token", "token", "ticket", "lease_token", "secret", "password"})


class GatewayError(RuntimeError):
    pass


class GatewaySecurityError(GatewayError):
    pass


class GatewayBusyError(GatewayError):
    pass


class GatewaySessionError(GatewayError):
    pass


class GatewayRequestError(GatewayError):
    pass


def _positive_int(v: Any, name: str) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return v


def _positive_finite(v: Any, name: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)) or float(v) <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return float(v)


def _identifier(v: Any, name: str, limit: int = 240) -> str:
    if not isinstance(v, str):
        raise ValueError(f"{name} must be a string")
    v = v.strip()
    if not v:
        raise ValueError(f"{name} is required")
    if len(v) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return v


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_bind_host(host: str, *, allow_remote: bool) -> str:
    host = _identifier(host, "host", 255)
    if not isinstance(allow_remote, bool):
        raise ValueError("allow_remote must be boolean")
    if host.lower() == "localhost":
        return host
    candidate = host[1:-1] if host.startswith("[") and host.endswith("]") else host
    try:
        address = ipaddress.ip_address(candidate)
    except ValueError as exc:
        if allow_remote:
            return host
        raise ValueError("non-loopback bind requires explicit remote enablement") from exc
    if not address.is_loopback and not allow_remote:
        raise ValueError("non-loopback bind requires explicit remote enablement")
    return host


def _host_without_port(value: str) -> str:
    value = value.strip()
    if not value or any(ch in value for ch in ("/", "@", " ", "\t", "\r", "\n")):
        raise GatewaySecurityError("host rejected")
    if value.startswith("["):
        end = value.find("]")
        if end < 0:
            raise GatewaySecurityError("host rejected")
        suffix = value[end + 1 :]
        if suffix and (not suffix.startswith(":") or not suffix[1:].isdigit()):
            raise GatewaySecurityError("host rejected")
        return value[: end + 1].lower()
    if value.count(":") > 1:
        raise GatewaySecurityError("host rejected")
    if ":" in value:
        host, port = value.rsplit(":", 1)
        if not host or not port.isdigit():
            raise GatewaySecurityError("host rejected")
        return host.lower()
    return value.lower()


def validate_host_header(host_header: str | None, allowed_hosts: frozenset[str]) -> None:
    if host_header is None or not isinstance(host_header, str):
        raise GatewaySecurityError("host rejected")
    allowed = {x.strip().lower() for x in allowed_hosts if isinstance(x, str) and x.strip()}
    if _host_without_port(host_header) not in allowed:
        raise GatewaySecurityError("host rejected")


def validate_origin(origin: str | None, allowed_origins: frozenset[str]) -> None:
    if origin in (None, ""):
        return
    if not isinstance(origin, str) or origin not in allowed_origins:
        raise GatewaySecurityError("origin rejected")


def bearer_matches(presented: str | None, expected: str) -> bool:
    if not isinstance(presented, str) or not isinstance(expected, str) or not expected:
        return False
    try:
        return hmac.compare_digest(presented.encode("utf-8"), expected.encode("utf-8"))
    except UnicodeEncodeError:
        return False


def _redact_obj(v: Any) -> Any:
    if isinstance(v, dict):
        return {str(k): "[REDACTED]" if str(k).lower() in _SENSITIVE_KEYS else _redact_obj(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set, frozenset)):
        return [_redact_obj(x) for x in v]
    if is_dataclass(v) and not isinstance(v, type):
        return _redact_obj({f.name: getattr(v, f.name) for f in fields(v)})
    return v


def redact_for_log(value: object, *, secrets_to_hide: tuple[str, ...] = ()) -> str:
    try:
        out = json.dumps(_redact_obj(value), sort_keys=True, default=str, ensure_ascii=False)
    except Exception:
        out = repr(value)
    for secret in secrets_to_hide:
        if isinstance(secret, str) and secret:
            out = out.replace(secret, "[REDACTED]")
    return out


@dataclass(frozen=True)
class GatewayConfig:
    host: str = "127.0.0.1"
    allow_remote: bool = False
    allowed_hosts: frozenset[str] = frozenset({"127.0.0.1", "localhost", "[::1]"})
    allowed_origins: frozenset[str] = frozenset()
    auth_timeout_seconds: float = 5.0
    heartbeat_seconds: float = 10.0
    client_idle_timeout_seconds: float = 60.0
    idle_poll_seconds: float = 0.25
    recovery_seconds: float = 1.0
    recovery_limit: int = 100
    default_lease_seconds: int = 30
    default_max_inflight: int = 16
    max_sessions: int = 256
    max_unused_tickets: int = 1024
    ticket_ttl_seconds: float = 30.0
    executor_queue_capacity: int = 128
    max_json_body_bytes: int = 32 * 1024
    max_ws_text_bytes: int = 64 * 1024

    def __post_init__(self) -> None:
        validate_bind_host(self.host, allow_remote=self.allow_remote)
        if not isinstance(self.allowed_hosts, frozenset) or not self.allowed_hosts:
            raise ValueError("allowed_hosts must be a non-empty frozenset")
        if not isinstance(self.allowed_origins, frozenset):
            raise ValueError("allowed_origins must be a frozenset")
        for n in ("auth_timeout_seconds", "heartbeat_seconds", "client_idle_timeout_seconds", "idle_poll_seconds", "recovery_seconds"):
            _positive_finite(getattr(self, n), n)
        if _positive_finite(self.ticket_ttl_seconds, "ticket_ttl_seconds") > 30:
            raise ValueError("ticket_ttl_seconds must be <= 30")
        for n in ("recovery_limit", "max_sessions", "max_unused_tickets", "executor_queue_capacity", "max_json_body_bytes", "max_ws_text_bytes"):
            _positive_int(getattr(self, n), n)
        if isinstance(self.default_max_inflight, bool) or not isinstance(self.default_max_inflight, int) or not 1 <= self.default_max_inflight <= 256:
            raise ValueError("default_max_inflight must be in [1, 256]")
        if isinstance(self.default_lease_seconds, bool) or not isinstance(self.default_lease_seconds, int) or not 5 <= self.default_lease_seconds <= 300:
            raise ValueError("default_lease_seconds must be in [5, 300]")


@dataclass(frozen=True)
class SessionBinding:
    subscription_id: str
    revision: int
    consumer_id: str
    lease_seconds: int
    max_inflight: int

    def __post_init__(self) -> None:
        _identifier(self.subscription_id, "subscription_id")
        _identifier(self.consumer_id, "consumer_id")
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 1:
            raise ValueError("revision must be an integer >= 1")
        if isinstance(self.lease_seconds, bool) or not isinstance(self.lease_seconds, int) or not 5 <= self.lease_seconds <= 300:
            raise ValueError("lease_seconds must be in [5, 300]")
        if isinstance(self.max_inflight, bool) or not isinstance(self.max_inflight, int) or not 1 <= self.max_inflight <= 256:
            raise ValueError("max_inflight must be in [1, 256]")


@dataclass
class GatewaySession:
    session_id: str
    transport: str
    binding: SessionBinding
    connected_at: str
    last_client_activity_at: str
    last_server_activity_at: str
    inflight_delivery_ids: set[str]
    closed: bool = False


class TicketStore:
    def __init__(self, *, max_tickets: int, ttl_seconds: float, token_factory: Callable[[], str] | None = None):
        self._max = _positive_int(max_tickets, "max_tickets")
        self._ttl = _positive_finite(ttl_seconds, "ttl_seconds")
        if self._ttl > 30:
            raise ValueError("ttl_seconds must be <= 30")
        self._factory = token_factory or (lambda: secrets.token_urlsafe(32))
        self._tickets: dict[str, tuple[float, SessionBinding]] = {}
        self._lock = threading.Lock()

    def _purge(self, now: float) -> None:
        for token in [token for token, (expires, _) in self._tickets.items() if expires <= now]:
            self._tickets.pop(token, None)

    def issue(self, binding: SessionBinding, *, now_monotonic: float) -> str:
        if not isinstance(binding, SessionBinding):
            raise ValueError("binding must be SessionBinding")
        now = float(now_monotonic)
        if not math.isfinite(now):
            raise ValueError("now_monotonic must be finite")
        with self._lock:
            self._purge(now)
            if len(self._tickets) >= self._max:
                raise GatewayBusyError("ticket store is full")
            token = _identifier(self._factory(), "ticket", 512)
            if token in self._tickets:
                raise GatewayBusyError("ticket collision")
            self._tickets[token] = (now + self._ttl, binding)
            return token

    def consume(self, ticket: str, *, now_monotonic: float) -> SessionBinding:
        ticket = _identifier(ticket, "ticket", 512)
        now = float(now_monotonic)
        with self._lock:
            self._purge(now)
            item = self._tickets.pop(ticket, None)
            if item is None:
                raise GatewaySecurityError("stream authentication failed")
            return item[1]

    def count(self, *, now_monotonic: float) -> int:
        now = float(now_monotonic)
        with self._lock:
            self._purge(now)
            return len(self._tickets)

    def __repr__(self) -> str:
        with self._lock:
            return f"<TicketStore count={len(self._tickets)} capacity={self._max}>"


class SessionRegistry:
    def __init__(self, *, max_sessions: int, session_id_factory: Callable[[], str] | None = None):
        self._max = _positive_int(max_sessions, "max_sessions")
        self._factory = session_id_factory or (lambda: secrets.token_urlsafe(24))
        self._sessions: dict[str, GatewaySession] = {}
        self._lock = threading.RLock()

    def create(self, transport: str, binding: SessionBinding, *, now: str) -> GatewaySession:
        if transport not in {"websocket", "sse"}:
            raise ValueError("transport must be websocket or sse")
        if not isinstance(binding, SessionBinding):
            raise ValueError("binding must be SessionBinding")
        now = _identifier(now, "now", 80)
        with self._lock:
            if len(self._sessions) >= self._max:
                raise GatewayBusyError("session registry is full")
            sid = _identifier(self._factory(), "session_id", 256)
            if sid in self._sessions:
                raise GatewayBusyError("session id collision")
            session = GatewaySession(sid, transport, binding, now, now, now, set())
            self._sessions[sid] = session
            return session

    def get(self, sid: str) -> GatewaySession | None:
        sid = _identifier(sid, "session_id", 256)
        with self._lock:
            return self._sessions.get(sid)

    def close(self, sid: str) -> tuple[str, ...]:
        sid = _identifier(sid, "session_id", 256)
        with self._lock:
            session = self._sessions.pop(sid, None)
            if session is None:
                return ()
            session.closed = True
            return tuple(sorted(session.inflight_delivery_ids))

    def add_inflight(self, sid: str, did: str) -> None:
        sid = _identifier(sid, "session_id", 256)
        did = _identifier(did, "delivery_id", 256)
        with self._lock:
            session = self._sessions.get(sid)
            if session is None or session.closed:
                raise GatewaySessionError("session is not active")
            if did not in session.inflight_delivery_ids and len(session.inflight_delivery_ids) >= session.binding.max_inflight:
                raise GatewayBusyError("session in-flight window is full")
            session.inflight_delivery_ids.add(did)

    def remove_inflight(self, sid: str, did: str) -> bool:
        sid = _identifier(sid, "session_id", 256)
        did = _identifier(did, "delivery_id", 256)
        with self._lock:
            session = self._sessions.get(sid)
            if session is None or did not in session.inflight_delivery_ids:
                return False
            session.inflight_delivery_ids.remove(did)
            return True

    def contains_inflight(self, sid: str, did: str) -> bool:
        sid = _identifier(sid, "session_id", 256)
        did = _identifier(did, "delivery_id", 256)
        with self._lock:
            session = self._sessions.get(sid)
            return bool(session and not session.closed and did in session.inflight_delivery_ids)

    def available_capacity(self, sid: str) -> tuple[GatewaySession, int]:
        sid = _identifier(sid, "session_id", 256)
        with self._lock:
            session = self._sessions.get(sid)
            if session is None or session.closed:
                raise GatewaySessionError("session is not active")
            return session, max(0, session.binding.max_inflight - len(session.inflight_delivery_ids))

    def remove_inflight_everywhere(self, did: str) -> int:
        did = _identifier(did, "delivery_id", 256)
        removed = 0
        with self._lock:
            for session in self._sessions.values():
                if did in session.inflight_delivery_ids:
                    session.inflight_delivery_ids.remove(did)
                    removed += 1
        return removed

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            sessions = tuple(self._sessions.values())
            return {
                "active_sessions": len(sessions),
                "websocket_sessions": sum(s.transport == "websocket" for s in sessions),
                "sse_sessions": sum(s.transport == "sse" for s in sessions),
                "inflight_total": sum(len(s.inflight_delivery_ids) for s in sessions),
            }


@dataclass
class _DeliveryCall:
    method: str
    args: tuple[object, ...]
    kwargs: dict[str, object]
    future: Future[object]
    dequeued: threading.Event


class DeliveryExecutor:
    def __init__(self, db_path: str, *, plane_factory: Callable[[str], object] = IntelligenceDeliveryPlane, queue_capacity: int = 128):
        self._db_path = _identifier(db_path, "db_path", 4096)
        self._factory = plane_factory
        self._queue: queue.Queue[_DeliveryCall | None] = queue.Queue(maxsize=_positive_int(queue_capacity, "queue_capacity"))
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._startup_error: BaseException | None = None
        self._started = False
        self._closed = False
        self._lock = threading.Lock()
        self._sat = 0
        self._active = 0

    @property
    def started(self) -> bool:
        return self._started

    @property
    def queue_depth(self) -> int:
        return self._queue.qsize()

    @property
    def saturation_count(self) -> int:
        with self._lock:
            return self._sat

    def start(self) -> None:
        if self._started:
            return
        if self._closed:
            raise RuntimeError("delivery executor is closed")
        self._ready.clear()
        self._startup_error = None
        self._thread = threading.Thread(target=self._run, name="icarus-intelligence-delivery", daemon=True)
        self._thread.start()
        self._ready.wait()
        if self._startup_error is not None:
            error = self._startup_error
            self._thread.join(timeout=5)
            self._thread = None
            self._started = False
            raise error
        self._started = True

    def submit(self, method: str, /, *args: object, **kwargs: object) -> Future[object]:
        if not self._started or self._closed:
            raise RuntimeError("delivery executor is not running")
        future: Future[object] = Future()
        call = _DeliveryCall(str(method), tuple(args), dict(kwargs), future, threading.Event())
        with self._lock:
            wait = self._active == 0
        try:
            self._queue.put_nowait(call)
        except queue.Full as exc:
            with self._lock:
                self._sat += 1
            raise GatewayBusyError("delivery executor queue is full") from exc
        if wait:
            call.dequeued.wait(timeout=0.25)
        return future

    async def call(self, method: str, /, *args: object, **kwargs: object) -> object:
        submitted = await asyncio.to_thread(self.submit, method, *args, **kwargs)
        return await asyncio.wrap_future(submitted)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._thread is not None and self._thread.is_alive():
            self._queue.put(None)
            self._thread.join(timeout=10)
        self._thread = None
        self._started = False

    def _run(self) -> None:
        plane = None
        try:
            plane = self._factory(self._db_path)
        except BaseException as exc:
            self._startup_error = exc
            self._ready.set()
            return
        self._ready.set()
        try:
            while True:
                call = self._queue.get()
                if call is None:
                    self._queue.task_done()
                    break
                with self._lock:
                    self._active += 1
                call.dequeued.set()
                try:
                    if not call.future.set_running_or_notify_cancel():
                        continue
                    if call.method not in _ALLOWED_DELIVERY_METHODS:
                        raise ValueError(f"unsupported delivery operation: {call.method}")
                    result = getattr(plane, call.method)(*call.args, **call.kwargs)
                except BaseException as exc:
                    call.future.set_exception(exc)
                else:
                    call.future.set_result(result)
                finally:
                    with self._lock:
                        self._active -= 1
                    self._queue.task_done()
        finally:
            close = getattr(plane, "close", None)
            if callable(close):
                close()


class IntelligenceGatewayService:
    def __init__(self, *, executor: Any, config: GatewayConfig | None = None, session_registry: SessionRegistry | None = None, ticket_store: TicketStore | None = None):
        self.config = config or GatewayConfig()
        self.executor = executor
        self.sessions = session_registry or SessionRegistry(max_sessions=self.config.max_sessions)
        self.tickets = ticket_store or TicketStore(max_tickets=self.config.max_unused_tickets, ttl_seconds=self.config.ticket_ttl_seconds)
        self._started = False
        self._closed = False
        self._recovery_task: asyncio.Task[None] | None = None

    async def _recovery_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.config.recovery_seconds)
                try:
                    await self.recover_expired(now=_utc_now())
                except asyncio.CancelledError:
                    raise
                except Exception:
                    continue
        except asyncio.CancelledError:
            return

    async def start(self) -> None:
        if self._closed:
            raise RuntimeError("gateway service is closed")
        if not self._started:
            self.executor.start()
            self._started = True
            self._recovery_task = asyncio.create_task(self._recovery_loop())

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        task = self._recovery_task
        self._recovery_task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self.executor.close()
        self._started = False

    def create_ws_session(self, binding: SessionBinding, *, now: str) -> GatewaySession:
        return self.sessions.create("websocket", binding, now=now)

    def create_sse_ticket(self, binding: SessionBinding, *, now_monotonic: float) -> str:
        return self.tickets.issue(binding, now_monotonic=now_monotonic)

    def consume_sse_ticket(self, ticket: str, *, now_monotonic: float, now: str) -> GatewaySession:
        return self.sessions.create("sse", self.tickets.consume(ticket, now_monotonic=now_monotonic), now=now)

    def _require(self, sid: str) -> GatewaySession:
        session = self.sessions.get(sid)
        if session is None or session.closed:
            raise GatewaySessionError("session is not active")
        return session

    async def claim_for_session(self, sid: str, *, now: str) -> list[dict[str, object]]:
        session, available = self.sessions.available_capacity(sid)
        if available <= 0:
            return []
        result = await self.executor.call(
            "claim",
            session.binding.subscription_id,
            session.binding.revision,
            session.binding.consumer_id,
            as_of=now,
            lease_seconds=session.binding.lease_seconds,
            limit=available,
        )
        if not isinstance(result, list) or len(result) > available:
            raise GatewayError("invalid claim batch")
        ids: list[str] = []
        for item in result:
            if not isinstance(item, Mapping):
                raise GatewayError("invalid delivery")
            ids.append(_identifier(item.get("delivery_id"), "delivery_id", 256))
        for did in ids:
            self.sessions.add_inflight(sid, did)
        return result

    async def ack_for_session(self, sid: str, did: str, token: str, *, now: str) -> dict[str, object]:
        session = self._require(sid)
        did = _identifier(did, "delivery_id", 256)
        token = _identifier(token, "lease_token", 512)
        if not self.sessions.contains_inflight(sid, did):
            raise GatewaySessionError("delivery is not in this session")
        result = await self.executor.call("ack", did, session.binding.consumer_id, token, as_of=now)
        if not isinstance(result, Mapping):
            raise GatewayError("invalid ACK result")
        self.sessions.remove_inflight(sid, did)
        return dict(result)

    async def nack_for_session(self, sid: str, did: str, token: str, *, now: str, reason: Mapping[str, object] | None = None) -> dict[str, object]:
        session = self._require(sid)
        did = _identifier(did, "delivery_id", 256)
        token = _identifier(token, "lease_token", 512)
        if not self.sessions.contains_inflight(sid, did):
            raise GatewaySessionError("delivery is not in this session")
        if reason is not None and not isinstance(reason, Mapping):
            raise ValueError("reason must be a mapping")
        reason_dict = dict(reason or {})
        result = await self.executor.call("nack", did, session.binding.consumer_id, token, as_of=now, reason=reason_dict)
        if not isinstance(result, Mapping):
            raise GatewayError("invalid NACK result")
        self.sessions.remove_inflight(sid, did)
        return dict(result)

    async def recover_expired(self, *, now: str) -> list[dict[str, object]]:
        result = await self.executor.call("recover_expired", as_of=now, limit=self.config.recovery_limit)
        if not isinstance(result, list):
            raise GatewayError("invalid recovery batch")
        for item in result:
            if not isinstance(item, Mapping):
                raise GatewayError("invalid recovered delivery")
            self.sessions.remove_inflight_everywhere(_identifier(item.get("delivery_id"), "delivery_id", 256))
        return result

    async def durable_metrics(self, subscription_id: str, revision: int, *, now: str) -> dict[str, object]:
        result = await self.executor.call("metrics", subscription_id, revision, as_of=now)
        if not isinstance(result, Mapping):
            raise GatewayError("invalid metrics")
        return dict(result)

    def ephemeral_metrics(self) -> dict[str, object]:
        out = dict(self.sessions.snapshot())
        out.update({
            "unused_tickets": self.tickets.count(now_monotonic=time.monotonic()),
            "executor_queue_depth": int(getattr(self.executor, "queue_depth", 0)),
            "executor_saturation_count": int(getattr(self.executor, "saturation_count", 0)),
            "ephemeral": True,
            "execution_authorized": False,
            "production_decision_authorized": False,
        })
        return out

    def close_session(self, sid: str) -> tuple[str, ...]:
        return self.sessions.close(sid)


def _authority_payload(**values: object) -> dict[str, object]:
    values["execution_authorized"] = False
    values["production_decision_authorized"] = False
    return values


def _error_payload(code: str, message: str, *, retryable: bool = False) -> dict[str, object]:
    return _authority_payload(code=code, message=message, retryable=retryable)


def error_frame(code: str, *, message: str, retryable: bool, request_id: str | None = None) -> dict[str, object]:
    out = _authority_payload(type="error", code=code, message=message, retryable=retryable)
    if request_id is not None:
        out["request_id"] = request_id
    return out


def heartbeat_frame(session: GatewaySession, *, server_time: str, sequence_lag: int | None = None) -> dict[str, object]:
    out = _authority_payload(
        type="heartbeat",
        session_id=session.session_id,
        server_time=server_time,
        inflight=len(session.inflight_delivery_ids),
        max_inflight=session.binding.max_inflight,
    )
    if sequence_lag is not None:
        out["sequence_lag"] = sequence_lag
    return out


def delivery_frame(session: GatewaySession, delivery: Mapping[str, object]) -> dict[str, object]:
    return _authority_payload(
        type="delivery",
        session_id=session.session_id,
        delivery_id=delivery.get("delivery_id"),
        event_id=delivery.get("event_id"),
        journal_sequence=delivery.get("journal_sequence"),
        attempt=delivery.get("attempt"),
        lease_token=delivery.get("lease_token"),
        lease_expires_at=delivery.get("lease_expires_at"),
        event=delivery.get("event"),
    )


def _hello_frame(session: GatewaySession, config: GatewayConfig, *, server_time: str) -> dict[str, object]:
    return _authority_payload(
        type="hello",
        protocol=PROTOCOL_VERSION,
        session_id=session.session_id,
        subscription_id=session.binding.subscription_id,
        revision=session.binding.revision,
        consumer_id=session.binding.consumer_id,
        heartbeat_seconds=config.heartbeat_seconds,
        lease_seconds=session.binding.lease_seconds,
        max_inflight=session.binding.max_inflight,
        server_time=server_time,
    )


def encode_sse(event: str, payload: Mapping[str, object]) -> bytes:
    event = _identifier(event, "SSE event", 80)
    if any(ch in event for ch in ("\r", "\n")):
        raise ValueError("SSE event must be a single line")
    if not isinstance(payload, Mapping):
        raise ValueError("SSE payload must be a mapping")
    raw = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=False)
    return f"event: {event}\ndata: {raw}\n\n".encode("utf-8")


def _bearer_from_request(request: Request) -> str | None:
    header = request.headers.get("authorization")
    return header[7:] if header and header.startswith("Bearer ") and header[7:] else None


def _reject_json_constant(v: str):
    raise ValueError(f"non-finite JSON constant: {v}")


async def _strict_json_request(request: Request, *, max_bytes: int) -> dict[str, object]:
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > max_bytes:
            raise GatewayRequestError("request body too large")
        raw.extend(chunk)
    try:
        parsed = json.loads(raw.decode("utf-8"), parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise GatewayRequestError("invalid JSON body") from exc
    if not isinstance(parsed, dict):
        raise GatewayRequestError("JSON object required")
    return parsed


def _strict_ws_json(text: str, *, max_bytes: int) -> dict[str, object]:
    if not isinstance(text, str) or len(text.encode("utf-8")) > max_bytes:
        raise GatewayRequestError("invalid WebSocket frame")
    try:
        parsed = json.loads(text, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise GatewayRequestError("invalid WebSocket frame") from exc
    if not isinstance(parsed, dict):
        raise GatewayRequestError("invalid WebSocket frame")
    return parsed


def _binding_from_mapping(body: Mapping[str, object], config: GatewayConfig) -> SessionBinding:
    return SessionBinding(
        body.get("subscription_id"),
        body.get("revision"),
        body.get("consumer_id"),
        body.get("lease_seconds", config.default_lease_seconds),
        body.get("max_inflight", config.default_max_inflight),
    )


def _require_sse_session_control(service: IntelligenceGatewayService, body: Mapping[str, object]) -> tuple[GatewaySession, str, str]:
    try:
        sid = _identifier(body.get("session_id"), "session_id", 256)
        cid = _identifier(body.get("consumer_id"), "consumer_id")
        did = _identifier(body.get("delivery_id"), "delivery_id", 256)
        session = service.sessions.get(sid)
    except ValueError as exc:
        raise GatewaySessionError("session control invalid") from exc
    if session is None or session.closed or session.transport != "sse" or session.binding.consumer_id != cid or not service.sessions.contains_inflight(sid, did):
        raise GatewaySessionError("session control invalid")
    return session, sid, did


def create_intelligence_gateway_app(*, db_path: str, bearer_token: str, config: GatewayConfig | None = None, plane_factory: Callable[..., object] = IntelligenceDeliveryPlane) -> FastAPI:
    if not isinstance(db_path, str) or not db_path.strip():
        raise ValueError("file-backed db_path is required")
    low = db_path.strip().lower()
    if low == ":memory:" or "mode=memory" in low or low.startswith("file::memory:"):
        raise ValueError("production gateway requires a file-backed database")
    bearer_token = _identifier(bearer_token, "bearer_token", 4096)
    config = config or GatewayConfig()
    executor = DeliveryExecutor(db_path, plane_factory=plane_factory, queue_capacity=config.executor_queue_capacity)
    service = IntelligenceGatewayService(executor=executor, config=config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await service.start()
        try:
            yield
        finally:
            await service.close()

    app = FastAPI(lifespan=lifespan)
    app.state.gateway_service = service
    app.state.gateway_config = config
    app.state.gateway_bearer = bearer_token

    @app.middleware("http")
    async def host_guard(request: Request, call_next):
        try:
            validate_host_header(request.headers.get("host"), config.allowed_hosts)
        except GatewaySecurityError:
            return JSONResponse(status_code=400, content=_error_payload("HOST_REJECTED", "request host rejected"))
        return await call_next(request)

    def authenticated(request: Request) -> bool:
        return bearer_matches(_bearer_from_request(request), bearer_token)

    def auth_failure():
        return JSONResponse(status_code=401, content=_error_payload("AUTH_FAILED", "authentication failed"))

    def request_failure(*, too_large: bool = False):
        return JSONResponse(status_code=413 if too_large else 400, content=_error_payload("INVALID_REQUEST", "request is invalid"))

    def operation_failure(exc: BaseException):
        if isinstance(exc, sqlite3.Error):
            return JSONResponse(status_code=503, content=_error_payload("DELIVERY_STORE_UNAVAILABLE", "delivery store is unavailable", retryable=True))
        if isinstance(exc, GatewayBusyError):
            return JSONResponse(status_code=503, content=_error_payload("GATEWAY_BUSY", "gateway is busy", retryable=True))
        if isinstance(exc, GatewaySessionError):
            return JSONResponse(status_code=409, content=_error_payload("SESSION_INVALID", "session control is invalid"))
        return JSONResponse(status_code=409, content=_error_payload("DELIVERY_STATE_INVALID", "delivery operation failed"))

    @app.get("/healthz")
    async def healthz():
        return _authority_payload(ok=bool(executor.started), protocol=PROTOCOL_VERSION, delivery_store_reachable=bool(executor.started))

    @app.websocket("/v1/intelligence/ws")
    async def intelligence_websocket(websocket: WebSocket):
        session: GatewaySession | None = None
        try:
            try:
                validate_host_header(websocket.headers.get("host"), config.allowed_hosts)
                validate_origin(websocket.headers.get("origin"), config.allowed_origins)
            except GatewaySecurityError:
                await websocket.close(code=1008)
                return
            await websocket.accept()
            try:
                auth_text = await asyncio.wait_for(websocket.receive_text(), timeout=config.auth_timeout_seconds)
            except asyncio.TimeoutError:
                await websocket.close(code=1008)
                return
            try:
                auth = _strict_ws_json(auth_text, max_bytes=config.max_ws_text_bytes)
            except GatewayRequestError:
                await websocket.send_json(error_frame("INVALID_FRAME", message="authentication frame is invalid", retryable=False))
                await websocket.close(code=1008)
                return
            if auth.get("type") != "authenticate":
                await websocket.send_json(error_frame("INVALID_FRAME", message="authentication frame is required", retryable=False))
                await websocket.close(code=1008)
                return
            if auth.get("protocol") != PROTOCOL_VERSION:
                await websocket.send_json(error_frame("PROTOCOL_UNSUPPORTED", message="protocol is unsupported", retryable=False))
                await websocket.close(code=1008)
                return
            token = auth.get("token")
            if not bearer_matches(token if isinstance(token, str) else None, bearer_token):
                await websocket.send_json(error_frame("AUTH_FAILED", message="authentication failed", retryable=False))
                await websocket.close(code=1008)
                return
            try:
                session = service.create_ws_session(_binding_from_mapping(auth, config), now=_utc_now())
            except (ValueError, GatewayBusyError):
                await websocket.send_json(error_frame("INVALID_REQUEST", message="session request is invalid", retryable=False))
                await websocket.close(code=1008)
                return
            await websocket.send_json(_hello_frame(session, config, server_time=_utc_now()))
            try:
                claimed = await service.claim_for_session(session.session_id, now=_utc_now())
            except GatewayBusyError:
                claimed = []
            except BaseException:
                await websocket.send_json(error_frame("DELIVERY_STORE_UNAVAILABLE", message="delivery store is unavailable", retryable=True))
                await websocket.close(code=1011)
                return
            for delivery in claimed:
                await websocket.send_json(delivery_frame(session, delivery))
            last_hb = time.monotonic()
            while True:
                try:
                    text = await asyncio.wait_for(websocket.receive_text(), timeout=config.idle_poll_seconds)
                except asyncio.TimeoutError:
                    current = service.sessions.get(session.session_id)
                    if current is None:
                        return
                    if len(current.inflight_delivery_ids) < current.binding.max_inflight:
                        try:
                            claimed = await service.claim_for_session(current.session_id, now=_utc_now())
                        except GatewayBusyError:
                            claimed = []
                        except BaseException:
                            await websocket.send_json(error_frame("DELIVERY_STORE_UNAVAILABLE", message="delivery store is unavailable", retryable=True))
                            await websocket.close(code=1011)
                            return
                        for delivery in claimed:
                            await websocket.send_json(delivery_frame(current, delivery))
                    if time.monotonic() - last_hb >= config.heartbeat_seconds:
                        await websocket.send_json(heartbeat_frame(current, server_time=_utc_now()))
                        last_hb = time.monotonic()
                    continue
                frame = _strict_ws_json(text, max_bytes=config.max_ws_text_bytes)
                session.last_client_activity_at = _utc_now()
                typ = frame.get("type")
                rid = frame.get("request_id")
                rid = rid if isinstance(rid, str) and rid else None
                if typ == "ping":
                    await websocket.send_json(heartbeat_frame(session, server_time=_utc_now()))
                    last_hb = time.monotonic()
                    continue
                if typ not in {"ack", "nack"}:
                    await websocket.send_json(error_frame("INVALID_FRAME", message="frame type is unsupported", retryable=False, request_id=rid))
                    continue
                try:
                    did = _identifier(frame.get("delivery_id"), "delivery_id", 256)
                    lease_token = _identifier(frame.get("lease_token"), "lease_token", 512)
                    if typ == "ack":
                        result = await service.ack_for_session(session.session_id, did, lease_token, now=_utc_now())
                        out = _authority_payload(type="ack_result", request_id=rid, delivery_id=did, state=result.get("state"), server_time=_utc_now())
                    else:
                        reason = frame.get("reason")
                        if reason is not None and not isinstance(reason, Mapping):
                            raise ValueError("reason must be an object")
                        result = await service.nack_for_session(session.session_id, did, lease_token, now=_utc_now(), reason=reason)
                        out = _authority_payload(type="nack_result", request_id=rid, delivery_id=did, state=result.get("state"), server_time=_utc_now())
                    await websocket.send_json(out)
                except GatewaySessionError:
                    await websocket.send_json(error_frame("DELIVERY_NOT_IN_SESSION", message="delivery control rejected", retryable=False, request_id=rid))
                except GatewayBusyError:
                    await websocket.send_json(error_frame("GATEWAY_BUSY", message="gateway is busy", retryable=True, request_id=rid))
                except (ValueError, TypeError):
                    await websocket.send_json(error_frame("DELIVERY_STATE_INVALID", message="delivery operation failed", retryable=False, request_id=rid))
                except BaseException:
                    await websocket.send_json(error_frame("INTERNAL_ERROR", message="gateway operation failed", retryable=True, request_id=rid))
        except WebSocketDisconnect:
            pass
        except GatewayRequestError:
            if session is not None:
                try:
                    await websocket.send_json(error_frame("INVALID_FRAME", message="frame is invalid", retryable=False))
                except BaseException:
                    pass
        finally:
            if session is not None:
                service.close_session(session.session_id)

    @app.post("/v1/intelligence/tickets", status_code=201)
    async def issue_ticket(request: Request):
        if not authenticated(request):
            return auth_failure()
        try:
            body = await _strict_json_request(request, max_bytes=config.max_json_body_bytes)
            binding = _binding_from_mapping(body, config)
            ticket = service.create_sse_ticket(binding, now_monotonic=time.monotonic())
        except GatewayRequestError as exc:
            return request_failure(too_large="too large" in str(exc))
        except (ValueError, TypeError):
            return request_failure()
        except GatewayBusyError as exc:
            return operation_failure(exc)
        return _authority_payload(protocol=PROTOCOL_VERSION, ticket=ticket)

    @app.get("/v1/intelligence/stream")
    async def intelligence_stream(request: Request):
        ticket = request.query_params.get("ticket")
        try:
            session = service.consume_sse_ticket(_identifier(ticket, "ticket", 512), now_monotonic=time.monotonic(), now=_utc_now())
        except (ValueError, GatewaySecurityError, GatewayBusyError):
            return auth_failure()

        async def events():
            last_hb = time.monotonic()
            flow_announced = False
            try:
                yield encode_sse("hello", _hello_frame(session, config, server_time=_utc_now()))
                while True:
                    if await request.is_disconnected():
                        return
                    current = service.sessions.get(session.session_id)
                    if current is None:
                        return
                    available = current.binding.max_inflight - len(current.inflight_delivery_ids)
                    if available > 0:
                        flow_announced = False
                        try:
                            claimed = await service.claim_for_session(current.session_id, now=_utc_now())
                        except GatewayBusyError:
                            claimed = []
                        except BaseException:
                            yield encode_sse("error", error_frame("DELIVERY_STORE_UNAVAILABLE", message="delivery store is unavailable", retryable=True))
                            return
                        for delivery in claimed:
                            yield encode_sse("delivery", delivery_frame(current, delivery))
                        current = service.sessions.get(session.session_id)
                        if current is None:
                            return
                    if len(current.inflight_delivery_ids) >= current.binding.max_inflight and not flow_announced:
                        yield encode_sse(
                            "flow",
                            _authority_payload(
                                type="flow",
                                paused=True,
                                reason="inflight_window_full",
                                inflight=len(current.inflight_delivery_ids),
                                max_inflight=current.binding.max_inflight,
                            ),
                        )
                        flow_announced = True
                    now_mono = time.monotonic()
                    if now_mono - last_hb >= config.heartbeat_seconds:
                        yield encode_sse("heartbeat", heartbeat_frame(current, server_time=_utc_now()))
                        last_hb = now_mono
                    await asyncio.sleep(config.idle_poll_seconds)
            finally:
                service.close_session(session.session_id)

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/v1/intelligence/metrics")
    async def metrics(request: Request):
        if not authenticated(request):
            return auth_failure()
        try:
            sid = _identifier(request.query_params.get("subscription_id"), "subscription_id")
            revision = int(request.query_params.get("revision") or 0)
            if revision < 1:
                raise ValueError
            durable = await service.durable_metrics(sid, revision, now=_utc_now())
        except (ValueError, TypeError):
            return request_failure()
        except BaseException as exc:
            return operation_failure(exc)
        return _authority_payload(durable=durable, gateway=service.ephemeral_metrics())

    @app.post("/v1/intelligence/ack")
    async def ack(request: Request):
        if not authenticated(request):
            return auth_failure()
        try:
            body = await _strict_json_request(request, max_bytes=config.max_json_body_bytes)
        except GatewayRequestError as exc:
            return request_failure(too_large="too large" in str(exc))
        try:
            _, sid, did = _require_sse_session_control(service, body)
            token = _identifier(body.get("lease_token"), "lease_token", 512)
            result = await service.ack_for_session(sid, did, token, now=_utc_now())
        except BaseException as exc:
            return operation_failure(exc)
        return _authority_payload(**dict(result))

    @app.post("/v1/intelligence/nack")
    async def nack(request: Request):
        if not authenticated(request):
            return auth_failure()
        try:
            body = await _strict_json_request(request, max_bytes=config.max_json_body_bytes)
        except GatewayRequestError as exc:
            return request_failure(too_large="too large" in str(exc))
        try:
            _, sid, did = _require_sse_session_control(service, body)
            token = _identifier(body.get("lease_token"), "lease_token", 512)
            reason = body.get("reason")
            if reason is not None and not isinstance(reason, Mapping):
                raise ValueError("reason must be an object")
            result = await service.nack_for_session(sid, did, token, now=_utc_now(), reason=reason)
        except BaseException as exc:
            return operation_failure(exc)
        return _authority_payload(**dict(result))

    return app


def _run_uvicorn(app: FastAPI, **kwargs: object) -> None:
    import uvicorn

    uvicorn.run(app, **kwargs)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ICARUS live intelligence gateway")
    parser.add_argument("--db", required=True, help="file-backed SQLite intelligence database")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8792)
    parser.add_argument("--allow-remote", action="store_true")
    parser.add_argument("--allowed-host", action="append", default=[])
    parser.add_argument("--allowed-origin", action="append", default=[])
    args = parser.parse_args(list(argv) if argv is not None else None)

    token = os.environ.get("ICARUS_INTELLIGENCE_GATEWAY_TOKEN", "").strip()
    if not token:
        parser.error("ICARUS_INTELLIGENCE_GATEWAY_TOKEN is required")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be in [1, 65535]")
    validate_bind_host(args.host, allow_remote=bool(args.allow_remote))

    default_hosts = frozenset({"127.0.0.1", "localhost", "[::1]"})
    config = GatewayConfig(
        host=args.host,
        allow_remote=bool(args.allow_remote),
        allowed_hosts=frozenset(args.allowed_host) if args.allowed_host else default_hosts,
        allowed_origins=frozenset(args.allowed_origin),
    )
    app = create_intelligence_gateway_app(db_path=args.db, bearer_token=token, config=config)
    _run_uvicorn(app, host=args.host, port=args.port, access_log=False, ws_max_size=config.max_ws_text_bytes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
