"""Real selected subsystem panels and owner controls never fall back to main."""
import json
import math

import pytest

from tests_engine.test_workspace_api import workspace_http  # noqa: F401


@pytest.mark.parametrize("workspace,price", [("cc1", 100), ("cc2", 200), ("cc3", 300), ("cc4", 400)])
@pytest.mark.parametrize("panel", ["possibility", "chronofold", "commissioning", "engine-control"])
def test_real_panel_reads_selected_runtime_without_parent_fallback(workspace_http, monkeypatch, workspace, price, panel):
    server, parent, request = workspace_http
    monkeypatch.setattr(parent, "status", lambda *a, **k: pytest.fail("parent runtime fallback"))
    code, data, _ = request(f"/api/command-centers/{workspace}/panels/{panel}?asset=NQ")
    assert code == 200, data
    assert data["workspace_id"] == workspace and data["config_revision"] == 0
    assert data["paper_only"] is True and data["execution_authorized"] is False
    if panel == "possibility":
        assert data["asset"] == "NQ" and data["price"] == price
    elif panel == "chronofold":
        assert data["asset"] == "NQ"
        assert math.exp(data["price_phase_field"]["log_price"]) == pytest.approx(price)
    elif panel == "commissioning":
        assert data["asset"] == "NQ" and data["ledger"]["predictions"] == 0
    else:
        assert data["subsystems"]["portfolio"]["data"]["assets"][0]["price"] == price
        assert data["authority"]["broker_arming"] is False


@pytest.mark.parametrize("panel", ["possibility", "chronofold", "commissioning", "engine-control"])
def test_panel_rejects_parent_only_asset_and_ambiguous_selectors(workspace_http, panel):
    _, _, request = workspace_http
    for query, expected in [("asset=ES", 404), ("asset=NQ&asset=ES", 400), ("workspace=cc2", 400)]:
        code, _, _ = request(f"/api/command-centers/cc1/panels/{panel}?{query}")
        assert code == expected
    assert request(f"/api/command-centers/cc1/panels/{panel}", token="bad")[0] == 401
    assert request(f"/api/command-centers/cc1/panels/{panel}", extra_headers={"X-Icarus-Workspace": "cc2"})[0] == 409


def test_engine_panel_pause_is_selected_and_stale_revision_has_no_side_effect(workspace_http):
    server, parent, request = workspace_http
    route = "/admin/command-centers/cc1/panels/engine-control"
    headers = {"X-Icarus-Config-Revision": "0", "X-Icarus-Workspace": "cc1"}
    body = {"action": "asset.pause", "target": "NQ"}
    code, data, _ = request(route, body=body, extra_headers=headers)
    assert code == 200, data
    assert data["workspace_id"] == "cc1" and data["execution_authorized"] is False
    assert server.command_centers.portfolios["cc1"].runners["NQ"].paused is True
    assert parent.runners["NQ"].paused is False
    assert server.command_centers.portfolios["cc2"].runners["NQ"].paused is False
    server.command_centers.profiles["cc1"]["config_revision"] = 1
    code, _, _ = request(route, body={"action": "asset.resume", "target": "NQ"}, extra_headers=headers)
    assert code == 409
    assert server.command_centers.portfolios["cc1"].runners["NQ"].paused is True
    assert request(route, body=body)[0] == 400


def test_panel_control_rejects_foreign_asset_before_audit_or_main_mutation(workspace_http):
    server, parent, request = workspace_http
    root = server.command_centers.root / "cc1" / "subsystems"
    before = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    code, _, _ = request("/admin/command-centers/cc1/panels/engine-control",
                         body={"action": "asset.pause", "target": "ES"},
                         extra_headers={"X-Icarus-Config-Revision": "0"})
    assert code == 404
    assert parent.runners["ES"].paused is False
    assert before == {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_nested_market_data_path_cannot_alias_the_existing_reader(workspace_http):
    _, _, request = workspace_http
    code, _, _ = request('/api/command-centers/cc1/panels/market-data/unknown?asset=NQ&resource=ticks')
    assert code == 404


def test_selected_panel_rejects_duplicate_json_fields_before_mutation(workspace_http):
    from http.client import HTTPConnection
    server, _, _ = workspace_http
    conn = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
    try:
        conn.request('POST', '/admin/command-centers/cc1/panels/engine-control',
            body='{"action":"asset.resume","action":"asset.pause","target":"NQ"}',
            headers={'Authorization':'Bearer api-owner', 'Content-Type':'application/json',
                     'X-Icarus-Config-Revision':'0'})
        response = conn.getresponse()
        response.read()
        assert response.status == 400
        assert server.command_centers.portfolios['cc1'].runners['NQ'].paused is False
    finally:
        conn.close()


def test_selected_control_rejects_unused_arguments(workspace_http):
    server, _, request = workspace_http
    code, _, _ = request('/admin/command-centers/cc1/panels/engine-control',
        body={'action':'asset.pause', 'target':'NQ', 'args':{'workspace':'cc2'}},
        extra_headers={'X-Icarus-Config-Revision':'0'})
    assert code == 400
    assert server.command_centers.portfolios['cc1'].runners['NQ'].paused is False


@pytest.mark.parametrize('panel', ['possibility', 'chronofold', 'commissioning', 'engine-control'])
def test_analytics_read_cached_provider_buffers_without_starting_sessions(workspace_http, panel):
    from tests_engine.test_workspace_market_data import owner
    server, _, request = workspace_http
    feed = owner()
    calls = []
    def acquire(*a, **k):
        calls.append((a, k))
        raise AssertionError("panel must not call a provider")
    feed.trades = feed.depth_events = feed.meta = feed.capabilities = acquire
    server.command_centers.portfolios["cc1"].runners["NQ"].feed = feed
    code, data, _ = request(f"/api/command-centers/cc1/panels/{panel}?asset=NQ")
    assert code == 200, data
    assert calls == []


@pytest.mark.parametrize('panel', ['possibility', 'chronofold', 'commissioning', 'engine-control'])
def test_unavailable_selected_panel_runtime_never_uses_parent(workspace_http, panel):
    server, _, request = workspace_http
    absent = server.command_centers.portfolios.pop('cc4')
    try:
        code, data, _ = request(f'/api/command-centers/cc4/panels/{panel}?asset=NQ')
        assert code == 503 and data['workspace_id'] == 'cc4'
        assert data['execution_authorized'] is False
    finally:
        server.command_centers.portfolios['cc4'] = absent


def test_selected_samplers_start_capture_and_close_independently(workspace_http):
    server, _, _ = workspace_http
    registry = server.workspace_panels
    try:
        registry.start()
        for index, workspace in enumerate(('cc1', 'cc2', 'cc3', 'cc4'), 1):
            service = registry._runtimes[workspace].commissioning
            assert service._thread.is_alive()
            assert service.root == server.command_centers.root / workspace / 'subsystems' / 'audit' / 'commissioning'
            predictions = list(service._predictions.values())
            assert predictions and predictions[0]['start_price'] == index * 100
    finally:
        registry.close()
    assert all(not runtime.commissioning._thread.is_alive() for runtime in registry._runtimes.values())


def test_commissioning_forecast_persists_only_in_selected_workspace(workspace_http):
    from icarus_engine.commissioning import CommissioningEngine
    server, _, request = workspace_http
    code, data, _ = request("/admin/command-centers/cc1/panels/engine-control",
        body={"action": "commissioning.capture", "target": "NQ"},
        extra_headers={"X-Icarus-Config-Revision": "0"})
    assert code == 200, data
    root = server.command_centers.root / "cc1" / "subsystems"
    path = root / "audit" / "commissioning" / "predictions.jsonl"
    assert path.is_file()
    assert '"start_price":100' in path.read_text().replace(" ", "")
    assert not (server.command_centers.root / "cc2" / "subsystems" / "audit" / "commissioning" / "predictions.jsonl").exists()
    reopened = CommissioningEngine(root, None, None)
    assert reopened.status("NQ")["ledger"]["predictions"] == 1
    assert reopened.status("NQ")["authority"]["execution_authorized"] is False


def test_possibility_panel_evidence_is_scoped_and_survives_service_recreation(workspace_http):
    from icarus_engine.possibility import PossibilityEngine
    server, _, request = workspace_http
    prefix = "/api/command-centers/cc1/panels/possibility/evidence"
    body = {"asset": "NQ", "source": "operator", "values": {"gamma_pressure": {"value": 0.6, "confidence": 0.8}}}
    code, data, _ = request("/admin/command-centers/cc1/panels/possibility/evidence", body=body,
                           extra_headers={"X-Icarus-Config-Revision": "0"})
    assert code == 200, data
    code, data, _ = request(prefix + "?asset=NQ&limit=10&include_expired=false")
    assert code == 200 and data["workspace_id"] == "cc1", data
    first = server.workspace_panels._runtimes["cc1"]
    reopened = PossibilityEngine(first.port)
    recovered = reopened.evidence_snapshot("NQ", as_of=data["as_of"])
    original = first.possibility.evidence_snapshot("NQ", as_of=data["as_of"])
    assert recovered["active"] == original["active"] and recovered["history"] == original["history"]
    assert recovered["integrity"]["ledger_digest_sha256"] == original["integrity"]["ledger_digest_sha256"]
    assert recovered["integrity"]["receipt_count"] == 1 and recovered["integrity"]["ok"] is True
    other = request("/api/command-centers/cc2/panels/possibility/evidence?asset=NQ")[1]
    assert "operator" not in json.dumps(other)


def test_panel_client_preserves_asset_query_and_revision_for_mutation():
    import shutil
    import subprocess
    from pathlib import Path
    node = shutil.which("node")
    if not node:
        pytest.skip("Node required for explicit module transport")
    script = r"""
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
vm.runInThisContext(fs.readFileSync(process.argv[1],'utf8'));
const calls=[];
const c=IcarusWorkspaceClient.create({id:'cc3'},{origin:'http://localhost:8791',fetch:async(url,init)=>{
  calls.push({url,init});
  return new Response(JSON.stringify({workspace_id:'cc3',config_revision:7,paper_only:true,execution_authorized:false}));
}});
(async()=>{
await c.request('/api/chronofold?asset=6E');
assert.equal(new URL(calls[0].url).pathname,'/api/command-centers/cc3/panels/chronofold');
assert.equal(new URL(calls[0].url).search,'?asset=6E');
await c.request('/admin/engine-control',{method:'POST',body:JSON.stringify({action:'asset.pause',target:'6E'})});
assert.equal(new URL(calls[1].url).pathname,'/admin/command-centers/cc3/panels/engine-control');
assert.equal(calls[1].init.headers.get('X-Icarus-Config-Revision'),'7');
assert.equal(JSON.parse(calls[1].init.body).target,'6E');
await c.request('/admin/engine-control?asset=ES',{method:'POST',body:JSON.stringify({action:'asset.pause',target:'6E'})});
assert.equal(new URL(calls[2].url).search,'?asset=ES','Server must be able to reject supplied mutation selectors');
})().catch(e=>{console.error(e);process.exit(1)});
"""
    result = subprocess.run([node, "-e", script, str(Path(__file__).resolve().parents[1] / "icarus_engine/workspace-client.js")],
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
