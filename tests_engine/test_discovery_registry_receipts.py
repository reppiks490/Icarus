import json
import os
from pathlib import Path

import pytest

from icarus_engine.discovery_registry.receipts import snapshot


CATALOGS = {
    "api-mega-list": "cporter202/API-mega-list",
    "scraping-apis-for-devs": "cporter202/scraping-apis-for-devs",
    "ai-agent-tools": "cporter202/ai-agent-tools",
}


def _receipt(catalog_id: str, upstream_repo: str) -> dict[str, object]:
    return {
        "catalog_id": catalog_id,
        "upstream_repo": upstream_repo,
        "upstream_path": "README.md",
        "upstream_commit": "a" * 40,
        "retrieved_at": "2026-10-25T00:00:00Z",
        "content_sha256": "b" * 64,
        "status": "SUCCESS",
        "execution_authorized": False,
        "production_decision_authorized": False,
        "import_summary": {
            "raw_count": 8,
            "imported_entries": 7,
            "unique_candidates": 6,
            "duplicate_groups": 1,
            "rejected": 1,
            "review_required": 6,
            "parse_failures": 1,
        },
    }


def _write_receipts(root: Path) -> None:
    latest = root / "automation_intelligence" / "catalog_registry_v1" / "latest"
    latest.mkdir(parents=True)
    for catalog_id, upstream_repo in CATALOGS.items():
        (latest / f"{catalog_id}.json").write_text(
            json.dumps(_receipt(catalog_id, upstream_repo)), encoding="utf-8"
        )


def test_receipt_snapshot_exposes_only_pinned_allowlisted_metadata(tmp_path: Path):
    _write_receipts(tmp_path)

    result = snapshot(tmp_path)

    assert result["status"] == "AVAILABLE"
    assert result["catalogs_available"] == result["catalogs_expected"] == 3
    assert result["source_probes_performed"] is False
    assert result["market_data_provided"] is False
    assert result["execution_authorized"] is False
    assert result["production_decision_authorized"] is False
    assert len(result["catalogs"]) == 3
    assert result["catalogs"][0]["summary"]["review_required"] == 6
    assert "raw_rows" not in result["catalogs"][0]


def test_missing_or_misbound_receipt_stays_unavailable_without_creating_registry(tmp_path: Path):
    _write_receipts(tmp_path)
    bad = tmp_path / "automation_intelligence" / "catalog_registry_v1" / "latest" / "ai-agent-tools.json"
    payload = _receipt("ai-agent-tools", CATALOGS["ai-agent-tools"])
    payload["upstream_repo"] = "attacker/other-repo"
    bad.write_text(json.dumps(payload), encoding="utf-8")

    result = snapshot(tmp_path)

    assert result["status"] == "PARTIAL"
    rejected = next(row for row in result["catalogs"] if row["catalog_id"] == "ai-agent-tools")
    assert rejected["status"] == "UNAVAILABLE"
    assert "research" not in {path.name for path in tmp_path.iterdir()}


def test_receipt_symlink_outside_repository_fails_closed(tmp_path: Path):
    _write_receipts(tmp_path)
    latest = tmp_path / "automation_intelligence" / "catalog_registry_v1" / "latest"
    target = tmp_path.parent / "outside-catalog-receipt.json"
    target.write_text(json.dumps(_receipt("api-mega-list", CATALOGS["api-mega-list"])), encoding="utf-8")
    path = latest / "api-mega-list.json"
    path.unlink()
    try:
        path.symlink_to(target)
    except OSError as error:
        if os.name == "nt" and getattr(error, "winerror", None) == 1314:
            pytest.skip("Windows runner does not permit symlink creation")
        raise

    result = snapshot(tmp_path)

    assert result["status"] == "PARTIAL"
    assert result["catalogs"][0]["status"] == "UNAVAILABLE"
