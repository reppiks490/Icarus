"""Execute the shipped dashboard's loading and receipt display behavior."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_native_validation_dashboard_shows_results_and_clears_failed_fetch(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node unavailable")
    source = Path(__file__).resolve().parents[1] / "icarus_engine/ascendancy-ui.js"
    probe = tmp_path / "native-dashboard.cjs"
    probe.write_text("""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const el={innerHTML:''},requests=[];let unavailable=false;
const native={enabled:true,worker_running:true,run_count:2,runs:[
 {run_id:'real-native-result',candidate_id:'<script>bad</script>',outcome:'PASS',
 submission_state:'SUBMITTED',resource_usage:{evaluations:1,wall_seconds:0.25,cost_units:0}},
 {run_id:'interrupted-intent',candidate_id:'candidate-two',outcome:null,submission_state:'RUNNING',
 error:'<img src=x onerror=bad>'}]};
const board={completed_count:1,orders:[{order_id:'matched-order',status:'COMPLETED',
 domain_result:{receipt_id:'accepted-receipt',stage:'CONTRACT_VALIDATION',outcome:'FAIL'}}]};
const context={window:{},document:{querySelector:()=>el},localStorage:{getItem:()=> 'token'},
 fetch:async(url,options)=>{requests.push(url);assert.strictEqual(options.headers.Authorization,'Bearer token');
 const isNative=url.endsWith('/native-validation');return{ok:!isNative||!unavailable,status:503,
 json:async()=>isNative?native:url.endsWith('/work-orders')?board:{}};}};
vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),context);
(async()=>{
 await context.window.loadAscendancy();
 assert(requests.includes('/api/ascendancy/native-validation'));
 assert(el.innerHTML.includes('NATIVE CONTRACT VALIDATION'));
 assert(el.innerHTML.includes('real-native-result'));
 assert(el.innerHTML.includes('Needs review'));
 assert(el.innerHTML.includes('Awaiting scientific tests'));
 assert(el.innerHTML.includes('accepted-receipt'));
 assert(el.innerHTML.includes('FAIL'));
 assert(!el.innerHTML.includes('<script>bad</script>'));
 assert(!el.innerHTML.includes('<img src=x onerror=bad>'));
 unavailable=true;await context.window.loadAscendancy();
 assert(el.innerHTML.includes('native validation state did not load'));
 assert(!el.innerHTML.includes('real-native-result'));
})().catch(e=>{console.error(e);process.exitCode=1;});
""", encoding="utf-8")
    result = subprocess.run([node, str(probe), str(source)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
