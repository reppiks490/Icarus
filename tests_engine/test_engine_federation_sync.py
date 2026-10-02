from __future__ import annotations

import json

import pytest

from icarus_engine.engine_federation_sync import (
    EngineFederationRemoteSync,
    _git_blob_sha,
    _normalize_contracts,
    _normalize_event,
)


def _producer_contract():
    return {
        "schema_version": "icarus-mcp-interface-contract-v1",
        "event_root": "automation_intelligence/mcp_interface/events",
        "event_schema": "icarus-mcp-event-v1",
        "required_categories": ["REPAIR", "AUDIT", "EVOLUTION", "INTEGRATION"],
        "required_fields": [
            "event_id", "at_utc", "category", "status", "severity", "summary",
            "surface", "source", "paths", "evidence", "execution_authorized",
        ],
        "ui_api": "/api/mcp/control",
        "ui_tab": "MCP / Automation",
        "source_of_truth": "LOCAL_REPOSITORY_SNAPSHOT",
        "trading_execution_authorized": False,
    }


def _consumer_contract():
    return {
        "schema_version": "icarus-engine-brain-federation-v1",
        "producer_repository": "reppiks490/Icarus-engine",
        "producer_ref": "main",
        "consumer_repository": "reppiks490/Icarus",
        "consumer_surface": "Adaptive Brain remote sync",
        "producer_contract": "automation_intelligence/mcp_interface/contract.json",
        "producer_contract_schema": "icarus-mcp-interface-contract-v1",
        "event_root": "automation_intelligence/mcp_interface/events",
        "event_schema": "icarus-mcp-event-v1",
        "accepted_sources": [
            "OMEGA_AUTOMATION", "MACRO_AUTOMATION", "FLOW_AUTOMATION",
            "AION_AUTOMATION", "DAEDALUS_AUTOMATION",
        ],
        "accepted_categories": ["REPAIR", "AUDIT", "EVOLUTION", "INTEGRATION"],
        "semantics": {
            "event_records": "RESEARCH_OBSERVABILITY_ONLY",
            "durability_receipts_are_substantive_evidence": False,
            "remote_status_is_production_decision": False,
            "raw_owner_data_transfer": False,
            "automatic_model_promotion": False,
            "production_decision_authorized": False,
            "automatic_execution_authority": False,
        },
        "execution_authorized": False,
        "production_decision_authorized": False,
        "event_validation": {
            "required_fields_source": "automation_intelligence/mcp_interface/contract.json#required_fields",
            "strict_v1_required_fields": True,
            "legacy_relaxed_blob_shas": ["1" * 40],
            "legacy_rule": "Only these exact immutable Git blobs may omit producer-required envelope fields. No future blob inherits this exception.",
        },
    }


def _event(**overrides):
    body = {
        "schema_version": "icarus-mcp-event-v1",
        "event_id": "flow-test-event",
        "at_utc": "2026-10-02T18:35:00Z",
        "category": "AUDIT",
        "status": "OBSERVED",
        "severity": "INFO",
        "summary": "Observed a provenance-bound research state transition.",
        "surface": "Flow Velocity Engine",
        "source": "FLOW_AUTOMATION",
        "paths": ["automation_intelligence/flow/latest.json"],
        "evidence": ["source:fixture"],
        "execution_authorized": False,
    }
    body.update(overrides)
    return body


def test_contracts_are_identity_bound_and_fail_closed():
    out = _normalize_contracts(_producer_contract(), _consumer_contract())
    assert out["producer_repository"] == "reppiks490/Icarus-engine"
    assert out["consumer_repository"] == "reppiks490/Icarus"
    assert out["event_schema"] == "icarus-mcp-event-v1"
    assert out["execution_authorized"] is False
    assert out["production_decision_authorized"] is False
    assert out["truth_contract"]["event_records_are_research_observability_only"] is True
    assert out["truth_contract"]["durability_receipts_are_substantive_evidence"] is False

    bad = _consumer_contract()
    bad["semantics"]["automatic_model_promotion"] = True
    with pytest.raises(ValueError, match="authority"):
        _normalize_contracts(_producer_contract(), bad)


def test_strict_event_normalization_preserves_remote_evidence_boundary():
    contracts = _normalize_contracts(_producer_contract(), _consumer_contract())
    row = _normalize_event(_event(), "a" * 40, contracts)
    assert row["event_id"] == "flow-test-event"
    assert row["source"] == "FLOW_AUTOMATION"
    assert row["category"] == "AUDIT"
    assert row["remote_blob_sha"] == "a" * 40
    assert row["foreign_evidence_only"] is True
    assert row["execution_authorized"] is False
    assert row["production_decision_authorized"] is False

    with pytest.raises(ValueError, match="accepted source"):
        _normalize_event(_event(source="UNKNOWN_AUTOMATION"), "b" * 40, contracts)

    with pytest.raises(ValueError, match="execution_authorized"):
        _normalize_event(_event(execution_authorized=True), "c" * 40, contracts)


def test_legacy_relaxation_applies_only_to_exact_declared_blob():
    contracts = _normalize_contracts(_producer_contract(), _consumer_contract())
    legacy = _event()
    legacy.pop("severity")
    legacy.pop("surface")

    row = _normalize_event(legacy, "1" * 40, contracts)
    assert row["legacy_relaxed"] is True
    assert row["remote_blob_sha"] == "1" * 40

    with pytest.raises(ValueError, match="required fields"):
        _normalize_event(legacy, "2" * 40, contracts)


def test_remote_sync_verifies_git_blobs_and_records_brain_evidence(tmp_path):
    producer = _producer_contract()
    consumer = _consumer_contract()
    event = _event()

    raw = {
        "producer": (json.dumps(producer, sort_keys=True) + "\n").encode(),
        "consumer": (json.dumps(consumer, sort_keys=True) + "\n").encode(),
        "event": (json.dumps(event, sort_keys=True) + "\n").encode(),
    }
    urls = {
        "producer": "https://example.invalid/producer",
        "consumer": "https://example.invalid/consumer",
        "event": "https://example.invalid/event",
    }
    producer_meta = {"type": "file", "sha": _git_blob_sha(raw["producer"]), "url": urls["producer"]}
    consumer_meta = {"type": "file", "sha": _git_blob_sha(raw["consumer"]), "url": urls["consumer"]}
    events_listing = [{
        "type": "file",
        "name": "20261002T183500Z-flow-test.json",
        "path": "automation_intelligence/mcp_interface/events/20261002T183500Z-flow-test.json",
        "sha": _git_blob_sha(raw["event"]),
        "url": urls["event"],
    }]

    def fetch_json(url):
        if url.endswith("contract.json?ref=main"):
            return producer_meta
        if url.endswith("icarus_consumer_contract.json?ref=main"):
            return consumer_meta
        if "/events?ref=main" in url:
            return events_listing
        raise AssertionError(url)

    def fetch_bytes(url):
        return next(raw[key] for key in raw if urls[key] == url)

    sync = EngineFederationRemoteSync(
        tmp_path,
        interval_seconds=30,
        fetch_json=fetch_json,
        fetch_bytes=fetch_bytes,
    )
    out = sync.sync_once()

    assert out["status"] == "green"
    assert out["accepted_event_count"] == 1
    assert out["latest_event_id"] == "flow-test-event"
    assert out["truth_contract"]["raw_owner_data_imported"] is False
    assert out["truth_contract"]["automatic_model_promotion"] is False
    assert out["execution_authorized"] is False

    journal = tmp_path / "audit" / "brain_events.jsonl"
    assert journal.exists()
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    assert rows[-1]["subject"] == "icarus-engine-federation"
    assert rows[-1]["details"]["remote_event"]["event_id"] == "flow-test-event"

    # Re-reading the exact same immutable blob does not duplicate the Brain event.
    sync.sync_once()
    rows2 = [json.loads(line) for line in journal.read_text().splitlines()]
    assert len(rows2) == len(rows)


def test_blob_mismatch_degrades_without_replacing_last_good_event_state(tmp_path):
    producer = _producer_contract()
    consumer = _consumer_contract()
    event = _event()
    raw_producer = (json.dumps(producer, sort_keys=True) + "\n").encode()
    raw_consumer = (json.dumps(consumer, sort_keys=True) + "\n").encode()
    raw_event = (json.dumps(event, sort_keys=True) + "\n").encode()

    producer_meta = {"type": "file", "sha": _git_blob_sha(raw_producer), "url": "p"}
    consumer_meta = {"type": "file", "sha": _git_blob_sha(raw_consumer), "url": "c"}
    listing = [{
        "type": "file", "name": "event.json", "path": "automation_intelligence/mcp_interface/events/event.json",
        "sha": _git_blob_sha(raw_event), "url": "e",
    }]
    blobs = {"p": raw_producer, "c": raw_consumer, "e": raw_event}

    def fetch_json(url):
        if "icarus_consumer_contract" in url:
            return consumer_meta
        if url.endswith("contract.json?ref=main"):
            return producer_meta
        return listing

    sync = EngineFederationRemoteSync(
        tmp_path,
        fetch_json=fetch_json,
        fetch_bytes=lambda url: blobs[url],
    )
    good = sync.sync_once()
    assert good["status"] == "green"
    good_event = good["latest_event_id"]

    listing[0]["sha"] = "f" * 40
    bad = sync.sync_once()
    assert bad["status"] == "degraded"
    assert "Git blob SHA mismatch" in bad["last_error"]
    assert bad["latest_event_id"] == good_event
