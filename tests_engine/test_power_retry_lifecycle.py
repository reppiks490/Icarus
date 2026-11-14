"""Rejected power changes must not survive a page lifecycle boundary."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest


NODE = shutil.which("node")
SOURCE = Path(__file__).resolve().parents[1] / "icarus_engine/workspace_power_ui.js"


@pytest.mark.skipif(NODE is None, reason="optional Node unavailable")
@pytest.mark.parametrize("restore_page", [False, True], ids=["pagehide", "pagehide-pageshow"])
def test_power_admission_retry_does_not_outlive_its_page(restore_page):
    # Expose the real request closure without mounting a DOM. The actual registered
    # pagehide/pageshow callbacks and native fetch primitives remain under test.
    script = r"""
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const handlers = {}, posts = [];
const window = {
  IcarusWorkspace:Object.freeze({id:'main'}),
  IcarusClient:Object.freeze({getToken:()=> 'power-lifecycle-test-token'}),
  addEventListener:(name, handler)=>{handlers[name]=handler;},
  dispatchEvent:()=>{},
  fetch:async(path, init)=>{
    if (init.method === 'GET') {
      // A restored page also refreshes its state. Leave that unrelated read in
      // flight until final teardown, so this test observes only old mutations.
      return new Promise((resolve,reject)=>init.signal.addEventListener('abort',()=>{
        const error = new Error('aborted'); error.name = 'AbortError'; reject(error);
      },{once:true}));
    }
    posts.push({path, body:JSON.parse(init.body), aborted:init.signal.aborted});
    return new Response(JSON.stringify(posts.length === 1 ?
      {detail:'Workspace is busy; retry after its current operation.'} : {ok:true}),
      {status:posts.length === 1 ? 409 : 200});
  }
};
const document = {readyState:'loading', addEventListener:()=>{}, querySelector:()=>null};
const original = fs.readFileSync(process.argv[1],'utf8');
const source = original.replace('  function isOff(id) {',
  '  window.requestForTest = request;\n  function isOff(id) {');
assert.notEqual(source, original, 'request harness injection point must exist');
vm.runInNewContext(source,{window,document,location:{pathname:'/'},
  setTimeout,clearTimeout,setInterval,clearInterval,AbortController});
(async()=>{
  const result = window.requestForTest('/admin/command-centers/cc1/runtime',
    {enabled:true,expected_revision:0}).then(()=>null,error=>error);
  await new Promise(resolve=>setTimeout(resolve,20));
  assert.equal(posts.length,1,'the first admission refusal must occur before navigation');
  handlers.pagehide({persisted:RESTORE_PAGE});
  if (RESTORE_PAGE) handlers.pageshow({persisted:true});
  try {
    await result;
    assert.equal(posts.length,1,
      'navigation must cancel a rejected mutation even when the same page is restored');
  } finally {
    handlers.pagehide({persisted:false});
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
""".replace("RESTORE_PAGE", json.dumps(restore_page))
    result = subprocess.run([NODE, "-e", script, str(SOURCE)], text=True,
                            capture_output=True, timeout=5)
    assert result.returncode == 0, result.stdout + result.stderr
