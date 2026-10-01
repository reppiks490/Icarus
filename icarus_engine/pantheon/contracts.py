"""Versioned, fail-closed contracts for ICARUS PANTHEON / AETHER.

This layer is research/shadow-only.  It can observe, explain, falsify and propose
research attention, but it cannot authorize orders, sizing, broker actions or
production promotion.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

SCHEMA_VERSION = "icarus-pantheon-v1"
OBSERVATION_SCHEMA = "icarus-pantheon-observation-v1"
FACULTIES = (
    "oracle",
    "parallax",
    "dreamstate",
    "nemesis",
    "godel",
    "socrates",
    "ananke",
    "ex_nihilo",
    "mint",
    "nullspace",
    "echo",
    "archon",
    "aether",
)

def authority_block() -> dict[str, Any]:
    return {
        "shadow_only": True,
        "execution_authorized": False,
        "production_decision_authorized": False,
        "broker_authorized": False,
        "sizing_authorized": False,
        "automatic_production_promotion": False,
    }

def text(value: Any, field: str, limit: int, *, required: bool = True) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{field} is required")
    if len(value) > limit:
        raise ValueError(f"{field} exceeds {limit} characters")
    return value

def finite(value: Any, field: str) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"{field} must be numeric")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{field} must be finite")
    return out

def unit(value: Any, field: str, default: float = 0.0) -> float:
    if value is None:
        return default
    out = finite(value, field)
    if not 0.0 <= out <= 1.0:
        raise ValueError(f"{field} must be between 0 and 1")
    return out

def signed_unit(value: Any, field: str, default: float = 0.0) -> float:
    if value is None:
        return default
    out = finite(value, field)
    if not -1.0 <= out <= 1.0:
        raise ValueError(f"{field} must be between -1 and 1")
    return out

def exact_git_sha(value: Any) -> str:
    value = text(value, "source_commit", 40).lower()
    if len(value) != 40 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("source_commit must be an exact 40-character Git SHA")
    return value

def iso_aware(value: Any, field: str = "observed_at") -> str:
    value = text(value, field, 80)
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as ex:
        raise ValueError(f"{field} must be ISO-8601") from ex
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    parsed_utc = parsed.astimezone(timezone.utc)
    if parsed_utc > datetime.now(timezone.utc) + timedelta(seconds=5):
        raise ValueError(f"{field} cannot be in the future")
    return parsed_utc.isoformat().replace("+00:00", "Z")

def json_canonical(value: Any, field: str, max_bytes: int = 131072) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{field} must be finite JSON") from ex
    if len(raw.encode("utf-8")) > max_bytes:
        raise ValueError(f"{field} exceeds {max_bytes} bytes")
    return raw

def digest(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()

def mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value
