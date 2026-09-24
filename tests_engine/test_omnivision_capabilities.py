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


import sqlite3
from icarus_engine.omnivision.capabilities import SourceCapabilityRegistry


def test_registry_replays_capability_as_of_decision_time(tmp_path):
    registry = SourceCapabilityRegistry(tmp_path / "capabilities.sqlite3")
    v1 = capability(version=1, valid_from=100, health_state="healthy")
    v2 = capability(version=2, valid_from=200, health_state="rate_limited")
    registry.register(v1, recorded_at=100)
    registry.register(v2, recorded_at=200)
    assert registry.as_of(v1.source_id, 99) is None
    assert registry.as_of(v1.source_id, 150) == v1
    assert registry.as_of(v1.source_id, 200) == v2
    assert registry.as_of(v1.source_id, 250) == v2


def test_registry_never_leaks_future_version_and_honors_expiry(tmp_path):
    registry = SourceCapabilityRegistry(tmp_path / "capabilities.sqlite3")
    expiring = capability(valid_from=100, valid_until=180)
    future = capability(version=2, valid_from=200, health_state="degraded")
    registry.register(expiring, recorded_at=100)
    registry.register(future, recorded_at=200)
    assert registry.as_of(expiring.source_id, 179) == expiring
    assert registry.as_of(expiring.source_id, 180) is None
    assert registry.as_of(expiring.source_id, 199) is None
    assert registry.as_of(expiring.source_id, 200) == future


def test_registry_preserves_review_after_without_auto_disabling(tmp_path):
    registry = SourceCapabilityRegistry(tmp_path / "capabilities.sqlite3")
    item = capability(review_after=120)
    registry.register(item, recorded_at=100)
    replay = registry.as_of(item.source_id, 500)
    assert replay == item
    assert replay.review_after == 120


def test_registry_duplicate_is_idempotent_but_version_collision_rejects(tmp_path):
    registry = SourceCapabilityRegistry(tmp_path / "capabilities.sqlite3")
    item = capability()
    assert registry.register(item, recorded_at=100) == item.capability_id
    assert registry.register(item, recorded_at=100) == item.capability_id
    with pytest.raises(ValueError):
        registry.register(capability(health_state="degraded"), recorded_at=100)


def test_registry_is_append_only_even_through_direct_sql(tmp_path):
    path = tmp_path / "capabilities.sqlite3"
    registry = SourceCapabilityRegistry(path)
    registry.register(capability(), recorded_at=100)
    connection = sqlite3.connect(path)
    with pytest.raises(sqlite3.DatabaseError):
        connection.execute("UPDATE source_capabilities SET recorded_at=999")
    connection.rollback()
    with pytest.raises(sqlite3.DatabaseError):
        connection.execute("DELETE FROM source_capabilities")
    connection.close()


def test_registry_restart_replays_identical_history(tmp_path):
    path = tmp_path / "capabilities.sqlite3"
    first = SourceCapabilityRegistry(path)
    v1 = capability(version=1, valid_from=100)
    v2 = capability(version=2, valid_from=200, health_state="degraded")
    first.register(v1, recorded_at=100)
    first.register(v2, recorded_at=200)
    second = SourceCapabilityRegistry(path)
    assert first.history(v1.source_id) == (v1, v2)
    assert second.history(v1.source_id) == (v1, v2)


def test_registry_rejects_backdated_registration_and_filters_eligible(tmp_path):
    registry = SourceCapabilityRegistry(tmp_path / "capabilities.sqlite3")
    with pytest.raises(ValueError):
        registry.register(capability(valid_from=100), recorded_at=99)
    macro = capability(source_id="macro", domain_classes=("macro",), valid_from=100)
    crypto = capability(source_id="crypto", domain_classes=("crypto",), valid_from=100)
    registry.register(macro, recorded_at=100)
    registry.register(crypto, recorded_at=100)
    assert registry.eligible(decision_at=150, domain="macro") == (macro,)
    assert registry.eligible(decision_at=150) == (crypto, macro)
