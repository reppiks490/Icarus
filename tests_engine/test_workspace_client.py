"""Exercise the explicit browser client with Node's real fetch primitives."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
CLIENT = Path(__file__).resolve().parents[1] / "icarus_engine/workspace-client.js"
pytestmark = pytest.mark.skipif(NODE is None, reason="optional Node unavailable")

HARNESS = r"""
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const world = {URL, Headers, Response, Blob, AbortController, setTimeout, clearTimeout};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), world);
const factory = world.IcarusWorkspaceClient;
const reply = (data, status=200, headers={}) => new Response(JSON.stringify(data), {status, headers});
const identity = (id='cc1', revision=0) => ({workspace_id:id, config_revision:revision});
function client(id='cc1', handler=()=>reply(identity(id))) {
  const calls=[];
  const c=factory.create({id, capabilities:{paper_only:id!=='main', nested:{enabled:true}}}, {
    origin:'http://localhost:8791', token:()=> 'test-token', timeoutMs:1000,
    fetch:async (url, init)=>{calls.push({path:new URL(url).pathname, query:new URL(url).search,
      headers:new Headers(init.headers), body:init.body?JSON.parse(init.body):null, method:init.method});
      return handler(url, init);}
  });
  return {c,calls};
}
const error = (code) => e => e.name==='WorkspaceClientError' && e.code===code;
"""


def run_js(body):
    result = subprocess.run([NODE, "-e", HARNESS + "\n(async()=>{\n" + body +
                             "\n})().catch(e=>{console.error(e);process.exitCode=1;});", str(CLIENT)],
                            text=True, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("scope", ["main", "cc1", "cc2", "cc3", "cc4"])
def test_explicit_client_selects_five_distinct_sources(scope):
    run_js("const scope=" + json.dumps(scope) + r""";
const prefix=scope==='main'?'':`/api/command-centers/${scope}`;
const selected=scope==='main'?900:Number(scope.slice(-1))*100;
const {c,calls}=client(scope, (url)=>{
 const p=new URL(url).pathname, own=scope==='main'?{}:identity(scope,2);
 if(p.endsWith('/trades/NQ'))return reply(scope==='main'?[{entry_id:scope}]:{...own,trades:[{entry_id:scope}]});
 return reply({...own,assets:[{symbol:'NQ',price:selected}],effective:{tp1_pts:selected},bars:[{c:selected}]});
});
assert.equal((await c.read('status')).assets[0].price,selected);
assert.equal((await c.read('inputs',{asset:'NQ'})).effective.tp1_pts,selected);
assert.equal((await c.read('chart',{asset:'NQ',n:20,offset:20})).bars[0].c,selected);
assert.equal((await c.read('trades',{asset:'NQ'}))[0].entry_id,scope);
assert.equal(calls[0].path,scope==='main'?'/status/public':prefix+'/status');
assert.equal(calls[1].path,scope==='main'?'/api/inputs/NQ':prefix+'/inputs/NQ');
assert.equal(calls[2].query,'?n=20&offset=20');
assert(calls.every(x=>x.headers.get('Authorization')==='Bearer test-token'));
if(scope!=='main')assert(calls.every(x=>x.path.startsWith(prefix+'/')&&x.headers.get('X-Icarus-Workspace')===scope));
""")


def test_bootstrap_is_required_defensively_copied_and_immutable():
    run_js(r"""
for(const bad of [undefined,{}, {id:''},{id:'CC1'},{id:'cc1/cc2'},{id:'other'}])
 assert.throws(()=>factory.create(bad,{origin:'http://localhost',fetch:async()=>reply({})}));
const seed={id:'cc3',capabilities:{nested:{enabled:true}}};
const c=factory.create(seed,{origin:'http://localhost',fetch:async()=>reply(identity('cc3'))});
seed.id='main';seed.capabilities.nested.enabled=false;
assert.equal(c.context.id,'cc3');assert.equal(c.context.capabilities.nested.enabled,true);
assert(Object.isFrozen(c)&&Object.isFrozen(c.context)&&Object.isFrozen(c.context.capabilities.nested));
assert.equal(c.href('NQ'),'/dashboards/cc3?asset=NQ');
""")


def test_missing_workspace_and_bad_identity_never_retry_parent():
    run_js(r"""
const {c,calls}=client('cc4',()=>reply({detail:'selected runtime missing'},503));
await assert.rejects(c.read('status'),e=>e.status===503);
assert.equal(calls.length,1);assert.equal(calls[0].path,'/api/command-centers/cc4/status');
for(const data of [identity('cc2'),identity('cc1',-1),identity('cc1',1.5),{assets:[]}]){
 const {c}=client('cc1',()=>reply(data));
 await assert.rejects(c.read('status'),error('INVALID_IDENTITY'));
}
""")


def test_revisions_and_slow_responses_cannot_replace_new_observations():
    run_js(r"""
const pending=[];const {c}=client('cc1',()=>new Promise(resolve=>pending.push(resolve)));
const first=c.read('status'),second=c.read('status');
await new Promise(resolve=>setTimeout(resolve,0));
pending[1](reply({...identity('cc1',4),assets:[{price:400}]}));assert.equal((await second).assets[0].price,400);
pending[0](reply({...identity('cc1',3),assets:[{price:300}]}));
await assert.rejects(first,error('STALE_RESPONSE'));
const lower=c.read('inputs',{asset:'NQ'});await new Promise(resolve=>setTimeout(resolve,0));
pending[2](reply(identity('cc1',2)));await assert.rejects(lower,error('STALE_RESPONSE'));
""")


def test_deadline_abort_and_close_are_bounded_even_if_transport_ignores_abort():
    run_js(r"""
const make=()=>factory.create({id:'cc1'},{origin:'http://localhost',timeoutMs:15,fetch:()=>new Promise(()=>{})});
await assert.rejects(make().read('status'),error('TIMEOUT'));
const c=make(),abort=new AbortController();const read=c.read('status',{signal:abort.signal});abort.abort();
await assert.rejects(read,error('CANCELLED'));
const other=make(),active=other.read('status');other.close();
await assert.rejects(active,error('CANCELLED'));await assert.rejects(other.read('status'),error('CANCELLED'));
""")


def test_configuration_preserves_editor_revision_and_explicit_control_scope():
    run_js(r"""
const {c,calls}=client('cc1',(url,init)=>init.method==='POST'?reply({detail:'stale editor'},409):reply(identity('cc1',7)));
await c.read('status');
await assert.rejects(c.configure('NQ',{inputs:{tp1_pts:17}},3),e=>e.status===409);
assert.equal(calls[1].body.expected_revision,3);assert.equal(calls[1].path,'/admin/command-centers/cc1/assets/NQ/config/async');
const n=calls.length;
await assert.rejects(c.configure('NQ',{inputs:{},asset:'ES'},7));
await assert.rejects(c.configure('NQ',{inputs:{}},undefined));assert.equal(calls.length,n);
const controls=client('cc2',()=>reply(identity('cc2',0)));
await controls.c.control('pause','NQ');await controls.c.control('resume');await controls.c.control('flatten','ES');
assert.equal(controls.calls[0].path,'/admin/command-centers/cc2/assets/NQ/pause');assert.deepEqual(controls.calls[0].body,{paused:true});
assert.equal(controls.calls[1].path,'/admin/command-centers/cc2/pause');assert.deepEqual(controls.calls[1].body,{paused:false});
assert.deepEqual(controls.calls[2].body,{confirm:true});
await assert.rejects(controls.c.control('arm','NQ'));assert.equal(controls.calls.length,3);
""")


def test_jobs_and_csv_keep_accepted_revision_after_configuration_advances():
    run_js(r"""
const {c,calls}=client('cc1',(url,init)=>{
 const p=new URL(url).pathname;
 if(p.endsWith('/backtest'))return reply({...identity('cc1',2),job:'ws-own',created:true},202);
 if(p.endsWith('/status'))return reply(identity('cc1',3));
 if(p.endsWith('/trades.csv'))return new Response('selected-csv',{headers:{'X-Icarus-Workspace':'cc1','X-Icarus-Config-Revision':'2'}});
 if(p.endsWith('/compare'))return reply({...identity('cc1',2),job:'ws-own',report:{}});
 return reply({...identity('cc1',2),id:'ws-own',asset:'NQ',kind:'backtest',status:'done',result:{...identity('cc1',2)}});
});
const receipt=await c.backtest('NQ',{},2);assert.equal(receipt.job,'ws-own');
assert(!('preset' in calls[0].body));await c.read('status');
assert.equal((await c.job('ws-own')).config_revision,2);
const downloaded=await c.csv({job:'ws-own'});assert.equal(await downloaded.blob.text(),'selected-csv');
assert(downloaded.filename.startsWith('cc1_')&&downloaded.filename.includes('ws-own'));
assert.equal((await c.compare('ws-own','own-csv')).config_revision,2);
assert(calls.every(x=>!x.path.startsWith('/api/backtest')&&!x.path.startsWith('/admin/backtest')));
const foreign=client('cc1',()=>reply({...identity('cc2',2),id:'ws-own'}));
await assert.rejects(foreign.c.job('ws-own'),error('INVALID_IDENTITY'));
""")


def test_csv_checks_headers_before_reading_and_authentication_is_current():
    run_js(r"""
let token='first',bodyReads=0;
const calls=[];
const c=factory.create({id:'cc1'},{origin:'http://localhost',token:()=>token,fetch:async(url,init)=>{
 calls.push(new Headers(init.headers));
 return {ok:true,status:200,headers:new Headers({'X-Icarus-Workspace':'cc2','X-Icarus-Config-Revision':'0'}),blob:async()=>{bodyReads++;return new Blob(['wrong']);}};
}});
token='updated';await assert.rejects(c.csv({asset:'NQ'}),error('INVALID_IDENTITY'));
assert.equal(bodyReads,0);assert.equal(calls[0].get('Authorization'),'Bearer updated');
for(const rev of ['','-1','1.5','not-a-revision']){
 const c=factory.create({id:'cc1'},{origin:'http://localhost',fetch:async()=>new Response('wrong',{headers:{'X-Icarus-Workspace':'cc1','X-Icarus-Config-Revision':rev}})});
 await assert.rejects(c.csv({asset:'NQ'}),error('INVALID_IDENTITY'));
}
""")


def test_navigation_shared_allowlist_and_scope_selectors_fail_closed():
    run_js(r"""
const {c,calls}=client('cc4',()=>reply([{name:'shared'}]));
assert.equal(c.href(),'/dashboards/cc4');assert.equal(c.href('NQ'),'/dashboards/cc4?asset=NQ');
for(const bad of ['nq','NQ/ES','NQ?workspace=main','%2FNQ'])assert.throws(()=>c.href(bad));
assert.equal((await c.shared('/api/presets'))[0].name,'shared');
for(const path of ['/api/brain','/admin/pause','https://external.example/api/presets'])await assert.rejects(c.shared(path));
assert.equal(calls.length,1);assert.equal(calls[0].method,'GET');
const main=client('main');assert.equal(main.c.href('NQ'),'/?asset=NQ');
""")


def test_live_csv_cannot_finish_with_an_obsolete_revision():
    run_js(r"""
let release;const delayedBlob=new Promise(resolve=>release=resolve);
const {c}=client('cc1',(url)=>new URL(url).pathname.endsWith('.csv')?
 {ok:true,status:200,headers:new Headers({'X-Icarus-Workspace':'cc1','X-Icarus-Config-Revision':'1'}),blob:()=>delayedBlob}:
 reply(identity('cc1',2)));
const download=c.csv({asset:'NQ'});await new Promise(resolve=>setTimeout(resolve,0));
await c.read('status');release(new Blob(['old-view']));
await assert.rejects(download,error('STALE_RESPONSE'));
""")


def test_main_configuration_uses_native_preset_and_input_contracts():
    run_js(r"""
let count=0;const {c,calls}=client('main',()=>reply({job:'main-job-'+(++count)},202));
await c.configure('*',{preset:null});
await c.configure('NQ',{inputs:{tp1_pts:17},chart:{timeframe:'10'}});
assert.equal(calls[0].path,'/admin/preset/async');assert.deepEqual(calls[0].body,{asset:'*',preset:null});
assert.equal(calls[1].path,'/admin/inputs/async');
assert.deepEqual(calls[1].body,{asset:'NQ',values:{tp1_pts:17},chart:{timeframe:'10'},persist:true});
assert(!('expected_revision' in calls[1].body));
""")


@pytest.mark.parametrize("operation", ["configure", "backtest"])
def test_job_admission_receipt_must_match_the_submitted_revision(operation):
    run_js("const operation=" + json.dumps(operation) + r""";
const {c,calls}=client('cc1',()=>reply({...identity('cc1',9),job:'ws-wrong-source'},202));
await assert.rejects(operation==='configure'?c.configure('NQ',{inputs:{tp1_pts:17}},8):c.backtest('NQ',{},8),error('INVALID_IDENTITY'));
assert.equal(calls.length,1);assert.equal(calls[0].body.expected_revision,8);
""")
