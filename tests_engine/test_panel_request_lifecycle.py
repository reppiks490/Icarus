"""Slow panel reads must finish without multiplying work or polling manual views."""
import pytest
from tests_engine.test_workspace_client import run_js
from tests_engine.test_workspace_dashboard_browser import common_page
from tests_engine.test_workspace_api import workspace_http  # noqa: F401


@pytest.mark.parametrize('scope', ['main', 'cc1', 'cc2', 'cc3', 'cc4'])
def test_identical_inflight_panel_reads_share_transport_but_not_response_body(scope):
    import json
    run_js('const scope=' + json.dumps(scope) + r''';
let release;
const gate=new Promise(resolve=>{release=resolve});
const {c,calls}=client(scope,async()=>{await gate;return reply({...identity(scope),observations:[1,2]});});
const first=c.request('/api/pantheon'),second=c.request('/api/pantheon');
await new Promise(resolve=>setTimeout(resolve,10));
assert.equal(calls.length,1,'a slow panel should have only one network read');
release();
const [a,b]=await Promise.all([first,second]);
assert.notEqual(a,b,'each consumer owns an independently readable Response');
assert.deepEqual(await a.json(),await b.json());
await c.request('/api/pantheon');
assert.equal(calls.length,2,'a completed read is not a cache of runtime state');
''')


def test_panel_read_sharing_does_not_merge_credentials_or_mutations():
    run_js(r'''
let release;
const gate=new Promise(resolve=>{release=resolve});
const {c,calls}=client('main',async()=>{await gate;return reply({ok:true});});
const a=c.request('/api/brain',{headers:{Authorization:'Bearer first'}});
const b=c.request('/api/brain',{headers:{Authorization:'Bearer second'}});
const x=c.request('/admin/pause',{method:'POST',body:'{"asset":"NQ"}'});
const y=c.request('/admin/pause',{method:'POST',body:'{"asset":"NQ"}'});
await new Promise(resolve=>setTimeout(resolve,10));
assert.equal(calls.length,4);release();await Promise.all([a,b,x,y]);
''')


@pytest.mark.parametrize('scope', ['main', 'cc1'])
def test_learning_is_manual_and_core_status_refresh_does_not_reissue_its_reads(workspace_http, scope):
    with common_page(workspace_http, scope, pause_periodic=True) as (page, _):
        requests=[]
        page.on('request',lambda r:requests.append(r.url) if '/learning' in r.url or '/intuition-omega' in r.url else None)
        page.locator('[data-v="learning"]').click()
        page.wait_for_function("()=>document.querySelector('#learningPanel')&&!document.querySelector('#learningPanel').textContent.includes('loading Learning Fabric')")
        initial=len(requests)
        assert initial >= 4
        page.evaluate('()=>{render(last);render(last);render(last)}')
        page.wait_for_timeout(300)
        assert len(requests)==initial,'status ticks must not poll the manual Learning view'
        page.locator('#learningRefresh').click()
        page.wait_for_timeout(300)
        assert len(requests)>initial,'the explicit Refresh button must still read new state'
