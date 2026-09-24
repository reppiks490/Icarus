import dataclasses

import pytest

from icarus_engine.omnivision.capabilities import SourceCapability


def capability(**changes):
    values = dict(
        source_id="fmp-treasury",
        provider="FMP",
        version=1,
        domain_classes=("macro", "rates"),
        access_class="licensed",
        epistemic_role="primary_observation",
        auth_mode="api_key",
        entitlement_state="active",
        health_state="healthy",
        rate_limit_state="within_limit",
        cost_class="metered",
        reliability_evidence=("dated_release",),
        timing_semantics="release_date",
        revision_semantics="append_revision",
        freshness_policy="until_superseded",
        allowed_entities=("US_TREASURY",),
        forbidden_uses=("live_execution",),
        valid_from=100,
        valid_until=None,
        review_after=200,
        upstream_source_ids=(),
    )
    values.update(changes)
    return SourceCapability(**values)


def test_capability_is_frozen_and_identity_is_deterministic():
    left = capability()
    right = capability()
    assert left.capability_id == right.capability_id
    assert len(left.capability_id) == 64
    with pytest.raises(dataclasses.FrozenInstanceError):
        left.provider = "changed"


def test_capability_identity_changes_with_health_and_timing():
    healthy = capability(health_state="healthy")
    limited = capability(health_state="rate_limited")
    timing_changed = capability(timing_semantics="session_end_date")
    assert healthy.capability_id != limited.capability_id
    assert healthy.capability_id != timing_changed.capability_id


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("version", 0),
        ("version", True),
        ("access_class", "scraped"),
        ("epistemic_role", "fact"),
        ("health_state", "up"),
        ("source_id", ""),
        ("provider", ""),
        ("auth_mode", ""),
        ("entitlement_state", ""),
        ("rate_limit_state", ""),
        ("cost_class", ""),
        ("timing_semantics", ""),
        ("revision_semantics", ""),
        ("freshness_policy", ""),
    ],
)
def test_capability_rejects_invalid_scalar_contract(field, value):
    with pytest.raises(ValueError):
        capability(**{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("domain_classes", []),
        ("domain_classes", ()),
        ("domain_classes", ("macro", "macro")),
        ("reliability_evidence", ()),
        ("reliability_evidence", ("dated_release", "dated_release")),
        ("allowed_entities", ()),
        ("allowed_entities", ("US_TREASURY", "US_TREASURY")),
        ("forbidden_uses", ["live_execution"]),
        ("upstream_source_ids", ["official-release"]),
    ],
)
def test_capability_rejects_invalid_tuple_contract(field, value):
    with pytest.raises(ValueError):
        capability(**{field: value})


def test_capability_rejects_invalid_validity_window():
    with pytest.raises(ValueError):
        capability(valid_until=100)
    with pytest.raises(ValueError):
        capability(valid_until=99)
    with pytest.raises(ValueError):
        capability(review_after=99)
    with pytest.raises(ValueError):
        capability(valid_from=True)


def test_capability_rejects_self_upstream_and_overlong_text():
    with pytest.raises(ValueError):
        capability(upstream_source_ids=("fmp-treasury",))
    with pytest.raises(ValueError):
        capability(provider="x" * 4097)


def test_negative_control_must_forbid_research_evidence_use():
    with pytest.raises(ValueError):
        capability(
            epistemic_role="negative_control",
            forbidden_uses=("live_execution",),
        )

    item = capability(
        epistemic_role="negative_control",
        forbidden_uses=("live_execution", "research_evidence"),
    )
    assert item.epistemic_role == "negative_control"
