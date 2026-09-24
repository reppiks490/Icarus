"""Canonical cross-domain evidence contracts for OMNIVISION."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
import re
from typing import Mapping
from urllib.parse import urlsplit

from icarus_engine.world_state import Observation

_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")


def _identity(value: str, name: str) -> str:
    if type(value) is not str or not _ID.fullmatch(value):
        raise ValueError(f"invalid {name}")
    return value


def _finite(value, name: str) -> float:
    if isinstance(value, bool) or type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def _timestamp(value: str, name: str) -> float:
    if type(value) is not str:
        raise ValueError(f"{name} must be timezone-aware ISO 8601")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{name} must be timezone-aware ISO 8601") from None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware ISO 8601")
    return stamp.timestamp()


def _url(value: str) -> str:
    if type(value) is not str or len(value) > 2048:
        raise ValueError("source_url must be an HTTPS URL")
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise ValueError("source_url must be an HTTPS URL") from None
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("source_url must be an HTTPS URL")
    return value


@dataclass(frozen=True)
class WorldEvent:
    source: str
    source_event_id: str
    revision_id: str
    source_url: str
    domain: str
    entity: str
    asset_ids: tuple[str, ...]
    observed_at: str
    published_at: str | None
    values: Mapping[str, float]
    units: Mapping[str, str]
    confidence: float
    timing_basis: str
    quality_flags: tuple[str, ...] = ()

    def __post_init__(self):
        for name in ("source", "source_event_id", "revision_id", "domain", "entity"):
            _identity(getattr(self, name), name)
        _url(self.source_url)
        if type(self.asset_ids) is not tuple or not self.asset_ids or len(self.asset_ids) > 32:
            raise ValueError("asset_ids must be a non-empty tuple")
        for asset in self.asset_ids:
            _identity(asset, "asset")
        if len(set(self.asset_ids)) != len(self.asset_ids):
            raise ValueError("asset_ids must be unique")
        observed = _timestamp(self.observed_at, "observed_at")
        if self.timing_basis not in ("published", "first_observed"):
            raise ValueError("unsupported timing_basis")
        if self.timing_basis == "published":
            if self.published_at is None:
                raise ValueError("published timing requires published_at")
            published = _timestamp(self.published_at, "published_at")
            if published < observed:
                raise ValueError("published_at cannot precede observed_at")
        elif self.published_at is not None:
            raise ValueError("first_observed timing must not invent published_at")
        if not isinstance(self.values, Mapping) or not isinstance(self.units, Mapping):
            raise ValueError("values and units must be mappings")
        if not self.values or set(self.values) != set(self.units) or len(self.values) > 128:
            raise ValueError("values and units must have matching non-empty keys")
        for name, value in self.values.items():
            _identity(name, "value name")
            _finite(value, name)
            unit = self.units[name]
            if type(unit) is not str or not unit.strip() or len(unit) > 80:
                raise ValueError("invalid unit")
        confidence = _finite(self.confidence, "confidence")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be in [0,1]")
        if type(self.quality_flags) is not tuple or len(self.quality_flags) > 32:
            raise ValueError("quality_flags must be a bounded tuple")
        for flag in self.quality_flags:
            _identity(flag, "quality flag")
        if self.timing_basis == "first_observed" and "publication_time_unknown" not in self.quality_flags:
            raise ValueError("first_observed evidence must declare publication_time_unknown")

    def to_advisory_event(self, schema_version: int = 1) -> dict:
        if type(schema_version) is not int or schema_version != 1:
            raise ValueError("unsupported schema_version")
        return {
            "schema_version": schema_version,
            "source": self.source,
            "source_event_id": self.source_event_id,
            "revision_id": self.revision_id,
            "source_url": self.source_url,
            "event_type": "world_state",
            "asset_ids": list(self.asset_ids),
            "instrument_id": self.entity,
            "observed_at": self.observed_at,
            "published_at": self.published_at,
            "values": dict(self.values),
            "units": dict(self.units),
            "timing_basis": self.timing_basis,
            "quality_flags": list(self.quality_flags),
            "domain": self.domain,
            "entity": self.entity,
            "confidence": float(self.confidence),
        }


def observation_from_event(event: Mapping, variable: str) -> Observation:
    if not isinstance(event, Mapping) or event.get("event_type") != "world_state":
        raise ValueError("world_state event required")
    if variable not in event.get("values", {}):
        raise ValueError("variable is not present in event")
    domain = _identity(event.get("domain"), "domain")
    entity = _identity(event.get("entity"), "entity")
    source = _identity(event.get("source"), "source")
    observed = _timestamp(event.get("observed_at"), "observed_at")
    published = event.get("published_at")
    received = event.get("received_at")
    received_ts = _timestamp(received, "received_at") if received is not None else None
    if published is not None:
        published_ts = _timestamp(published, "published_at")
        if received_ts is None:
            raise ValueError("received_at is required for ledger-backed evidence")
        available = max(published_ts, received_ts)
    elif received_ts is not None:
        available = received_ts
    else:
        raise ValueError("event availability is unknown")
    confidence = _finite(event.get("confidence"), "confidence")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be in [0,1]")
    return Observation(
        source=source,
        domain=domain,
        entity=entity,
        variable=_identity(variable, "variable"),
        value=_finite(event["values"][variable], variable),
        observed_at=int(observed),
        available_at=int(available),
        confidence=confidence,
        provenance=_url(event.get("source_url")),
        evidence_id=event.get("event_id"),
    )
