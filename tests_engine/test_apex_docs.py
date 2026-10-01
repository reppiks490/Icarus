from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_apex_installed_documentation_matches_integrated_surface():
    docs = (REPO / "docs/icarus/APEX_OMEGA.md").read_text(encoding="utf-8")
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "Projects A–F" in docs or "Projects A-F" in docs
    assert "research/apex.sqlite3" in docs
    assert "/api/apex" in docs
    assert "/admin/apex/evidence" in docs
    assert "APEX Ω" in readme
    assert "docs/icarus/APEX_OMEGA.md" in readme
    assert "execution_authorized=false" in docs
    assert "production_decision_authorized=false" in docs


def test_apex_integration_receipt_is_research_only_and_commit_bound():
    events = REPO / "automation_intelligence/mcp_interface/events"
    receipts = sorted(events.glob("*_apex_omega_integrated.json"))
    assert receipts, "APEX Ω integration receipt is missing"
    body = json.loads(receipts[-1].read_text(encoding="utf-8"))
    assert body["subsystem"] == "APEX Ω"
    assert body["source_repository"] == "reppiks490/Icarus"
    assert len(body["source_commit"]) == 40
    assert all(ch in "0123456789abcdef" for ch in body["source_commit"].lower())
    assert body["execution_authorized"] is False
    assert body["production_decision_authorized"] is False
    assert body["documentation"] == "docs/icarus/APEX_OMEGA.md"
