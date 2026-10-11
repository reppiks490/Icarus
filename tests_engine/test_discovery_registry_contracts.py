from __future__ import annotations

import pytest

from icarus_engine.discovery_registry.contracts import (
    Candidate,
    CatalogSnapshot,
    QualificationState,
    assert_transition,
)


def test_catalog_snapshot_requires_pinned_commit_and_content_hash():
    with pytest.raises(ValueError):
        CatalogSnapshot(
            catalog_id="api-mega-list",
            upstream_repo="cporter202/API-mega-list",
            upstream_commit="main",
            upstream_path="README.md",
            content_sha256="x",
            retrieved_at="2026-10-11T00:00:00Z",
            parser_revision="v1",
        )


def test_authority_is_permanently_false():
    candidate = Candidate.minimum(
        candidate_id="a" * 64,
        canonical_name="Example",
        endpoint_or_tool_url="https://example.com",
    )
    assert candidate.execution_authorized is False
    assert candidate.production_decision_authorized is False


def test_illegal_lifecycle_jump_fails_closed():
    with pytest.raises(ValueError):
        assert_transition(QualificationState.DISCOVERED, QualificationState.PRODUCTION)


def test_numeric_quality_rejects_bool_nan_and_inf():
    for value in (True, float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            Candidate.minimum(
                candidate_id="b" * 64,
                canonical_name="Bad numeric",
                endpoint_or_tool_url="https://example.com/x",
                source_quality=value,
            )
