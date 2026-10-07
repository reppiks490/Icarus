from __future__ import annotations

from datetime import date, datetime, timezone
import json
from typing import Any
from urllib.parse import urlencode

from ..normalization import CollectedBatch
from ..transport import HttpRequest, HttpResponse, Transport


UTC = timezone.utc


def decode_json(payload: bytes) -> Any:
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("provider payload is not valid UTF-8 JSON") from exc


def utc_day(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing required date field {field}")
    text = value.strip()[:10]
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"invalid date for {field}: {value!r}") from exc
    return datetime(parsed.year, parsed.month, parsed.day, tzinfo=UTC)


def period_start(value: Any, *, field: str = "period") -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing required period field {field}")
    text = value.strip()
    try:
        if len(text) == 4:
            return datetime(int(text), 1, 1, tzinfo=UTC)
        if len(text) == 7:
            year, month = text.split("-", 1)
            return datetime(int(year), int(month), 1, tzinfo=UTC)
        return utc_day(text, field=field)
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith(("missing", "invalid")):
            raise
        raise ValueError(f"invalid period for {field}: {value!r}") from exc


def number(value: Any, *, field: str) -> float:
    if value is None or value == "":
        raise ValueError(f"missing required numeric field {field}")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid numeric field {field}: {value!r}") from exc


def integer(value: Any, *, field: str) -> int:
    numeric = number(value, field=field)
    if not numeric.is_integer():
        raise ValueError(f"expected integer quantity for {field}: {value!r}")
    return int(numeric)


def require_text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing required text field {field}")
    return value.strip()


def request_json(
    transport: Transport,
    *,
    provider_id: str,
    base_url: str,
    params: list[tuple[str, str]] | None = None,
    secret_keys=(),
    timeout: float = 30.0,
) -> tuple[HttpRequest, HttpResponse]:
    query = urlencode(params or [], doseq=True)
    url = base_url + (("?" + query) if query else "")
    request = HttpRequest(
        provider_id=provider_id,
        method="GET",
        url=url,
        timeout=timeout,
        secret_keys=frozenset(secret_keys),
    )
    response = transport.request(request)
    if response.status < 200 or response.status >= 300:
        raise ValueError(f"{provider_id} returned HTTP {response.status}")
    return request, response


def response_batch(
    response: HttpResponse,
    *,
    dataset: str,
    retrieved_at: datetime,
    metadata: dict[str, Any] | None = None,
) -> CollectedBatch:
    return CollectedBatch(
        dataset=dataset,
        payload=response.body,
        retrieved_at=retrieved_at,
        content_type=response.headers.get("Content-Type") or "application/json",
        source_url=response.url or None,
        metadata=metadata or {},
    )
