from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from icarus_engine.external_data.contracts import ProviderDescriptor
from icarus_engine.external_data.normalization import CollectedBatch, NormalizedObservation
from icarus_engine.external_data.pipeline import (
    IngestPipeline,
    ProviderPlanLimited,
)
from icarus_engine.external_data.registry import ProviderRegistry, ProviderRegistryCollision
from icarus_engine.external_data.storage import EvidenceCatalog, RawArtifactStore


UTC = timezone.utc
NOW = datetime(2026, 10, 6, 18, 0, tzinfo=UTC)


def _descriptor(provider_id: str, *, credentials=(), cadence="minute") -> ProviderDescriptor:
    return ProviderDescriptor(
        provider_id=provider_id,
        name=provider_id.upper(),
        domain="test",
        role="test_evidence",
        source_class="fixture",
        capabilities=("quotes",),
        credential_names=tuple(credentials),
        configuration_names=(),
        cadence_class=cadence,
        licensing_policy="test-only",
        raw_retention_policy="retain-test-fixture",
    )


class _Adapter:
    def __init__(
        self,
        provider_id: str,
        *,
        data=None,
        event_time=NOW,
        available_at=NOW,
        retrieved_at=NOW,
        source_id=None,
        fail_collect=False,
        fail_normalize=False,
        plan_limited=False,
        credentials=(),
        events=None,
    ):
        self.descriptor = _descriptor(provider_id, credentials=credentials)
        self.data = dict(data or {"price": 100.0})
        self.event_time = event_time
        self.available_at = available_at
        self.retrieved_at = retrieved_at
        self.source_id = source_id or f"{provider_id}:NQ"
        self.fail_collect = fail_collect
        self.fail_normalize = fail_normalize
        self.plan_limited = plan_limited
        self.events = events if events is not None else []
        self.collect_calls = 0
        self.normalize_calls = 0

    def collect(self, ctx):
        self.collect_calls += 1
        self.events.append("collect")
        if self.plan_limited:
            raise ProviderPlanLimited("fixture entitlement excludes this surface")
        if self.fail_collect:
            raise RuntimeError("collect failed")
        return CollectedBatch(
            dataset="quotes",
            payload=(f"raw:{self.descriptor.provider_id}:{self.data}").encode(),
            retrieved_at=self.retrieved_at,
            content_type="application/json",
            source_url="https://example.test/data",
            metadata={"fixture": True},
        )

    def normalize(self, batch, ctx):
        self.normalize_calls += 1
        self.events.append(("normalize", batch.raw_ref.path.exists()))
        if self.fail_normalize:
            raise RuntimeError("normalize failed")
        return [
            NormalizedObservation(
                source_id=self.source_id,
                dataset="quotes",
                instrument="NQ",
                venue="CME",
                source_event_time=self.event_time,
                source_publication_time=self.event_time,
                source_available_at=self.available_at,
                revision_id=None,
                vintage_id=None,
                data=self.data,
            )
        ]


def _pipeline(tmp_path, adapters, **kwargs):
    registry = ProviderRegistry()
    for adapter in adapters:
        registry.register(adapter)
    raw_store = RawArtifactStore(tmp_path / "external")
    catalog = EvidenceCatalog(tmp_path / "external" / "catalog.sqlite3")
    return IngestPipeline(registry, raw_store, catalog, **kwargs), catalog


def test_registry_rejects_provider_id_collisions_and_exposes_static_capabilities():
    registry = ProviderRegistry()
    first = _Adapter("alpha")
    second = _Adapter("alpha")
    registry.register(first)

    assert registry.get("alpha") is first
    assert registry.capabilities() == {"alpha": ("quotes",)}
    with pytest.raises(ProviderRegistryCollision):
        registry.register(second)


def test_disabled_unconfigured_and_plan_limited_states_are_not_reported_as_success(tmp_path):
    disabled = _Adapter("disabled")
    unconfigured = _Adapter("unconfigured", credentials=("MISSING_TEST_KEY",))
    limited = _Adapter("limited")
    pipeline, _ = _pipeline(
        tmp_path,
        [disabled, unconfigured, limited],
        environment={},
        runtime_states={"disabled": "DISABLED", "limited": "PLAN_LIMITED"},
    )

    assert pipeline.run_provider("disabled", NOW).state == "DISABLED"
    assert pipeline.run_provider("unconfigured", NOW).state == "UNCONFIGURED"
    assert pipeline.run_provider("limited", NOW).state == "PLAN_LIMITED"
    assert disabled.collect_calls == unconfigured.collect_calls == limited.collect_calls == 0


def test_provider_entitlement_exception_becomes_plan_limited(tmp_path):
    adapter = _Adapter("trial_vendor", plan_limited=True)
    pipeline, _ = _pipeline(tmp_path, [adapter])

    receipt = pipeline.run_provider("trial_vendor", NOW)

    assert receipt.state == "PLAN_LIMITED"
    assert receipt.error is not None
    assert "entitlement" in receipt.error.lower()


def test_run_id_is_deterministic_and_authority_is_immutable_false(tmp_path):
    adapter = _Adapter("alpha")
    pipeline, _ = _pipeline(tmp_path, [adapter])

    first = pipeline.run_provider("alpha", NOW, force=True)
    second = pipeline.run_provider("alpha", NOW, force=True)

    assert first.run_id == second.run_id
    assert first.execution_authorized is False
    assert first.production_decision_authorized is False
    with pytest.raises(FrozenInstanceError):
        first.execution_authorized = True


def test_raw_artifact_is_persisted_before_normalization_and_canonical_evidence_is_upserted(tmp_path):
    events = []
    adapter = _Adapter("alpha", events=events)
    pipeline, catalog = _pipeline(tmp_path, [adapter])

    receipt = pipeline.run_provider("alpha", NOW)

    assert receipt.state == "OK"
    assert events[0] == "collect"
    assert events[1] == ("normalize", True)
    assert len(receipt.raw_artifact_sha256s) == 1
    assert len(receipt.evidence_ids) == 1
    evidence = catalog.query_as_of(NOW + timedelta(seconds=1), provider_id="alpha")
    assert len(evidence) == 1
    assert evidence[0].data["price"] == 100.0
    assert evidence[0].execution_authorized is False
    assert evidence[0].production_decision_authorized is False


def test_failed_normalization_keeps_raw_artifact_and_returns_error_receipt(tmp_path):
    adapter = _Adapter("alpha", fail_normalize=True)
    pipeline, catalog = _pipeline(tmp_path, [adapter])

    receipt = pipeline.run_provider("alpha", NOW)

    assert receipt.state == "ERROR"
    assert len(receipt.raw_artifact_sha256s) == 1
    assert list((tmp_path / "external" / "raw" / "alpha" / "quotes").glob("*.payload"))
    assert catalog.query_as_of(NOW + timedelta(seconds=1), provider_id="alpha") == []


def test_stale_feed_is_labeled_without_discarding_the_evidence(tmp_path):
    old = NOW - timedelta(minutes=10)
    adapter = _Adapter("alpha", event_time=old, available_at=old, retrieved_at=NOW)
    pipeline, catalog = _pipeline(tmp_path, [adapter], stale_after_seconds={"alpha": 60})

    receipt = pipeline.run_provider("alpha", NOW)

    assert receipt.state == "STALE"
    evidence = catalog.query_as_of(NOW, provider_id="alpha")
    assert len(evidence) == 1
    assert "STALE" in evidence[0].quality_flags


def test_run_due_isolates_provider_failures_and_preserves_successful_evidence(tmp_path):
    good = _Adapter("good", data={"price": 100.0})
    bad = _Adapter("bad", fail_normalize=True)
    pipeline, catalog = _pipeline(
        tmp_path,
        [good, bad],
        cadence_seconds={"minute": 60},
    )

    receipts = pipeline.run_due(NOW)
    states = {receipt.provider_id: receipt.state for receipt in receipts}

    assert states == {"bad": "ERROR", "good": "OK"}
    persisted = catalog.query_as_of(NOW + timedelta(seconds=1), provider_id="good")
    assert len(persisted) == 1
    assert persisted[0].data["price"] == 100.0


def test_run_due_respects_cadence_after_success(tmp_path):
    adapter = _Adapter("alpha")
    pipeline, _ = _pipeline(tmp_path, [adapter], cadence_seconds={"minute": 60})

    first = pipeline.run_due(NOW)
    too_soon = pipeline.run_due(NOW + timedelta(seconds=30))
    due_again = pipeline.run_due(NOW + timedelta(seconds=61))

    assert len(first) == 1
    assert too_soon == []
    assert len(due_again) == 1


def test_cross_provider_disagreement_remains_two_observations_with_conflict_edge(tmp_path):
    left = _Adapter("left", data={"price": 100.0}, source_id="left:NQ")
    right = _Adapter("right", data={"price": 101.0}, source_id="right:NQ")
    pipeline, catalog = _pipeline(tmp_path, [left, right])

    left_receipt = pipeline.run_provider("left", NOW)
    right_receipt = pipeline.run_provider("right", NOW)

    assert left_receipt.state == "OK"
    assert right_receipt.state == "OK"
    assert len(right_receipt.conflict_edges) == 1
    edge = right_receipt.conflict_edges[0]
    assert edge.reason == "CROSS_PROVIDER_DISAGREEMENT"
    assert {edge.left_evidence_id, edge.right_evidence_id} == {
        left_receipt.evidence_ids[0],
        right_receipt.evidence_ids[0],
    }

    evidence = catalog.query_as_of(NOW + timedelta(seconds=1), dataset="quotes")
    assert {item.provider_id for item in evidence} == {"left", "right"}
    assert sorted(item.data["price"] for item in evidence) == [100.0, 101.0]
    assert all("average" not in item.data for item in evidence)
