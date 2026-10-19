"""Real browser exercises for the four-portfolio performance panel, offline."""
from pathlib import Path
import subprocess
import shutil

import pytest


def test_four_views_render_own_performance_and_clear_wrong_or_failed_responses():
    node = shutil.which('node')
    if not node:
        pytest.skip('optional Node browser runtime unavailable')
    probe = subprocess.run([node, '-e', "const fs=require('fs'),{chromium}=require('playwright');process.exit(fs.existsSync(chromium.executablePath())?0:1)"],
                           capture_output=True, timeout=15)
    if probe.returncode:
        pytest.skip('optional Playwright/Chromium unavailable; required in workspace-performance workflow')
    root = Path(__file__).resolve().parents[1]
    script = r'''
const {chromium}=require('playwright'),fs=require('fs'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try {
  for(const width of [390,1440])for(const id of ['cc1','cc2','cc3','cc4']){
   const page=await browser.newPage({viewport:{width,height:950}});let mode='ok';
   await page.route('http://127.0.0.1:8791/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.startsWith('/dashboards/'))return route.fulfill({contentType:'text/html',body:'<meta name="viewport" content="width=device-width"><main id="workspace-panel"></main>'});
    if(mode==='fail')return route.fulfill({status:503,body:'{}'});
    const payload={schema_version:1,workspace_id:mode==='wrong'?'cc4-other':id,paper_only:true,execution_authorized:false,available:true,status:'AVAILABLE',as_of_ts:Date.now()/1000,realized_pnl:123,closed_pieces:2,trades:[{id:1,symbol:'<img src=x onerror=alert(1)>',entry_id:'entry',direction:1,qty:1,entry_price:1,exit_price:2,entry_ts:1700000000,exit_ts:1700000060,profit:123,exit_comment:'<script>bad()</script>'}],equity_curve:[{ts:1700000060,realized_pnl:123}],daily_activity:[{date:'2023-11-14',ts:1699920000,realized_pnl:123,closed_pieces:2}],ratios:{sharpe:1.25,sortino:1.75,sample_days:24,minimum_days:20,reason:'AVAILABLE',basis:'Closed UTC day realized P&L proxy'},historical:{predictive:false,win_rate:.5,mean_closure_pnl:61.5,max_realized_drawdown:12},display:{trades_truncated:false,equity_sampled:false,daily_sampled:false}};
    return route.fulfill({contentType:'application/json',body:JSON.stringify(payload)});
   });
   await page.goto('http://127.0.0.1:8791/dashboards/'+id);
   await page.addScriptTag({path:process.argv[1]});
   await page.waitForFunction(()=>document.querySelector('#performance-status')?.textContent.includes('persisted'));
   assert.match(await page.locator('#performance-title').textContent(),new RegExp(id.toUpperCase()));
   assert.equal(await page.locator('#performance-sharpe').textContent(),'1.250');
   assert.equal(await page.locator('#performance-sortino').textContent(),'1.750');
   assert.equal(await page.locator('#performance-trades img').count(),0);
   assert.equal(await page.locator('#performance-trades script').count(),0);
   assert.equal(await page.locator('#performance-switch option').count(),4);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   mode='wrong';await page.locator('#performance-refresh').click();
   await page.waitForFunction(()=>document.querySelector('#performance-sharpe').textContent==='Unavailable');
   assert.match(await page.locator('#performance-status').textContent(),/unavailable/i);
   mode='ok';await page.locator('#performance-refresh').click();
   await page.waitForFunction(()=>document.querySelector('#performance-sharpe').textContent==='1.250');
   mode='fail';await page.locator('#performance-refresh').click();
   await page.waitForFunction(()=>document.querySelector('#performance-sharpe').textContent==='Unavailable');
   assert.equal(await page.locator('#performance-trades tr').count(),0);
   await page.close();
  }
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
'''
    result = subprocess.run([node, '-e', script, str(root/'icarus_engine/workspace-performance-ui.js')],
                            text=True, capture_output=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
