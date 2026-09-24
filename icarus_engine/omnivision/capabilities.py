"""Versioned source-capability contracts for OMNIVISION research."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Final

ACCESS_CLASSES: Final = frozenset({"public", "licensed", "connected", "user_authorized"})
EPISTEMIC_ROLES: Final = frozenset({
    "primary_observation", "aggregator", "analyst_opinion", "media",
    "derived_market_data", "negative_control",
})
HEALTH_STATES: Final = frozenset({
    "healthy", "degraded", "rate_limited", "quota_exhausted",
    "blocked_by_source_policy", "entitlement_missing", "schema_changed",
    "stale", "disabled",
})
_MAX_TEXT = 4096


def _canon(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _text(value, name: str) -> str:
    if type(value) is not str or not value.strip() or len(value) > _MAX_TEXT:
        raise ValueError(f"{name} must be a non-empty string <= {_MAX_TEXT} characters")
    return value


def _text_tuple(value, name: str, *, required: bool) -> tuple[str, ...]:
    if type(value) is not tuple or (required and not value):
        qualifier = "non-empty " if required else ""
        raise ValueError(f"{name} must be a {qualifier}tuple")
    for item in value:
        _text(item, f"{name} entry")
    if len(set(value)) != len(value):
        raise ValueError(f"{name} entries must be unique")
    return value


def _time(value, name: str, *, optional: bool = False) -> int | None:
    if value is None and optional:
        return None
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


@dataclass(frozen=True)
class SourceCapability:
    source_id: str
    provider: str
    version: int
    domain_classes: tuple[str, ...]
    access_class: str
    epistemic_role: str
    auth_mode: str
    entitlement_state: str
    health_state: str
    rate_limit_state: str
    cost_class: str
    reliability_evidence: tuple[str, ...]
    timing_semantics: str
    revision_semantics: str
    freshness_policy: str
    allowed_entities: tuple[str, ...]
    forbidden_uses: tuple[str, ...]
    valid_from: int
    valid_until: int | None = None
    review_after: int | None = None
    upstream_source_ids: tuple[str, ...] = ()

    def __post_init__(self):
        _text(self.source_id, "source_id")
        _text(self.provider, "provider")
        if type(self.version) is not int or self.version <= 0:
            raise ValueError("version must be a positive integer")
        _text_tuple(self.domain_classes, "domain_classes", required=True)
        if self.access_class not in ACCESS_CLASSES:
            raise ValueError("unsupported access_class")
        if self.epistemic_role not in EPISTEMIC_ROLES:
            raise ValueError("unsupported epistemic_role")
        for name in (
            "auth_mode", "entitlement_state", "rate_limit_state", "cost_class",
            "timing_semantics", "revision_semantics", "freshness_policy",
        ):
            _text(getattr(self, name), name)
        if self.health_state not in HEALTH_STATES:
            raise ValueError("unsupported health_state")
        _text_tuple(self.reliability_evidence, "reliability_evidence", required=True)
        _text_tuple(self.allowed_entities, "allowed_entities", required=True)
        _text_tuple(self.forbidden_uses, "forbidden_uses", required=False)
        _text_tuple(self.upstream_source_ids, "upstream_source_ids", required=False)
        _time(self.valid_from, "valid_from")
        _time(self.valid_until, "valid_until", optional=True)
        _time(self.review_after, "review_after", optional=True)
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be greater than valid_from")
        if self.review_after is not None and self.review_after < self.valid_from:
            raise ValueError("review_after must be >= valid_from")
        if self.source_id in self.upstream_source_ids:
            raise ValueError("source cannot list itself as upstream")
        if self.epistemic_role == "negative_control" and "research_evidence" not in self.forbidden_uses:
            raise ValueError("negative controls must forbid research_evidence use")

    @property
    def capability_id(self) -> str:
        return _digest(asdict(self))


def source_capability_id(capability: SourceCapability) -> str:
    if not isinstance(capability, SourceCapability):
        raise TypeError("capability must be SourceCapability")
    return capability.capability_id
