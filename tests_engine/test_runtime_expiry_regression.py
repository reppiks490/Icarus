"""Regression coverage for dashboard status expiry and selected-workspace reads."""

from tests_engine.test_workspace_api import workspace_http  # noqa: F401
from tests_engine.test_workspace_client import run_js


def test_core_status_reads_are_single_flight():
    """The 3s dashboard cadence must join an unresolved core-status read."""
    run_js(r"""
let release;
const pending = new Promise(resolve => { release = resolve; });
const {c,calls}=client('cc1',()=>pending);
const first=c.read('status',{channel:'core-status'});
const second=c.read('status',{channel:'core-status'});
await new Promise(resolve=>setTimeout(resolve,0));
assert.equal(calls.length,1);
release(reply({...identity('cc1',4),assets:[{price:400}]}));
assert.equal((await first).assets[0].price,400);
assert.equal((await second).assets[0].price,400);
""")


def test_selected_status_snapshots_only_selected_workspace(workspace_http, monkeypatch):
    """A cc1 status read must not pay for cc2-cc4 snapshot work."""
    server, _, request = workspace_http
    manager = server.command_centers
    original = manager._profile_snapshot
    touched = []

    def observed(profile_id, now):
        touched.append(profile_id)
        return original(profile_id, now)

    monkeypatch.setattr(manager, "_profile_snapshot", observed)
    code, payload, _ = request("/api/command-centers/cc1/status")

    assert code == 200
    assert payload["workspace_id"] == "cc1"
    assert payload["paper_only"] is True
    assert payload["execution_authorized"] is False
    assert touched == ["cc1"]
