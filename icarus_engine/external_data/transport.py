from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
import time
from typing import Protocol
import urllib.error
import urllib.request

from .redaction import (
    normalized_secret_keys,
    redact_headers,
    redact_text,
    redact_url,
    secret_values,
)


DEFAULT_USER_AGENT = "ICARUS-External-Data/1"
DEFAULT_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


class TransportError(RuntimeError):
    """Secret-safe transport failure."""


class RateBudgetExceeded(TransportError):
    """Raised before an outbound request would exceed a configured provider budget."""


@dataclass(frozen=True)
class HttpRequest:
    provider_id: str
    method: str
    url: str = field(repr=False)
    headers: Mapping[str, str] = field(default_factory=dict, repr=False)
    body: bytes | None = field(default=None, repr=False)
    timeout: float = 10.0
    secret_keys: frozenset[str] = field(default_factory=frozenset, repr=False)

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id is required")
        if not self.method.strip():
            raise ValueError("method is required")
        if not self.url.strip():
            raise ValueError("url is required")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        object.__setattr__(self, "method", self.method.upper())
        object.__setattr__(self, "headers", dict(self.headers))
        object.__setattr__(self, "secret_keys", frozenset(self.secret_keys))

    def __repr__(self) -> str:
        keys = normalized_secret_keys(self.secret_keys)
        safe_url = redact_url(self.url, keys)
        safe_headers = redact_headers(self.headers, keys)
        body_len = 0 if self.body is None else len(self.body)
        return (
            "HttpRequest("
            f"provider_id={self.provider_id!r}, method={self.method!r}, "
            f"url={safe_url!r}, headers={safe_headers!r}, body_len={body_len}, "
            f"timeout={self.timeout!r})"
        )


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str] = field(default_factory=dict, repr=False)
    body: bytes = field(default=b"", repr=False)
    url: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "headers", dict(self.headers))
        object.__setattr__(self, "body", bytes(self.body))

    def __repr__(self) -> str:
        return f"HttpResponse(status={self.status!r}, body_len={len(self.body)}, header_names={sorted(self.headers)!r})"


class Transport(Protocol):
    def request(self, request: HttpRequest) -> HttpResponse:
        ...


class RateBudget:
    """Simple in-memory per-provider call budget.

    Each actual outbound attempt consumes one unit, including retries. Providers not
    present in ``limits`` are unlimited. This object is intentionally process-local;
    durable quota accounting belongs in orchestration state, not HTTP transport.
    """

    def __init__(self, limits: Mapping[str, int] | None = None):
        self._limits = dict(limits or {})
        for provider_id, limit in self._limits.items():
            if limit < 0:
                raise ValueError(f"negative call budget for {provider_id}")
        self._used: MutableMapping[str, int] = {}

    def consume(self, provider_id: str) -> None:
        used = self._used.get(provider_id, 0)
        limit = self._limits.get(provider_id)
        if limit is not None and used >= limit:
            raise RateBudgetExceeded(f"call budget exhausted for provider {provider_id!r}")
        self._used[provider_id] = used + 1

    def used(self, provider_id: str) -> int:
        return self._used.get(provider_id, 0)

    def remaining(self, provider_id: str) -> int | None:
        limit = self._limits.get(provider_id)
        if limit is None:
            return None
        return max(0, limit - self.used(provider_id))


class FakeTransport:
    """Deterministic no-socket transport for provider/parser unit tests."""

    def __init__(self, outcomes: Iterable[HttpResponse | BaseException]):
        self._outcomes = list(outcomes)
        self.calls: list[HttpRequest] = []

    def request(self, request: HttpRequest) -> HttpResponse:
        self.calls.append(request)
        if not self._outcomes:
            raise AssertionError("FakeTransport exhausted")
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class UrllibTransport:
    def __init__(
        self,
        *,
        open_fn=None,
        user_agent: str = DEFAULT_USER_AGENT,
        budget: RateBudget | None = None,
        max_retries: int = 2,
        retry_statuses: Iterable[int] = DEFAULT_RETRY_STATUSES,
        sleep_fn=time.sleep,
        backoff_seconds: float = 0.5,
    ):
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if backoff_seconds < 0:
            raise ValueError("backoff_seconds must be non-negative")
        self._open = open_fn or urllib.request.urlopen
        self._user_agent = user_agent
        self._budget = budget
        self._max_retries = max_retries
        self._retry_statuses = frozenset(int(status) for status in retry_statuses)
        self._sleep = sleep_fn
        self._backoff_seconds = float(backoff_seconds)

    def request(self, request: HttpRequest) -> HttpResponse:
        secret_keys = normalized_secret_keys(request.secret_keys)
        values = secret_values(request.url, request.headers, secret_keys)
        safe_url = redact_url(request.url, secret_keys)

        for attempt in range(self._max_retries + 1):
            if self._budget is not None:
                self._budget.consume(request.provider_id)

            prepared = self._prepare(request)
            try:
                response = self._perform(prepared, timeout=request.timeout, fallback_url=request.url)
            except urllib.error.HTTPError as exc:
                response = self._from_http_error(exc, fallback_url=request.url)
            except Exception as exc:
                safe_message = redact_text(str(exc), values)
                raise TransportError(
                    f"provider {request.provider_id!r} request failed for {safe_url}: {safe_message}"
                ) from None

            if response.status not in self._retry_statuses or attempt >= self._max_retries:
                return response

            delay = self._retry_delay(response.headers, attempt)
            if delay > 0:
                self._sleep(delay)

        raise AssertionError("unreachable")

    def _prepare(self, request: HttpRequest) -> urllib.request.Request:
        headers = dict(request.headers)
        if not any(name.lower() == "user-agent" for name in headers):
            headers["User-Agent"] = self._user_agent
        return urllib.request.Request(
            request.url,
            data=request.body,
            headers=headers,
            method=request.method,
        )

    def _perform(self, prepared: urllib.request.Request, *, timeout: float, fallback_url: str) -> HttpResponse:
        opened = self._open(prepared, timeout=timeout)
        if hasattr(opened, "__enter__"):
            with opened as response:
                return self._read_response(response, fallback_url=fallback_url)
        return self._read_response(opened, fallback_url=fallback_url)

    @staticmethod
    def _read_response(response, *, fallback_url: str) -> HttpResponse:
        status = getattr(response, "status", None)
        if status is None and hasattr(response, "getcode"):
            status = response.getcode()
        if status is None:
            raise TransportError("response did not expose an HTTP status")
        headers = UrllibTransport._headers_to_dict(getattr(response, "headers", {}))
        body = response.read()
        url = response.geturl() if hasattr(response, "geturl") else fallback_url
        return HttpResponse(status=int(status), headers=headers, body=body, url=url)

    @staticmethod
    def _from_http_error(exc: urllib.error.HTTPError, *, fallback_url: str) -> HttpResponse:
        try:
            body = exc.read()
        except Exception:
            body = b""
        return HttpResponse(
            status=int(exc.code),
            headers=UrllibTransport._headers_to_dict(exc.headers or {}),
            body=body,
            url=getattr(exc, "url", None) or fallback_url,
        )

    @staticmethod
    def _headers_to_dict(headers) -> dict[str, str]:
        if headers is None:
            return {}
        if hasattr(headers, "items"):
            return {str(key): str(value) for key, value in headers.items()}
        return dict(headers)

    def _retry_delay(self, headers: Mapping[str, str], attempt: int) -> float:
        retry_after = None
        for key, value in headers.items():
            if key.lower() == "retry-after":
                retry_after = value
                break
        parsed = self._parse_retry_after(retry_after)
        if parsed is not None:
            return parsed
        return self._backoff_seconds * (2**attempt)

    @staticmethod
    def _parse_retry_after(value: str | None) -> float | None:
        if not value:
            return None
        stripped = value.strip()
        try:
            return max(0.0, float(stripped))
        except ValueError:
            pass
        try:
            target = parsedate_to_datetime(stripped)
            if target.tzinfo is None:
                return None
            return max(0.0, target.timestamp() - time.time())
        except (TypeError, ValueError, OverflowError):
            return None
