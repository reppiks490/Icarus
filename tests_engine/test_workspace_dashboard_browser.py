"""Actual five-route common renderer, source isolation and lifecycle acceptance."""
import json
import os
import re
import shutil
from pathlib import Path
from contextlib import contextmanager
from urllib.parse import urlparse

import pytest

from tests_engine.test_workspace_api import _job_tape, workspace_http  # noqa: F401


@pytest.mark.skipif(not shutil.which('node'), reason='optional Node unavailable')
@pytest.mark.parametrize('count,message,kind', [
    (3, '', 'historical'),
    (3, 'HTTP 429 Too Many Requests', 'active'),
    (0, '<img src=x onerror=alert(1)> feed failed', 'active'),
])
def test_asset_card_distinguishes_past_error_counts_from_current_faults(count, message, kind):
    import subprocess
    source = (Path(__file__).resolve().parents[1] / 'icarus_engine/dashboard.html').read_text(encoding='utf-8')
    implementation = source.split('/* ── asset card ── */', 1)[1].split('async function loadChart', 1)[0]
    escaping = next(line for line in source.splitlines() if line.startswith('const esc = '))
    driver = (escaping + '\nconst px=String, age=String, sgn$=String;\n' + implementation +
              '\nprocess.stdout.write(assetCard(JSON.parse(process.argv[1])));')
    asset = {'symbol': 'NQ', 'errors': count, 'last_error': message, 'warm': True,
             'bar_age': 27, 'price': 100, 'tf': 10, 'state': {}}
    result = subprocess.run([shutil.which('node'), '-e', driver, json.dumps(asset)],
                            capture_output=True, text=True, encoding='utf-8', timeout=10, check=True)
    assert f'data-asset-error="{kind}"' in result.stdout
    assert 'bar 27' in result.stdout, 'past errors must not hide current bar age'
    if kind == 'historical':
        assert '3 past errors' in result.stdout
        assert 'data-asset-error-detail' not in result.stdout
    else:
        assert 'data-asset-error-detail' in result.stdout
        assert ('&lt;img' if message.startswith('<img') else message) in result.stdout
        assert '<img' not in result.stdout


@contextmanager
def common_page(workspace_http, scope="cc1", token="api-owner", *, viewport=None):
    playwright = pytest.importorskip("playwright.sync_api")
    server, _, request = workspace_http
    base = f"http://127.0.0.1:{server.server_port}"
    path = "/" if scope == "main" else "/dashboards/" + scope
    with playwright.sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(headless=True, executable_path=os.environ.get("ICARUS_BROWSER_BINARY") or shutil.which("chromium"))
        except playwright.Error as error:
            if os.environ.get("ICARUS_REQUIRE_WORKSPACE_BROWSER")=="1":raise
            pytest.skip("optional Chromium unavailable: " + str(error).splitlines()[0])
        try:
            page = browser.new_page(viewport=viewport or {"width": 1440, "height": 1000}, reduced_motion="reduce")
            page.icarus_errors=[]
            page.on('pageerror',lambda error:page.icarus_errors.append(str(error)))
            page.add_init_script("localStorage.setItem('icarus-engine-token'," + json.dumps(token) + ");sessionStorage.setItem('icarus-intro-seen','1')")
            def route_request(route):
                if route.request.url.startswith(base + "/"):
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
        page.locator('#inRevert').click()
        page.wait_for_function('()=>inState.revision===1')
        assert page.evaluate('({value:inState.base.tp1_pts,edits:inState.edits})')=={'value':12,'edits':{}}


def test_common_unrelated_config_completion_does_not_discard_or_rebase_draft(workspace_http):
    _,_,request=workspace_http
    with common_page(workspace_http) as (page,base):
        page.evaluate("setView('inputs')")
        page.wait_for_function("()=>inState.asset==='NQ'")
        page.evaluate('inState.edits.tp1_pts=77')
        assert request('/admin/command-centers/cc1/assets/NQ/config',body={'inputs':{'tp1_pts':12},'expected_revision':0})[0]==200
        page.route(base+'/api/command-centers/cc1/jobs/external-config',lambda route:route.fulfill(
            status=200,content_type='application/json',body=json.dumps({'id':'external-config','kind':'config','workspace_id':'cc1',
            'config_revision':0,'paper_only':True,'execution_authorized':False,'status':'done','result':{'config_revision':1}})))
        page.evaluate("async()=>{await watchConfigJob('external-config','External configuration')}")
        assert page.evaluate('({value:inState.edits.tp1_pts,revision:inState.revision})')=={'value':77,'revision':0}


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


def test_common_linked_panels_never_request_parent_runtime_readers(workspace_http):
    from icarus_engine.workspace_context import SHARED_READS
    with common_page(workspace_http) as (page,_):
        reads=[]
        page.on('request',lambda req:reads.append(urlparse(req.url).path) if req.method=='GET' else None)
        for panel in ['brain','research','sources','market-data','evolution','parallax','possibility',
                      'pantheon','sibyl','apex','ascendancy','learning','chronofold','commissioning',
                      'integrity','engine-control','autopilot','system','golive','agent']:
            page.evaluate('panel=>setView(panel)',panel)
            page.wait_for_timeout(30)
        page.wait_for_timeout(150)
        parent=[path for path in reads if (path.startswith('/api/') or path=='/status/public')
                and not path.startswith('/api/command-centers/cc1/')
                and path not in SHARED_READS and not path.startswith('/api/market-history/')]
        assert not parent,parent


def test_common_commissioning_direct_post_uses_real_selected_endpoint(workspace_http):
    server,parent,request=workspace_http
    with common_page(workspace_http) as (page,_):
        held=[]
        page.route(re.compile(r'.*/(?:api/commissioning|api/command-centers/cc1/panels/commissioning).*'),lambda route:held.append(route))
        page.on('dialog',lambda dialog:dialog.dismiss())
        page.evaluate("setView('commissioning')")
        with page.expect_response(lambda res:res.request.method=='POST') as submitted:
            page.evaluate("()=>document.querySelector('#scTick').onclick()")
        assert urlparse(submitted.value.url).path=='/admin/command-centers/cc1/panels/engine-control'
        assert submitted.value.status==200
        assert submitted.value.json()['workspace_id']=='cc1'
        assert submitted.value.json()['execution_authorized'] is False
        code,data,_=request('/api/command-centers/cc1/panels/commissioning')
        assert code==200 and data['ledger']['predictions']>=1
        assert not parent.runners['NQ'].paused
        assert not server.command_centers.portfolios['cc1'].runners['NQ'].paused


def test_common_selected_panel_controls_and_shared_evidence_are_labeled(workspace_http):
    with common_page(workspace_http) as (page,base):
        held=[]
        page.route(base+'/api/command-centers/cc1/panels/engine-control',lambda route:held.append(route))
        page.evaluate("setView('engine-control')")
        assert 'CC1' in page.locator('[data-workspace-scope-note]').inner_text()
        assert page.locator('#ecRefresh').is_enabled()
        assert page.locator('#ecSyncAll').is_enabled()
        assert page.locator('#ecSyncAll').inner_text()=='Refresh workspace diagnostics'
        for route in held:
            route.fulfill(status=503,content_type='application/json',body='{"workspace_id":"cc1","detail":"unavailable"}')
        page.evaluate("setView('system')")
        assert 'Shared' in page.locator('[data-workspace-scope-note]').inner_text()


@pytest.mark.parametrize('panel,selector',[('possibility','#possibilityPanel'),('chronofold','#chronofoldPanel'),
    ('commissioning','#commissioningPanel'),('engine-control','#ecSummary')])
def test_completed_subsystem_panels_render_real_selected_responses(workspace_http,panel,selector):
    with common_page(workspace_http) as (page,_):
        with page.expect_response(lambda res:urlparse(res.url).path=='/api/command-centers/cc1/panels/'+panel) as response:
            page.evaluate('panel=>setView(panel)',panel)
        assert response.value.status==200
        assert response.value.json()['workspace_id']=='cc1'
        page.locator(selector).wait_for(state='visible')
        assert 'CC1' in page.locator('[data-workspace-scope-note]').inner_text()
        assert not page.icarus_errors


def test_completed_panel_controls_stay_read_only_for_viewer(workspace_http):
    _,_,request=workspace_http
    viewer=request('/admin/access/add',body={'label':'panel-viewer'})[1]['user']['token']
    with common_page(workspace_http,token=viewer) as (page,_):
        page.evaluate("setView('commissioning')")
        page.wait_for_function("()=>document.querySelector('#scTick')?.disabled===true")
        assert page.locator('#scRefresh').is_enabled()
    assert request('/admin/command-centers/cc1/panels/engine-control',token=viewer,
        body={'action':'commissioning.tick'},extra_headers={'X-Icarus-Config-Revision':'0'})[0]==403


@pytest.mark.parametrize('scope,profit',[('main',90),('cc1',10),('cc2',20),('cc3',30),('cc4',40)])
def test_common_persisted_performance_component_uses_selected_journal(workspace_http,scope,profit):
    server,parent,_=workspace_http
    journal=parent.journal if scope=='main' else server.command_centers.portfolios[scope].journal
    import time
    now=int(time.time())
    with journal._lock:
        journal.con.execute('INSERT INTO trades(symbol,entry_id,direction,qty,entry_price,entry_ts,exit_price,exit_ts,profit,live) VALUES(?,?,?,?,?,?,?,?,?,?)',
                            ('REMOVED',scope+'-persisted',1,1,100.0,now-60,101.0,now-1,profit,1))
        journal.con.commit()
    with common_page(workspace_http,scope) as (page,_):
        page.evaluate("setView('performance')")
        assert page.locator('#workspace-performance').count()==1
        page.wait_for_function("()=>document.querySelector('#performance-count').textContent==='1'")
        assert str(profit)+'.00' in page.locator('#performance-realized').inner_text()
        assert scope.upper() in page.locator('#performance-title').inner_text()
        assert page.locator('#performance-trades').inner_text().startswith('REMOVED')
        assert page.locator('#performance-switch option').count()==5


@pytest.mark.parametrize('scope',['main','cc1','cc2','cc3','cc4'])
def test_common_evidence_preserves_corpus_catalog_and_connections(workspace_http,monkeypatch,scope):
    monkeypatch.setattr('icarus_engine.corpus_evidence.snapshot',lambda:{
        'status':'HISTORICAL_CONSUMPTION_VERIFIED','corpora':[{
            'cache_name':'fixture_corpus','dataset_count':1,'retained_rows':100,'historical':True,
            'workspaces':{key:{'input_tag':key+'-only'} for key in ['cc1','cc2','cc3','cc4']}}]})
    with common_page(workspace_http,scope) as (page,_):
        page.evaluate("setView('evidence')")
        assert page.locator('#workspace-evidence').count()==1
        page.wait_for_function("()=>document.querySelector('#corpus-sources').textContent.includes('fixture_corpus')")
        page.wait_for_function("()=>document.querySelector('#a200-instrument').options.length===200")
        page.locator('#corpus-sources details').evaluate_all('nodes=>nodes.forEach(node=>node.open=true)')
        text=page.locator('#corpus-sources').inner_text()
        for key in ['cc1','cc2','cc3','cc4']:
            assert (key+'-only' in text)==(scope==key),text
        assert page.locator('#workspace-evidence a[href="/dashboards/connections"]').count()==1
        assert page.locator('#a200-rows tr').count()==200


def test_common_equity_history_is_explicit_and_retains_receipt_authority(workspace_http):
    from urllib.parse import parse_qs,unquote
    with common_page(workspace_http) as (page,_):
        reads=[];mode={'wrong':False}
        def history(route):
            url=urlparse(route.request.url);instrument=unquote(url.path.rsplit('/',1)[1]);query=parse_qs(url.query)
            start=int(query['start_ts'][0]);reads.append(instrument)
            route.fulfill(status=200,content_type='application/json',body=json.dumps({
                'instrument':{'instrument_id':instrument},'provider':'fmp' if mode['wrong'] else 'yahoo',
                'execution_authorized':False,'pulse_enabled':False,'qualification':'UNQUALIFIED',
                'receipt':{'instrument_id':instrument,'provider':'yahoo','receipt_id':'b'*64,'checksum_sha256':'a'*64},
                'bars':[{'ts':start+i*3600,'o':100,'h':102,'l':99,'c':100+i,'v':10} for i in range(2)]}))
        page.route('**/api/market-history/**',history)
        page.evaluate("setView('evidence')")
        page.wait_for_function("()=>document.querySelector('#a200-instrument').options.length===200")
        assert reads==[]
        page.locator('#evidenceReadHistory').click()
        page.wait_for_function("()=>document.querySelector('#a200-receipt').textContent.includes('aaaaaaaa')")
        assert len(reads)==1
        receipt=json.loads(page.locator('#a200-receipt').inner_text())
        assert receipt['instrument_id']==reads[0] and receipt['provider']=='yahoo'
        assert receipt['pulse_enabled'] is False and receipt['execution_authorized'] is False
        mode['wrong']=True
        page.locator('#evidenceReadHistory').click()
        page.wait_for_function("()=>document.querySelector('#a200-history-note').textContent.includes('identity or authority')")
        assert 'aaaaaaaa' not in page.locator('#a200-receipt').inner_text()


def test_common_equity_history_requires_owner_both_in_ui_and_server(workspace_http):
    _,_,request=workspace_http
    viewer=request('/admin/access/add',body={'label':'shared-evidence-viewer'})[1]['user']['token']
    with common_page(workspace_http,token=viewer) as (page,_):
        page.evaluate("setView('evidence')")
        page.wait_for_function("()=>document.querySelector('#a200-instrument').options.length===200")
        assert page.locator('#evidenceReadHistory').is_disabled()
    assert request('/api/market-history/not-a-catalog-id?start_ts=1&end_ts=60&interval_seconds=60',token=viewer)[0]==403


def test_actual_five_dashboard_routes_share_main_source_and_bind_server_identity(workspace_http):
    _,_,request=workspace_http
    baseline=None
    for scope in ['main','cc1','cc2','cc3','cc4']:
        code,html,_=request('/' if scope=='main' else '/dashboards/'+scope,raw=True)
        assert code==200
        match=re.search(r'const icContext=(.*?);Object.freeze',html)
        assert match,scope
        assert json.loads(match.group(1))['id']==scope
        normalized=re.sub(r'<script id="icarus-workspace-bootstrap">.*?</script>','',html,flags=re.S)
        if baseline is None:baseline=normalized
        assert normalized==baseline,scope
    code,connections,_=request('/dashboards/connections',raw=True)
    assert code==200 and 'src="/workspace-dashboard.js"' in connections


@pytest.mark.parametrize('scope,price',[('main',900),('cc1',100),('cc2',200),('cc3',300),('cc4',400)])
@pytest.mark.parametrize('viewport',[{'width':390,'height':844},{'width':1440,'height':1000}])
def test_actual_common_dashboard_desktop_mobile_components_and_source(workspace_http,scope,price,viewport,tmp_path):
    with common_page(workspace_http,scope,viewport=viewport) as (page,_):
        assert page.locator('#workspaceIdentity').inner_text()==scope.upper()
        assert page.evaluate("last.assets.find(a=>a.symbol==='NQ').price")==price
        views=page.locator('#tabs [data-v]').evaluate_all('nodes=>nodes.map(node=>node.dataset.v)')
        assert {'overview','performance','evidence','inputs','backtest','market-data','command-centers','brain','commissioning'}.issubset(views)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        output=Path(os.environ.get('ICARUS_BROWSER_OUTPUT',str(tmp_path)));output.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(output/('common-'+scope+'-'+str(viewport['width'])+'.png')),full_page=True)
        for panel,selector in [('performance','#workspace-performance'),('evidence','#workspace-evidence'),('inputs','#inGroups'),('market-data','#mdHealth')]:
            page.evaluate('panel=>setView(panel)',panel)
            assert page.locator(selector).count()==1,(scope,panel)
        page.wait_for_function("()=>document.querySelector('#mdHealth').textContent.includes('UNOBSERVED')")
        if scope!='main':assert page.locator('#mdSnapshot').is_disabled()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert not page.icarus_errors,page.icarus_errors


def test_actual_query_state_and_full_navigation_cannot_reselect_workspace(workspace_http):
    with common_page(workspace_http,'cc1') as (page,base):
        page.goto(base+'/dashboards/cc1?workspace=cc4&profile=cc4#overview',wait_until='load')
        page.evaluate('async()=>{await dashboardReady}')
        assert page.evaluate('IcarusClient.context.id')=='cc1'
        assert page.locator('#workspaceIdentity').inner_text()=='CC1'
        page.goto(base+'/dashboards/cc1?asset=NQ',wait_until='load')
        page.evaluate('async()=>{await dashboardReady}')
        assert page.locator('#tabs a').get_attribute('href')=='/dashboards/cc1'
        page.goto(base+'/dashboards/cc1#command-centers',wait_until='load')
        page.evaluate('async()=>{await dashboardReady}')
        page.locator('a.paper-portfolio[href="/dashboards/cc3"]').click()
        page.wait_for_url('**/dashboards/cc3')
        page.evaluate('async()=>{await dashboardReady}')
        assert page.evaluate('IcarusClient.context.id')=='cc3'
        assert page.evaluate("last.assets.find(a=>a.symbol==='NQ').price")==300


@pytest.mark.parametrize("scope", ["main", "cc1"])
def test_automatic_poll_does_not_discard_inflight_manual_status(workspace_http, scope):
    # The former guard tracked only automatic polls, so a tick could obsolete
    # a still-valid explicit refresh even while its response was in flight.
    with common_page(workspace_http, scope) as (page, base):
        page.evaluate("async()=>{await refresh()}")
        path = "/status/public" if scope == "main" else "/api/command-centers/cc1/status"
        held = []
        page.route(base + path, lambda route: held.append(route))
        page.evaluate("()=>{window.explicitStatus=refresh();return null}")
        page.wait_for_timeout(150)
        assert len(held) == 1
        page.evaluate("()=>{void pollStatus();return null}")
        page.wait_for_timeout(150)
        assert len(held) == 1, "automatic poll replaced an unresolved explicit refresh"
        held[0].continue_()
        page.evaluate("async()=>{await window.explicitStatus}")
        assert page.evaluate("last?.assets.find(a=>a.symbol==='NQ')?.price") == (900 if scope == "main" else 100)
        assert page.icarus_errors == []


def test_status_deadline_clears_then_later_success_restores_observation(workspace_http):
    with common_page(workspace_http) as (page, base):
        page.evaluate("async()=>{await refresh();await refreshTrades('NQ');await loadChart('NQ',80,null)}")
        held = []
        path = base + "/api/command-centers/cc1/status"
        page.route(path, lambda route: held.append(route))
        page.evaluate("()=>{window.expiredStatus=refresh();return null}")
        page.wait_for_function("()=>last===null", timeout=15000)
        page.evaluate("async()=>{await window.expiredStatus}")
        assert page.evaluate("Object.keys(charts).length===0 && Object.keys(tradesCache).length===0")
        page.unroute(path)
        page.evaluate("async()=>{await refresh()}")
        assert page.evaluate("last?.assets[0]?.price") == 100
        assert page.icarus_errors == []


def test_shared_access_keeps_typing_across_runtime_polls_and_reloads_explicitly(workspace_http):
    with common_page(workspace_http) as (page, _):
        page.evaluate("setView('access')")
        page.wait_for_selector('#accessLabel')
        assert page.locator('#accessLabel').is_enabled()
        page.locator('#accessLabel').fill('owner-local-viewer-draft')
        page.evaluate("async()=>{window.savedAccessInput=document.querySelector('#accessLabel');await refresh();await refresh()}")
        assert page.locator('#accessLabel').input_value() == 'owner-local-viewer-draft'
        assert page.evaluate("document.querySelector('#accessLabel')===window.savedAccessInput")
        assert 'shared' in page.locator('[data-workspace-scope-note]').inner_text().lower()
        page.locator('#accessRefresh').click()
        page.wait_for_function("()=>document.querySelector('#accessLabel')!==window.savedAccessInput")
        assert page.locator('#accessLabel').input_value() == ''
        assert page.icarus_errors == []


@pytest.mark.parametrize("panel,selector", [
    ("parallax", "#parallaxPanel"), ("pantheon", "#pantheonPanel"),
    ("sibyl", "#sibylPanel"), ("apex", "#apexPanel"),
    ("brain", "#brainPanel"), ("research", "#researchStatus"),
    ("learning", "#learningPanel"), ("autopilot", "#apStatus"),
    ("ascendancy", "#ascendancyBody"), ("golive", "#goliveCard"),
])
def test_native_read_only_panels_render_without_arming_actions(workspace_http, panel, selector):
    with common_page(workspace_http) as (page, _):
        page.evaluate("panel=>setView(panel)", panel)
        page.wait_for_selector(selector)
        page.wait_for_function("selector=>{const el=document.querySelector(selector);return el&& !/loading[.\u2026]|Loading|waiting for.*state/i.test(el.innerText)}", arg=selector)
        assert 'read-only' in page.locator('[data-workspace-scope-note]').inner_text()
        for action in ['#apStart','#apStep','#learningScan','#learningTick','#learningToggle','#rsRun','#rsAnalyse']:
            if page.locator(action).count():
                assert page.locator(action).is_disabled()
        assert page.icarus_errors == []
