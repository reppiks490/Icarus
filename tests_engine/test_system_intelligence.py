from __future__ import annotations

import json
from pathlib import Path

from icarus_engine.system_intelligence import SCHEMA, load, report


def _write(tmp_path: Path, items):
    directory = tmp_path / "integration"
    directory.mkdir()
    (directory / "SYSTEM_INTELLIGENCE.json").write_text(
        json.dumps({
            "schema": SCHEMA,
            "generated_at": "2026-10-01T00:00:00Z",
            "items": items,
        }),
        encoding="utf-8",
    )


def test_important_items_require_interface_surface(tmp_path):
    _write(tmp_path, [{
        "id": "x",
        "subsystem": "ARGUS",
        "kind": "evolution",
        "status": "in_progress",
        "severity": "notice",
        "important": True,
        "summary": "test",
        "source_repo": "owner/repo",
        "source_branch": "branch",
        "source_commit": "a" * 40,
        "validation": {"state": "partial", "checks": []},
    }])
    result = load(tmp_path)
    assert result["mirror_ok"] is False
    assert result["items"][0]["surface_status"] == "required"
    assert any("not mirrored" in warning for warning in result["warnings"])
    assert result["execution_authorized"] is False
    assert result["production_authorized"] is False


def test_mirrored_item_is_visible_and_runtime_is_read_only(tmp_path):
    _write(tmp_path, [{
        "id": "athena",
        "subsystem": "ATHENA",
        "kind": "repair",
        "status": "verified",
        "severity": "info",
        "important": True,
        "summary": "receipt-time evidence repair",
        "interface_surface": "Intelligence",
        "source_repo": "owner/repo",
        "source_branch": "branch",
        "source_commit": "b" * 40,
        "validation": {
            "state": "verified",
            "checks": [{"name": "pytest", "status": "passed", "detail": "all green"}],
        },
    }])
    result = report(tmp_path, runtime={
        "feed_mode": "databento",
        "running_assets": ["NQ", "ES"],
        "all_warm": True,
    })
    assert result["mirror_ok"] is True
    assert result["summary"]["verified_or_merged"] == 1
    assert result["summary"]["needs_attention"] == 0
    assert result["runtime"]["feed_mode"] == "databento"
    assert result["runtime"]["running_assets"] == ["NQ", "ES"]
    assert result["execution_authorized"] is False


def test_missing_or_invalid_manifest_fails_closed(tmp_path):
    missing = load(tmp_path)
    assert missing["mirror_ok"] is False
    assert missing["items"] == []

    directory = tmp_path / "integration"
    directory.mkdir()
    (directory / "SYSTEM_INTELLIGENCE.json").write_text("{broken", encoding="utf-8")
    invalid = load(tmp_path)
    assert invalid["mirror_ok"] is False
    assert invalid["items"] == []
    assert invalid["warnings"]
