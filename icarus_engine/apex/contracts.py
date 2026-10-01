"""Strict evidence contracts for ICARUS APEX Ω.

This layer is intentionally small and dependency-free. It defines the truth
boundary consumed by all higher APEX subsystems and never grants production or
execution authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any, Mapping

EVIDENCE_KINDS = frozenset({"observed", "derived", "reconstructed", "inferred", "unavailable"})
_SCHEMA_VERSION = "icarus-apex-evidence-v1"


def authority_flags() -> dict[str, bool]:
    return {
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def _text(value: Any, field: str, *, required: bool = True, max_len: int = 512) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{field} is required")
    if len(value) > max_len:
        raise ValueError(f"{field} exceeds {max_len} characters")
    return value


def _unit_interval(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{field} must be a finite number")
    if out < 0.0 or out > 1.0:
        raise ValueError(f"{field} must be in [0, 1]")
    return out


def _finite_json(value: Any, field: str, *, max_bytes: int = 131072) -> Any:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{field} must be finite JSON") from ex
    if len(raw.encode("utf-8")) > max_bytes:
        raise ValueError(f"{field} exceeds {max_bytes} bytes")
    return value


def _string_list(value: Any, field: str, *, max_items: int = 128) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > max_items:
        raise ValueError(f"{field} must be a list with at most {max_items} items")
    return [_text(item, f"{field} item", max_len=700) for item in value]


def parse_utc(value: str, field: str) -> datetime:
    raw = _text(value, field, max_len=80)
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as ex:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from ex
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return dt.astimezone(timezone.utc)


def _utc_text(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _source(value: Any, *, observed: bool) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError("source must be an object")
    subsystem = _text(value.get("subsystem"), "source.subsystem", max_len=100)
    source_repo = _text(value.get("source_repo"), "source.source_repo", max_len=200)
    if "/" not in source_repo:
        raise ValueError("source.source_repo must be owner/repository")
    source_commit = _text(value.get("source_commit"), "source.source_commit", max_len=40).lower()
    if len(source_commit) != 40 or any(ch not in "0123456789abcdef" for ch in source_commit):
        raise ValueError("source.source_commit must be an exact 40-character Git SHA")
    source_record_id = _text(
        value.get("source_record_id"),
        "source.source_record_id",
        required=observed,
        max_len=300,
    )
    return {
        "subsystem": subsystem,
        "source_repo": source_repo,
        "source_commit": source_commit,
        "source_record_id": source_record_id,
    }


def normalize_evidence(body: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(body, Mapping):
        raise ValueError("evidence must be an object")

    kind = _text(body.get("kind"), "kind", max_len=32).lower()
    if kind not in EVIDENCE_KINDS:
        raise ValueError(f"unsupported evidence kind: {kind}")

    observed_at = parse_utc(body.get("observed_at"), "observed_at")
    received_at = parse_utc(body.get("received_at"), "received_at")
    calculated_at = parse_utc(body.get("calculated_at"), "calculated_at")
    valid_from = parse_utc(body.get("valid_from"), "valid_from")

    raw_valid_until = body.get("valid_until")
    valid_until = None if raw_valid_until is None else parse_utc(raw_valid_until, "valid_until")

    if received_at < observed_at:
        raise ValueError("received_at cannot precede observed_at")
    if calculated_at < received_at:
        raise ValueError("calculated_at cannot precede received_at")
    if valid_until is not None and valid_until < valid_from:
        raise ValueError("valid_until cannot precede valid_from")

    confidence = _unit_interval(body.get("confidence"), "confidence")
    quality = _unit_interval(body.get("quality"), "quality")
    if kind == "unavailable" and confidence != 0.0:
        raise ValueError("unavailable evidence must have zero confidence")

    semantic: dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "kind": kind,
        "subject": _text(body.get("subject"), "subject", max_len=300),
        "value": _finite_json(body.get("value"), "value"),
        "source": _source(body.get("source"), observed=kind == "observed"),
        "observed_at": _utc_text(observed_at),
        "received_at": _utc_text(received_at),
        "calculated_at": _utc_text(calculated_at),
        "valid_from": _utc_text(valid_from),
        "valid_until": None if valid_until is None else _utc_text(valid_until),
        "confidence": confidence,
        "quality": quality,
        "dependencies": _string_list(body.get("dependencies", []), "dependencies"),
        "contradictions": _string_list(body.get("contradictions", []), "contradictions"),
        "falsifiers": _string_list(body.get("falsifiers", []), "falsifiers"),
        **authority_flags(),
    }
    _finite_json(semantic, "evidence")
    return semantic


def evidence_id(semantic: Mapping[str, Any]) -> str:
    if not isinstance(semantic, Mapping):
        raise ValueError("semantic evidence must be an object")
    payload = {k: v for k, v in semantic.items() if k not in {"evidence_id", "recorded_at"}}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
