from __future__ import annotations

import json

import pytest

from icarus_engine.system_audit import (
    DEFAULT_REPOSITORY_AUDIT,
    DEFAULT_SYSTEM_EVOLUTION,
    evolution_path,
    load_repository_audit,
    load_system_evolution,
    normalize_repository_audit,
    normalize_system_evolution,
    repository_audit_path,
    save_repository_audit,
    save_system_evolution,
)


def test_repository_audit_defaults_are_visible_without_runtime_file(tmp_path):
    out = load_repository_audit(tmp_path)
    assert out["status"] == "green"
    assert out["main"]["sha"] == DEFAULT_REPOSITORY_AUDIT["main"]["sha"]
    assert out["summary"]["current_head_failures"] == 0
    assert out["storage"]["source"] == "bundled-default"
    assert out["evolution"]["items"]
    assert out["evolution"]["mirror_ok"] is True
    assert out["evolution"]["execution_authorized"] is False
    assert out["evolution"]["production_authorized"] is False


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



def test_system_evolution_is_separate_durable_state_and_repository_refresh_cannot_erase_it(tmp_path):
    evolution = {
        "source": "test-mcp",
        "recorded_at": "2026-10-01T02:30:00Z",
        "items": [{
            "id": "athena-repair",
            "subsystem": "ATHENA",
            "kind": "repair",
            "status": "verified",
            "severity": "notice",
            "important": True,
            "summary": "causal journal repair",
            "detail": "receipt time remains the visibility boundary",
            "source_repo": "owner/repo",
            "source_branch": "branch",
            "source_commit": "a" * 40,
            "validation_state": "green",
            "interface_surface": "System",
        }],
    }
    saved = save_system_evolution(tmp_path, evolution)
    assert saved["mirror_ok"] is True
    assert evolution_path(tmp_path).exists()

    save_repository_audit(tmp_path, {
        "repository": "reppiks490/Icarus",
        "status": "green",
        "main": {"sha": "abc", "workflow_run": 1, "linux": "success", "windows": "success"},
        "summary": {"branches_audited": 1, "current_head_failures": 0, "pending": 0, "unresolved": 0},
    })
    combined = load_repository_audit(tmp_path)
    assert combined["evolution"]["items"][0]["id"] == "athena-repair"
    assert combined["evolution"]["storage"]["source"] == "runtime"


def test_important_mcp_evolution_fails_mirror_if_not_surfaced_in_system_panel():
    result = normalize_system_evolution({
        "items": [{
            "id": "missing-ui",
            "subsystem": "PARALLAX",
            "kind": "evolution",
            "status": "in_progress",
            "severity": "warning",
            "important": True,
            "summary": "important work",
            "interface_surface": "",
        }],
    })
    assert result["mirror_ok"] is False
    assert result["summary"]["needs_attention"] == 1
    assert result["items"][0]["surface_status"] == "required"


def test_default_evolution_has_every_important_item_mirrored_and_read_only():
    result = normalize_system_evolution(DEFAULT_SYSTEM_EVOLUTION)
    assert result["mirror_ok"] is True
    assert result["items"]
    assert all(x["interface_surface"] == "System" for x in result["items"] if x["important"])
    assert all(x["execution_authorized"] is False for x in result["items"])
    assert all(x["production_authorized"] is False for x in result["items"])


@pytest.mark.parametrize("bad", [None, [], "x", {"items": "not-a-list"}])
def test_system_evolution_rejects_invalid_shapes(bad):
    with pytest.raises(ValueError):
        normalize_system_evolution(bad)
