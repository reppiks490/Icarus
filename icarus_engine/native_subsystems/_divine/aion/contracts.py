"""Shared contracts. There is deliberately no order or broker command."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import IntEnum
import hashlib
import json
import math
import re
from typing import Any


class EvidenceTier(IntEnum):
    CANDLE_PROXY = 1
    INFERRED_TRADE = 2
    TRUE_TRADE = 3
    TRUE_DEPTH = 4


KINDS = frozenset({"bar", "schedule", "macro", "trade", "book_snapshot", "book_delta", "context"})
PLANES = frozenset({"research", "shadow", "production_observation"})
CAPABILITIES = frozenset({"bar", "schedule", "macro", "trade", "book_snapshot", "book_delta", "context"})
SHA = re.compile(r"[0-9a-f]{64}\Z")


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _name(value: str, field: str) -> None:
    if not isinstance(value, str) or not 1 <= len(value) <= 160 or any(ord(c) < 33 for c in value):
        raise ValueError(f"invalid {field}")


def _ns(value: int, field: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field} must be a nonnegative integer nanosecond timestamp")


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    representation_id: str
    symbol: str
    capabilities: tuple[str, ...]
    max_evidence_tier: EvidenceTier
    source_sha256: str
    sequence_policy: str = "none"  # none, monotone, contiguous
    origin: str = "unknown"
    license_reference: str = "unspecified"
    evidence_reference: str = "unspecified"

    def __post_init__(self):
        for key in ("source_id", "representation_id", "symbol", "origin"):
            _name(getattr(self, key), key)
        if (not isinstance(self.capabilities, tuple) or not self.capabilities
                or len(self.capabilities) != len(set(self.capabilities))
                or set(self.capabilities) - CAPABILITIES):
            raise ValueError("source capabilities must be explicit and supported")
        if self.sequence_policy not in ("none", "monotone", "contiguous"):
            raise ValueError("invalid sequence policy")
        if not isinstance(self.source_sha256, str) or not SHA.fullmatch(self.source_sha256):
            raise ValueError("source SHA-256 required")
        if not isinstance(self.max_evidence_tier, EvidenceTier):
            raise ValueError("evidence tier must be an EvidenceTier")
        if self.max_evidence_tier >= EvidenceTier.TRUE_TRADE and self.origin != "synthetic":
            if self.origin == "unknown" or self.license_reference == "unspecified" or self.evidence_reference == "unspecified":
                raise ValueError("real trade/depth source needs provider, license and provenance references")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict) -> "SourceSpec":
        return cls(**{**value, "capabilities": tuple(value["capabilities"]),
                      "max_evidence_tier": EvidenceTier(value["max_evidence_tier"])})


@dataclass(frozen=True)
class Observation:
    source_id: str
    source_event_id: str
    revision: int
    kind: str
    event_ns: int
    available_ns: int
    ingested_ns: int
    evidence_tier: EvidenceTier
    payload: dict[str, Any]
    plane: str = "research"
    published_ns: int | None = None
    sequence: int | None = None
    quality_flags: tuple[str, ...] = ()
    availability_basis: str = "observed_receipt"

    def __post_init__(self):
        _name(self.source_id, "source_id")
        _name(self.source_event_id, "source_event_id")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be positive")
        if self.kind not in KINDS or self.plane not in PLANES:
            raise ValueError("unknown observation kind or plane")
        for key in ("event_ns", "available_ns", "ingested_ns"):
            _ns(getattr(self, key), key)
        if self.kind != "schedule" and self.event_ns > self.available_ns:
            raise ValueError("observation cannot be available before its event")
        if self.available_ns > self.ingested_ns:
            raise ValueError("availability cannot be after ingestion")
        if self.availability_basis == "observed_receipt" and self.available_ns != self.ingested_ns:
            raise ValueError("observed receipt availability must equal ingestion time")
        if self.published_ns is not None:
            _ns(self.published_ns, "published_ns")
            if self.published_ns > self.available_ns:
                raise ValueError("publication cannot follow claimed availability")
        if self.sequence is not None and (type(self.sequence) is not int or self.sequence < 0):
            raise ValueError("invalid source-local sequence")
        if self.availability_basis not in ("observed_receipt", "attested_release", "verified_bar_close", "derived_at_decision", "synthetic"):
            raise ValueError("unknown availability basis")
        if self.availability_basis == "derived_at_decision":
            if self.kind != "context":
                raise ValueError("derived_at_decision is restricted to context observations")
            if self.event_ns != self.available_ns:
                raise ValueError("derived_at_decision requires event_ns == available_ns")
        if not isinstance(self.payload, dict) or any(not isinstance(k, str) for k in self.payload):
            raise ValueError("payload must be an object")
        canonical(self.payload)
        if not isinstance(self.quality_flags, tuple) or any(not isinstance(flag, str) or len(flag) > 80 for flag in self.quality_flags):
            raise ValueError("invalid quality flag")
        if not isinstance(self.evidence_tier, EvidenceTier):
            raise ValueError("evidence tier must be an EvidenceTier")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict) -> "Observation":
        return cls(**{**value, "quality_flags": tuple(value.get("quality_flags", ())),
                      "evidence_tier": EvidenceTier(value["evidence_tier"])})


def validate_source_event(source: SourceSpec, event: Observation) -> None:
    if event.source_id != source.source_id or event.kind not in source.capabilities:
        raise ValueError("event does not match registered source capability")
    if event.evidence_tier > source.max_evidence_tier:
        raise ValueError("evidence tier exceeds source capability")
    if event.kind == "trade" and event.evidence_tier != EvidenceTier.TRUE_TRADE:
        raise ValueError("trade event requires authenticated trade evidence")
    if event.kind.startswith("book_") and event.evidence_tier != EvidenceTier.TRUE_DEPTH:
        raise ValueError("book event requires authenticated depth evidence")
    if event.kind.startswith("book_") and source.sequence_policy != "contiguous":
        raise ValueError("book replay requires a contiguous source sequence")
    if event.kind == "bar" and event.evidence_tier != EvidenceTier.CANDLE_PROXY:
        raise ValueError("aggregated bars do not inherit order-book evidence")
    if event.kind in ("book_snapshot", "book_delta") and event.sequence is None:
        raise ValueError("book event requires source sequence")
    if source.sequence_policy != "none" and event.sequence is None:
        raise ValueError("sequenced source requires source-local sequence")
    if event.availability_basis == "synthetic" and "synthetic" not in event.quality_flags:
        raise ValueError("synthetic data must be labeled")
    if event.availability_basis == "derived_at_decision" and source.origin != "nexus_derived":
        raise ValueError("derived_at_decision requires a nexus_derived source")
    if source.origin == "synthetic" and event.availability_basis != "synthetic":
        raise ValueError("synthetic source must retain its synthetic label")
    if source.origin != "synthetic" and (event.availability_basis == "synthetic" or "synthetic" in event.quality_flags):
        raise ValueError("synthetic event requires a synthetic source manifest")
    p = event.payload
    def number(key, *, positive=False, nonnegative=False):
        v = p.get(key)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise ValueError(f"{event.kind} requires finite {key}")
        if (positive and v <= 0) or (nonnegative and v < 0):
            raise ValueError(f"invalid {event.kind} {key}")
        return float(v)
    if event.kind == "bar":
        o, h, lo, c = (number(k) for k in ("open", "high", "low", "close"))
        if h < max(o, c) or lo > min(o, c) or h < lo:
            raise ValueError("bar OHLC is inconsistent")
        if "volume" in p:
            number("volume", nonnegative=True)
    elif event.kind == "trade":
        number("price"); number("size", positive=True)
        if p.get("side", "unknown") not in ("buy", "sell", "unknown"):
            raise ValueError("trade aggressor side is unknown or buy/sell")
    elif event.kind == "book_snapshot":
        if not all(isinstance(p.get(k), list) and p[k] for k in ("bids", "asks")):
            raise ValueError("book snapshot requires both sides")
        for side in ("bids", "asks"):
            for level in p[side]:
                if not isinstance(level, list) or len(level) != 2 or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in level) or level[1] <= 0:
                    raise ValueError("book levels must have finite price and positive size")
        if max(level[0] for level in p["bids"]) >= min(level[0] for level in p["asks"]):
            raise ValueError("book snapshot is crossed")
    elif event.kind == "book_delta":
        if p.get("side") not in ("bid", "ask") or p.get("action") not in ("set", "delete"):
            raise ValueError("book delta requires side and set/delete action")
        number("price"); size = number("size", nonnegative=True)
        if p["action"] == "set" and size == 0:
            raise ValueError("set delta cannot have zero size")
    elif event.kind == "macro":
        if not isinstance(p.get("series"), str) or not p["series"]:
            raise ValueError("macro observation requires a series identity")
        if source.origin != "synthetic" and (not isinstance(p.get("period"), str) or not p["period"]):
            raise ValueError("real macro observation requires a period identity")
    elif event.kind == "schedule" and not isinstance(p.get("name"), str):
        raise ValueError("schedule requires a named event")
