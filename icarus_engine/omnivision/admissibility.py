"""Deterministic semantic admission firewall for OMNIVISION sources."""
from __future__ import annotations

from dataclasses import dataclass

from .capabilities import EPISTEMIC_ROLES, SourceCapability

ADMISSION_REASONS = frozenset({
    "admitted", "capability_not_yet_valid", "capability_expired",
    "health_not_usable", "domain_mismatch", "role_mismatch",
    "entity_not_allowed", "forbidden_use", "negative_control",
})


def _text(value, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _time(value, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


@dataclass(frozen=True)
class AdmissionRequest:
    domain: str
    required_roles: tuple[str, ...]
    entity: str | None = None
    intended_use: str = "research_evidence"

    def __post_init__(self):
        _text(self.domain, "domain")
        if type(self.required_roles) is not tuple or not self.required_roles:
            raise ValueError("required_roles must be a non-empty tuple")
        if len(set(self.required_roles)) != len(self.required_roles):
            raise ValueError("required_roles must be unique")
        if any(role not in EPISTEMIC_ROLES for role in self.required_roles):
            raise ValueError("required_roles contains unsupported role")
        if self.entity is not None:
            _text(self.entity, "entity")
        _text(self.intended_use, "intended_use")


@dataclass(frozen=True)
class AdmissionDecision:
    admitted: bool
    reason_code: str
    capability_id: str
    source_id: str
    decision_at: int


def evaluate_admission(
    capability: SourceCapability,
    request: AdmissionRequest,
    *,
    decision_at: int,
) -> AdmissionDecision:
    if not isinstance(capability, SourceCapability):
        raise TypeError("capability must be SourceCapability")
    if not isinstance(request, AdmissionRequest):
        raise TypeError("request must be AdmissionRequest")
    _time(decision_at, "decision_at")

    reason = "admitted"
    if decision_at < capability.valid_from:
        reason = "capability_not_yet_valid"
    elif capability.valid_until is not None and decision_at >= capability.valid_until:
        reason = "capability_expired"
    elif capability.health_state != "healthy":
        reason = "health_not_usable"
    elif request.domain not in capability.domain_classes:
        reason = "domain_mismatch"
    elif capability.epistemic_role == "negative_control" and request.intended_use == "research_evidence":
        reason = "negative_control"
    elif capability.epistemic_role not in request.required_roles:
        reason = "role_mismatch"
    elif request.entity is not None and request.entity not in capability.allowed_entities and "*" not in capability.allowed_entities:
        reason = "entity_not_allowed"
    elif request.intended_use in capability.forbidden_uses:
        reason = "forbidden_use"

    return AdmissionDecision(
        admitted=reason == "admitted",
        reason_code=reason,
        capability_id=capability.capability_id,
        source_id=capability.source_id,
        decision_at=decision_at,
    )
