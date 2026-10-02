from __future__ import annotations

import json

from icarus_engine.brain import brain_snapshot
from icarus_engine.brain_sync import (
    BrainRemoteSync,
    REMOTE_ROOT,
    _REMOTE_CONSUMER_CONTRACT_API,
    _REMOTE_PRODUCER_CONTRACT_API,
    _git_blob_sha,
)


def _remote_event(**overrides):
    payload = {
        "schema": "icarus-mcp-event-v1",
        "category": "AUDIT",
        "source": "FLOW_AUTOMATION",
        "execution_authorized": False,
        "retrieval_time_utc": "2026-10-01T04:23:01Z",
        "net_new_delta": "Authenticated flow delta.",
        "evidence": {"btc": "measured spot evidence"},
        "argus": {"status": "USEFUL", "finding": "True depth snapshot preserved as snapshot-only evidence."},
        "nexus": {"status": "USEFUL", "finding": "Representations and data gaps remain separated."},
        "data_gaps": ["direct NQ unavailable"],
        "conflicts": [],
    }
    payload.update(overrides)
    return payload


def _consumer_contract(**overrides):
    payload = {
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
            "OMEGA_AUTOMATION",
            "MACRO_AUTOMATION",
            "FLOW_AUTOMATION",
            "AION_AUTOMATION",
            "DAEDALUS_AUTOMATION",
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
    }
    payload.update(overrides)
    return payload


def _producer_contract():
    return {
        "schema_version": "icarus-mcp-interface-contract-v1",
        "event_root": "automation_intelligence/mcp_interface/events",
        "event_schema": "icarus-mcp-event-v1",
        "required_categories": ["REPAIR", "AUDIT", "EVOLUTION", "INTEGRATION"],
        "trading_execution_authorized": False,
    }


def _fixture(payload, *, consumer=None, corrupt_event_blob=False, corrupt_consumer_blob=False):
    event_raw = (json.dumps(payload, sort_keys=True) + "\n").encode()
    event_sha = _git_blob_sha(event_raw)
    path = f"{REMOTE_ROOT}/flow-test.json"
    event_url = "https://api.github.test/flow-test"
    listing = [{
        "name": "flow-test.json",
        "path": path,
        "sha": "a" * 40 if corrupt_event_blob else event_sha,
        "url": event_url,
        "type": "file",
    }]

    consumer_doc = consumer or _consumer_contract()
    producer_doc = _producer_contract()
    consumer_raw = (json.dumps(consumer_doc, sort_keys=True) + "\n").encode()
    producer_raw = (json.dumps(producer_doc, sort_keys=True) + "\n").encode()
    consumer_sha = _git_blob_sha(consumer_raw)
    producer_sha = _git_blob_sha(producer_raw)
    consumer_url = "https://api.github.test/consumer-contract"
    producer_url = "https://api.github.test/producer-contract"

    def fetch_json(requested):
        if requested == _REMOTE_CONSUMER_CONTRACT_API:
            return {
                "type": "file",
                "sha": "b" * 40 if corrupt_consumer_blob else consumer_sha,
                "url": consumer_url,
            }
        if requested == _REMOTE_PRODUCER_CONTRACT_API:
            return {"type": "file", "sha": producer_sha, "url": producer_url}
        return listing

    def fetch_bytes(requested):
        if requested == event_url:
            return event_raw
        if requested == consumer_url:
            return consumer_raw
        if requested == producer_url:
            return producer_raw
        return b""

    return {
        "event_raw": event_raw,
        "event_sha": event_sha,
        "path": path,
        "event_url": event_url,
        "listing": listing,
        "consumer_sha": consumer_sha,
        "producer_sha": producer_sha,
        "fetch_json": fetch_json,
        "fetch_bytes": fetch_bytes,
    }


def test_remote_sync_ingests_custom_agent_and_owned_subsystem_events(tmp_path):
    fixture = _fixture(_remote_event())

    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
    )
    status = sync.sync_once()
    assert status["status"] == "green"
    assert status["ingested_total"] == 1
    assert status["last_ingested"] == [fixture["path"]]
    assert status["consumer_contract_blob_sha"] == fixture["consumer_sha"]
    assert status["producer_contract_blob_sha"] == fixture["producer_sha"]
    assert status["truth_contract"]["federation_schema"] == "icarus-engine-brain-federation-v1"
    assert status["truth_contract"]["event_records"] == "RESEARCH_OBSERVABILITY_ONLY"
    assert status["truth_contract"]["automatic_execution_authority"] is False
    assert status["execution_authorized"] is False

    snap = brain_snapshot(tmp_path, remote_sync=status)
    agents = {x["id"]: x for x in snap["architecture"]["agents"]}
    subsystems = {x["id"]: x for x in snap["architecture"]["subsystems"]}
    assert agents["flow"]["detail"] == "Authenticated flow delta."
    assert subsystems["argus"]["detail"].startswith("True depth snapshot")
    assert subsystems["nexus"]["detail"].startswith("Representations and data gaps")
    assert snap["remote_sync"]["status"] == "green"

    again = sync.sync_once()
    assert again["ingested_total"] == 1
    assert len(brain_snapshot(tmp_path)["events"]) == 3


def test_remote_sync_rejects_authority_escalation(tmp_path):
    fixture = _fixture(_remote_event(execution_authorized=True))
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["rejected_total"] == 1
    assert "execution_authorized=false" in status["last_error"]
    assert brain_snapshot(tmp_path)["events"] == []


def test_remote_sync_detects_event_blob_substitution(tmp_path):
    fixture = _fixture(_remote_event(), corrupt_event_blob=True)
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["rejected_total"] == 1
    assert "Git blob SHA mismatch" in status["last_error"]
    assert brain_snapshot(tmp_path)["events"] == []


def test_remote_sync_rejects_invalid_custom_agent_schema(tmp_path):
    fixture = _fixture(_remote_event(schema="wrong-schema"))
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["rejected_total"] == 1
    assert "unsupported custom-agent event schema" in status["last_error"]
    assert brain_snapshot(tmp_path)["events"] == []


def test_remote_sync_fails_closed_when_consumer_contract_escalates_authority(tmp_path):
    consumer = _consumer_contract(
        semantics={
            **_consumer_contract()["semantics"],
            "automatic_execution_authority": True,
        }
    )
    fixture = _fixture(_remote_event(), consumer=consumer)
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["ingested_total"] == 0
    assert "attempts authority escalation" in status["last_error"]
    assert brain_snapshot(tmp_path)["events"] == []


def test_remote_sync_fails_closed_on_consumer_contract_blob_substitution(tmp_path):
    fixture = _fixture(_remote_event(), corrupt_consumer_blob=True)
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["ingested_total"] == 0
    assert "consumer federation contract Git blob SHA mismatch" in status["last_error"]
    assert brain_snapshot(tmp_path)["events"] == []
