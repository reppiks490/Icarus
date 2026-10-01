from __future__ import annotations

import json

import pytest

from icarus_engine.system_audit import (
    DEFAULT_REPOSITORY_AUDIT,
    load_repository_audit,
    normalize_repository_audit,
    repository_audit_path,
    save_repository_audit,
)


def test_repository_audit_defaults_are_visible_without_runtime_file(tmp_path):
    out = load_repository_audit(tmp_path)
    assert out["status"] == "green"
    assert out["main"]["sha"] == DEFAULT_REPOSITORY_AUDIT["main"]["sha"]
    assert out["summary"]["current_head_failures"] == 0
    assert out["storage"]["source"] == "bundled-default"


def test_repository_audit_persists_atomically_and_round_trips(tmp_path):
    payload = {
        "repository": "reppiks490/Icarus",
        "source": "test-mcp",
        "status": "warn",
        "recorded_at": "2026-10-01T02:10:00Z",
        "main": {"sha": "abc123", "workflow_run": 42, "linux": "success", "windows": "success"},
        "summary": {"branches_audited": 3, "current_head_failures": 0, "pending": 1, "unresolved": 0},
        "checks": [{"name": "branch-x", "status": "queued", "detail": "waiting for exact-head run"}],
        "issue": {"number": 62, "url": "https://github.com/reppiks490/Icarus/issues/62"},
        "note": "test",
    }
    saved = save_repository_audit(tmp_path, payload)
    assert saved["storage"]["source"] == "runtime"
    path = repository_audit_path(tmp_path)
    assert path.exists()
    assert not list(tmp_path.glob(".repository_audit.json.*.tmp"))
    assert json.loads(path.read_text(encoding="utf-8"))["status"] == "warn"

    loaded = load_repository_audit(tmp_path)
    assert loaded["status"] == "warn"
    assert loaded["main"]["workflow_run"] == 42
    assert loaded["summary"]["pending"] == 1
    assert loaded["checks"][0]["name"] == "branch-x"


@pytest.mark.parametrize("bad", [None, [], "green"])
def test_repository_audit_requires_object(bad):
    with pytest.raises(ValueError):
        normalize_repository_audit(bad)


def test_repository_audit_rejects_invalid_status_and_negative_counts():
    with pytest.raises(ValueError):
        normalize_repository_audit({"status": "perfect"})
    with pytest.raises(ValueError):
        normalize_repository_audit({"status": "green", "summary": {"current_head_failures": -1}})
