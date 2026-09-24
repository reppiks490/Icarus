import pytest

from icarus_engine.omnivision.admissibility import AdmissionRequest, evaluate_admission
from icarus_engine.omnivision.capabilities import SourceCapability


def capability(**changes):
    values = dict(
        source_id="macro-source", provider="Provider", version=1,
        domain_classes=("macro",), access_class="public",
        epistemic_role="primary_observation", auth_mode="none",
        entitlement_state="public", health_state="healthy",
        rate_limit_state="within_limit", cost_class="free",
        reliability_evidence=("official_release",), timing_semantics="published_at",
        revision_semantics="versioned", freshness_policy="until_superseded",
        allowed_entities=("US_CPI",), forbidden_uses=("live_execution",),
        valid_from=100, valid_until=300, review_after=250, upstream_source_ids=(),
    )
    values.update(changes)
    return SourceCapability(**values)


def request(**changes):
    values = dict(domain="macro", required_roles=("primary_observation",), entity="US_CPI")
    values.update(changes)
    return AdmissionRequest(**values)


def test_matching_healthy_primary_source_is_admitted():
    decision = evaluate_admission(capability(), request(), decision_at=150)
    assert decision.admitted is True
    assert decision.reason_code == "admitted"
    assert decision.capability_id == capability().capability_id
    assert decision.source_id == "macro-source"
    assert decision.decision_at == 150


@pytest.mark.parametrize("health", [
    "degraded", "rate_limited", "quota_exhausted", "blocked_by_source_policy",
    "entitlement_missing", "schema_changed", "stale", "disabled",
])
def test_nonhealthy_capability_fails_closed(health):
    decision = evaluate_admission(capability(health_state=health), request(), decision_at=150)
    assert decision.admitted is False
    assert decision.reason_code == "health_not_usable"


@pytest.mark.parametrize("role", ["aggregator", "analyst_opinion", "media", "derived_market_data"])
def test_nonprimary_role_cannot_satisfy_primary_requirement(role):
    decision = evaluate_admission(capability(epistemic_role=role), request(), decision_at=150)
    assert decision.admitted is False
    assert decision.reason_code == "role_mismatch"


def test_aggregator_is_admitted_only_when_explicitly_requested():
    item = capability(epistemic_role="aggregator")
    decision = evaluate_admission(item, request(required_roles=("aggregator",)), decision_at=150)
    assert decision.admitted is True


def test_negative_control_never_becomes_research_evidence():
    item = capability(
        epistemic_role="negative_control",
        forbidden_uses=("live_execution", "research_evidence"),
    )
    decision = evaluate_admission(
        item,
        request(required_roles=("negative_control",), intended_use="research_evidence"),
        decision_at=150,
    )
    assert decision.admitted is False
    assert decision.reason_code == "negative_control"


def test_domain_entity_and_forbidden_use_fail_closed():
    assert evaluate_admission(capability(), request(domain="weather"), decision_at=150).reason_code == "domain_mismatch"
    assert evaluate_admission(capability(), request(entity="EU_CPI"), decision_at=150).reason_code == "entity_not_allowed"
    assert evaluate_admission(capability(), request(intended_use="live_execution"), decision_at=150).reason_code == "forbidden_use"


def test_validity_window_is_enforced():
    assert evaluate_admission(capability(), request(), decision_at=99).reason_code == "capability_not_yet_valid"
    assert evaluate_admission(capability(), request(), decision_at=300).reason_code == "capability_expired"


def test_request_rejects_invalid_roles_or_time():
    with pytest.raises(ValueError):
        request(required_roles=())
    with pytest.raises(ValueError):
        request(required_roles=("fact",))
    with pytest.raises(ValueError):
        evaluate_admission(capability(), request(), decision_at=-1)
