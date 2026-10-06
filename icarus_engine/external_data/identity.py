from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping
from datetime import date, datetime, timezone
from typing import Any


def normalize_utc(value: datetime | str | None) -> datetime | None:
    """Normalize an explicitly zoned timestamp to aware UTC.

    Missing timestamps stay missing. Naive timestamps are rejected rather than
    silently inventing a timezone, which would corrupt point-in-time replay.
    """
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(f"invalid timestamp: {value!r}") from exc
    elif isinstance(value, datetime):
        parsed = value
    else:
        raise TypeError("timestamp must be datetime, ISO-8601 string, or None")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include timezone information")
    return parsed.astimezone(timezone.utc)


def _utc_text(value: datetime) -> str:
    normalized = normalize_utc(value)
    assert normalized is not None
    return normalized.isoformat().replace("+00:00", "Z")


def _canonicalize(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        if hasattr(value, "to_canonical_dict"):
            return _canonicalize(value.to_canonical_dict())
        return _canonicalize({field.name: getattr(value, field.name) for field in dataclasses.fields(value)})
    if isinstance(value, datetime):
        return _utc_text(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _canonicalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported canonical JSON type: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON bytes suitable for hashing."""
    normalized = _canonicalize(value)
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def raw_sha256(payload: bytes) -> str:
    """Hash exact provider bytes before parsing or normalization."""
    if not isinstance(payload, bytes):
        raise TypeError("raw payload must be bytes")
    return hashlib.sha256(payload).hexdigest()


def canonical_sha256(record: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(record)).hexdigest()


def evidence_id(record: Any) -> str:
    return "ev_" + canonical_sha256(record)
