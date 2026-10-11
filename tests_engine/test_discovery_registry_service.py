import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from icarus_engine.discovery_registry.contracts import CatalogSnapshot, PolicyState, QualificationState
from icarus_engine.discovery_registry.service import DiscoveryRegistryService


TEXT = """# Finance
| API Name | Description |
|---|---|
| [News](https://apify.com/acme/news?fpr=a) | Public news |
| [News](https://apify.com/acme/news?fpr=b) | Public news |
| [Unsafe](https://example.com/bypass) | Bypass the paywall |
| broken | malformed |
"""


def snapshot(text=TEXT, **kwargs):
    values = dict(catalog_id="api-mega-list", upstream_repo="cporter202/API-mega-list",
                  upstream_commit="a" * 40, upstream_path="README.md",
                  content_sha256=hashlib.sha256(text.encode()).hexdigest(),
                  retrieved_at="2026-10-11T21:00:00Z", parser_revision="v1")
    return CatalogSnapshot(**(values | kwargs))


def test_import_snapshot_is_idempotent_and_survives_restart(tmp_path):
    service = DiscoveryRegistryService(tmp_path)
    first = service.import_snapshot(snapshot(), TEXT, importer_name="api_mega")
    assert first.imported_entries == 3
    assert first.raw_count == 4
    assert first.rejected == 1
    assert first.review_required == 2
    assert first.parse_failures == 1
    assert service.import_snapshot(snapshot(), TEXT, importer_name="api_mega") == first
    before = service.snapshot()
    service.close()
    reopened = DiscoveryRegistryService(tmp_path)
    # Re-fetch time is not a new content/parse identity; preserve the first retrieval.
    later = replace(snapshot(), retrieved_at="2026-10-11T22:00:00Z")
    assert reopened.import_snapshot(later, TEXT, importer_name="api_mega") == first
    assert reopened.snapshot() == before
    reopened.close()


def test_provenance_is_preserved_while_duplicate_independence_collapses(tmp_path):
    service = DiscoveryRegistryService(tmp_path)
    summary = service.import_snapshot(snapshot(), TEXT, importer_name="api_mega")
    assert summary.duplicate_groups == 1
    assert summary.unique_candidates == 3
    records = service.store.candidates()
    assert len(records) == 3
    assert all(c.upstream_catalog_refs and c.upstream_entry_hashes for c in records)
    assert service.snapshot()["candidate_catalog_links"] == 3
    assert sum(c.duplicate_group_id is not None for c in records) == 2
    assert {c.qualification_state for c in records} == {QualificationState.DISCOVERED}
    assert any(c.policy_state is PolicyState.REJECTED for c in records)
    assert service.snapshot()["execution_authorized"] is False
    assert service.snapshot()["production_decision_authorized"] is False
    assert summary.to_dict()["execution_authorized"] is False
    service.close()


def test_new_catalog_revision_preserves_observation_identity_and_all_links(tmp_path):
    service = DiscoveryRegistryService(tmp_path)
    service.import_snapshot(snapshot(), TEXT, importer_name="api_mega")
    service.import_snapshot(snapshot(upstream_commit="b" * 40), TEXT, importer_name="api_mega")
    assert len(service.store.candidates()) == 3
    assert service.snapshot()["candidate_catalog_links"] == 6
    assert all(len(c.upstream_catalog_refs) == 2 for c in service.store.candidates())
    service.close()


def test_last_seen_timestamp_compares_instants_not_iso_string_order(tmp_path):
    service = DiscoveryRegistryService(tmp_path)
    service.import_snapshot(snapshot(), TEXT, importer_name="api_mega")
    later = snapshot(upstream_commit="b" * 40, retrieved_at="2026-10-11T21:00:00.500000Z")
    service.import_snapshot(later, TEXT, importer_name="api_mega")
    assert {c.last_seen_at for c in service.store.candidates()} == {later.retrieved_at}
    service.close()


def test_sponsored_placement_does_not_change_quality_or_policy(tmp_path):
    text = TEXT.replace("# Finance", "# Sponsored — Featured")
    service = DiscoveryRegistryService(tmp_path)
    service.import_snapshot(snapshot(text), text, importer_name="api_mega")
    ordinary = [c for c in service.store.candidates() if c.policy_state is not PolicyState.REJECTED]
    assert {c.source_quality for c in ordinary} == {None}
    assert {c.policy_state for c in ordinary} == {PolicyState.REVIEW_REQUIRED}
    service.close()


def test_hash_mismatch_or_importer_mismatch_writes_nothing(tmp_path):
    service = DiscoveryRegistryService(tmp_path)
    with pytest.raises(ValueError, match="content hash"):
        service.import_snapshot(snapshot(), TEXT + "\n", importer_name="api_mega")
    with pytest.raises(ValueError, match="importer"):
        service.import_snapshot(snapshot(), TEXT, importer_name="ai_agent_tools")
    assert service.snapshot()["catalog_snapshots"] == 0
    service.close()


def test_invalid_urls_are_audited_without_crashing_other_rows(tmp_path):
    text = TEXT + "| [Invalid](javascript:boom) | bad |\n"
    service = DiscoveryRegistryService(tmp_path)
    summary = service.import_snapshot(snapshot(text), text, importer_name="api_mega")
    assert summary.imported_entries == 3
    assert summary.parse_failures == 2
    service.close()


def test_pipeline_failure_rolls_back_whole_snapshot(tmp_path, monkeypatch):
    service = DiscoveryRegistryService(tmp_path)
    def fail(*args):
        raise RuntimeError("injected persistence fault")
    monkeypatch.setattr(service.store, "link_candidate", fail)
    with pytest.raises(RuntimeError, match="injected"):
        service.import_snapshot(snapshot(), TEXT, importer_name="api_mega")
    assert service.snapshot()["catalog_snapshots"] == 0
    assert service.snapshot()["candidates"] == 0
    assert service.snapshot()["catalog_entries"] == 0
    service.close()


def test_foundation_doc_states_authority_and_scope():
    text = (Path(__file__).resolve().parents[1] / "docs/icarus/CAPABILITY_DATA_DISCOVERY_REGISTRY.md").read_text()
    assert "execution_authorized=false" in text
    assert "production_decision_authorized=false" in text
    assert "DISCOVERED does not mean qualified" in text
    assert "provider federation is read-only" in text.lower()
    assert "does not expose HTTP, MCP, or dashboard surfaces yet" in text


def test_credential_bearing_row_is_only_a_hashed_failure(tmp_path):
    text = TEXT + "| [Credential](https://user:SECRET_SENTINEL@example.com/data) | Private endpoint |\n"
    service = DiscoveryRegistryService(tmp_path)
    result = service.import_snapshot(snapshot(text), text, importer_name="api_mega")
    assert result.parse_failures == 2
    assert "SECRET_SENTINEL" not in str([c.to_dict() for c in service.store.candidates()])
    assert "SECRET_SENTINEL" not in str(service.store.catalog_snapshot(snapshot(text).snapshot_id).to_dict())
    service.close()
