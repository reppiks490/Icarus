from __future__ import annotations

import json

import pytest

from icarus_engine.evidence_lab_sync import (
    EvidenceLabRemoteSync,
    _git_blob_sha,
    _normalize_snapshot,
)


def _docs(*, current_run="advanced-csv-20261002T151500Z", latest_run="advanced-csv-20260929T191500Z"):
    scheduler = "6abaef9d5c28819190d98a5af7f308b8"
    return {
        "icarus_consumer_contract.json": {
            "schema_version": "icarus-csv-evidence-federation-v1",
            "producer_repository": "reppiks490/icarus-csv-evidence-lab",
            "producer_ref": "main",
            "consumer_repository": "reppiks490/Icarus",
            "lane": "advanced_csv",
            "files": {
                "heartbeat": "automation_intelligence/advanced_csv/heartbeat.json",
                "evidence_state": "automation_intelligence/advanced_csv/evidence_state.json",
                "latest": "automation_intelligence/advanced_csv/latest.json",
                "finalization_state": "automation_intelligence/advanced_csv/finalization_state.json",
            },
            "semantics": {
                "run_persisted": "DURABILITY_RECEIPT_ONLY",
                "substantive_evidence_authority": "evidence_state.EVIDENCE_STATUS",
                "raw_owner_data_transfer": False,
                "automatic_model_promotion": False,
                "automatic_execution_authority": False,
            },
            "execution_authorized": False,
            "production_decision_authorized": False,
        },
        "evidence_state.json": {
            "schema_version": "scheduler-evidence-v5.6-ready",
            "lane": "advanced_csv",
            "scheduler_id": scheduler,
            "RUN_ID": None,
            "EVIDENCE_STATUS": "EMPTY_READY",
            "execution_authorized": False,
        },
        "heartbeat.json": {
            "RUN_ID": current_run,
            "RUN_STATUS": "RUN_PERSISTED",
            "scheduler_id": scheduler,
            "execution_authorized": False,
        },
        "latest.json": {
            "schema_version": "advanced-csv-run-v4",
            "RUN_ID": latest_run,
            "RUN_STATUS": "RUN_PERSISTED",
            "scheduler_id": scheduler,
            "execution_authorized": False,
        },
        "finalization_state.json": {
            "schema_version": "scheduler-finalization-v5.7",
            "scheduler_id": scheduler,
            "RUN_ID": current_run,
            "RUN_STATUS": "RUN_PERSISTED",
            "completion_semantics": "DURABILITY_RECEIPT_ONLY",
            "execution_authorized": False,
        },
    }


def test_evidence_lab_normalization_keeps_durability_separate_from_evidence():
    docs = _docs()
    out = _normalize_snapshot(docs, {name: "a" * 40 for name in docs})

    assert out["current_run_id"] == "advanced-csv-20261002T151500Z"
    assert out["run_status"] == "RUN_PERSISTED"
    assert out["evidence_status"] == "EMPTY_READY"
    assert out["finalization_run_id"] == "advanced-csv-20261002T151500Z"
    assert out["finalization_status"] == "RUN_PERSISTED"
    assert out["finalization_pointer_matches_heartbeat"] is True
    assert out["heartbeat_finalization_blob_matches"] is None
    assert out["latest_pointer_matches_heartbeat"] is False
    assert out["compatibility_pointer_lag"] is True
    assert out["evidence_pointer_matches_heartbeat"] is None
    assert out["truth_contract"]["run_persisted_is_substantive_evidence"] is False
    assert out["truth_contract"]["automatic_model_promotion"] is False
    assert out["truth_contract"]["federation_schema"] == "icarus-csv-evidence-federation-v1"
    assert out["truth_contract"]["automatic_execution_authority"] is False
    assert out["execution_authorized"] is False


def test_evidence_lab_rejects_authority_escalation():
    docs = _docs()
    docs["heartbeat.json"]["execution_authorized"] = True
    with pytest.raises(ValueError, match="execution_authorized=false"):
        _normalize_snapshot(docs, {name: "a" * 40 for name in docs})


def test_evidence_lab_remote_sync_verifies_blobs_and_surfaces_pointer_lag(tmp_path):
    docs = _docs()
    urls = {name: f"https://example.invalid/{name}" for name in docs}
    raw = {
        name: (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
        for name, payload in docs.items()
    }
    listing = [
        {
            "type": "file",
            "name": name,
            "path": f"automation_intelligence/advanced_csv/{name}",
            "sha": _git_blob_sha(raw[name]),
            "url": urls[name],
        }
        for name in docs
    ]

    sync = EvidenceLabRemoteSync(
        tmp_path,
        interval_seconds=30,
        fetch_json=lambda _url: listing,
        fetch_bytes=lambda url: next(raw[name] for name in docs if urls[name] == url),
    )
    out = sync.sync_once()

    assert out["status"] == "green"
    assert out["last_error"] is None
    assert "latest.json compatibility mirror lags heartbeat RUN_ID" in out["last_warning"]
    assert out["compatibility_pointer_lag"] is True
    assert out["finalization_pointer_matches_heartbeat"] is True
    assert out["current_run_id"] == "advanced-csv-20261002T151500Z"
    assert out["evidence_status"] == "EMPTY_READY"
    assert out["execution_authorized"] is False

    # A new verified run becomes a first-class, research-only Brain subsystem event.
    journal = tmp_path / "audit" / "brain_events.jsonl"
    assert journal.exists()
    rows = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["subject"] == "csv-evidence-lab"
    assert rows[-1]["details"]["rule"].startswith("RUN_PERSISTED is durability only")


def test_evidence_lab_degrades_on_canonical_finalization_heartbeat_mismatch(tmp_path):
    docs = _docs()
    docs["finalization_state.json"]["RUN_ID"] = "advanced-csv-20261002T141500Z"
    urls = {name: f"https://example.invalid/{name}" for name in docs}
    raw = {
        name: (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
        for name, payload in docs.items()
    }
    listing = [
        {
            "type": "file",
            "name": name,
            "path": f"automation_intelligence/advanced_csv/{name}",
            "sha": _git_blob_sha(raw[name]),
            "url": urls[name],
        }
        for name in docs
    ]

    sync = EvidenceLabRemoteSync(
        tmp_path,
        interval_seconds=30,
        fetch_json=lambda _url: listing,
        fetch_bytes=lambda url: next(raw[name] for name in docs if urls[name] == url),
    )
    out = sync.sync_once()

    assert out["status"] == "degraded"
    assert out["finalization_pointer_matches_heartbeat"] is False
    assert "finalization_state RUN_ID does not match heartbeat RUN_ID" in out["last_error"]
    assert out["execution_authorized"] is False


def test_evidence_lab_does_not_treat_evidence_run_lag_as_durability_failure(tmp_path):
    docs = _docs()
    docs["evidence_state.json"]["RUN_ID"] = "advanced-csv-20261002T141500Z"
    docs["evidence_state.json"]["EVIDENCE_STATUS"] = "NO_NEW_EVIDENCE"
    urls = {name: f"https://example.invalid/{name}" for name in docs}
    raw = {
        name: (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
        for name, payload in docs.items()
    }
    listing = [
        {
            "type": "file",
            "name": name,
            "path": f"automation_intelligence/advanced_csv/{name}",
            "sha": _git_blob_sha(raw[name]),
            "url": urls[name],
        }
        for name in docs
    ]

    sync = EvidenceLabRemoteSync(
        tmp_path,
        interval_seconds=30,
        fetch_json=lambda _url: listing,
        fetch_bytes=lambda url: next(raw[name] for name in docs if urls[name] == url),
    )
    out = sync.sync_once()

    assert out["status"] == "green"
    assert out["last_error"] is None
    assert out["evidence_pointer_matches_heartbeat"] is False
    assert "evidence authority remains independent of durability" in out["last_warning"]
    assert out["execution_authorized"] is False
