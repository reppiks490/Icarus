"""Common renderer integration before enabling it on production CC routes."""
import json
import re
import shutil
from contextlib import contextmanager

import pytest

from tests_engine.test_workspace_api import _job_tape, workspace_http  # noqa: F401


@contextmanager
def common_page(workspace_http, scope="cc1", token="api-owner"):
    playwright = pytest.importorskip("playwright.sync_api")
    server, _, request = workspace_http
    base = f"http://127.0.0.1:{server.server_port}"
    code, html, _ = request("/", raw=True)
    assert code == 200
    # Test-only rendering of the existing main HTML with a server-constant
    # identity. The actual CC route stays on its rollback renderer until all
    # core, panel and parity dependencies pass.
    context = {"id": scope, "capabilities": {"paper_only": scope != "main",
               "execution_authorized": False, "scoped_trading": scope != "main",
               "parent_runtime_panels": scope == "main"}}
    html = re.sub(r"const icContext=.*?;Object.freeze", "const icContext=" + json.dumps(context) + ";Object.freeze", html, count=1)
    path = "/" if scope == "main" else "/dashboards/" + scope
    with playwright.sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(headless=True, executable_path=shutil.which("chromium"))
        except playwright.Error as error:
            pytest.skip("optional Chromium unavailable: " + str(error).splitlines()[0])
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
            page.add_init_script("localStorage.setItem('icarus-engine-token'," + json.dumps(token) + ");sessionStorage.setItem('icarus-intro-seen','1')")
            def route_request(route):
                if route.request.url == base + path and route.request.is_navigation_request():
                    route.fulfill(status=200, content_type="text/html", body=html)
                elif route.request.url.startswith(base + "/"):
                    route.continue_()
                else:
                    route.abort()
            page.route("**/*", route_request)
            page.goto(base + path, wait_until="load")
            page.evaluate("async()=>{await dashboardReady}")
            yield page, base
        finally:
            browser.close()


@pytest.mark.parametrize("scope,price", [("main", 900), ("cc1", 100), ("cc2", 200), ("cc3", 300), ("cc4", 400)])
def test_common_core_uses_selected_status_chart_and_trade_source(workspace_http, scope, price):
    with common_page(workspace_http, scope) as (page, _):
        state = page.evaluate("""async()=>{
          await refresh(); await refreshTrades('NQ'); await loadChart('NQ',80,null);
          return {id:IcarusClient.context.id,price:last?.assets.find(a=>a.symbol==='NQ')?.price,
            chart:charts.NQ80?.bars[0]?.[4],trades:tradesCache.NQ,
            shown:document.querySelector('.asset[data-sym="NQ"] .px')?.textContent};
        }""")
        assert state["id"] == scope and state.get("price") == price, state
        assert state["chart"] == price, state
        assert ("main-entry" if scope == "main" else scope + "-entry") in json.dumps(state["trades"])
        assert float(state["shown"].replace(",", "")) == price, state


def test_common_failed_status_clears_observations_and_retains_editor_draft(workspace_http):
    with common_page(workspace_http) as (page, base):
        page.evaluate("async()=>{await refresh();await refreshTrades('NQ');await loadChart('NQ',80,null);setView('inputs')}")
        page.wait_for_function("()=>inState.asset !== null")
        page.evaluate("inState.edits.tp1_pts=77")
        revision = page.evaluate("inState.revision")
        page.route(base + "/api/command-centers/cc1/status", lambda route: route.fulfill(
            status=503, content_type="application/json", body='{"workspace_id":"cc1","detail":"selected runtime unavailable"}'))
        state = page.evaluate("""async()=>{await refresh();return {last,charts,tradesCache,
          edit:inState.edits.tp1_pts,revision:inState.revision,visible:document.querySelector('#inGroups')?.textContent}}""")
        assert state["last"] is None and state["charts"] == {} and state["tradesCache"] == {}, state
        assert state["edit"] == 77 and state["revision"] == revision
        assert state["visible"], state


def test_common_input_draft_conflict_preserves_edits_and_original_revision(workspace_http):
    _, _, request = workspace_http
    with common_page(workspace_http) as (page, _):
        page.evaluate("async()=>{await refresh();setView('inputs')}")
        page.wait_for_function("()=>inState.asset==='NQ'")
        page.evaluate("inState.edits.tp1_pts=77")
        assert request("/admin/command-centers/cc1/assets/NQ/config", body={"inputs":{"tp1_pts":12},"expected_revision":0})[0] == 200
        state = page.evaluate("""async()=>{await refresh();const draft=inState;
          const result=await admin('/admin/inputs/async',{asset:'NQ',values:draft.edits,chart:{},persist:true},false,draft);
          return {result,edit:inState.edits.tp1_pts,revision:inState.revision,toast:document.querySelector('#toast').textContent};}""")
        assert state["result"] is None and state["edit"] == 77 and state["revision"] == 0, state
        assert "revision" in state["toast"].lower(), state
        assert request("/api/command-centers/cc1/inputs/NQ")[1]["base"]["tp1_pts"] == 12


def test_common_viewer_controls_disabled_and_server_rejects_bypass(workspace_http):
    server, parent, request = workspace_http
    viewer = request("/admin/access/add", body={"label":"browser-viewer"})[1]["user"]["token"]
    with common_page(workspace_http, token=viewer) as (page, _):
        page.evaluate("async()=>{await refresh();setView('asset:NQ')}")
        assert page.locator('[data-cmd="pause"]').is_disabled()
        result = page.evaluate("""async()=>{try{await IcarusClient.control('pause','NQ');return 'unexpected';}
          catch(error){return error.status;}}""")
        assert result == 403
        page.evaluate("setView('inputs')")
        page.wait_for_function("()=>inState.asset==='NQ'")
        assert page.locator('#inApply').is_disabled()
        page.evaluate("setView('command-centers')")
        page.wait_for_selector('[data-paper-pause="cc1"]')
        assert page.locator('[data-paper-pause="cc1"]').is_disabled()
        assert not server.command_centers.portfolios['cc1'].runners['NQ'].paused and not parent.runners['NQ'].paused


def test_common_config_acceptance_and_failure_keep_draft_until_commit(workspace_http):
    with common_page(workspace_http) as (page, base):
        page.evaluate("async()=>{await refresh();setView('inputs')}")
        page.wait_for_function("()=>inState.asset==='NQ'")
        page.evaluate("inState.edits.tp1_pts=77")
        identity = {"workspace_id":"cc1", "config_revision":0, "paper_only":True, "execution_authorized":False}
        page.route(base + "/admin/command-centers/cc1/assets/NQ/config/async", lambda route: route.fulfill(
            status=202, content_type="application/json", body=json.dumps({**identity,"job":"held-config"})))
        state = {"status":"queued"}
        page.route(base + "/api/command-centers/cc1/jobs/held-config", lambda route: route.fulfill(
            status=200, content_type="application/json", body=json.dumps({**identity,"id":"held-config","kind":"config",**state})))
        page.locator('#inApply').click()
        page.wait_for_function("()=>inState.pending===true")
        assert page.evaluate("inState.edits.tp1_pts") == 77
        assert page.locator('#inReset').is_disabled()
        state.update(status="error", error="fixture commit refused")
        page.wait_for_function("()=>inState.pending===false")
        assert page.evaluate("({edit:inState.edits.tp1_pts,revision:inState.revision})") == {"edit":77,"revision":0}
        assert not page.locator('#inApply').is_disabled()


def test_common_input_submission_reserves_draft_before_http_admission(workspace_http):
    with common_page(workspace_http) as (page,base):
        page.evaluate("async()=>{await refresh();setView('inputs')}")
        page.wait_for_function("()=>inState.asset==='NQ'")
        page.evaluate("inState.edits.tp1_pts=77")
        held=[]
        page.route(base+'/admin/command-centers/cc1/assets/NQ/config/async',lambda route:held.append(route))
        page.locator('#inApply').click()
        assert page.locator('#inAsset').is_disabled()
        assert page.locator('#inReset').is_disabled()
        assert page.evaluate('inState.edits.tp1_pts')==77


def test_common_controls_csv_and_ledger_navigation_keep_identity(workspace_http):
    server, parent, _ = workspace_http
    with common_page(workspace_http, "cc2") as (page, _):
        page.evaluate("async()=>{await refresh();await admin('/admin/pause',{asset:'NQ'})}")
        assert server.command_centers.portfolios['cc2'].runners['NQ'].paused
        assert not parent.runners['NQ'].paused
        assert all(not server.command_centers.portfolios[scope].runners['NQ'].paused for scope in ['cc1','cc3','cc4'])
        with page.expect_download() as downloading:
            page.evaluate("()=>runCommand('export','NQ')")
        download = downloading.value
        assert download.suggested_filename.startswith('cc2_NQ')
        with open(download.path()) as exported:
            csv = exported.read()
        assert 'cc2-entry' in csv and 'main-entry' not in csv and 'cc1-entry' not in csv
        page.evaluate("setView('command-centers')")
        page.wait_for_selector('a.paper-portfolio[href="/dashboards/cc3"]')
        assert page.locator('[data-paper-apply]').count() == 0
        assert page.locator('[data-paper-pause="cc1"]').count() == 0
        assert page.locator('[data-paper-pause="cc2"]').count() == 1
        page.locator('a.paper-portfolio[href="/dashboards/cc3"]').click()
        page.wait_for_url('**/dashboards/cc3')


def test_common_chart_and_trade_failure_remove_cached_observations(workspace_http):
    with common_page(workspace_http) as (page, base):
        page.evaluate("async()=>{await refresh();await refreshTrades('NQ');await loadChart('NQ',80,null)}")
        assert page.evaluate("Boolean(charts.NQ80&&tradesCache.NQ?.length)")
        for resource in ['chart/NQ*','trades/NQ*']:
            page.route(base+'/api/command-centers/cc1/'+resource, lambda route: route.fulfill(
                status=503,content_type='application/json',body='{"workspace_id":"cc1","detail":"fixture unavailable"}'))
        state=page.evaluate("""async()=>{await refreshTrades('NQ');await loadChart('NQ',80,null);
          return {chart:charts.NQ80??null,trades:tradesCache.NQ??null,error:tradeErrors.NQ}}""")
        assert state['chart'] is None and state['trades'] is None and 'fixture unavailable' in state['error'],state


def test_common_late_failed_refresh_cannot_erase_new_selected_observation(workspace_http):
    with common_page(workspace_http) as (page, base):
        page.evaluate("async()=>{await refresh()}")
        held=[]
        page.route(base+'/api/command-centers/cc1/status',lambda route:held.append(route))
        page.evaluate("()=>{window.olderRefresh=refresh();return null}")
        for _ in range(20):
            if held:break
            page.wait_for_timeout(20)
        assert len(held)==1
        page.unroute(base+'/api/command-centers/cc1/status')
        page.evaluate("async()=>{await refresh()}")
        held[0].fulfill(status=503,content_type='application/json',body='{"workspace_id":"cc1","detail":"older failure"}')
        page.evaluate("async()=>{await window.olderRefresh}")
        assert page.evaluate("last?.assets[0]?.price")==100


def test_common_backtest_job_and_csv_retain_accepted_source_revision(workspace_http):
    server, _, request=workspace_http
    _job_tape(server,'cc1')
    writes=[]
    with common_page(workspace_http) as (page,_):
        page.on('request',lambda req:writes.append(json.loads(req.post_data))
                if req.method=='POST' and req.url.endswith('/assets/NQ/backtest') else None)
        page.evaluate("async()=>{await refresh();setView('backtest')}")
        page.locator('#btPreset').select_option('')
        page.locator('#btTf').select_option('1')
        page.locator('#btRun').click()
        page.wait_for_function("()=>Boolean(BT.res)")
        assert len(writes)==1 and writes[0]['expected_revision']==0 and 'preset' not in writes[0],writes
        assert page.evaluate("({workspace:BT.res.workspace_id,revision:BT.res.config_revision})")=={'workspace':'cc1','revision':0}
        assert request('/admin/command-centers/cc1/assets/NQ/config',body={'inputs':{'tp1_pts':12},'expected_revision':0})[0]==200
        page.evaluate("async()=>{await refresh()}")
        with page.expect_download() as downloading:
            page.locator('#btExport').click()
        assert downloading.value.suggested_filename=='cc1_'+page.evaluate('BT.job')+'_trades.csv'
        with open(downloading.value.path()) as exported:
            csv=exported.read()
        comparison=page.evaluate("csv=>IcarusClient.compare(BT.job,csv)",csv)
        assert comparison['workspace_id']=='cc1' and comparison['config_revision']==0 and comparison['report']
