from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any
import math

class DataPlane(str, Enum):
    RESEARCH = "research"
    SHADOW = "shadow"
    PRODUCTION = "production"

class QualityFlag(str, Enum):
    APPLEDOUBLE = "appledouble"
    EMPTY = "empty"
    BAD_HEADER = "bad_header"
    BACKWARD_TIME = "backward_time"
    REPEATED_TIME = "repeated_time"
    FRACTIONAL_TIME = "fractional_time"
    CADENCE_AMBIGUOUS = "cadence_ambiguous"
    CLAIM_MISMATCH = "claim_mismatch"
    MISSING_OHLC = "missing_ohlc"
    NON_NUMERIC = "non_numeric"
    EXACT_BYTE_DUPLICATE = "exact_byte_duplicate"
    LOGICAL_DUPLICATE = "logical_duplicate"
    STALE = "stale"
    AVAILABILITY_UNKNOWN = "availability_unknown"
    STAMP_SEMANTICS_UNKNOWN = "stamp_semantics_unknown"
    DERIVED_REPRESENTATION = "derived_representation"
    EVENT_DRIVEN_REPRESENTATION = "event_driven_representation"
    CLOCK_POLICY_REVIEWED = "clock_policy_reviewed"
    DUPLICATE_HEADER = "duplicate_header"
    OHLC_INCONSISTENT = "ohlc_inconsistent"

@dataclass(frozen=True, slots=True)
class StreamIdentity:
    source_id: str
    venue: str | None
    symbol: str
    filename_claim: str | None
    representation: str = "unknown"
    source_path: str = ""
    raw_sha256: str = ""

    def __post_init__(self) -> None:
        for name,value in (("source_id",self.source_id),("symbol",self.symbol)):
            if not isinstance(value,str) or not value.strip() or value != value.strip():
                raise ValueError(f"{name} must be a non-empty trimmed string")
        if self.venue is not None and (
            not isinstance(self.venue,str) or not self.venue.strip() or self.venue != self.venue.strip()
        ):
            raise ValueError("venue must be a non-empty trimmed string or None")
        if self.filename_claim is not None and not isinstance(self.filename_claim,str):
            raise TypeError("filename_claim must be a string or None")
        if not isinstance(self.representation,str) or not self.representation.strip():
            raise ValueError("representation must be non-empty")
        if not isinstance(self.source_path,str):
            raise TypeError("source_path must be a string")
        if not isinstance(self.raw_sha256,str) or len(self.raw_sha256)!=64:
            raise ValueError("raw_sha256 must be a SHA-256 hex digest")
        try:
            int(self.raw_sha256,16)
        except ValueError as exc:
            raise ValueError("raw_sha256 must be a SHA-256 hex digest") from exc
        object.__setattr__(self,"raw_sha256",self.raw_sha256.lower())

    @property
    def stream_id(self) -> str:
        return f"{self.source_id}:{self.symbol}:{self.raw_sha256[:12]}"

@dataclass(slots=True)
class StreamManifest:
    identity: StreamIdentity
    row_count: int
    columns: list[str]
    first_event_ns: int | None
    last_event_ns: int | None
    observed_cadence_ns: int | None
    cadence_confidence: float
    repeated_timestamp_count: int
    backward_timestamp_count: int
    fractional_timestamp_count: int
    byte_duplicate_of: str | None = None
    quality_flags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.identity,StreamIdentity):
            raise TypeError("identity must be StreamIdentity")
        if type(self.row_count) is not int or self.row_count < 0:
            raise ValueError("row_count must be a non-negative integer")
        if not isinstance(self.columns,list) or any(not isinstance(x,str) for x in self.columns):
            raise TypeError("columns must be a list of strings")
        for name,value in (
            ("first_event_ns",self.first_event_ns),
            ("last_event_ns",self.last_event_ns),
        ):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{name} must be a non-negative integer or None")
        if (
            self.first_event_ns is not None
            and self.last_event_ns is not None
            and self.last_event_ns < self.first_event_ns
        ):
            raise ValueError("last_event_ns cannot precede first_event_ns")
        if self.observed_cadence_ns is not None and (
            type(self.observed_cadence_ns) is not int or self.observed_cadence_ns <= 0
        ):
            raise ValueError("observed_cadence_ns must be a positive integer or None")
        confidence=float(self.cadence_confidence)
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise ValueError("cadence_confidence must be finite and in [0,1]")
        for name,value in (
            ("repeated_timestamp_count",self.repeated_timestamp_count),
            ("backward_timestamp_count",self.backward_timestamp_count),
            ("fractional_timestamp_count",self.fractional_timestamp_count),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
            if value > self.row_count:
                raise ValueError(f"{name} cannot exceed row_count")
        if self.byte_duplicate_of is not None and not isinstance(self.byte_duplicate_of,str):
            raise TypeError("byte_duplicate_of must be a string or None")
        if not isinstance(self.quality_flags,list) or any(
            not isinstance(x,str) for x in self.quality_flags
        ):
            raise TypeError("quality_flags must be a list of strings")
        if not isinstance(self.metadata,dict):
            raise TypeError("metadata must be a dict")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["identity"] = asdict(self.identity)
        return d

@dataclass(frozen=True, slots=True)
class BarEvent:
    stream_id: str
    event_ns: int  # completed market-event time; for bars this should be bar close
    source_sequence: int
    open: float
    high: float
    low: float
    close: float
    volume: float | None
    source_path: str
    data_plane: str = DataPlane.RESEARCH.value
    quality_flags: tuple[str, ...] = ()
    available_ns: int | None = None
    revision: int = 0
    source_timestamp_ns: int | None = None
    availability_basis: str = "unknown"

    def __post_init__(self) -> None:
        if not isinstance(self.stream_id,str) or not self.stream_id:
            raise ValueError("stream_id is required")
        for name,value in (
            ("event_ns",self.event_ns),
            ("source_sequence",self.source_sequence),
            ("revision",self.revision),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        for name,value in (
            ("available_ns",self.available_ns),
            ("source_timestamp_ns",self.source_timestamp_ns),
        ):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{name} must be a non-negative integer or None")
        for name,value in (
            ("open",self.open),("high",self.high),("low",self.low),("close",self.close)
        ):
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        if self.volume is not None and not math.isfinite(float(self.volume)):
            raise ValueError("volume must be finite or None")
        if self.data_plane not in {x.value for x in DataPlane}:
            raise ValueError("unsupported data_plane")
        if not isinstance(self.source_path,str):
            raise TypeError("source_path must be a string")
        if not isinstance(self.quality_flags,tuple) or any(
            not isinstance(x,str) for x in self.quality_flags
        ):
            raise TypeError("quality_flags must be a tuple of strings")
        if not isinstance(self.availability_basis,str) or not self.availability_basis:
            raise ValueError("availability_basis is required")

    @property
    def visible_ns(self) -> int:
        return self.event_ns if self.available_ns is None else self.available_ns

    @property
    def ordering_key(self) -> tuple[int, str, int, int]:
        return (self.visible_ns, self.stream_id, self.source_sequence, self.revision)

@dataclass(frozen=True, slots=True)
class ReplayBatch:
    visible_ns: int
    events: tuple[BarEvent, ...]

    def __post_init__(self):
        if type(self.visible_ns) is not int or self.visible_ns < 0:
            raise ValueError("replay-batch visible_ns must be a non-negative integer")
        if not isinstance(self.events,tuple) or not self.events:
            raise ValueError("replay batch must contain at least one event")
        if any(e.visible_ns != self.visible_ns for e in self.events):
            raise ValueError("all replay-batch events must share visible_ns")

@dataclass(frozen=True, slots=True)
class ReplayInstant:
    """One atomic replay batch bound to the post-batch market state it produced."""

    batch: ReplayBatch
    state: "StatePacket"

    def __post_init__(self) -> None:
        if self.state.decision_ns != self.batch.visible_ns:
            raise ValueError("replay instant state and batch must share decision/visibility time")
        if self.state.batch_size != len(self.batch.events):
            raise ValueError("replay instant state batch_size mismatch")
        if not self.state.frame_hash:
            raise ValueError("replay instant requires deterministic frame_hash")

    @property
    def decision_ns(self) -> int:
        return self.state.decision_ns


@dataclass(frozen=True, slots=True)
class StatePacket:
    decision_ns: int
    values: dict[str, float]
    ages_ns: dict[str, int]
    missing: tuple[str, ...]
    source_sequences: dict[str, int]
    lineage: dict[str, str]
    data_plane: str = DataPlane.RESEARCH.value
    batch_size: int = 1
    frame_hash: str | None = None

    def __post_init__(self) -> None:
        if type(self.decision_ns) is not int or self.decision_ns < 0:
            raise ValueError("decision_ns must be a non-negative integer")
        if type(self.batch_size) is not int or self.batch_size < 1:
            raise ValueError("batch_size must be a positive integer")
        if self.data_plane not in {x.value for x in DataPlane}:
            raise ValueError("unsupported data_plane")
        if self.frame_hash is not None and (
            not isinstance(self.frame_hash,str) or not self.frame_hash
        ):
            raise ValueError("frame_hash must be a non-empty string or None")
        keys=set(self.values)
        if keys != set(self.ages_ns) or keys != set(self.source_sequences) or keys != set(self.lineage):
            raise ValueError("state values/ages/source_sequences/lineage keys must match")
        if (
            not isinstance(self.missing,tuple)
            or any(not isinstance(x,str) or not x for x in self.missing)
            or len(set(self.missing)) != len(self.missing)
        ):
            raise ValueError("missing must be a unique tuple of non-empty stream ids")
        if tuple(sorted(self.missing)) != self.missing:
            raise ValueError("missing stream ids must be sorted canonically")
        if keys & set(self.missing):
            raise ValueError("present state values cannot also be missing")
        for sid,value in self.values.items():
            if not isinstance(sid,str) or not sid:
                raise ValueError("state stream ids must be non-empty strings")
            if not math.isfinite(float(value)):
                raise ValueError(f"state value for {sid!r} must be finite")
            age=self.ages_ns[sid]
            seq=self.source_sequences[sid]
            if type(age) is not int or age < 0 or age > self.decision_ns:
                raise ValueError(f"state age for {sid!r} is invalid")
            if type(seq) is not int or seq < 0:
                raise ValueError(f"state sequence for {sid!r} must be non-negative")
            if not isinstance(self.lineage[sid],str) or not self.lineage[sid]:
                raise ValueError(f"state lineage for {sid!r} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class SyntheticPoint:
    ticker: str
    event_ns: int
    value: float
    component_values: dict[str, float]
    weights: dict[str, float]
    confidence: float
    lineage: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.ticker,str) or not self.ticker.strip() or self.ticker != self.ticker.strip():
            raise ValueError("ticker must be a non-empty trimmed string")
        if type(self.event_ns) is not int or self.event_ns < 0:
            raise ValueError("event_ns must be a non-negative integer")
        if not math.isfinite(float(self.value)):
            raise ValueError("synthetic value must be finite")
        if not isinstance(self.component_values,dict) or not self.component_values:
            raise ValueError("component_values must be a non-empty dict")
        if not isinstance(self.weights,dict) or set(self.weights) != set(self.component_values):
            raise ValueError("weights must be a dict with exactly the component keys")
        for key,value in self.component_values.items():
            if not isinstance(key,str) or not key:
                raise ValueError("component ids must be non-empty strings")
            if not math.isfinite(float(value)):
                raise ValueError(f"component value for {key!r} must be finite")
            weight=self.weights[key]
            if not math.isfinite(float(weight)):
                raise ValueError(f"weight for {key!r} must be finite")
        conf=float(self.confidence)
        if not math.isfinite(conf) or not 0.0 <= conf <= 1.0:
            raise ValueError("confidence must be finite and in [0,1]")
        if (
            not isinstance(self.lineage,tuple)
            or not self.lineage
            or any(not isinstance(x,str) or not x for x in self.lineage)
            or len(set(self.lineage)) != len(self.lineage)
        ):
            raise ValueError("lineage must be a non-empty unique tuple of identifiers")

@dataclass(frozen=True, slots=True)
class VectorEvent:
    """Generic numeric market/context event with position-stable field identities."""
    stream_id: str
    event_ns: int
    source_sequence: int
    fields: tuple[tuple[str, float], ...]
    source_path: str
    data_plane: str = DataPlane.RESEARCH.value
    quality_flags: tuple[str, ...] = ()
    available_ns: int | None = None
    revision: int = 0
    source_timestamp_ns: int | None = None
    availability_basis: str = "unknown"

    def __post_init__(self) -> None:
        if not isinstance(self.stream_id,str) or not self.stream_id:
            raise ValueError("stream_id is required")
        for name,value in (
            ("event_ns",self.event_ns),
            ("source_sequence",self.source_sequence),
            ("revision",self.revision),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        for name,value in (
            ("available_ns",self.available_ns),
            ("source_timestamp_ns",self.source_timestamp_ns),
        ):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{name} must be a non-negative integer or None")
        if not isinstance(self.fields,tuple):
            raise TypeError("fields must be a tuple")
        if not self.fields:
            raise ValueError("vector event must contain at least one numeric field")
        names=[]
        for field_name,value in self.fields:
            if not isinstance(field_name,str) or not field_name:
                raise ValueError("vector field names must be non-empty strings")
            if not math.isfinite(float(value)):
                raise ValueError(f"vector field {field_name!r} must be finite")
            names.append(field_name)
        if len(set(names)) != len(names):
            raise ValueError("vector field names must be unique")
        if self.data_plane not in {x.value for x in DataPlane}:
            raise ValueError("unsupported data_plane")
        if not isinstance(self.source_path,str):
            raise TypeError("source_path must be a string")
        if not isinstance(self.quality_flags,tuple) or any(
            not isinstance(x,str) for x in self.quality_flags
        ):
            raise TypeError("quality_flags must be a tuple of strings")
        if not isinstance(self.availability_basis,str) or not self.availability_basis:
            raise ValueError("availability_basis is required")

    @property
    def visible_ns(self) -> int:
        return self.event_ns if self.available_ns is None else self.available_ns

    @property
    def ordering_key(self) -> tuple[int, str, int, int]:
        return (self.visible_ns, self.stream_id, self.source_sequence, self.revision)

    def values(self) -> dict[str, float]:
        return dict(self.fields)

@dataclass(frozen=True, slots=True)
class VectorStatePacket:
    decision_ns: int
    values: dict[str, dict[str, float]]
    ages_ns: dict[str, int]
    missing: tuple[str, ...]
    source_sequences: dict[str, int]
    lineage: dict[str, str]
    data_plane: str = DataPlane.RESEARCH.value
    batch_size: int = 1
    frame_hash: str | None = None

    def __post_init__(self) -> None:
        if type(self.decision_ns) is not int or self.decision_ns < 0:
            raise ValueError("decision_ns must be a non-negative integer")
        if type(self.batch_size) is not int or self.batch_size < 1:
            raise ValueError("batch_size must be a positive integer")
        if self.data_plane not in {x.value for x in DataPlane}:
            raise ValueError("unsupported data_plane")
        if self.frame_hash is not None and (
            not isinstance(self.frame_hash,str) or not self.frame_hash
        ):
            raise ValueError("frame_hash must be a non-empty string or None")
        keys=set(self.values)
        if keys != set(self.ages_ns) or keys != set(self.source_sequences) or keys != set(self.lineage):
            raise ValueError("vector state values/ages/source_sequences/lineage keys must match")
        if (
            not isinstance(self.missing,tuple)
            or any(not isinstance(x,str) or not x for x in self.missing)
            or len(set(self.missing)) != len(self.missing)
        ):
            raise ValueError("missing must be a unique tuple of non-empty stream ids")
        if tuple(sorted(self.missing)) != self.missing:
            raise ValueError("missing stream ids must be sorted canonically")
        if keys & set(self.missing):
            raise ValueError("present vector state values cannot also be missing")
        for sid,fields in self.values.items():
            if not isinstance(sid,str) or not sid:
                raise ValueError("vector state stream ids must be non-empty strings")
            if not isinstance(fields,dict) or not fields:
                raise ValueError(f"vector state fields for {sid!r} must be non-empty")
            if any(not isinstance(k,str) or not k for k in fields):
                raise ValueError(f"vector state field names for {sid!r} must be non-empty strings")
            if any(not math.isfinite(float(v)) for v in fields.values()):
                raise ValueError(f"vector state fields for {sid!r} must be finite")
            age=self.ages_ns[sid]
            seq=self.source_sequences[sid]
            if type(age) is not int or age < 0 or age > self.decision_ns:
                raise ValueError(f"vector state age for {sid!r} is invalid")
            if type(seq) is not int or seq < 0:
                raise ValueError(f"vector state sequence for {sid!r} must be non-negative")
            if not isinstance(self.lineage[sid],str) or not self.lineage[sid]:
                raise ValueError(f"vector state lineage for {sid!r} must be a non-empty string")
