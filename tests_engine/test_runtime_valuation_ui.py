"""Runtime observations stay independent of fail-closed paper valuation."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

import pytest

from icarus_engine.paper_pnl import validate_paper_pnl


pytestmark = pytest.mark.skipif(shutil.which('node') is None, reason='optional Node unavailable')


def snapshot(*, incomplete=True, stale_runner=False):
    now = int(time.time())
    profiles = [dict(id=f'cc{i}', name=f'Ledger {i}', runtime_available=True,
        status=dict(now=now, view_stale=stale_runner, all_warm=not incomplete, paused=False,
            positions=1, assets=[dict(symbol='NQ', warm=not incomplete, position=1,
                price_age=1, open_profit=777, live_profit=888, view_stale=stale_runner)]),
        feed=dict(status='warming' if incomplete else 'healthy', healthy_assets=0 if incomplete else 1, total_assets=1))
        for i in range(1, 5)]
    ledger = validate_paper_pnl([dict(id=p['id'], currency='USD', runtime_available=True,
        snapshot_ts=now, realized_pnl=10, open_pnl=None if incomplete else 2,
        open_positions=1, oldest_open_mark_ts=now) for p in profiles], as_of_ts=now)
    return dict(mode='concurrent_paper', paper_only=True, execution_authorized=False,
        profiles=profiles, paper_pnl=ledger, connections=dict(feeds=[dict(id='yahoo', label='Yahoo',
        status='warming', detail='Paper runners warming')], adapters=[dict(id='local-paper',
        label='Local paper', configured=True, connected=True, execution_authorized=False)]))


def run_ui(data, assertions):
    script = r'''
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const elements=new Map();
for(const id of ['#combinedPaperPnl','#paperAggregate','#paperWorkspaceTabs','#paperConnections','#paperWorkspaceRuntime'])
 elements.set(id,{textContent:'',innerHTML:'',className:'',querySelector:()=>null});
const context={payload:JSON.parse(process.argv[2]),document:{querySelector:s=>elements.get(s)||null,
 addEventListener:()=>{},querySelectorAll:()=>[],activeElement:null},setInterval:()=>{},
 IcarusClient:{context:{id:'cc1'}}};
vm.createContext(context);
for(const file of ['paper-pnl-ui.js','command-centers-ui.js'])vm.runInContext(fs.readFileSync(process.argv[1]+'/'+file,'utf8'),context);
vm.runInContext('paperWorkspaces=payload;paperSetHeader(payload);renderPaperLiveSections()',context);
const profile=()=>vm.runInContext('paperProfileHtml(payload.profiles[0])',context);
const runtime=()=>elements.get('#paperWorkspaceRuntime').innerHTML;
const aggregate=()=>elements.get('#paperAggregate').innerHTML;
const connections=()=>elements.get('#paperConnections').innerHTML;
'''+assertions
    result = subprocess.run([shutil.which('node'), '-e', script,
        str(Path(__file__).resolve().parents[1]/'icarus_engine'), json.dumps(data)],
        capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout+result.stderr


def test_warming_runtime_and_feed_survive_incomplete_valuation_and_stale_runner_views():
    run_ui(snapshot(stale_runner=True), r'''
assert.doesNotMatch(profile(),/Runtime unavailable|Feed unavailable/);
assert.match(profile(),/Warming/);assert.match(profile(),/snapshot stale/i);
assert.match(profile(),/Feed warming 0\/1/);assert.match(profile(),/aria-current="page"/);
assert.match(runtime(),/Independent paper runners/);assert.match(runtime(),/data-paper-pause="cc1"/);
assert.match(runtime(),/data-paper-flatten="cc1"/);assert.doesNotMatch(runtime(),/777\.00|888\.00/);
assert.match(runtime(),/valuation incomplete/i);assert.match(aggregate(),/valuation incomplete/i);
assert.match(aggregate(),/open marks unavailable/i);assert.doesNotMatch(aggregate(),/updated engine server/);
assert.match(connections(),/Yahoo/);assert.match(connections(),/warming/);assert.match(connections(),/no live arming/);
context.IcarusClient.context.id='cc2';vm.runInContext('renderPaperLiveSections()',context);
assert.match(runtime(),/data-paper-pause="cc2"/);assert.doesNotMatch(runtime(),/data-paper-pause="cc1"/);
context.IcarusClient.context.id='main';vm.runInContext('renderPaperWorkspaces()',context);
assert.doesNotMatch(vm.runInContext('paperRuntimeHtml(payload.profiles[0])',context),/data-paper-pause|data-paper-flatten/);
''')


def test_malformed_accounting_withholds_money_without_hiding_runtime_or_feed():
    data = snapshot(incomplete=False)
    data['paper_pnl']['profiles'][0]['total_pnl'] = 999
    run_ui(data, r'''
assert.equal(vm.runInContext('IcarusPaperPnl.read(payload)',context),null);
assert.match(profile(),/Runners ready/);assert.match(profile(),/Feed healthy/);
assert.match(runtime(),/Independent paper runners/);assert.doesNotMatch(runtime(),/777\.00|888\.00|999\.00/);
assert.match(aggregate(),/invalid accounting evidence/i);assert.match(connections(),/Yahoo/);
assert.equal(elements.get('#combinedPaperPnl').textContent,'—');
''')


def test_expired_receipt_withholds_runtime_feed_controls_and_amounts():
    data = snapshot(incomplete=False)
    data['paper_pnl']['as_of_ts'] -= 91
    for profile in data['profiles']:
        profile['status']['now'] -= 91
    run_ui(data, r'''
assert.match(profile(),/snapshot stale/i);assert.doesNotMatch(profile(),/Runners ready|Feed healthy/);
assert.doesNotMatch(runtime(),/data-paper-pause|data-paper-flatten|777\.00|888\.00/);
assert.match(runtime(),/stale/i);assert.match(aggregate(),/snapshot stale/i);
assert.doesNotMatch(connections(),/Paper runners warming/);
assert.equal(elements.get('#combinedPaperPnl').textContent,'—');
''')


def test_valid_complete_valuation_retains_money_and_selected_paper_controls():
    run_ui(snapshot(incomplete=False), r'''
assert.match(profile(),/Runners ready/);assert.match(profile(),/12\.00/);
assert.match(runtime(),/data-paper-pause="cc1"/);assert.match(aggregate(),/48\.00/);
assert.match(connections(),/no live arming/);
assert.match(elements.get('#combinedPaperPnl').textContent,/48\.00/);
''')


def test_missing_accounting_uses_runtime_receipt_without_inventing_money():
    data = snapshot(incomplete=False)
    del data['paper_pnl']
    run_ui(data, r'''
assert.match(profile(),/Runners ready/);assert.match(profile(),/Feed healthy/);
assert.match(runtime(),/data-paper-pause="cc1"/);assert.match(aggregate(),/missing or invalid accounting evidence/);
assert.doesNotMatch(runtime(),/777\.00|888\.00|12\.00/);
''')


@pytest.mark.parametrize('kind', ['missing_runtime', 'busy_snapshot', 'live_authority', 'bad_identity'])
def test_observation_guards_do_not_turn_missing_or_unsafe_runtime_into_ready(kind):
    data = snapshot()
    if kind == 'missing_runtime':
        data['profiles'][0]['runtime_available'] = False
        expected = 'Runtime unavailable'
    elif kind == 'busy_snapshot':
        data['profiles'][0]['status']['snapshot_unavailable'] = True
        expected = 'Runtime running · observations unavailable'
    elif kind == 'live_authority':
        data['execution_authorized'] = True
        expected = 'Snapshot stale or unavailable'
    else:
        data['profiles'][0]['id'] = 'cc2'
        expected = 'Snapshot stale or unavailable'
    run_ui(data, r'''
assert.match(profile(),new RegExp('''+json.dumps(expected)+r'''));
assert.doesNotMatch(runtime(),/data-paper-pause|data-paper-flatten|Independent paper runners/);
''')


def test_browser_renders_warming_ledger_and_expires_snapshot_without_navigation():
    playwright = pytest.importorskip('playwright.sync_api')
    root = Path(__file__).resolve().parents[1]/'icarus_engine'
    with playwright.sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(headless=True, executable_path=os.environ.get('ICARUS_BROWSER_BINARY') or shutil.which('chromium'))
        except playwright.Error as error:
            if os.environ.get('ICARUS_REQUIRE_WORKSPACE_BROWSER') == '1':
                raise
            pytest.skip('optional Chromium unavailable: '+str(error).splitlines()[0])
        try:
            page = browser.new_page()
            page.set_content('<span id="combinedPaperPnl"></span><main id="deck"></main>')
            page.evaluate("globalThis.IcarusClient={context:{id:'cc1'}}")
            for name in ('paper-pnl-ui.js', 'command-centers-ui.js'):
                page.add_script_tag(content=(root/name).read_text(encoding='utf-8'))
            page.evaluate("data=>{paperWorkspaces=data;document.querySelector('#deck').innerHTML=paperWorkspacesHtml();renderPaperWorkspaces();paperSetHeader(data)}", snapshot(stale_runner=True))
            assert 'Warming · runner snapshot stale' in page.locator('[data-paper-profile="cc1"]').inner_text()
            assert 'Feed warming 0/1' in page.locator('[data-paper-profile="cc1"]').inner_text()
            assert page.locator('[data-paper-pause="cc1"]').count() == 1
            assert page.locator('[data-paper-pause="cc2"]').count() == 0
            assert 'valuation incomplete' in page.locator('#paperAggregate').inner_text()
            assert page.locator('#combinedPaperPnl').inner_text() == '—'
            page.evaluate('paperWorkspaces.paper_pnl.as_of_ts-=91;paperWorkspaces.profiles.forEach(p=>p.status.now-=91);paperExpireObservations()')
            assert 'Snapshot stale' in page.locator('[data-paper-profile="cc1"]').inner_text()
            assert page.locator('[data-paper-pause]').count() == 0
            assert 'snapshot stale' in page.locator('#paperAggregate').inner_text()
        finally:
            browser.close()


def test_paused_entries_remain_explicit_when_runner_market_view_is_stale():
    data = snapshot(stale_runner=True)
    data['profiles'][0]['status'].update(all_warm=True, paused=True)
    run_ui(data, r'''
assert.match(profile(),/Entries paused · runner snapshot stale/);
assert.match(runtime(),/Entries paused · runner snapshot stale/);
assert.match(runtime(),/Resume entries/);
''')


def test_stale_accounting_does_not_hide_fresh_runtime_observations():
    data = snapshot(incomplete=False)
    data['paper_pnl']['as_of_ts'] -= 91
    run_ui(data, r'''
assert.match(profile(),/Runners ready/);assert.match(profile(),/Feed healthy/);
assert.match(runtime(),/data-paper-pause="cc1"/);assert.match(connections(),/Yahoo/);
assert.match(aggregate(),/accounting snapshot stale/i);
assert.equal(elements.get('#combinedPaperPnl').textContent,'—');
assert.doesNotMatch(runtime(),/777\.00|888\.00|12\.00/);
''')
