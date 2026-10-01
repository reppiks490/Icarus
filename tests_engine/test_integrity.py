from __future__ import annotations

import json

import pytest

from icarus_engine.integrity import integrity_snapshot, record_integrity_event


def _manifest(path):
    path.write_text(json.dumps({
        "schema_version": "icarus-interface-ledger-v2",
        "execution_authorized": False,
        "policy": {"mcp_mirror_required": True},
        "export_intake": {"unique_payloads": 11},
        "checklist": [{"id": "O14", "status": "verified"}],
        "repairs": [],
        "events": [],
    }), encoding="utf-8")


def _event():
    return {
        "kind": "repair",
        "area": "ingestion",
        "summary": "Reject backward timestamps.",
        "status": "repaired",
        "severity": "high",
        "source_repo": "reppiks490/divine-providence",
        "source_branch": "main",
        "source_commit": "4a27b4776a56bd63bedd3243696316440c5a8ef8",
        "verification": "Regression checked.",
        "interface_effect": "Blocker is shown as repaired.",
        "evidence": ["pytest"],
        "details": {"test": "green"},
    }


def test_integrity_snapshot_is_fail_closed_and_loads_manifest(tmp_path):
    manifest = tmp_path / "manifest.json"
    _manifest(manifest)
    snap = integrity_snapshot(tmp_path, manifest_path=manifest)
    assert snap["execution_authorized"] is False
    assert snap["policy"]["mcp_mirror_required"] is True
    assert snap["export_intake"]["unique_payloads"] == 11
    assert snap["runtime_event_count"] == 0
    assert snap["manifest_error"] is None


def test_mcp_integrity_event_is_idempotent_and_fully_provenanced(tmp_path):
    first = record_integrity_event(tmp_path, _event())
    second = record_integrity_event(tmp_path, _event())
    assert first["execution_authorized"] is False
    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert first["event"]["id"] == second["event"]["id"]
    assert first["event"]["source_commit"] == _event()["source_commit"]

    manifest = tmp_path / "manifest.json"
    _manifest(manifest)
    snap = integrity_snapshot(tmp_path, manifest_path=manifest)
    assert snap["runtime_event_count"] == 1
    assert snap["events"][0]["summary"] == "Reject backward timestamps."
    assert snap["events"][0]["execution_authorized"] is False


def test_integrity_event_requires_exact_provenance_and_rejects_authority(tmp_path):
    bad = _event()
    bad["source_commit"] = "abc123"
    with pytest.raises(ValueError, match="exact 40-character Git SHA"):
        record_integrity_event(tmp_path, bad)

    bad = _event()
    bad["execution_authorized"] = True
    with pytest.raises(ValueError, match="unknown integrity fields"):
        record_integrity_event(tmp_path, bad)


def test_corrupt_journal_row_is_counted_not_trusted(tmp_path):
    journal = tmp_path / "audit" / "interface_events.jsonl"
    journal.parent.mkdir()
    journal.write_text('{"execution_authorized":true}\n', encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    _manifest(manifest)
    snap = integrity_snapshot(tmp_path, manifest_path=manifest)
    assert snap["journal_errors"] == 1
    assert snap["runtime_event_count"] == 0
    assert snap["execution_authorized"] is False


def test_invalid_manifest_cannot_raise_execution_authority(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"execution_authorized": true}', encoding="utf-8")
    snap = integrity_snapshot(tmp_path, manifest_path=manifest)
    assert snap["execution_authorized"] is False
    assert snap["manifest_error"]
