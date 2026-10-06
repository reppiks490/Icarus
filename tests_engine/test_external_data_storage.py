from __future__ import annotations

from pathlib import Path

import pytest

from icarus_engine.external_data.contracts import EvidenceEnvelope
from icarus_engine.external_data.identity import raw_sha256
from icarus_engine.external_data.storage import (
    EvidenceCatalog,
    RawArtifactStore,
    StorageIntegrityError,
    observation_key,
)

ROOT = Path(__file__).resolve().parents[1]


def _env(
    *,
    source_id="fred:CPIAUCSL:2026-09",
    value=319.1,
    revision="2026-09-11",
    vintage="2026-09-11",
    available="2026-09-11T12:30:00Z",
    retrieved="2026-10-06T15:00:00Z",
    ingested="2026-10-06T15:00:01Z",
    batch="batch_20261006T150000Z",
    raw_payload=b"fred-cpi-v1",
    parents=(),
):
    return EvidenceEnvelope(
        source_id=source_id,
        provider_id="fred_alfred",
        dataset="CPIAUCSL",
        instrument=None,
        venue=None,
        source_event_time="2026-09-01T00:00:00Z",
        source_publication_time="2026-09-11T12:30:00Z",
        source_available_at=available,
        retrieved_at=retrieved,
        ingested_at=ingested,
        revision_id=revision,
        vintage_id=vintage,
        raw_artifact_sha256=raw_sha256(raw_payload),
        ingest_batch_id=batch,
        data={"value": value, "units": "Index 1982-1984=100"},
        quality_flags=(),
        lineage_parents=parents,
    )


def test_external_storage_roots_are_explicitly_gitignored():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "corpus/external/" in text.splitlines()
    assert ".external_data_cache/" in text.splitlines()


def test_raw_artifact_store_is_content_addressed_atomic_and_idempotent(tmp_path):
    store = RawArtifactStore(tmp_path)
    payload = b"exact vendor bytes\n"
    first = store.put("fred_alfred", "CPIAUCSL", payload, {"retrieved_at": "2026-10-06T15:00:00Z"})
    expected = tmp_path / "raw" / "fred_alfred" / "CPIAUCSL" / f"{raw_sha256(payload)}.payload"
    assert first.path == expected
    assert first.sha256 == raw_sha256(payload)
    assert first.created is True
    assert expected.read_bytes() == payload

    second = store.put("fred_alfred", "CPIAUCSL", payload, {"retrieved_at": "2026-10-06T16:00:00Z"})
    assert second.path == expected
    assert second.created is False
    assert list(expected.parent.glob(".tmp-*")) == []

    with pytest.raises(ValueError):
        store.put("../escape", "CPIAUCSL", payload, {})


def test_raw_artifact_store_refuses_corruption_at_content_address(tmp_path):
    store = RawArtifactStore(tmp_path)
    payload = b"immutable"
    ref = store.put("fred_alfred", "CPIAUCSL", payload, {})
    ref.path.write_bytes(b"corrupt")
    with pytest.raises(StorageIntegrityError, match="content-address"):
        store.put("fred_alfred", "CPIAUCSL", payload, {})


def test_catalog_exact_retry_is_idempotent_and_sqlite_unique(tmp_path):
    catalog = EvidenceCatalog(tmp_path / "catalog.sqlite3")
    first = _env()
    result = catalog.upsert(first)
    assert result.inserted is True
    assert result.duplicate is False
    assert result.flags == ()

    retry = catalog.upsert(first)
    assert retry.inserted is False
    assert retry.duplicate is True
    assert retry.evidence_id == first.evidence_id

    rows = catalog.revisions(first.source_id, observation_key(first))
    assert len(rows) == 1
    assert rows[0].evidence_id == first.evidence_id


def test_catalog_preserves_revision_conflict_and_never_overwrites_prior_evidence(tmp_path):
    catalog = EvidenceCatalog(tmp_path / "catalog.sqlite3")
    first = _env()
    catalog.upsert(first)
    revised = _env(
        value=319.2,
        revision="2026-10-01",
        vintage="2026-10-01",
        available="2026-10-01T12:30:00Z",
        raw_payload=b"fred-cpi-v2",
        parents=(first.evidence_id,),
    )
    result = catalog.upsert(revised)
    assert result.inserted is True
    assert set(result.flags) == {"REVISION", "CONFLICT"}

    rows = catalog.revisions(first.source_id, observation_key(first))
    assert [row.evidence_id for row in rows] == [first.evidence_id, revised.evidence_id]
    assert [row.data["value"] for row in rows] == [319.1, 319.2]
    assert rows[0].canonical_sha256 == first.canonical_sha256
    assert rows[1].lineage_parents == (first.evidence_id,)


def test_query_as_of_returns_latest_revision_known_at_cutoff_and_excludes_unknown_availability(tmp_path):
    catalog = EvidenceCatalog(tmp_path / "catalog.sqlite3")
    first = _env()
    revised = _env(
        value=319.2,
        revision="2026-10-01",
        vintage="2026-10-01",
        available="2026-10-01T12:30:00Z",
        raw_payload=b"fred-cpi-v2",
        parents=(first.evidence_id,),
    )
    unknown = _env(source_id="fred:UNKNOWN:2026-09", available=None, raw_payload=b"unknown")
    for env in (first, revised, unknown):
        catalog.upsert(env)

    early = catalog.query_as_of("2026-09-20T00:00:00Z")
    assert [row.evidence_id for row in early] == [first.evidence_id]

    later = catalog.query_as_of("2026-10-02T00:00:00Z")
    assert [row.evidence_id for row in later] == [revised.evidence_id]
    assert all(row.source_id != unknown.source_id for row in later)


def test_transaction_rolls_back_after_post_insert_failure_and_retry_succeeds(tmp_path, monkeypatch):
    catalog = EvidenceCatalog(tmp_path / "catalog.sqlite3")
    env = _env()

    def crash(*_args, **_kwargs):
        raise RuntimeError("simulated crash before commit")

    monkeypatch.setattr(EvidenceCatalog, "_before_commit", crash)
    with pytest.raises(RuntimeError, match="simulated crash"):
        catalog.upsert(env)
    assert catalog.revisions(env.source_id, observation_key(env)) == []

    monkeypatch.setattr(EvidenceCatalog, "_before_commit", lambda *_args, **_kwargs: None)
    result = catalog.upsert(env)
    assert result.inserted is True
    assert [row.evidence_id for row in catalog.revisions(env.source_id, observation_key(env))] == [env.evidence_id]
