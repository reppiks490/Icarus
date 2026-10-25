"""Regression coverage for dashboard status expiry and selected-workspace reads."""

from pathlib import Path
import re

from tests_engine.test_workspace_api import workspace_http  # noqa: F401


def test_periodic_status_poll_is_single_flight():
    """The automatic 3s cadence must not overlap an unresolved status read."""
    source = Path("icarus_engine/dashboard.html").read_text(encoding="utf-8")

    assert "setInterval(refresh, 3000)" not in source
    poll = re.search(
        r"async function pollStatus\(\)\s*\{(?P<body>[\s\S]*?)\n\}",
        source,
    )
    assert poll, "dashboard needs a dedicated periodic status poll"
    body = poll.group("body")
    assert re.search(r"if\s*\(statusPollBusy\)\s*return", body)
    assert re.search(r"statusPollBusy\s*=\s*true", body)
    assert re.search(r"finally\s*\{\s*statusPollBusy\s*=\s*false", body)
    assert re.search(
        r"setInterval\((?:\(\)=>void\s+)?pollStatus(?:\(\))?\s*,\s*3000\)",
        source,
    )


def test_selected_status_snapshots_only_selected_workspace(workspace_http, monkeypatch):
    """A cc1 status read must not pay for cc2-cc4 snapshot work."""
    server, _, request = workspace_http
    manager = server.command_centers
    original = manager._profile_snapshot
    touched = []

    def observed(profile_id, now, **kwargs):
        touched.append(profile_id)
        return original(profile_id, now, **kwargs)

    monkeypatch.setattr(manager, "_profile_snapshot", observed)
    code, payload, _ = request("/api/command-centers/cc1/status")

    assert code == 200
    assert payload["workspace_id"] == "cc1"
    assert payload["paper_only"] is True
    assert payload["execution_authorized"] is False
    assert touched == ["cc1"]
