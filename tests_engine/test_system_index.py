from __future__ import annotations

import json

from icarus_engine.futures_catalog import FUTURES_PRODUCTS
from icarus_engine.system_index import (
    build_system_index,
    system_index_json,
    system_index_markdown,
    system_index_sha256,
)


def test_system_index_is_deterministic_and_covers_every_futures_root():
    first = build_system_index()
    second = build_system_index()
    assert first == second
    assert first["schema_version"] == "icarus-system-index-v1"
    assert set(first["assets"]) == set(FUTURES_PRODUCTS)
    assert first["integrity"]["algorithm"] == "sha256"
    assert first["integrity"]["sha256"] == system_index_sha256(first)
    assert system_index_json(first) == system_index_json(second)


def test_system_index_never_promotes_configured_sources_to_verified_data():
    index = build_system_index()
    for root, record in index["assets"].items():
        assert record["data"]["configured"] is True
        assert record["data"]["qualification"] == "configured_unverified"
        assert record["data"]["verified_access"] is False
        assert record["data"]["fresh"] is False
        assert "provider evidence" in record["data"]["blocker"].lower()


def test_system_index_separates_structural_execution_from_broker_and_live_authorization():
    index = build_system_index()
    for root, record in index["assets"].items():
        product = FUTURES_PRODUCTS[root]
        execution = record["execution"]
        assert execution["structural_qualified"] is product.execution_qualified
        assert execution["broker_paper_readback_verified"] is False
        assert execution["broker_paper_tradeable"] is False
        assert execution["live_authorized"] is False
        assert execution["live_tradeable"] is False
        if product.execution_qualified:
            assert execution["structural_blocker"] is None
        else:
            assert execution["structural_blocker"] == product.execution_blocker


def test_system_index_hash_excludes_itself_and_detects_payload_changes():
    index = build_system_index()
    before = index["integrity"]["sha256"]
    clone = json.loads(system_index_json(index))
    clone["assets"]["NQ"]["identity"]["name"] = "tampered"
    assert system_index_sha256(clone) != before


def test_markdown_projection_exposes_each_asset_and_authorization_boundary():
    text = system_index_markdown(build_system_index())
    assert "ICARUS Canonical System Index" in text
    assert "Live execution: DISABLED" in text
    for root in FUTURES_PRODUCTS:
        assert f"| {root} |" in text
