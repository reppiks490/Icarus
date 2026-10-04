"""Independent presentation invariants for the procedural renderer."""
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which('node') is None, reason='Node unavailable')
def test_cinema_geometry_is_finite_and_has_no_external_effects():
    source = Path(__file__).parents[1] / 'icarus_engine' / 'world-cinema.js'
    # Canvas recorder deliberately rejects NaN/infinite geometry and media/network
    # access. Exercise both layout branches, all palettes and fold boundaries.
    script = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let calls=0;
const record=(...args)=>{calls++;for(const a of args)if(typeof a==='number')assert.ok(Number.isFinite(a),'Nonfinite canvas coordinate');};
const gradient={addColorStop:record};
const ctx=new Proxy({}, {get:(_,key)=>key.startsWith('create')?(...args)=>{record(...args);return gradient;}:record,set:()=>true});
const root={dataset:{world:'divine',motion:'live',experience:'cinematic'}};
const forbidden=()=>{throw Error('Presentation attempted external access');};
const window={};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),{
 window,document:{documentElement:root,hidden:false,querySelectorAll:()=>[]},
 fetch:forbidden,XMLHttpRequest:forbidden,AudioContext:forbidden,cancelAnimationFrame:()=>{},console
});
for(const world of ['divine','void','astral']) {
 root.dataset.world=world;
 for(const [w,h] of [[1440,470],[390,590],[2560,760],[1,1],[0,0]])
 for(const t of [0,.1,7.9,8,9.5,10.7,11.4,13,17.99,18,10000])
 for(const intro of [true,false])for(const detail of ['rich','light'])window.IcarusWorldCinema.draw(ctx,w,h,t,.033,{intro,detail,pointer:{x:.5,y:-.5}});
}
assert.ok(calls>10000,'Renderer produced no geometry');
const el={isConnected:true,querySelector:()=>true,animate:forbidden};
root.dataset.motion='off';window.IcarusWorldCinema.enterChart('TEST',el);
root.dataset.motion='live';root.dataset.experience='focus';window.IcarusWorldCinema.enterChart('OTHER',el);
window.IcarusWorldCinema.sync(false);
console.log('Finite geometry, motion gates, no network or automatic audio');
'''
    result = subprocess.run(['node', '-e', script, str(source)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
