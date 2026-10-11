from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import math
import re
from types import MappingProxyType
from typing import Any, Mapping


_HEX64_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_HEX40_RE = re.compile(r"^[0-9a-fA-F]{40}$")


class SourceClass(str, Enum):
    LICENSED_FEED = "licensed_feed"
    OFFICIAL_PUBLIC_API = "official_public_api"
    OFFICIAL_PUBLIC_FILE = "official_public_file"
    PUBLIC_STRUCTURED_PAGE = "public_structured_page"
    PUBLIC_UNSTRUCTURED_PAGE = "public_unstructured_page"
    THIRD_PARTY_API = "third_party_api"
    SCRAPER_ACTOR = "scraper_actor"
    BROWSER_AGENT = "browser_agent"
    LLM_EXTRACTOR = "llm_extractor"
    MCP_CAPABILITY = "mcp_capability"
    AI_TOOL = "ai_tool"
    RESEARCH_TOOL = "research_tool"
    UNKNOWN = "unknown"


class DataClass(str, Enum):
    MARKET_PRICE = "market_price"
    MARKET_MICROSTRUCTURE = "market_microstructure"
    DERIVATIVES_POSITIONING = "derivatives_positioning"
    FUNDAMENTAL = "fundamental"
    CORPORATE_EVENT = "corporate_event"
    MACRO = "macro"
    RATES_CREDIT = "rates_credit"
    NEWS = "news"
    GEOPOLITICAL = "geopolitical"
    SOCIAL = "social"
    SEARCH_ATTENTION = "search_attention"
    REGULATORY = "regulatory"
    SUPPLY_CHAIN = "supply_chain"
    PROCUREMENT = "procurement"
    WEATHER = "weather"
    LABOR = "labor"
    CONSUMER_ECOMMERCE = "consumer_ecommerce"
    HOUSING_REAL_ESTATE = "housing_real_estate"
    TRAVEL_MOBILITY = "travel_mobility"
    CRYPTO_CHAIN = "crypto_chain"
    RESEARCH_DOCUMENT = "research_document"
    SOFTWARE_CAPABILITY = "software_capability"
    OTHER = "other"


class PolicyState(str, Enum):
    UNKNOWN = "UNKNOWN"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ALLOWED_RESEARCH = "ALLOWED_RESEARCH"
    ALLOWED_PRODUCTION_DATA = "ALLOWED_PRODUCTION_DATA"
    RESTRICTED = "RESTRICTED"
    REJECTED = "REJECTED"


class CostModel(str, Enum):
    FREE = "free"
    SUBSCRIPTION = "subscription"
    PER_REQUEST = "per_request"
    PER_RESULT = "per_result"
    COMPUTE_METERED = "compute_metered"
    UNKNOWN = "unknown"


class QualificationState(str, Enum):
    DISCOVERED = "DISCOVERED"
    ACCESS_TESTED = "ACCESS_TESTED"
    SCHEMA_PROFILED = "SCHEMA_PROFILED"
    LICENSE_TOS_CHECKED = "LICENSE_TOS_CHECKED"
    LATENCY_TESTED = "LATENCY_TESTED"
    RELIABILITY_TESTED = "RELIABILITY_TESTED"
    DUPLICATE_CHECKED = "DUPLICATE_CHECKED"
    HISTORICAL_DEPTH_TESTED = "HISTORICAL_DEPTH_TESTED"
    ALPHA_HYPOTHESIS_DEFINED = "ALPHA_HYPOTHESIS_DEFINED"
    POINT_IN_TIME_BACKTESTED = "POINT_IN_TIME_BACKTESTED"
    SHADOW_MODE = "SHADOW_MODE"
    PRODUCTION = "PRODUCTION"


class Disposition(str, Enum):
    ACTIVE = "ACTIVE"
    QUARANTINED = "QUARANTINED"
    REJECTED = "REJECTED"
    STALE = "STALE"
    DEMOTED = "DEMOTED"
    RETIRED = "RETIRED"


def validate_sha256(value: str) -> str:
    if not isinstance(value, str) or not _HEX64_RE.fullmatch(value):
        raise ValueError("expected a 64-hex SHA-256")
    return value.lower()


def validate_commit_sha(value: str) -> str:
    if not isinstance(value, str) or not _HEX40_RE.fullmatch(value):
        raise ValueError("expected an immutable 40-hex git commit SHA")
    return value.lower()


def utc_iso(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must be a non-empty ISO-8601 string")
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw[:-1] + "+00:00" if raw.endswith("Z") else raw)
    except ValueError as exc:
        raise ValueError("timestamp must be valid ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include an explicit timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _finite_optional(value: float | int | None, *, name: str, non_negative: bool = False) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number or null")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    if non_negative and result < 0:
        raise ValueError(f"{name} must be non-negative")
    return result


def _non_negative_int(value: int, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _authority(execution_authorized: bool, production_decision_authorized: bool) -> None:
    if execution_authorized is not False or production_decision_authorized is not False:
        raise ValueError("discovery registry records cannot carry execution or production-decision authority")


def _freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


def _serialize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(k): _serialize(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if is_dataclass(value):
        return {item.name: _serialize(getattr(value, item.name)) for item in fields(value)}
    return value


class _Serializable:
    def to_dict(self) -> dict[str, Any]:
        payload = {item.name: _serialize(getattr(self, item.name)) for item in fields(self)}
        payload["execution_authorized"] = False
        payload["production_decision_authorized"] = False
        return payload


@dataclass(frozen=True, slots=True, kw_only=True)
class CatalogSnapshot(_Serializable):
    catalog_id: str
    upstream_repo: str
    upstream_commit: str
    upstream_path: str
    content_sha256: str
    retrieved_at: str
    parser_revision: str
    snapshot_id: str | None = None
    entry_count_raw: int = 0
    entry_count_normalized: int = 0
    parse_failures: tuple[Mapping[str, str], ...] = ()
    execution_authorized: bool = False
    production_decision_authorized: bool = False

    def __post_init__(self) -> None:
        _authority(self.execution_authorized, self.production_decision_authorized)
        if not self.catalog_id or not self.upstream_repo or not self.upstream_path or not self.parser_revision:
            raise ValueError("catalog snapshot identity fields must be non-empty")
        commit = validate_commit_sha(self.upstream_commit)
        digest = validate_sha256(self.content_sha256)
        retrieved = utc_iso(self.retrieved_at)
        _non_negative_int(self.entry_count_raw, name="entry_count_raw")
        _non_negative_int(self.entry_count_normalized, name="entry_count_normalized")
        failures = tuple(MappingProxyType(dict(item)) for item in self.parse_failures)
        snapshot_id = self.snapshot_id
        if snapshot_id is None:
            material = "\0".join(
                (self.catalog_id, self.upstream_repo, commit, self.upstream_path, self.parser_revision, digest)
            )
            snapshot_id = hashlib.sha256(material.encode("utf-8")).hexdigest()
        elif not isinstance(snapshot_id, str) or not snapshot_id:
            raise ValueError("snapshot_id must be non-empty when supplied")
        object.__setattr__(self, "upstream_commit", commit)
        object.__setattr__(self, "content_sha256", digest)
        object.__setattr__(self, "retrieved_at", retrieved)
        object.__setattr__(self, "parse_failures", failures)
        object.__setattr__(self, "snapshot_id", snapshot_id)


@dataclass(frozen=True, slots=True, kw_only=True)
class CatalogEntry(_Serializable):
    entry_id: str
    snapshot_id: str
    catalog_id: str
    source_path: str
    canonical_name: str
    endpoint_or_tool_url: str
    description: str = ""
    category: str | None = None
    raw_row_sha256: str | None = None
    source_order: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_authorized: bool = False
    production_decision_authorized: bool = False

    def __post_init__(self) -> None:
        _authority(self.execution_authorized, self.production_decision_authorized)
        if not all((self.entry_id, self.snapshot_id, self.catalog_id, self.source_path, self.canonical_name, self.endpoint_or_tool_url)):
            raise ValueError("catalog entry identity fields must be non-empty")
        if self.raw_row_sha256 is not None:
            object.__setattr__(self, "raw_row_sha256", validate_sha256(self.raw_row_sha256))
        _non_negative_int(self.source_order, name="source_order")
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True, slots=True, kw_only=True)
class Candidate(_Serializable):
    candidate_id: str
    canonical_name: str
    endpoint_or_tool_url: str
    provider_name: str | None = None
    capability_kind: str | None = None
    data_class: tuple[DataClass, ...] = (DataClass.OTHER,)
    asset_classes: tuple[str, ...] = ()
    source_class: SourceClass = SourceClass.UNKNOWN
    protocols: tuple[str, ...] = ()
    upstream_catalog_refs: tuple[str, ...] = ()
    upstream_entry_hashes: tuple[str, ...] = ()
    description: str = ""
    capability_only: bool = False
    challenger_only: bool = False
    auth_type: str | None = None
    license_state: str | None = None
    tos_state: str | None = None
    policy_state: PolicyState = PolicyState.UNKNOWN
    estimated_cost_model: CostModel = CostModel.UNKNOWN
    budget_required: bool = False
    event_time_support: bool | None = None
    retrieval_time_support: bool | None = None
    historical_depth: str | None = None
    refresh_frequency: str | None = None
    schema_fingerprint: str | None = None
    schema_stability: float | None = None
    source_quality: float | None = None
    reliability: float | None = None
    latency_ms: float | None = None
    freshness: float | None = None
    leakage_risk: float | None = None
    duplicate_group_id: str | None = None
    predictive_value: float | None = None
    marginal_information_score: float | None = None
    qualification_state: QualificationState = QualificationState.DISCOVERED
    disposition: Disposition = Disposition.ACTIVE
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    last_verified_at: str | None = None
    staleness_reason: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_authorized: bool = False
    production_decision_authorized: bool = False

    def __post_init__(self) -> None:
        _authority(self.execution_authorized, self.production_decision_authorized)
        object.__setattr__(self, "candidate_id", validate_sha256(self.candidate_id))
        if not self.canonical_name or not self.endpoint_or_tool_url:
            raise ValueError("candidate name and URL must be non-empty")
        if not self.data_class:
            raise ValueError("candidate data_class cannot be empty")
        for field_name in (
            "schema_stability",
            "source_quality",
            "reliability",
            "freshness",
            "leakage_risk",
            "predictive_value",
            "marginal_information_score",
        ):
            object.__setattr__(self, field_name, _finite_optional(getattr(self, field_name), name=field_name))
        object.__setattr__(self, "latency_ms", _finite_optional(self.latency_ms, name="latency_ms", non_negative=True))
        for time_field in ("first_seen_at", "last_seen_at", "last_verified_at"):
            current = getattr(self, time_field)
            if current is not None:
                object.__setattr__(self, time_field, utc_iso(current))
        for tuple_field in ("data_class", "asset_classes", "protocols", "upstream_catalog_refs", "upstream_entry_hashes"):
            object.__setattr__(self, tuple_field, tuple(getattr(self, tuple_field)))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    @classmethod
    def minimum(
        cls,
        *,
        candidate_id: str,
        canonical_name: str,
        endpoint_or_tool_url: str,
        source_quality: float | int | None = None,
        **overrides: Any,
    ) -> "Candidate":
        forbidden = {"execution_authorized", "production_decision_authorized"} & overrides.keys()
        if forbidden:
            raise ValueError("authority flags cannot be overridden")
        return cls(
            candidate_id=candidate_id,
            canonical_name=canonical_name,
            endpoint_or_tool_url=endpoint_or_tool_url,
            source_quality=source_quality,
            **overrides,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class QualificationEvent(_Serializable):
    candidate_id: str
    old_state: QualificationState
    new_state: QualificationState
    occurred_at: str
    event_id: str | None = None
    evidence_ref: str | None = None
    reason_code: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_authorized: bool = False
    production_decision_authorized: bool = False

    def __post_init__(self) -> None:
        _authority(self.execution_authorized, self.production_decision_authorized)
        object.__setattr__(self, "candidate_id", validate_sha256(self.candidate_id))
        object.__setattr__(self, "occurred_at", utc_iso(self.occurred_at))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))
        assert_transition(self.old_state, self.new_state)


@dataclass(frozen=True, slots=True, kw_only=True)
class PolicyDecision(_Serializable):
    policy_state: PolicyState
    reason_code: str
    decided_at: str
    entry_id: str | None = None
    candidate_id: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)
    execution_authorized: bool = False
    production_decision_authorized: bool = False

    def __post_init__(self) -> None:
        _authority(self.execution_authorized, self.production_decision_authorized)
        if not self.reason_code:
            raise ValueError("policy decision requires a reason_code")
        if self.candidate_id is not None:
            object.__setattr__(self, "candidate_id", validate_sha256(self.candidate_id))
        object.__setattr__(self, "decided_at", utc_iso(self.decided_at))
        object.__setattr__(self, "details", _freeze_mapping(self.details))


@dataclass(frozen=True, slots=True, kw_only=True)
class DuplicateGroup(_Serializable):
    group_id: str
    member_ids: tuple[str, ...]
    evidence_level: str
    evidence_key: str
    catalog_refs: tuple[str, ...] = ()
    execution_authorized: bool = False
    production_decision_authorized: bool = False

    def __post_init__(self) -> None:
        _authority(self.execution_authorized, self.production_decision_authorized)
        if not self.group_id or not self.evidence_level or not self.evidence_key:
            raise ValueError("duplicate group identity fields must be non-empty")
        members = tuple(validate_sha256(item) for item in self.member_ids)
        if len(members) < 2:
            raise ValueError("duplicate group requires at least two members")
        object.__setattr__(self, "member_ids", members)
        object.__setattr__(self, "catalog_refs", tuple(self.catalog_refs))

    @property
    def effective_independent_count(self) -> int:
        """A structural family is one evidence lineage, not multiple sources."""
        return 1


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderLink(_Serializable):
    candidate_id: str
    provider_id: str
    operation_id: str
    linked_at: str
    evidence_ref: str | None = None
    link_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_authorized: bool = False
    production_decision_authorized: bool = False

    def __post_init__(self) -> None:
        _authority(self.execution_authorized, self.production_decision_authorized)
        object.__setattr__(self, "candidate_id", validate_sha256(self.candidate_id))
        if not self.provider_id or not self.operation_id:
            raise ValueError("provider link requires provider_id and operation_id")
        object.__setattr__(self, "linked_at", utc_iso(self.linked_at))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


_QUALIFICATION_ORDER = tuple(QualificationState)
_QUALIFICATION_INDEX = {state: idx for idx, state in enumerate(_QUALIFICATION_ORDER)}


def assert_transition(old: QualificationState, new: QualificationState) -> None:
    if not isinstance(old, QualificationState) or not isinstance(new, QualificationState):
        raise ValueError("lifecycle transition requires QualificationState values")
    if _QUALIFICATION_INDEX[new] != _QUALIFICATION_INDEX[old] + 1:
        raise ValueError(f"illegal qualification transition: {old.value} -> {new.value}")


__all__ = [
    "CatalogEntry",
    "CatalogSnapshot",
    "Candidate",
    "CostModel",
    "DataClass",
    "Disposition",
    "DuplicateGroup",
    "PolicyDecision",
    "PolicyState",
    "ProviderLink",
    "QualificationEvent",
    "QualificationState",
    "SourceClass",
    "assert_transition",
    "utc_iso",
    "validate_commit_sha",
    "validate_sha256",
]
