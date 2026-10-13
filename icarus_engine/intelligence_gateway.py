"""Live transport gateway for the ICARUS intelligence delivery plane.

Phase 3 owns transport/authentication state only. Phase 1 remains the canonical
intelligence journal and Phase 2 remains the canonical durable delivery state
machine. Nothing in this module authorizes trading or production decisions.
"""
from __future__ import annotations

import asyncio
import hmac
import ipaddress
import json
import math
import queue
import secrets
import threading
import time
from concurrent.futures import Future
from contextlib import asynccontextmanager
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .intelligence_delivery import IntelligenceDeliveryPlane

PROTOCOL_VERSION = "icarus-intelligence-gateway-v1"

_ALLOWED_DELIVERY_METHODS = frozenset({"claim", "ack", "nack", "recover_expired", "metrics"})
_SENSITIVE_KEYS = frozenset(
    {
        "authorization",
        "bearer",
        "bearer_token",
        "token",
        "ticket",
        "lease_token",
        "secret",
        "password",
    }
)


class GatewayError(RuntimeError):
    """Base class for gateway-local failures."""


class GatewaySecurityError(GatewayError):
    """Fail-closed request/bind security validation error."""


class GatewayBusyError(GatewayError):
    """A bounded gateway resource has no capacity."""


class GatewaySessionError(GatewayError):
    """Ephemeral gateway session is absent, closed, or lacks a delivery."""


class GatewayRequestError(GatewayError):
    """Bounded/strict external request validation error."""


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _positive_finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a positive finite number")
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return value


def _identifier(value: Any, name: str, limit: int = 240) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    value = value.strip()
    if not value:
        raise ValueError(f"{name} is required")
    if len(value) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return value


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_bind_host(host: str, *, allow_remote: bool) -> str:
    if not isinstance(host, str) or not host.strip():
        raise ValueError("host is required")
    host = host.strip()
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


def _host_without_port(host_header: str) -> str:
    value = host_header.strip()
    if not value or any(ch in value for ch in ("/", "@", " ", "\t", "\r", "\n")):
        raise GatewaySecurityError("host rejected")
    if value.startswith("["):
        end = value.find("]")
        if end < 0:
            raise GatewaySecurityError("host rejected")
        host = value[: end + 1]
        suffix = value[end + 1 :]
        if suffix and (not suffix.startswith(":") or not suffix[1:].isdigit()):
            raise GatewaySecurityError("host rejected")
        return host.lower()
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
    normalized_allowed = {item.strip().lower() for item in allowed_hosts if isinstance(item, str) and item.strip()}
    if _host_without_port(host_header) not in normalized_allowed:
        raise GatewaySecurityError("host rejected")


def validate_origin(origin: str | None, allowed_origins: frozenset[str]) -> None:
    if origin in (None, ""):
        return
    if not isinstance(origin, str) or origin not in allowed_origins:
        raise GatewaySecurityError("origin rejected")


def bearer_matches(presented: str | None, expected: str) -> bool:
    if presented is None or not isinstance(presented, str):
        return False
    if not isinstance(expected, str) or not expected:
        return False
    return hmac.compare_digest(presented, expected)


def _redacted_value(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            label = str(key)
            result[label] = "[REDACTED]" if label.lower() in _SENSITIVE_KEYS else _redacted_value(item)
        return result
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_redacted_value(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return _redacted_value({field.name: getattr(value, field.name) for field in fields(value)})
    return value


def redact_for_log(value: object, *, secrets_to_hide: tuple[str, ...] = ()) -> str:
    try:
        rendered = json.dumps(_redacted_value(value), sort_keys=True, default=str, ensure_ascii=False)
    except Exception:
        rendered = repr(value)
    for secret in secrets_to_hide:
        if isinstance(secret, str) and secret:
            rendered = rendered.replace(secret, "[REDACTED]")
    return rendered


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
        for name in (
            "auth_timeout_seconds",
            "heartbeat_seconds",
            "client_idle_timeout_seconds",
            "idle_poll_seconds",
            "recovery_seconds",
        ):
            _positive_finite(getattr(self, name), name)
        ttl = _positive_finite(self.ticket_ttl_seconds, "ticket_ttl_seconds")
        if ttl > 30.0:
            raise ValueError("ticket_ttl_seconds must be <= 30")
        for name in (
            "recovery_limit",
            "max_sessions",
            "max_unused_tickets",
            "executor_queue_capacity",
            "max_json_body_bytes",
            "max_ws_text_bytes",
        ):
            _positive_int(getattr(self, name), name)
        if (
            isinstance(self.default_max_inflight, bool)
            or not isinstance(self.default_max_inflight, int)
            or not 1 <= self.default_max_inflight <= 256
        ):
            raise ValueError("default_max_inflight must be in [1, 256]")
        if (
            isinstance(self.default_lease_seconds, bool)
            or not isinstance(self.default_lease_seconds, int)
            or not 5 <= self.default_lease_seconds <= 300
        ):
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
        if (
            isinstance(self.lease_seconds, bool)
            or not isinstance(self.lease_seconds, int)
            or not 5 <= self.lease_seconds <= 300
        ):
            raise ValueError("lease_seconds must be in [5, 300]")
        if (
            isinstance(self.max_inflight, bool)
            or not isinstance(self.max_inflight, int)
            or not 1 <= self.max_inflight <= 256
        ):
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
    """Process-local bounded one-use capability tickets for SSE bootstrap."""

    def __init__(
        self,
        *,
        max_tickets: int,
        ttl_seconds: float,
        token_factory: Callable[[], str] | None = None,
    ) -> None:
        self._max_tickets = _positive_int(max_tickets, "max_tickets")
        self._ttl_seconds = _positive_finite(ttl_seconds, "ttl_seconds")
        if self._ttl_seconds > 30.0:
            raise ValueError("ttl_seconds must be <= 30")
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(32))
        self._tickets: dict[str, tuple[float, SessionBinding]] = {}
        self._lock = threading.Lock()

    def _purge_locked(self, now_monotonic: float) -> None:
        expired = [token for token, (expires, _binding) in self._tickets.items() if expires <= now_monotonic]
        for token in expired:
            self._tickets.pop(token, None)

    def issue(self, binding: SessionBinding, *, now_monotonic: float) -> str:
        if not isinstance(binding, SessionBinding):
            raise ValueError("binding must be SessionBinding")
        now = float(now_monotonic)
        if not math.isfinite(now):
            raise ValueError("now_monotonic must be finite")
        with self._lock:
            self._purge_locked(now)
            if len(self._tickets) >= self._max_tickets:
                raise GatewayBusyError("ticket store is full")
            token = _identifier(self._token_factory(), "ticket", 512)
            if token in self._tickets:
                raise GatewayBusyError("ticket collision")
            self._tickets[token] = (now + self._ttl_seconds, binding)
            return token

    def consume(self, ticket: str, *, now_monotonic: float) -> SessionBinding:
        ticket = _identifier(ticket, "ticket", 512)
        now = float(now_monotonic)
        if not math.isfinite(now):
            raise ValueError("now_monotonic must be finite")
        with self._lock:
            self._purge_locked(now)
            item = self._tickets.pop(ticket, None)
            if item is None:
                raise GatewaySecurityError("stream authentication failed")
            return item[1]

    def count(self, *, now_monotonic: float) -> int:
        now = float(now_monotonic)
        if not math.isfinite(now):
            raise ValueError("now_monotonic must be finite")
        with self._lock:
            self._purge_locked(now)
            return len(self._tickets)

    def __repr__(self) -> str:
        with self._lock:
            return f"<TicketStore count={len(self._tickets)} capacity={self._max_tickets}>"


class SessionRegistry:
    """Thread-safe process-local gateway session registry."""

    def __init__(
        self,
        *,
        max_sessions: int,
        session_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._max_sessions = _positive_int(max_sessions, "max_sessions")
        self._session_id_factory = session_id_factory or (lambda: secrets.token_urlsafe(24))
        self._sessions: dict[str, GatewaySession] = {}
        self._lock = threading.RLock()

    def create(self, transport: str, binding: SessionBinding, *, now: str) -> GatewaySession:
        if transport not in {"websocket", "sse"}:
            raise ValueError("transport must be websocket or sse")
        if not isinstance(binding, SessionBinding):
            raise ValueError("binding must be SessionBinding")
        now = _identifier(now, "now", 80)
        with self._lock:
            if len(self._sessions) >= self._max_sessions:
                raise GatewayBusyError("session registry is full")
            session_id = _identifier(self._session_id_factory(), "session_id", 256)
            if session_id in self._sessions:
                raise GatewayBusyError("session id collision")
            session = GatewaySession(
                session_id=session_id,
                transport=transport,
                binding=binding,
                connected_at=now,
                last_client_activity_at=now,
                last_server_activity_at=now,
                inflight_delivery_ids=set(),
            )
            self._sessions[session_id] = session
            return session

    def get(self, session_id: str) -> GatewaySession | None:
        session_id = _identifier(session_id, "session_id", 256)
        with self._lock:
            return self._sessions.get(session_id)

    def close(self, session_id: str) -> tuple[str, ...]:
        session_id = _identifier(session_id, "session_id", 256)
        with self._lock:
            session = self._sessions.pop(session_id, None)
            if session is None:
                return ()
            session.closed = True
            return tuple(sorted(session.inflight_delivery_ids))

    def add_inflight(self, session_id: str, delivery_id: str) -> None:
        session_id = _identifier(session_id, "session_id", 256)
        delivery_id = _identifier(delivery_id, "delivery_id", 256)
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.closed:
                raise GatewaySessionError("session is not active")
            if (
                delivery_id not in session.inflight_delivery_ids
                and len(session.inflight_delivery_ids) >= session.binding.max_inflight
            ):
                raise GatewayBusyError("session in-flight window is full")
            session.inflight_delivery_ids.add(delivery_id)

    def remove_inflight(self, session_id: str, delivery_id: str) -> bool:
        session_id = _identifier(session_id, "session_id", 256)
        delivery_id = _identifier(delivery_id, "delivery_id", 256)
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or delivery_id not in session.inflight_delivery_ids:
                return False
            session.inflight_delivery_ids.remove(delivery_id)
            return True

    def contains_inflight(self, session_id: str, delivery_id: str) -> bool:
        session_id = _identifier(session_id, "session_id", 256)
        delivery_id = _identifier(delivery_id, "delivery_id", 256)
        with self._lock:
            session = self._sessions.get(session_id)
            return bool(session is not None and not session.closed and delivery_id in session.inflight_delivery_ids)

    def available_capacity(self, session_id: str) -> tuple[GatewaySession, int]:
        session_id = _identifier(session_id, "session_id", 256)
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.closed:
                raise GatewaySessionError("session is not active")
            return session, max(0, session.binding.max_inflight - len(session.inflight_delivery_ids))

    def remove_inflight_everywhere(self, delivery_id: str) -> int:
        delivery_id = _identifier(delivery_id, "delivery_id", 256)
        removed = 0
        with self._lock:
            for session in self._sessions.values():
                if delivery_id in session.inflight_delivery_ids:
                    session.inflight_delivery_ids.remove(delivery_id)
                    removed += 1
        return removed

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            sessions = tuple(self._sessions.values())
            return {
                "active_sessions": len(sessions),
                "websocket_sessions": sum(1 for session in sessions if session.transport == "websocket"),
                "sse_sessions": sum(1 for session in sessions if session.transport == "sse"),
                "inflight_total": sum(len(session.inflight_delivery_ids) for session in sessions),
            }


@dataclass
class _DeliveryCall:
    method: str
    args: tuple[object, ...]
    kwargs: dict[str, object]
    future: Future[object]
    dequeued: threading.Event


class DeliveryExecutor:
    """One bounded worker that exclusively owns the Phase 2 SQLite connection."""

    def __init__(
        self,
        db_path: str,
        *,
        plane_factory: Callable[[str], object] = IntelligenceDeliveryPlane,
        queue_capacity: int = 128,
    ) -> None:
        if not isinstance(db_path, str) or not db_path.strip():
            raise ValueError("db_path is required")
        self._db_path = db_path
        self._plane_factory = plane_factory
        self._queue: queue.Queue[_DeliveryCall | None] = queue.Queue(
            maxsize=_positive_int(queue_capacity, "queue_capacity")
        )
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._startup_error: BaseException | None = None
        self._started = False
        self._closed = False
        self._counter_lock = threading.Lock()
        self._saturation_count = 0
        self._active_count = 0

    @property
    def started(self) -> bool:
        return self._started

    @property
    def queue_depth(self) -> int:
        return self._queue.qsize()

    @property
    def saturation_count(self) -> int:
        with self._counter_lock:
            return self._saturation_count

    def start(self) -> None:
        if self._started:
            return
        if self._closed:
            raise RuntimeError("delivery executor is closed")
        self._ready.clear()
        self._startup_error = None
        self._thread = threading.Thread(
            target=self._run,
            name="icarus-intelligence-delivery",
            daemon=True,
        )
        self._thread.start()
        self._ready.wait()
        if self._startup_error is not None:
            error = self._startup_error
            if self._thread is not None:
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
        with self._counter_lock:
            wait_for_dequeue = self._active_count == 0
        try:
            self._queue.put_nowait(call)
        except queue.Full as exc:
            with self._counter_lock:
                self._saturation_count += 1
            raise GatewayBusyError("delivery executor queue is full") from exc
        if wait_for_dequeue:
            call.dequeued.wait(timeout=0.25)
        return future

    async def call(self, method: str, /, *args: object, **kwargs: object) -> object:
        return await asyncio.wrap_future(self.submit(method, *args, **kwargs))

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
        plane: object | None = None
        try:
            plane = self._plane_factory(self._db_path)
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
                with self._counter_lock:
                    self._active_count += 1
                call.dequeued.set()
                try:
                    if call.method not in _ALLOWED_DELIVERY_METHODS:
                        raise ValueError(f"unsupported delivery operation: {call.method}")
                    operation = getattr(plane, call.method)
                    result = operation(*call.args, **call.kwargs)
                except BaseException as exc:
                    call.future.set_exception(exc)
                else:
                    call.future.set_result(result)
                finally:
                    with self._counter_lock:
                        self._active_count -= 1
                    self._queue.task_done()
        finally:
            close = getattr(plane, "close", None)
            if callable(close):
                close()


class IntelligenceGatewayService:
    """Transport-neutral orchestration over Phase 2 and ephemeral gateway state."""

    def __init__(
        self,
        *,
        executor: Any,
        config: GatewayConfig | None = None,
        session_registry: SessionRegistry | None = None,
        ticket_store: TicketStore | None = None,
    ) -> None:
        self.config = config or GatewayConfig()
        self.executor = executor
        self.sessions = session_registry or SessionRegistry(max_sessions=self.config.max_sessions)
        self.tickets = ticket_store or TicketStore(
            max_tickets=self.config.max_unused_tickets,
            ttl_seconds=self.config.ticket_ttl_seconds,
        )
        self._started = False
        self._closed = False

    async def start(self) -> None:
        if self._closed:
            raise RuntimeError("gateway service is closed")
        if not self._started:
            self.executor.start()
            self._started = True

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.executor.close()
        self._started = False

    def create_ws_session(self, binding: SessionBinding, *, now: str) -> GatewaySession:
        return self.sessions.create("websocket", binding, now=now)

    def create_sse_ticket(self, binding: SessionBinding, *, now_monotonic: float) -> str:
        return self.tickets.issue(binding, now_monotonic=now_monotonic)

    def consume_sse_ticket(self, ticket: str, *, now_monotonic: float, now: str) -> GatewaySession:
        binding = self.tickets.consume(ticket, now_monotonic=now_monotonic)
        return self.sessions.create("sse", binding, now=now)

    def _require_session(self, session_id: str) -> GatewaySession:
        session = self.sessions.get(session_id)
        if session is None or session.closed:
            raise GatewaySessionError("session is not active")
        return session

    async def claim_for_session(self, session_id: str, *, now: str) -> list[dict[str, object]]:
        session, available = self.sessions.available_capacity(session_id)
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
        if not isinstance(result, list):
            raise GatewayError("delivery plane returned an invalid claim batch")
        if len(result) > available:
            raise GatewayError("delivery plane exceeded gateway in-flight limit")
        delivery_ids: list[str] = []
        for item in result:
            if not isinstance(item, Mapping):
                raise GatewayError("delivery plane returned an invalid delivery")
            delivery_ids.append(_identifier(item.get("delivery_id"), "delivery_id", 256))
        for delivery_id in delivery_ids:
            self.sessions.add_inflight(session_id, delivery_id)
        return result

    async def ack_for_session(
        self,
        session_id: str,
        delivery_id: str,
        lease_token: str,
        *,
        now: str,
    ) -> dict[str, object]:
        session = self._require_session(session_id)
        delivery_id = _identifier(delivery_id, "delivery_id", 256)
        lease_token = _identifier(lease_token, "lease_token", 512)
        if not self.sessions.contains_inflight(session_id, delivery_id):
            raise GatewaySessionError("delivery is not in this session")
        result = await self.executor.call(
            "ack",
            delivery_id,
            session.binding.consumer_id,
            lease_token,
            as_of=now,
        )
        if not isinstance(result, Mapping):
            raise GatewayError("delivery plane returned an invalid ACK result")
        self.sessions.remove_inflight(session_id, delivery_id)
        return dict(result)

    async def nack_for_session(
        self,
        session_id: str,
        delivery_id: str,
        lease_token: str,
        *,
        now: str,
        reason: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        session = self._require_session(session_id)
        delivery_id = _identifier(delivery_id, "delivery_id", 256)
        lease_token = _identifier(lease_token, "lease_token", 512)
        if not self.sessions.contains_inflight(session_id, delivery_id):
            raise GatewaySessionError("delivery is not in this session")
        if reason is not None and not isinstance(reason, Mapping):
            raise ValueError("reason must be a mapping")
        reason_dict = dict(reason or {})
        result = await self.executor.call(
            "nack",
            delivery_id,
            session.binding.consumer_id,
            lease_token,
            as_of=now,
            reason=reason_dict,
        )
        if not isinstance(result, Mapping):
            raise GatewayError("delivery plane returned an invalid NACK result")
        self.sessions.remove_inflight(session_id, delivery_id)
        return dict(result)

    async def recover_expired(self, *, now: str) -> list[dict[str, object]]:
        result = await self.executor.call(
            "recover_expired",
            as_of=now,
            limit=self.config.recovery_limit,
        )
        if not isinstance(result, list):
            raise GatewayError("delivery plane returned an invalid recovery batch")
        for item in result:
            if not isinstance(item, Mapping):
                raise GatewayError("delivery plane returned an invalid recovered delivery")
            delivery_id = _identifier(item.get("delivery_id"), "delivery_id", 256)
            self.sessions.remove_inflight_everywhere(delivery_id)
        return result

    async def durable_metrics(
        self,
        subscription_id: str,
        revision: int,
        *,
        now: str,
    ) -> dict[str, object]:
        result = await self.executor.call("metrics", subscription_id, revision, as_of=now)
        if not isinstance(result, Mapping):
            raise GatewayError("delivery plane returned invalid metrics")
        return dict(result)

    def ephemeral_metrics(self) -> dict[str, object]:
        result: dict[str, object] = dict(self.sessions.snapshot())
        result.update(
            {
                "unused_tickets": self.tickets.count(now_monotonic=time.monotonic()),
                "executor_queue_depth": int(getattr(self.executor, "queue_depth", 0)),
                "executor_saturation_count": int(getattr(self.executor, "saturation_count", 0)),
                "ephemeral": True,
                "execution_authorized": False,
                "production_decision_authorized": False,
            }
        )
        return result

    def close_session(self, session_id: str) -> tuple[str, ...]:
        return self.sessions.close(session_id)


def _authority_payload(**values: object) -> dict[str, object]:
    values["execution_authorized"] = False
    values["production_decision_authorized"] = False
    return values


def _error_payload(code: str, message: str, *, retryable: bool = False) -> dict[str, object]:
    return _authority_payload(code=code, message=message, retryable=retryable)


def _bearer_from_request(request: Request) -> str | None:
    header = request.headers.get("authorization")
    if not header or not header.startswith("Bearer "):
        return None
    token = header[7:]
    return token if token else None


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


async def _strict_json_request(request: Request, *, max_bytes: int) -> dict[str, object]:
    raw = await request.body()
    if len(raw) > max_bytes:
        raise GatewayRequestError("request body too large")
    if not raw:
        raise GatewayRequestError("JSON object required")
    try:
        decoded = raw.decode("utf-8")
        parsed = json.loads(decoded, parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise GatewayRequestError("invalid JSON body") from exc
    if not isinstance(parsed, dict):
        raise GatewayRequestError("JSON object required")
    return parsed


def _binding_from_mapping(body: Mapping[str, object], config: GatewayConfig) -> SessionBinding:
    return SessionBinding(
        subscription_id=body.get("subscription_id"),
        revision=body.get("revision"),
        consumer_id=body.get("consumer_id"),
        lease_seconds=body.get("lease_seconds", config.default_lease_seconds),
        max_inflight=body.get("max_inflight", config.default_max_inflight),
    )


def _require_sse_session_control(
    service: IntelligenceGatewayService,
    body: Mapping[str, object],
) -> tuple[GatewaySession, str, str]:
    try:
        session_id = _identifier(body.get("session_id"), "session_id", 256)
        consumer_id = _identifier(body.get("consumer_id"), "consumer_id", 240)
        delivery_id = _identifier(body.get("delivery_id"), "delivery_id", 256)
    except ValueError as exc:
        raise GatewaySessionError("session control invalid") from exc
    try:
        session = service.sessions.get(session_id)
    except ValueError as exc:
        raise GatewaySessionError("session control invalid") from exc
    if (
        session is None
        or session.closed
        or session.transport != "sse"
        or session.binding.consumer_id != consumer_id
        or not service.sessions.contains_inflight(session_id, delivery_id)
    ):
        raise GatewaySessionError("session control invalid")
    return session, session_id, delivery_id


def create_intelligence_gateway_app(
    *,
    db_path: str,
    bearer_token: str,
    config: GatewayConfig | None = None,
    plane_factory: Callable[..., object] = IntelligenceDeliveryPlane,
) -> FastAPI:
    """Create the standalone Phase 3 ASGI app without changing Phase 1/2 semantics."""
    if not isinstance(db_path, str) or not db_path.strip():
        raise ValueError("file-backed db_path is required")
    normalized_path = db_path.strip().lower()
    if normalized_path == ":memory:" or "mode=memory" in normalized_path or normalized_path.startswith("file::memory:"):
        raise ValueError("production gateway requires a file-backed database")
    if not isinstance(bearer_token, str) or not bearer_token.strip():
        raise ValueError("bearer_token is required")
    bearer_token = bearer_token.strip()
    config = config or GatewayConfig()

    executor = DeliveryExecutor(
        db_path,
        plane_factory=plane_factory,
        queue_capacity=config.executor_queue_capacity,
    )
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
            return JSONResponse(
                status_code=400,
                content=_error_payload("HOST_REJECTED", "request host rejected"),
            )
        return await call_next(request)

    def authenticated(request: Request) -> bool:
        return bearer_matches(_bearer_from_request(request), bearer_token)

    def auth_failure() -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content=_error_payload("AUTH_FAILED", "authentication failed"),
        )

    def request_failure(*, too_large: bool = False) -> JSONResponse:
        return JSONResponse(
            status_code=413 if too_large else 400,
            content=_error_payload("INVALID_REQUEST", "request is invalid"),
        )

    def operation_failure(exc: BaseException) -> JSONResponse:
        if isinstance(exc, GatewayBusyError):
            return JSONResponse(
                status_code=503,
                content=_error_payload("GATEWAY_BUSY", "gateway is busy", retryable=True),
            )
        if isinstance(exc, GatewaySessionError):
            return JSONResponse(
                status_code=409,
                content=_error_payload("SESSION_INVALID", "session control is invalid"),
            )
        return JSONResponse(
            status_code=409,
            content=_error_payload("DELIVERY_STATE_INVALID", "delivery operation failed"),
        )

    @app.get("/healthz")
    async def healthz():
        return _authority_payload(
            ok=bool(executor.started),
            protocol=PROTOCOL_VERSION,
            delivery_store_reachable=bool(executor.started),
        )

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

    @app.get("/v1/intelligence/metrics")
    async def metrics(request: Request):
        if not authenticated(request):
            return auth_failure()
        try:
            subscription_id = _identifier(request.query_params.get("subscription_id"), "subscription_id")
            raw_revision = request.query_params.get("revision")
            revision = int(raw_revision) if raw_revision is not None else 0
            if revision < 1:
                raise ValueError("revision must be >= 1")
            durable = await service.durable_metrics(subscription_id, revision, now=_utc_now())
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
            _session, session_id, delivery_id = _require_sse_session_control(service, body)
            lease_token = _identifier(body.get("lease_token"), "lease_token", 512)
            result = await service.ack_for_session(
                session_id,
                delivery_id,
                lease_token,
                now=_utc_now(),
            )
        except (GatewaySessionError, GatewayBusyError) as exc:
            return operation_failure(exc)
        except (ValueError, TypeError) as exc:
            return operation_failure(exc)
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
            _session, session_id, delivery_id = _require_sse_session_control(service, body)
            lease_token = _identifier(body.get("lease_token"), "lease_token", 512)
            reason = body.get("reason")
            if reason is not None and not isinstance(reason, Mapping):
                raise ValueError("reason must be an object")
            result = await service.nack_for_session(
                session_id,
                delivery_id,
                lease_token,
                now=_utc_now(),
                reason=reason,
            )
        except (GatewaySessionError, GatewayBusyError) as exc:
            return operation_failure(exc)
        except (ValueError, TypeError) as exc:
            return operation_failure(exc)
        except BaseException as exc:
            return operation_failure(exc)
        return _authority_payload(**dict(result))

    return app
