"""Exercise shipped browser accounting and failure handling without provider I/O."""
import json
from pathlib import Path
import shutil
import subprocess
import time

import pytest

from icarus_engine.paper_pnl import validate_paper_pnl


@pytest.mark.skipif(shutil.which('node') is None, reason='optional Node unavailable')
def test_shipped_accounting_validator_and_legacy_failure_clear_cached_results():
    now = int(time.time())
    strict = validate_paper_pnl([dict(id=f'cc{i}', currency='USD', runtime_available=True,
        snapshot_ts=now, realized_pnl=i * 10, open_pnl=i, open_positions=1,
        oldest_open_mark_ts=now) for i in range(1,5)], as_of_ts=now)
    data = dict(mode='concurrent_paper', profiles=[dict(id=f'cc{i}') for i in range(1,5)], paper_pnl=strict)
    script = r'''
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const path=process.argv[1],data=JSON.parse(process.argv[2]);
const elements=new Map();
for(const name of ['#combinedPaperPnl','#paperSnapshotNotice','#paperAggregate','#paperWorkspaceTabs','#paperConnections','#paperWorkspaceBody','#paperWorkspaceRuntime'])elements.set(name,{textContent:'',innerHTML:'',className:'',querySelectorAll:()=>[]});
const intervals=[],timers=[];
const context={document:{querySelector:s=>elements.get(s)||null,addEventListener:()=>{},querySelectorAll:()=>[],activeElement:null},setInterval:f=>intervals.push(f),setTimeout:f=>{timers.push(f);return timers.length;},clearTimeout:()=>{},AbortController,fetch:async()=>{throw Error('forced network failure');}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path+'/paper-pnl-ui.js','utf8'),context);
vm.runInContext(fs.readFileSync(path+'/command-centers-ui.js','utf8'),context);
context.payload=data;
assert.equal(vm.runInContext('IcarusPaperPnl.read(payload).aggregate.total_pnl',context),110);
for(const badClock of [NaN,Infinity,-Infinity,-1]){context.badClock=badClock;assert.equal(vm.runInContext('IcarusPaperPnl.read(payload,badClock)',context),null);}
vm.runInContext('paperWorkspaces=payload;paperSetHeader(payload);',context);
assert.match(elements.get('#combinedPaperPnl').textContent,/110.00/);
const copy=()=>JSON.parse(JSON.stringify(data));
for(const mutate of [p=>p.profiles[0].id='cc2',p=>p.profiles[0].currency='EUR',p=>p.as_of_ts-=91,p=>p.as_of_ts+=100,p=>p.aggregate.total_pnl=111,p=>p.profiles[0].realized_pnl=true]){
 const bad=copy();mutate(bad.paper_pnl);context.bad=bad;assert.equal(vm.runInContext('IcarusPaperPnl.read(bad)',context),null);
}
(async()=>{
 await vm.runInContext('loadPaperWorkspaces()',context);
 assert.equal(elements.get('#combinedPaperPnl').textContent,'—');
 assert.match(elements.get('#paperWorkspaceRuntime').innerHTML,/unavailable/);
 assert.match(elements.get('#paperAggregate').innerHTML,/unavailable/);
 assert.equal(vm.runInContext('paperWorkspaces',context),null);
 // A hanging transport receives an abort at its bounded deadline.
 let signal;
 context.fetch=(_path,options)=>new Promise((resolve,reject)=>{signal=options.signal;signal.addEventListener('abort',()=>reject(Error('aborted')));});
 const pending=vm.runInContext("IcarusPaperPnl.fetchJson('/no-network').catch(e=>e.message)",context);
 timers.at(-1)();assert.equal(await pending,'aborted');assert.equal(signal.aborted,true);
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
    result = subprocess.run([shutil.which('node'), '-e', script,
        str(Path(__file__).resolve().parents[1] / 'icarus_engine'), json.dumps(data)],
        capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(shutil.which('node') is None, reason='optional Node unavailable')
def test_browser_matches_python_cancellation_of_large_safe_ledger_values():
    now = int(time.time())
    values = [2**53 - 1, 2, -(2**53 - 1), 1]
    contract = validate_paper_pnl([dict(id=f'cc{i}',currency='USD',runtime_available=True,snapshot_ts=now,
        realized_pnl=value,open_pnl=0,open_positions=0,oldest_open_mark_ts=None)
        for i,value in enumerate(values,1)],as_of_ts=now)
    assert contract['aggregate']['total_pnl'] == 3
    script = "const fs=require('node:fs');eval(fs.readFileSync(process.argv[1],'utf8'));const p=IcarusPaperPnl.read(JSON.parse(process.argv[2]));require('node:assert/strict').equal(p?.aggregate.total_pnl,3);"
    result = subprocess.run([shutil.which('node'),'-e',script,
        str(Path(__file__).resolve().parents[1]/'icarus_engine/paper-pnl-ui.js'),
        json.dumps(dict(mode='concurrent_paper',paper_pnl=contract))],capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
