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
import threading
from concurrent.futures import Future
from dataclasses import dataclass, fields, is_dataclass
from typing import Any, Callable

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
    """The bounded delivery worker queue has no capacity."""


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
    if not isinstance(origin, str):
        raise GatewaySecurityError("origin rejected")
    if origin not in allowed_origins:
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
        if isinstance(self.default_max_inflight, bool) or not isinstance(self.default_max_inflight, int) or not 1 <= self.default_max_inflight <= 256:
            raise ValueError("default_max_inflight must be in [1, 256]")
        if isinstance(self.default_lease_seconds, bool) or not isinstance(self.default_lease_seconds, int) or not 5 <= self.default_lease_seconds <= 300:
            raise ValueError("default_lease_seconds must be in [5, 300]")


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
        self._queue: queue.Queue[_DeliveryCall | None] = queue.Queue(maxsize=_positive_int(queue_capacity, "queue_capacity"))
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
        self._thread = threading.Thread(target=self._run, name="icarus-intelligence-delivery", daemon=True)
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
