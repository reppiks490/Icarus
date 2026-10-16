from __future__ import annotations

import json

from icarus_engine.futures_catalog import FUTURES_PRODUCTS
from icarus_engine.system_index import (
    build_system_index,
    system_index_json,
    system_index_markdown,
    system_index_sha256,
)


EXECUTION_QUALIFIED_ROOTS = {
    "NQ", "MNQ", "ES", "MES", "YM", "MYM", "RTY", "M2K",
    "GC", "MGC", "SI", "SIL",
}


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


def test_system_index_separates_structural_candidate_execution_and_broker_authorization():
    index = build_system_index()
    for root, record in index["assets"].items():
        product = FUTURES_PRODUCTS[root]
        execution = record["execution"]
        assert execution["static_candidate_available"] is True
        assert execution["candidate_execution_root"] == product.execution_root
        assert execution["broker_qualification_required"] is True
        assert execution["structural_qualified"] is product.execution_qualified
        assert execution["execution_qualified"] is product.execution_qualified
        assert execution["broker_paper_readback_verified"] is False
        assert execution["broker_paper_tradeable"] is False
        assert execution["live_authorized"] is False
        assert execution["live_tradeable"] is False
        if product.execution_qualified:
            assert execution["structural_blocker"] is None
        else:
            assert execution["structural_blocker"] == product.execution_blocker


def test_system_index_counts_all_32_candidates_but_only_safe_execution_subset():
    index = build_system_index()
    counts = index["counts"]
    assert counts["futures_roots"] == 32
    assert counts["runtime_admitted"] == 32
    assert counts["static_candidates_available"] == 32
    assert counts["structural_execution_qualified"] == len(EXECUTION_QUALIFIED_ROOTS)
    assert counts["broker_paper_tradeable"] == 0
    assert counts["live_tradeable"] == 0


def test_verified_provider_and_broker_evidence_cannot_bypass_unqualified_execution_route():
    provider = {
        root: {"verified_access": True, "fresh": True, "qualification": "verified"}
        for root in FUTURES_PRODUCTS
    }
    broker = {
        root: {
            "paper_account_verified": True,
            "exact_contract_verified": True,
            "broker_paper_readback_verified": True,
            "reconciliation_verified": True,
        }
        for root in FUTURES_PRODUCTS
    }
    index = build_system_index(provider_state=provider, broker_state=broker)
    assert index["assets"]["NQ"]["execution"]["broker_paper_tradeable"] is True
    assert index["assets"]["CL"]["execution"]["static_candidate_available"] is True
    assert index["assets"]["CL"]["execution"]["execution_qualified"] is False
    assert index["assets"]["CL"]["execution"]["broker_paper_tradeable"] is False


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
    assert "Static candidate" in text
    for root in FUTURES_PRODUCTS:
        assert f"| {root} |" in text
