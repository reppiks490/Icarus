from __future__ import annotations

import pytest

from icarus_engine.discovery_registry.contracts import (
    Candidate,
    CatalogEntry,
    CatalogSnapshot,
    DuplicateGroup,
    PolicyDecision,
    PolicyState,
    ProviderLink,
    QualificationEvent,
    QualificationState,
)
from icarus_engine.discovery_registry.store import RegistryStore


NOW = "2026-10-11T19:20:00Z"


def snapshot_fixture(*, snapshot_id: str = "s1", content_sha256: str = "1" * 64) -> CatalogSnapshot:
    return CatalogSnapshot(
        snapshot_id=snapshot_id,
        catalog_id="api-mega-list",
        upstream_repo="cporter202/API-mega-list",
        upstream_commit="a" * 40,
        upstream_path="README.md",
        content_sha256=content_sha256,
        retrieved_at=NOW,
        parser_revision="v1",
    )


def candidate_fixture(candidate_id: str = "c" * 64) -> Candidate:
    return Candidate.minimum(
        candidate_id=candidate_id,
        canonical_name="Example",
        endpoint_or_tool_url="https://example.com/data",
        upstream_catalog_refs=("api-mega-list:s1:e1",),
    )


def event_fixture(old: QualificationState, new: QualificationState) -> QualificationEvent:
    return QualificationEvent(
        event_id=f"{old.value}->{new.value}",
        candidate_id="c" * 64,
        old_state=old,
        new_state=new,
        occurred_at=NOW,
        reason_code="TEST_EVIDENCE",
    )


def test_store_uses_wal_and_is_idempotent(tmp_path):
    store = RegistryStore(tmp_path)
    assert store.pragma_journal_mode() == "wal"
    snap = snapshot_fixture(snapshot_id="s1", content_sha256="1" * 64)
    store.record_snapshot(snap)
    store.record_snapshot(snap)
    assert store.summary()["catalog_snapshots"] == 1
    store.close()


def test_conflicting_same_snapshot_identity_fails(tmp_path):
    store = RegistryStore(tmp_path)
    store.record_snapshot(snapshot_fixture(snapshot_id="s1", content_sha256="1" * 64))
    with pytest.raises(ValueError):
        store.record_snapshot(snapshot_fixture(snapshot_id="s1", content_sha256="2" * 64))
    store.close()


def test_transition_history_is_append_only(tmp_path):
    store = RegistryStore(tmp_path)
    store.upsert_candidates([candidate_fixture()])
    store.record_transition(event_fixture(QualificationState.DISCOVERED, QualificationState.ACCESS_TESTED))
    assert store.candidate("c" * 64).qualification_state is QualificationState.ACCESS_TESTED
    assert store.summary()["qualification_events"] == 1
    with pytest.raises(ValueError):
        store.record_transition(
            QualificationEvent(
                event_id="illegal",
                candidate_id="c" * 64,
                old_state=QualificationState.ACCESS_TESTED,
                new_state=QualificationState.PRODUCTION,
                occurred_at=NOW,
            )
        )
    assert store.summary()["qualification_events"] == 1
    store.close()


def test_candidate_and_authority_invariants_survive_reopen(tmp_path):
    first = RegistryStore(tmp_path)
    first.upsert_candidates([candidate_fixture()])
    first.close()

    reopened = RegistryStore(tmp_path)
    got = reopened.candidate("c" * 64)
    assert got is not None
    assert got.execution_authorized is False
    assert got.production_decision_authorized is False
    assert got.qualification_state is QualificationState.DISCOVERED
    reopened.close()


def test_audit_entities_are_idempotent_and_counted(tmp_path):
    store = RegistryStore(tmp_path)
    snap = snapshot_fixture()
    store.record_snapshot(snap)
    entry = CatalogEntry(
        entry_id="e1",
        snapshot_id="s1",
        catalog_id="api-mega-list",
        source_path="README.md",
        canonical_name="Example",
        endpoint_or_tool_url="https://example.com/data",
        raw_row_sha256="2" * 64,
    )
    assert store.record_entries("s1", [entry, entry]) == 1
    assert store.upsert_candidates([candidate_fixture(), candidate_fixture()]) == 1
    store.link_candidate("c" * 64, "e1")
    store.link_candidate("c" * 64, "e1")

    decision = PolicyDecision(
        candidate_id="c" * 64,
        entry_id="e1",
        policy_state=PolicyState.REVIEW_REQUIRED,
        reason_code="UNVERIFIED_CATALOG_METADATA",
        decided_at=NOW,
    )
    store.record_policy(decision)
    store.record_policy(decision)

    other = candidate_fixture("d" * 64)
    store.upsert_candidates([other])
    group = DuplicateGroup(
        group_id="g1",
        member_ids=("c" * 64, "d" * 64),
        evidence_level="EXACT_IDENTITY_URL",
        evidence_key="https://example.com/data",
    )
    store.replace_duplicate_groups([group])

    provider_link = ProviderLink(
        link_id="p1",
        candidate_id="c" * 64,
        provider_id="twelve",
        operation_id="twelve:get:/time_series",
        linked_at=NOW,
    )
    assert store.record_provider_links([provider_link, provider_link]) == 1

    summary = store.summary()
    assert summary["catalog_entries"] == 1
    assert summary["candidates"] == 2
    assert summary["candidate_catalog_links"] == 1
    assert summary["policy_reviews"] == 1
    assert summary["duplicate_groups"] == 1
    assert summary["duplicate_members"] == 2
    assert summary["provider_links"] == 1
    store.close()
