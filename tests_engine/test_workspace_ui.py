"""Typed action translation keeps editor revisions and workspace boundaries."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(NODE is None, reason="optional Node unavailable")

HARNESS = r"""
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const world={URL,Headers,Response,Blob,AbortController,setTimeout,clearTimeout};
for(const path of process.argv.slice(1))vm.runInNewContext(fs.readFileSync(path,'utf8'),world);
const reply=(data,status=200)=>new Response(JSON.stringify(data),{status});
const own=(id='cc1',rev=2)=>({workspace_id:id,config_revision:rev,paper_only:true,execution_authorized:false});
function profile(id='cc1',rev=2){return {id,config_revision:rev,assets:['NQ','ES'],
 inputs:{tp1_pts:10,tp2_pts:30},chart:{timeframe:'20',fill_on:'real'},
 asset_overrides:{NQ:{inputs:{tp1_pts:1,sl_pts:9},chart:{timeframe:'5',fill_on:'chart'},preset:'retained'},
 ES:{inputs:{tp1_pts:2,use_tide:false},preset:null}}};}
function fixture(id='cc1',handler=null){
 const calls=[],p=profile(id),api=`/api/command-centers/${id}`;
 const c=world.IcarusWorkspaceClient.create({id},{origin:'http://localhost:8791',token:()=> 'fixture-owner',timeoutMs:1000,
 fetch:async(url,init)=>{const call={path:new URL(url).pathname,method:init.method,body:init.body?JSON.parse(init.body):null};calls.push(call);
 if(handler){const result=handler(call,p);if(result)return result;}
 if(call.path===api)return reply({profile:p});
 if(call.path.endsWith('/inputs/NQ'))return reply({...own(id,p.config_revision),asset:'NQ',effective:{tp1_pts:1},base:{tp1_pts:1}});
 if(call.path.endsWith('/assets'))return reply({...own(id,p.config_revision),registry:[
  {symbol:'6E',selectable:true,runtime_qualified:true},{symbol:'BAD',selectable:true,runtime_qualified:false}]});
 if(call.path.endsWith('/unavailable'))return reply({...own(id),detail:'Unavailable operation'},501);
 return reply({...own(id,call.method==='POST'&&Number.isSafeInteger(call.body.expected_revision)?call.body.expected_revision:p.config_revision),job:'fixture-job',note:'accepted'});
 }});
 return {c,ui:world.IcarusWorkspaceUI.create(c),calls,p};
}
const plain=value=>JSON.parse(JSON.stringify(value));
const error=code=>e=>e.name==='WorkspaceClientError'&&e.code===code;
"""


def run_js(body):
    result = subprocess.run([NODE, "-e", HARNESS + "\n(async()=>{\n" + body +
                             "\n})().catch(e=>{console.error(e);process.exitCode=1;});",
                             str(ROOT / "icarus_engine/workspace-client.js"),
                             str(ROOT / "icarus_engine/workspace-ui.js")],
                            text=True, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("scope", ["main", "cc1", "cc2", "cc3", "cc4"])
def test_controls_keep_the_explicit_page_source(scope):
    run_js("const id=" + json.dumps(scope) + r""";
const {ui,calls}=fixture(id);
await ui.admin('/admin/pause',{asset:'NQ',reason:'dashboard'});
await ui.admin('/admin/resume',{asset:'*'});
await ui.admin('/admin/flatten',{asset:'NQ',confirm:true});
const expected=id==='main'?['/admin/pause','/admin/resume','/admin/flatten']:[
 `/admin/command-centers/${id}/assets/NQ/pause`,`/admin/command-centers/${id}/pause`,
 `/admin/command-centers/${id}/assets/NQ/flatten`];
assert.deepEqual(calls.map(c=>c.path),expected);
if(id!=='main'){assert.deepEqual(calls[0].body,{paused:true});assert.deepEqual(calls[1].body,{paused:false});}
""")


def test_editor_snapshot_is_immutable_consistent_and_asset_specific():
    run_js(r"""
const {ui,p,calls}=fixture();const draft=await ui.loadInputs('*','NQ');
assert.equal(draft.asset,'*');assert.equal(draft.revision,2);assert.equal(draft.input.asset,'NQ');
assert(Object.isFrozen(draft)&&Object.isFrozen(draft.profile.asset_overrides.NQ.inputs)&&Object.isFrozen(draft.input.effective));
p.inputs.tp1_pts=999;assert.equal(draft.profile.inputs.tp1_pts,10);
assert.equal(calls.length,2);
const mismatch=fixture('cc2',call=>call.path.endsWith('/inputs/NQ')?reply({...own('cc2',3),asset:'NQ'}):null);
await assert.rejects(mismatch.ui.loadInputs('NQ'),error('REVISION_CONFLICT'));
assert(mismatch.calls.every(call=>call.method==='GET'));
const wrongAsset=fixture('cc3',call=>call.path.endsWith('/inputs/NQ')?reply({...own('cc3'),asset:'ES'}):null);
await assert.rejects(wrongAsset.ui.loadInputs('NQ'),error('INVALID_IDENTITY'));
""")


def test_main_editor_does_not_invent_a_revision_or_request_workspace_configuration():
    run_js(r"""
const {ui,calls}=fixture('main',()=>reply({asset:'NQ',effective:{tp1_pts:9}}));
const draft=await ui.loadInputs('NQ');assert.equal(draft.profile,null);assert.equal(draft.revision,null);
assert.equal(calls.length,1);assert.equal(calls[0].path,'/api/inputs/NQ');
""")


def test_whole_edits_remove_only_overlapping_override_fields():
    run_js(r"""
const {ui,calls,p}=fixture();const before=plain(p);const draft=await ui.loadInputs('*','NQ');
await ui.admin('/admin/inputs/async',{asset:'*',values:{tp1_pts:50},chart:{timeframe:'10'},persist:true},draft);
const write=calls.at(-1);assert.equal(write.path,'/admin/command-centers/cc1/config/async');
assert.deepEqual(write.body,{expected_revision:2,inputs:{tp1_pts:50,tp2_pts:30},chart:{timeframe:'10',fill_on:'real'},
 asset_overrides:{NQ:{inputs:{sl_pts:9},chart:{fill_on:'chart'},preset:'retained'},ES:{inputs:{use_tide:false},preset:null}}});
assert.deepEqual(p,before);assert.equal(draft.profile.asset_overrides.NQ.inputs.tp1_pts,1);
""")


def test_per_asset_apply_reset_and_presets_keep_captured_revision():
    run_js(r"""
const {ui,calls,p}=fixture();const draft=await ui.loadInputs('NQ');p.config_revision=7;
for(const [path,body,changes] of [
 ['/admin/inputs/async',{asset:'NQ',values:{tp1_pts:70},chart:{timeframe:'10'}},{inputs:{tp1_pts:70},chart:{timeframe:'10'}}],
 ['/admin/inputs/reset',{asset:'NQ'},{reset:true}],
 ['/admin/preset/async',{asset:'NQ',preset:null},{preset:null}],
]){
 await ui.admin(path,body,draft);
 assert.equal(calls.at(-1).path,'/admin/command-centers/cc1/assets/NQ/config/async');
 assert.deepEqual(calls.at(-1).body,{...changes,expected_revision:2});
}
assert.equal(calls.filter(c=>c.path==='/api/command-centers/cc1').length,1);
""")


@pytest.mark.parametrize("kind", ["reset", "preset"])
def test_whole_reset_or_preset_preserves_defaults(kind):
    run_js("const kind=" + json.dumps(kind) + r""";
const {ui,calls,p}=fixture();const before=plain(p);const draft=await ui.loadInputs('*','NQ');
await ui.admin(kind==='reset'?'/admin/inputs/reset/async':'/admin/preset/async',
 kind==='reset'?{asset:'*'}:{asset:'*',preset:'new-preset'},draft);
const result=calls.at(-1).body;assert.equal(result.expected_revision,2);
assert.equal('inputs' in result,false);assert.equal('chart' in result,false);
const expected=kind==='reset'?{}:plain(before.asset_overrides);
if(kind!=='reset')for(const symbol of before.assets)expected[symbol].preset='new-preset';
assert.deepEqual(result.asset_overrides,expected);assert.deepEqual(p,before);
""")


def test_drafts_are_never_rebased_and_invalid_scope_does_not_write():
    run_js(r"""
const {ui,calls}=fixture('cc1',call=>call.method==='POST'?reply({...own('cc1',9),detail:'configuration changed'},409):null);
const draft=await ui.loadInputs('NQ');
await assert.rejects(ui.admin('/admin/inputs/async',{asset:'NQ',values:{tp1_pts:70}},draft),e=>e.status===409);
assert.equal(calls.at(-1).body.expected_revision,2);
const count=calls.length;
await assert.rejects(ui.admin('/admin/inputs/reset/async',{asset:'ES'},draft),error('INVALID_REQUEST'));
await assert.rejects(ui.admin('/admin/inputs/async',{asset:'NQ',values:{x:1}}, {...draft,revision:undefined}),error('INVALID_IDENTITY'));
await assert.rejects(ui.admin('/admin/flatten',{asset:'NQ'}),error('INVALID_REQUEST'));
assert.equal(calls.length,count);
""")


def test_asset_admission_uses_qualified_registry_and_single_profile_cas():
    run_js(r"""
const {ui,calls,p}=fixture();const before=plain(p);
await ui.admin('/admin/assets/add',{symbol:'6E',tf:'10',preset:'currency'});
assert.deepEqual(calls.at(-1).body,{expected_revision:2,assets:['NQ','ES','6E'],asset_overrides:{
 ...before.asset_overrides,'6E':{chart:{timeframe:'10'},preset:'currency'}}});
assert.equal(calls.filter(c=>c.path==='/api/command-centers/cc1').length,1);
assert.deepEqual(p,before);
const blocked=fixture();await assert.rejects(blocked.ui.admin('/admin/assets/add',{symbol:'BAD'}),error('INVALID_REQUEST'));
assert(blocked.calls.every(c=>c.method==='GET'));
await assert.rejects(blocked.ui.admin('/admin/assets/add',{symbol:'6e'}),error('INVALID_REQUEST'));
assert(blocked.calls.every(c=>c.method==='GET'));
""")


def test_removal_explicitly_disposes_only_removed_asset_override():
    run_js(r"""
const {ui,calls,p}=fixture();await ui.admin('/admin/assets/remove',{symbol:'NQ'});
assert.deepEqual(calls.at(-1).body,{expected_revision:2,assets:['ES'],asset_overrides:{ES:plain(p.asset_overrides.ES)}});
assert.equal(calls.filter(c=>c.path==='/api/command-centers/cc1').length,1);
const single=fixture();single.p.assets=['NQ'];
await assert.rejects(single.ui.admin('/admin/assets/remove',{symbol:'NQ'}),error('INVALID_REQUEST'));
assert(single.calls.every(c=>c.method==='GET'));
""")


def test_rewarm_and_backtest_select_revision_without_changing_default_preset():
    run_js(r"""
const {ui,calls,p}=fixture('cc4');p.assets.push('6E');
await ui.admin('/admin/rewarm',{asset:'*'});
assert.deepEqual(calls.at(-1),{path:'/admin/command-centers/cc4/rewarm/async',method:'POST',body:{expected_revision:2}});
await ui.backtest('6E',{timeframe:null,commission:'',capital:undefined,fill_on:'real'});
assert.deepEqual(calls.at(-1).body,{expected_revision:2,fill_on:'real'});
await ui.backtest('NQ',{preset:null,commission:0});assert.equal(calls.at(-1).body.preset,null);
assert.equal(calls.at(-1).body.commission,0);
""")


def test_main_config_jobs_use_typed_registration_and_unknown_cc_actions_reject():
    run_js(r"""
const main=fixture('main',call=>call.path.startsWith('/api/config-jobs/')?reply({id:'fixture-job',status:'done'}):null);
const receipt=await main.ui.admin('/admin/inputs/async',{asset:'NQ',values:{tp1_pts:3},persist:true});
await main.c.job(receipt.job);assert.equal(main.calls.at(-1).path,'/api/config-jobs/fixture-job');
await main.ui.admin('/admin/assets/add',{symbol:'6E'});assert.equal(main.calls.at(-1).path,'/admin/assets/add');
const cc=fixture('cc3');
await assert.rejects(cc.ui.admin('/admin/autopilot/start',{asset:'NQ',armed:true}),e=>e.status===501);
assert.equal(cc.calls.length,1);assert.equal(cc.calls[0].path,'/admin/command-centers/cc3/unavailable');
assert.deepEqual(cc.calls[0].body,{operation:'POST /admin/autopilot/start'});
""")
