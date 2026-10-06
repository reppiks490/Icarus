from __future__ import annotations

import hashlib
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from icarus_engine.external_data.contracts import EvidenceEnvelope, ProviderDescriptor, ProviderHealth, SourceArtifact
from icarus_engine.external_data.identity import canonical_json_bytes, canonical_sha256, evidence_id, normalize_utc, raw_sha256


def _envelope(**overrides):
    values = dict(
        source_id="fred:CPIAUCSL:2026-09",
        provider_id="fred_alfred",
        dataset="CPIAUCSL",
        instrument=None,
        venue=None,
        source_event_time="2026-09-01T00:00:00Z",
        source_publication_time="2026-09-11T08:30:00-04:00",
        source_available_at="2026-09-11T12:30:00Z",
        retrieved_at="2026-10-06T15:00:00Z",
        ingested_at="2026-10-06T15:00:01Z",
        revision_id="2026-09-11",
        vintage_id="2026-09-11",
        raw_artifact_sha256="a" * 64,
        ingest_batch_id="batch_20261006T150000Z",
        data={"value": 319.1, "units": "Index 1982-1984=100"},
        quality_flags=(),
        lineage_parents=(),
    )
    values.update(overrides)
    return EvidenceEnvelope(**values)


def test_canonical_json_and_hashes_are_order_independent_and_exact_for_raw_bytes():
    left = {"b": 2, "a": {"z": 3, "y": 1}}
    right = {"a": {"y": 1, "z": 3}, "b": 2}
    assert canonical_json_bytes(left) == canonical_json_bytes(right)
    assert canonical_json_bytes({"b": 2, "a": 1}) == b'{"a":1,"b":2}'
    assert canonical_sha256(left) == canonical_sha256(right)
    payload = b"exact vendor bytes\n"
    assert raw_sha256(payload) == hashlib.sha256(payload).hexdigest()
    with pytest.raises(ValueError):
        canonical_json_bytes({"bad": float("nan")})


def test_timestamp_normalization_converts_offsets_to_aware_utc_and_rejects_naive_values():
    eastern = datetime(2026, 10, 6, 10, 0, tzinfo=timezone(timedelta(hours=-5)))
    assert normalize_utc(eastern) == datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
    assert normalize_utc("2026-10-06T15:00:00Z") == datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
    assert normalize_utc(None) is None
    with pytest.raises(ValueError, match="timezone"):
        normalize_utc(datetime(2026, 10, 6, 15, 0))
    with pytest.raises(ValueError, match="timezone"):
        normalize_utc("2026-10-06T15:00:00")


def test_envelope_preserves_distinct_point_in_time_fields_and_never_fills_unknown_event_time():
    env = _envelope(source_event_time=None)
    assert env.source_event_time is None
    assert env.source_publication_time == datetime(2026, 9, 11, 12, 30, tzinfo=timezone.utc)
    assert env.source_available_at == datetime(2026, 9, 11, 12, 30, tzinfo=timezone.utc)
    assert env.retrieved_at == datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
    assert env.ingested_at == datetime(2026, 10, 6, 15, 0, 1, tzinfo=timezone.utc)
    assert env.execution_authorized is False
    assert env.production_decision_authorized is False


def test_exact_duplicate_identity_ignores_retrieval_batch_but_revision_changes_identity():
    first = _envelope()
    duplicate = _envelope(
        retrieved_at="2026-10-06T16:00:00Z",
        ingested_at="2026-10-06T16:00:01Z",
        ingest_batch_id="batch_20261006T160000Z",
    )
    assert first.evidence_id == duplicate.evidence_id
    assert first.canonical_sha256 == duplicate.canonical_sha256

    revised = _envelope(
        revision_id="2026-10-01",
        vintage_id="2026-10-01",
        data={"units": "Index 1982-1984=100", "value": 319.2},
        lineage_parents=(first.evidence_id,),
    )
    assert revised.evidence_id != first.evidence_id
    assert revised.lineage_parents == (first.evidence_id,)


def test_generic_evidence_id_is_deterministic_and_revision_sensitive():
    base = {"provider_id": "x", "revision_id": "1", "data": {"b": 2, "a": 1}}
    reordered = {"data": {"a": 1, "b": 2}, "revision_id": "1", "provider_id": "x"}
    assert evidence_id(base) == evidence_id(reordered)
    assert evidence_id({**base, "revision_id": "2"}) != evidence_id(base)


def test_contract_dataclasses_are_immutable_and_health_is_separate_from_descriptor():
    descriptor = ProviderDescriptor(
        provider_id="fred_alfred",
        name="FRED and ALFRED",
        domain="public_macro",
        role="macro_series_and_vintage_evidence",
        source_class="credentialed_public_api",
        capabilities=("fred_series", "alfred_vintages"),
        credential_names=("FRED_API_KEY",),
        configuration_names=(),
        cadence_class="release_driven",
        licensing_policy="public_source_terms",
        raw_retention_policy="public_cache_allowed_no_raw_git",
    )
    health = ProviderHealth(provider_id="fred_alfred", state="OK", checked_at="2026-10-06T15:00:00Z")
    assert not hasattr(descriptor, "state")
    assert health.state == "OK"
    assert health.checked_at.tzinfo is timezone.utc
    with pytest.raises(FrozenInstanceError):
        descriptor.role = "changed"

    artifact = SourceArtifact(
        provider_id="fred_alfred",
        dataset="CPIAUCSL",
        raw_artifact_sha256="c" * 64,
        retrieved_at="2026-10-06T15:00:00Z",
    )
    assert artifact.retrieved_at.tzinfo is timezone.utc
