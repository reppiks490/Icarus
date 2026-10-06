from __future__ import annotations

from dataclasses import replace

import pytest

from icarus_engine.external_data.redaction import redact_url
from icarus_engine.external_data.transport import (
    FakeTransport,
    HttpRequest,
    HttpResponse,
    RateBudget,
    RateBudgetExceeded,
    TransportError,
    UrllibTransport,
)


class _FakeResponse:
    def __init__(self, status: int, body: bytes, headers: dict[str, str] | None = None):
        self.status = status
        self._body = body
        self.headers = headers or {}

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _SequenceOpener:
    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls: list[tuple[object, float | None]] = []

    def __call__(self, request, timeout=None):
        self.calls.append((request, timeout))
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def test_redact_url_masks_named_secret_query_values():
    url = "https://example.test/data?symbol=NQ&api_key=SENTINEL-SECRET&limit=10"
    redacted = redact_url(url, {"api_key"})
    assert "SENTINEL-SECRET" not in redacted
    assert "symbol=NQ" in redacted
    assert "api_key=%2A%2A%2A" in redacted or "api_key=***" in redacted


def test_timeout_user_agent_and_bytes_are_preserved():
    opener = _SequenceOpener([_FakeResponse(200, b"\x00\xffraw-bytes", {"X-Test": "ok"})])
    transport = UrllibTransport(open_fn=opener, user_agent="ICARUS-External-Data/1")
    request = HttpRequest(
        provider_id="fred",
        method="GET",
        url="https://example.test/data",
        timeout=7.25,
    )

    response = transport.request(request)

    assert response.status == 200
    assert response.body == b"\x00\xffraw-bytes"
    assert opener.calls[0][1] == 7.25
    sent = opener.calls[0][0]
    assert sent.get_header("User-agent") == "ICARUS-External-Data/1"


def test_retry_is_bounded_for_429_and_5xx_and_honors_retry_after():
    opener = _SequenceOpener(
        [
            _FakeResponse(429, b"slow", {"Retry-After": "2"}),
            _FakeResponse(503, b"down"),
            _FakeResponse(200, b"ok"),
        ]
    )
    sleeps: list[float] = []
    transport = UrllibTransport(
        open_fn=opener,
        max_retries=2,
        sleep_fn=sleeps.append,
        backoff_seconds=0.25,
    )

    response = transport.request(
        HttpRequest(provider_id="intrinio", method="GET", url="https://example.test/data")
    )

    assert response.status == 200
    assert len(opener.calls) == 3
    assert sleeps == [2.0, 0.5]


def test_terminal_4xx_is_not_retried_by_default():
    opener = _SequenceOpener([_FakeResponse(404, b"missing"), _FakeResponse(200, b"unexpected")])
    transport = UrllibTransport(open_fn=opener, max_retries=3, sleep_fn=lambda _: None)

    response = transport.request(
        HttpRequest(provider_id="treasury", method="GET", url="https://example.test/missing")
    )

    assert response.status == 404
    assert len(opener.calls) == 1


def test_provider_policy_can_add_retryable_status():
    opener = _SequenceOpener([_FakeResponse(409, b"retry"), _FakeResponse(200, b"ok")])
    transport = UrllibTransport(
        open_fn=opener,
        max_retries=1,
        retry_statuses={409, 429, 500, 502, 503, 504},
        sleep_fn=lambda _: None,
    )

    response = transport.request(
        HttpRequest(provider_id="quiver", method="GET", url="https://example.test/data")
    )

    assert response.status == 200
    assert len(opener.calls) == 2


def test_rate_budget_is_per_provider_and_counts_actual_attempts():
    budget = RateBudget({"fred": 1, "eia": 2})
    opener = _SequenceOpener(
        [
            _FakeResponse(200, b"fred"),
            _FakeResponse(200, b"eia-1"),
            _FakeResponse(200, b"eia-2"),
        ]
    )
    transport = UrllibTransport(open_fn=opener, budget=budget)

    assert transport.request(HttpRequest("fred", "GET", "https://example.test/fred")).body == b"fred"
    with pytest.raises(RateBudgetExceeded):
        transport.request(HttpRequest("fred", "GET", "https://example.test/fred2"))

    assert transport.request(HttpRequest("eia", "GET", "https://example.test/eia1")).body == b"eia-1"
    assert transport.request(HttpRequest("eia", "GET", "https://example.test/eia2")).body == b"eia-2"


def test_fake_transport_is_deterministic_and_captures_calls():
    first = HttpResponse(status=200, headers={"X": "1"}, body=b"one", url="https://example.test/1")
    second = HttpResponse(status=200, headers={"X": "2"}, body=b"two", url="https://example.test/2")
    transport = FakeTransport([first, second])

    r1 = HttpRequest("nyfed", "GET", "https://example.test/a")
    r2 = replace(r1, url="https://example.test/b")

    assert transport.request(r1) is first
    assert transport.request(r2) is second
    assert transport.calls == [r1, r2]


def test_secret_values_do_not_leak_from_repr_or_transport_errors():
    sentinel = "SENTINEL-ULTRA-SECRET"
    request = HttpRequest(
        provider_id="intrinio",
        method="GET",
        url=f"https://example.test/data?api_key={sentinel}&symbol=NQ",
        headers={"Authorization": f"Bearer {sentinel}", "X-Api-Key": sentinel},
        secret_keys=frozenset({"api_key", "authorization", "x-api-key"}),
    )
    opener = _SequenceOpener([RuntimeError(f"provider exploded with {sentinel}")])
    transport = UrllibTransport(open_fn=opener, max_retries=0)

    assert sentinel not in repr(request)
    with pytest.raises(TransportError) as excinfo:
        transport.request(request)
    assert sentinel not in str(excinfo.value)
    assert sentinel not in repr(excinfo.value)


def test_secret_headers_are_not_copied_into_response_or_error_metadata():
    sentinel = "HEADER-SENTINEL"
    request = HttpRequest(
        provider_id="tick_stream",
        method="GET",
        url="https://example.test/ticks",
        headers={"Authorization": f"Bearer {sentinel}"},
        secret_keys=frozenset({"authorization"}),
    )
    opener = _SequenceOpener([RuntimeError(f"Authorization: Bearer {sentinel}")])
    transport = UrllibTransport(open_fn=opener, max_retries=0)

    with pytest.raises(TransportError) as excinfo:
        transport.request(request)
    rendered = f"{excinfo.value!s} {excinfo.value!r}"
    assert sentinel not in rendered
