"""Dedicated views use the selected real workspace and never the main ledger."""
import json
import time
import sys
import threading
import types
from http.client import HTTPConnection
from unittest.mock import Mock

import pytest

from icarus_engine import paper_workspaces
from icarus_engine.assets import REGISTRY
from icarus_engine.runtime import Journal, Portfolio
from icarus_engine.server import serve


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_FEED", "file")
    journal = Journal(":memory:")
    parent = Portfolio(journal, str(tmp_path), feeds={})
    srv = serve(parent, 0, token="owner-test", start=False)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()

    def request(path, *, method="GET", body=None, token=None, host=None):
        connection = HTTPConnection("127.0.0.1", srv.server_port, timeout=5)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        if host:
            headers["Host"] = host
        connection.request(method, path, json.dumps(body) if body is not None else None, headers)
        response = connection.getresponse()
        raw = response.read()
        status, kind = response.status, response.getheader("Content-Type")
        connection.close()
        return status, json.loads(raw) if kind.startswith("application/json") else raw.decode()

    yield srv, request
    srv.shutdown()
    thread.join(timeout=5)
    srv.command_centers.portfolios.clear()
    srv.server_close()
    journal.close()


@pytest.mark.parametrize("profile_id", ["cc1", "cc2", "cc3", "cc4"])
def test_dedicated_page_and_profile_filter(engine, profile_id):
    srv, request = engine
    code, page = request("/dashboards/" + profile_id)
    assert code == 200
    assert 'id="combined-accounting"' in page
    assert page.index('id="combined-accounting"') < page.index('id="workspace-panel"')
    assert '/workspace-dashboard.js' in page
    code, payload = request("/api/command-centers/" + profile_id + "?profile=cc4")
    assert code == 200
    assert payload["profile"]["id"] == profile_id
    assert "profiles" not in payload
    assert payload["aggregate"]["workspace_count"] == 4
    assert payload["accounting"]["reconciled_broker_pnl"] is None
    assert payload["accounting"]["fees_verified"] is False
    assert payload["accounting"]["complete"] is False
    assert payload["aggregate"]["realized_pnl"] is None
    assert payload["profile"]["pnl"]["realized_pnl"] is None
    assert payload["execution_authorized"] is False


@pytest.mark.parametrize("path", ["/dashboards/cc5", "/dashboards/cc1/extra", "/api/command-centers/CC1", "/api/command-centers/cc1/extra", "/api/command-centers/cc1%2Fcc2"])
def test_unknown_profile_routes_fail_closed(engine, path):
    assert engine[1](path)[0] == 404


def test_corpus_safe_reader_has_no_user_selected_path(engine, monkeypatch):
    called = Mock(return_value={"status": "HISTORICAL_CONSUMPTION_VERIFIED", "corpora": [], "execution_authorized": False})
    monkeypatch.setitem(sys.modules, "icarus_engine.corpus_evidence", types.SimpleNamespace(snapshot=called))
    status, result = engine[1]("/api/corpus-consumption?path=/etc/passwd&now_ns=1")
    assert status == 200
    assert result["status"] == "HISTORICAL_CONSUMPTION_VERIFIED"
    called.assert_called_once_with()


def test_chart_is_scoped_to_workspace_and_auth_controls_preserved(engine):
    srv, request = engine
    workspace_runner = Mock()
    workspace_runner.chart.return_value = {"asset": "NQ", "bars": [{"c": 121}]}
    workspace = Mock()
    workspace.runners = {"NQ": workspace_runner}
    srv.command_centers.portfolios["cc2"] = workspace
    code, result = request("/api/command-centers/cc2/chart/NQ?n=40")
    assert code == 200 and result["bars"][0]["c"] == 121
    workspace_runner.chart.assert_called_once_with(40, nonblocking=True)
    assert request("/api/command-centers/cc1/chart/NQ")[0] == 503
    assert request("/api/command-centers/cc2/chart/ES")[0] == 404
    assert request("/admin/command-centers/cc2/pause", method="POST", body={"paused": True})[0] == 401
    assert request("/dashboards/cc2", host="attacker.example")[0] == 403
    srv.command_centers.portfolios.clear()


def test_complete_paper_accounting_reuses_manager_totals(engine, monkeypatch):
    srv, request = engine
    snapshot = srv.command_centers.snapshot()
    for i, profile in enumerate(snapshot["profiles"], 1):
        profile["pnl"].update(realized_pnl=10 * i, open_pnl=i)
        profile.update(runtime_available=True, valuation_complete=True)
    snapshot["aggregate"].update(realized_pnl=100, open_pnl=10, accounting_complete=True)
    from icarus_engine.paper_pnl import validate_paper_pnl
    now = int(time.time())
    snapshot["paper_pnl"] = validate_paper_pnl([
        {"id": row["id"], "currency": "USD", "runtime_available": True, "snapshot_ts": now,
         "realized_pnl": row["pnl"]["realized_pnl"], "open_pnl": row["pnl"]["open_pnl"],
         "open_positions": 1, "oldest_open_mark_ts": now} for row in snapshot["profiles"]], as_of_ts=now)
    monkeypatch.setattr(srv.command_centers, "snapshot", lambda: snapshot)
    srv.command_centers.portfolios = {key: object() for key in ("cc1", "cc2", "cc3", "cc4")}
    status, result = request("/api/command-centers/cc3")
    assert status == 200
    assert result["accounting"]["complete"] is True
    assert result["aggregate"]["realized_pnl"] == 100
    assert result["aggregate"]["open_pnl"] == 10
    assert result["profile"]["pnl"]["realized_pnl"] == 30
    srv.command_centers.portfolios.clear()


def test_old_ui_links_all_four_separate_views(engine):
    status, script = engine[1]("/command-centers-ui.js")
    assert status == 200
    assert '/dashboards/' in script
    assert '/dashboards/connections' in script


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), True, "12.50", 10 ** 1000])
def test_invalid_accounting_values_never_produce_complete_aggregate(engine, monkeypatch, bad_value):
    srv, request = engine
    snapshot = srv.command_centers.snapshot()
    snapshot["profiles"][0]["pnl"]["open_pnl"] = bad_value
    monkeypatch.setattr(srv.command_centers, "snapshot", lambda: snapshot)
    srv.command_centers.portfolios = {key: object() for key in ("cc1", "cc2", "cc3", "cc4")}
    status, result = request("/api/command-centers/cc1")
    assert status == 200
    assert result["accounting"]["complete"] is False
    assert result["aggregate"]["realized_pnl"] is None


def test_connections_routes_authenticate_before_any_account_read(engine):
    srv, request = engine
    assert request("/connections")[0] == 200
    assert request("/api/account-connections")[0] == 401
    assert request("/admin/account-connections", method="POST", body={})[0] == 401
    assert request("/admin/account-connections/arbitrary/connect", method="POST", body={})[0] == 401


def test_unavailable_private_account_store_does_not_disable_dashboards(monkeypatch, request):
    constructor = Mock(side_effect=ValueError("PRIVATE_FAILURE_MARKER"))
    monkeypatch.setitem(sys.modules, "icarus_engine.account_connections", types.SimpleNamespace(ConnectionManager=constructor))
    srv, http = request.getfixturevalue("engine")
    assert http("/dashboards/cc1")[0] == 200
    code, result = http("/api/account-connections", token="owner-test")
    assert code == 503
    assert "PRIVATE_FAILURE_MARKER" not in json.dumps(result)


def test_corrupt_duplicate_workspace_accounting_is_unavailable(engine, monkeypatch):
    srv, request = engine
    snapshot = srv.command_centers.snapshot()
    snapshot["profiles"][3]["id"] = "cc1"
    monkeypatch.setattr(srv.command_centers, "snapshot", lambda: snapshot)
    srv.command_centers.portfolios = {key: object() for key in ("cc1", "cc2", "cc3", "cc4")}
    result = request("/api/command-centers/cc1")[1]
    assert result["accounting"]["complete"] is False
    assert result["aggregate"]["open_pnl"] is None


def test_connections_hooks_use_authenticated_manager_and_owner_controls(monkeypatch, request):
    manager = Mock()
    manager.snapshot.return_value = {"connections": [], "execution_authorized": False}
    manager.upsert.return_value = {"id": "paper-one", "status": "CONFIGURED", "execution_authorized": False}
    manager.connect.return_value = {"id": "paper-one", "status": "UNSUPPORTED", "execution_authorized": False}
    constructor = Mock(return_value=manager)
    monkeypatch.setitem(sys.modules, "icarus_engine.account_connections", types.SimpleNamespace(ConnectionManager=constructor))
    srv, http = request.getfixturevalue("engine")
    assert http("/api/account-connections", token="owner-test")[0] == 200
    manager.snapshot.assert_called_once_with()
    assert http("/admin/account-connections", method="POST", body={"id": "paper-one"}, token="owner-test")[0] == 200
    manager.upsert.assert_called_once_with({"id": "paper-one"})
    assert http("/admin/account-connections/paper-one/connect", method="POST", body={}, token="owner-test")[0] == 200
    manager.connect.assert_called_once_with("paper-one")
    assert http("/admin/account-connections/paper-one/connect/extra", method="POST", body={}, token="owner-test")[0] == 404


def test_missing_marks_with_numeric_fallback_never_appear_as_verified_pnl(engine, monkeypatch):
    srv, request = engine
    snapshot = srv.command_centers.snapshot()
    snapshot["aggregate"]["accounting_complete"] = False
    snapshot["profiles"][0]["valuation_complete"] = False
    snapshot["profiles"][0]["pnl"]["open_pnl"] = 0.0
    monkeypatch.setattr(srv.command_centers, "snapshot", lambda: snapshot)
    srv.command_centers.portfolios = {key: object() for key in ("cc1", "cc2", "cc3", "cc4")}
    result = request("/api/command-centers/cc1")[1]
    assert result["accounting"]["complete"] is False
    assert result["aggregate"]["open_pnl"] is None
    assert result["profile"]["pnl"]["open_pnl"] is None


def test_a200_research_browser_is_shared_and_history_is_explicit_and_isolated(engine):
    """Optional real Chromium flow; provider responses are synthetic interceptions."""
    import shutil
    import subprocess

    node = shutil.which("node")
    chromium = shutil.which("chromium") or shutil.which("chromium-browser")
    if not node or not chromium:
        pytest.skip("optional Node/Chromium presentation environment unavailable")
    available = subprocess.run([node, "-e", "require.resolve('playwright')"], capture_output=True)
    if available.returncode:
        pytest.skip("optional Playwright presentation dependency unavailable")
    script = r"""
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
let browser;
(async()=>{
 browser=await chromium.launch({executablePath:process.argv[2],headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900}});page.setDefaultTimeout(8000);
 let mismatch=false;const historyCalls=[];const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/api/market-history/**',async route=>{
  const request=route.request(),url=new URL(request.url()),instrumentId=decodeURIComponent(url.pathname.split('/').pop());
  historyCalls.push({url:url.href,headers:request.headers()});
  const start=Number(url.searchParams.get('start_ts'));
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({
   instrument:{instrument_id:instrumentId,display_symbol:'NVDA'},provider:'yahoo',qualification:'UNQUALIFIED',pulse_enabled:false,execution_authorized:false,
   receipt:{instrument_id:mismatch?'wrong-identity':instrumentId,provider:'yahoo',receipt_id:'synthetic-browser-fixture',historical_bars_qualified:false,entitlement_status:'UNKNOWN',corporate_action_policy:'UNKNOWN'},
   bars:[{ts:start+3600,o:101,h:103,l:100,c:102,v:10},{ts:start+7200,o:102,h:105,l:101,c:104,v:15}]
  })});
 });
 for(const id of ['cc1','cc2','cc3','cc4']){
  await page.goto(process.argv[1]+'/dashboards/'+id);
  await page.waitForFunction(()=>document.querySelectorAll('#a200-instrument option').length===200);
  assert.equal(await page.locator('#a200-rows tr').count(),200);
  assert.match(await page.locator('#a200-summary').textContent(),/200 catalogued/);
  assert.match(await page.locator('#a200-summary').textContent(),/0 Pulse/);
 }
 assert.equal(historyCalls.length,0,'browsing all four dashboards must not acquire history');
 await page.locator('#a200-search').fill('TSLA');
 assert.equal(await page.locator('#a200-rows tr').count(),1);
 assert.match(await page.locator('#a200-rows').textContent(),/Tesla/);
 await page.locator('#a200-search').fill('');
 const before=await page.locator('#all-total').textContent();
 await page.locator('#a200-history').click();
 assert.equal(historyCalls.length,0,'no owner token means no request');
 await page.locator('#owner-token').fill('owner-test');
 await page.locator('#a200-history').click();
 await page.waitForFunction(()=>document.querySelector('#a200-history-note').textContent.includes('2 observed bars'));
 assert.equal(historyCalls.length,1);
 const call=historyCalls[0],url=new URL(call.url);
 assert.equal(call.headers.authorization,'Bearer owner-test');
 assert.equal(url.searchParams.get('provider'),'yahoo');
 assert.equal(url.searchParams.get('interval_seconds'),'3600');
 assert.equal(url.searchParams.get('limit'),'240');
 assert.equal(Number(url.searchParams.get('end_ts'))-Number(url.searchParams.get('start_ts')),5*86400);
 assert.match(await page.locator('#a200-receipt').textContent(),/UNKNOWN/);
 assert.equal(await page.locator('#all-total').textContent(),before,'research cannot change P&L');
 assert.match(await page.locator('#chart-note').textContent(),/No selected workspace/);
 await page.locator('#a200-instrument').selectOption({index:1});
 assert.match(await page.locator('#a200-history-note').textContent(),/No history requested/);
 assert.equal(historyCalls.length,1,'selection cannot acquire another dataset');
 mismatch=true;await page.locator('#a200-history').click();
 await page.waitForFunction(()=>document.querySelector('#a200-history-note').textContent.includes('does not match'));
 assert.equal(historyCalls.length,2);
 assert.equal(await page.locator('#all-total').textContent(),before);
 await page.setViewportSize({width:390,height:844});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 assert.deepEqual(errors,[]);
 await browser.close();
})().catch(async error=>{console.error(error);await browser?.close();process.exitCode=1;});
"""
    srv, _ = engine
    result = subprocess.run(
        [node, "-e", script, f"http://127.0.0.1:{srv.server_port}", chromium],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_a200_context_history_http_is_one_authenticated_yahoo_read_without_runtime_admission(engine, monkeypatch):
    from datetime import datetime, timezone
    from urllib.parse import urlencode
    from icarus_engine import market_universe_adapter
    from icarus_engine.bar_receipts import make_bar_batch_receipt
    from icarus_engine.market_universe import snapshot
    from icarus_engine.pine.timeframe import Bar

    srv, request = engine
    code, catalog = request('/api/market-universe')
    assert code == 200 and len(catalog['instruments']) == 200
    assert catalog['counts']['pulse_enabled_count'] == 0
    row = catalog['instruments'][0]
    source_symbol = next(m['symbol'] for m in row['provider_symbol_candidates'] if m['provider'] == 'yahoo')
    start = int(datetime(2026, 10, 12, 13, 30, tzinfo=timezone.utc).timestamp())
    end = start + 5 * 86400
    bars = [Bar(start, 100, 103, 99, 102, 10), Bar(start + 3600, 102, 104, 101, 103, 20)]
    _, receipt = make_bar_batch_receipt(
        instrument_id=row['instrument_id'], provider='yahoo', expected_provider_symbol=source_symbol,
        observed_provider_symbol=source_symbol, interval_seconds=3600, requested_start_ts=start,
        requested_end_ts=end, bars=bars, fetched_at_ns=1, received_at_ns=2,
        entitlement_status='UNKNOWN', provider_mapping_status='UNVERIFIED',
    )
    calls = []
    class FakeAdapter:
        def __init__(self, *, providers):
            assert providers == ('yahoo',)
        def fetch_history(self, identity, interval, start_ts, end_ts, *, provider):
            calls.append((identity, interval, start_ts, end_ts, provider))
            return bars, receipt
    monkeypatch.setattr(market_universe_adapter, 'MarketUniverseAdapter', FakeAdapter)
    path = '/api/market-history/' + row['instrument_id'] + '?' + urlencode(dict(
        start_ts=start, end_ts=end, interval_seconds=3600, limit=240, provider='yahoo'))
    assert request(path)[0] == 401
    assert calls == []
    code, response = request(path, token='owner-test')
    assert code == 200
    assert calls == [(row['instrument_id'], 3600, start, end, 'yahoo')]
    assert response['bars'][1]['c'] == 103
    assert response['receipt']['entitlement_status'] == 'UNKNOWN'
    assert response['receipt']['corporate_action_policy'] == 'UNKNOWN'
    assert response['qualification'] == 'UNQUALIFIED'
    assert response['pulse_enabled'] is False and response['execution_authorized'] is False
    assert srv.command_centers.portfolios == {}
    assert snapshot()['counts']['pulse_enabled_count'] == 0


def test_public_firm_catalog_exposes_only_source_metadata_and_no_private_connection_reads(engine, monkeypatch):
    srv, request = engine
    assert request('/api/account-connections')[0] == 401
    code, result = request('/api/prop-firm-catalog')
    assert code == 200 and len(result['firms']) == 8
    assert sum(len(firm['account_types']) for firm in result['firms']) >= 42
    assert result['topstep_configuration_phase'] == 'LATER'
    assert not any(key in result for key in ('connections','readback','credential_refs'))
    assert all(firm['execution_authorized'] is False for firm in result['firms'])


def test_browser_all_four_pnl_expiry_and_eight_firm_configuration(engine):
    import shutil
    import subprocess
    from icarus_engine.paper_pnl import validate_paper_pnl
    node, chromium = shutil.which('node'), shutil.which('chromium') or shutil.which('chromium-browser')
    if not node or not chromium or subprocess.run([node,'-e',"require.resolve('playwright')"],capture_output=True).returncode:
        pytest.skip('optional browser presentation environment unavailable')
    srv, _ = engine
    base = srv.command_centers.snapshot()
    now = int(time.time())
    pnl = validate_paper_pnl([dict(id=f'cc{i}',currency='USD',runtime_available=True,
        snapshot_ts=now,realized_pnl=10*i,open_pnl=i,open_positions=1,oldest_open_mark_ts=now)
        for i in range(1,5)],as_of_ts=now)
    payloads = {row['id']:dict(mode='concurrent_paper',profile=dict(row,runtime_available=True),paper_pnl=pnl,
        aggregate=pnl['aggregate'],accounting={'complete':True},available_assets=[],input_meta=[]) for row in base['profiles']}
    script = r'''
const assert=require('node:assert/strict'),{chromium}=require('playwright');
const payloads=JSON.parse(process.argv[3]);let browser;
(async()=>{
 browser=await chromium.launch({executablePath:process.argv[2],headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900}});page.setDefaultTimeout(8000);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/command-centers/cc*',async route=>{
  const key=new URL(route.request().url()).pathname.split('/').at(-1);
  if(payloads[key])await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(payloads[key])});else await route.continue();
 });
 for(const id of ['cc1','cc2','cc3','cc4']){
  await page.goto(process.argv[1]+'/dashboards/'+id);
  await page.waitForFunction(()=>document.querySelector('#all-total').textContent.includes('110.00'));
  assert.match(await page.locator('#all-realized').textContent(),/100.00/);
  assert.match(await page.locator('#all-open').textContent(),/10.00/);
  await page.waitForFunction(()=>document.querySelector('#corpus-sources').textContent.includes('all ten warmed in all four workspaces'));
  assert.match(await page.locator('#corpus-sources').textContent(),/Missing archived micros: MNG, MHG, M6E, MJY, M6B, M6A/);
  await page.waitForFunction(()=>document.querySelector('#provider-context')?.textContent.includes('25 unique numeric statistics consumed'));
  const provider=await page.locator('#provider-context').textContent();
  assert.match(provider,/132,554 upstream rows reported/);
  assert.match(provider,/Raw source rows read by this context: 0/);
  assert.match(provider,new RegExp(id.toUpperCase()+': 25 numeric reads and 14 provider-status reads'));
  assert.match(provider,/unusual_whales: BLOCKED/);
  assert.match(provider,/111 historical fallback rows/);
  assert.equal(await page.locator('#provider-context table tr').count(),6);
  assert.match(await page.locator('#provider-context table').textContent(),/92\.75882111436948/);
 }
 await page.setViewportSize({width:390,height:844});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Provider statistics must fit the mobile viewport');
 await page.setViewportSize({width:1280,height:900});
 // Browser time moves, the provider remains untouched, and cached totals expire.
 await page.clock.install({time:new Date(payloads.cc4.paper_pnl.as_of_ts*1000)});
 await page.clock.runFor(92000);
 await page.waitForFunction(()=>document.querySelector('#all-total').textContent==='Unavailable');
 assert.equal(await page.locator('#own-open').textContent(),'Unavailable');
 await page.clock.pauseAt(new Date((payloads.cc4.paper_pnl.as_of_ts+93)*1000));
 await page.goto(process.argv[1]+'/connections');
 await page.waitForFunction(()=>document.querySelectorAll('#firm-catalog option').length===9);
 assert.equal(await page.locator('section[aria-label="Eight researched prop firms"] details').count(),8);
 assert.equal(await page.locator('option[value="projectx_topstep"]').evaluate(e=>e.disabled && e.hasAttribute('disabled')),true);
 for(const [index,id] of ['apex','lucid','myfundedfutures','goat','tradeify','takeprofittrader','earn2trade','bulenox'].entries()){
  await page.locator('#firm-catalog').selectOption(id);
  assert.equal(await page.locator('select[name="platform"]').inputValue(),'manual_inventory');
  assert.ok(await page.locator('#firm-program option').count()>0);
  assert.ok(await page.locator('#firm-stage option').count()>0);
  if(id==='bulenox'){assert.ok(await page.locator('#firm-variant option').count()>1);await page.locator('#firm-variant').selectOption('variant #1');assert.match(await page.locator('input[name="program"]').inputValue(),/variant #1/);}
  await page.locator('input[name="id"]').fill('local_'+index);
  await page.locator('input[name="owner_token"]').fill('owner-test');
  await page.getByRole('button',{name:'Save account configuration'}).click();
  await page.waitForFunction(id=>document.querySelector('main#connections [role="status"]').textContent.includes('Saved '+id+': INVENTORY_ONLY'),'local_'+index);
 }
 await page.setViewportSize({width:390,height:844});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 assert.deepEqual(errors,[]);
 await page.evaluate(()=>scrollTo(0,0));
 await page.screenshot({path:'/workspace/scratch/four-workspace-connections-mobile.png'});
 await browser.close();
})().catch(async e=>{console.error(e);await browser?.close();process.exitCode=1;});
'''
    result = subprocess.run([node,'-e',script,f'http://127.0.0.1:{srv.server_port}',chromium,json.dumps(payloads)],
        capture_output=True,text=True,timeout=65)
    assert result.returncode == 0, result.stdout + result.stderr


def test_expansion_receipt_api_is_pinned_metadata_and_ignores_user_path(engine, monkeypatch):
    called = Mock(return_value={"status":"HISTORICAL_EXPANSION_CONSUMPTION_VERIFIED","execution_authorized":False})
    monkeypatch.setitem(sys.modules,"icarus_engine.corpus_expansion",types.SimpleNamespace(snapshot=called))
    code, result = engine[1]("/api/corpus-expansion?path=/etc/passwd&now_ns=1")
    assert code == 200
    assert result["status"] == "HISTORICAL_EXPANSION_CONSUMPTION_VERIFIED"
    called.assert_called_once_with()


def test_provider_context_readonly_route_exposes_actual_consumption_and_ignores_query(engine):
    status, result = engine[1]('/api/provider-corpus?path=/etc/passwd&now_ns=1')
    assert status == 200
    assert result['status'] == 'HISTORICAL_CONTEXT_CONSUMED'
    assert result['summary']['source_rows_reported'] == 132554
    assert result['summary']['unique_numeric_values_consumed'] == 25
    assert result['summary']['raw_rows_consumed'] == 0
    assert set(result['workspaces']) == {'cc1', 'cc2', 'cc3', 'cc4'}
    assert {row['consumer_id'] for row in result['read_receipts']} == {'quality','research','cc1','cc2','cc3','cc4'}
    assert result['workspaces']['cc2']['features'][0]['statistics']['mean'] is not None
    assert result['execution_authorized'] is False
    assert result['point_in_time_qualified'] is False
    assert engine[1]('/api/provider-corpus', method='POST', body={'execute': True})[0] in (404, 405)
