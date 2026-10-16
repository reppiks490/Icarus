// Read-only UI contract for real-price shadow evidence; route all status data to fixtures.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const {mkdirSync}=require('node:fs');
const output=process.env.ICARUS_BROWSER_OUTPUT||'/tmp/icarus-shadow-previews';
mkdirSync(output,{recursive:true});
const fixture={
  now:1781568000,
  execution_authorized:false,
  assets:[{
    symbol:'NQ',
    real_price_shadow:{
      asset:'NQ',status:'ACTIVE',reason:null,fill_basis:'STANDARD_REAL_BAR_EMULATOR',
      primary_fill_basis:'HA_BAR_CLOSE',entry_fill_parity:0.75,pairable_closed_episodes:4,
      outcome_agreement_rate:0.75,outcome_agreement_denominator:4,primary_win_preservation:0.8,
      primary:{net:200},real_price_shadow:{net:123},
      primary_bar_close_max_drawdown:30,real_price_shadow_bar_close_max_drawdown:18,
      administrative_censored_shadow_positions:0,
      provenance:{price_provider:'test-feed',timeframe_minutes:10,calendar:'CME',session_mode:'RTH',
        primary_fill_basis:'HA_BAR_CLOSE',shadow_fill_basis:'standard_real_ohlc',
        feed_health:{status:'GREEN'}}
    }
  }],
  real_price_shadow:{
    schema:'icarus.real_price_shadow.portfolio/1',enabled:true,status:'ACTIVE',execution_authorized:false,
    asset_count:1,primary_entry_fills:4,shadow_entry_fills:3,entry_fill_parity:0.75,
    matched_entry_intents:3,primary_only_entry_fills:1,shadow_only_entry_fills:0,
    administrative_censored_shadow_positions:0,pairable_closed_episodes:4,
    outcome_agreement_denominator:4,outcome_agreement_rate:0.75,
    outcome_matrix:{win:{win:2,loss:1,break_even:0},loss:{win:0,loss:1,break_even:0},break_even:{win:0,loss:0,break_even:0}},
    primary_win_preservation:0.8,primary_net:200,real_price_shadow_net:123,net_realization_ratio:0.615,
    paired_profit_capture:0.65,drawdown_aggregation:'per_asset_only; cross_asset_close_timestamps_are_not_yet_aligned',
    assets:[{asset:'NQ',status:'ACTIVE',reason:null,administrative_censored_shadow_positions:0,
      provenance:{price_provider:'test-feed',timeframe_minutes:10,calendar:'CME',session_mode:'RTH',
        primary_fill_basis:'HA_BAR_CLOSE',shadow_fill_basis:'standard_real_ohlc',feed_health:{status:'GREEN'}}}]
  }
};
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.ICARUS_BROWSER_BINARY?{executablePath:process.env.ICARUS_BROWSER_BINARY}:{})});
  try {
    const context=await browser.newContext({viewport:{width:1280,height:900}}),page=await context.newPage();
    const errors=[],writes=[];
    page.on('pageerror',error=>errors.push(error.message));
    page.on('request',request=>{if(request.method()!=='GET')writes.push(request.url());});
    await page.route('**/status/public',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(fixture)}));
    await page.goto(process.env.ICARUS_PREVIEW_URL||'http://127.0.0.1:8879');
    const launcher=page.locator('#rt01-open'); await launcher.waitFor();
    assert.equal(await launcher.evaluate(el=>getComputedStyle(el).position),'fixed');
    await launcher.click();
    await page.locator('#rt01-content .rt01-table-wrap').waitFor();
    const content=await page.locator('#rt01-content').innerText();
    assert.match(content,/Entry fill parity[\s\S]*75\.0%/i);
    assert.match(content,/Shadow net[\s\S]*\$123\.00/i);
    assert.match(content,/NQ/);
    assert.match(content,/test-feed/);
    assert.match(content,/\$200\.00 \/ \$123\.00/);
    assert.match(content,/execution authorized[\s\S]*false/i);
    assert.equal(await page.locator('#rt01-content script').count(),0);
    await page.screenshot({path:`${output}/shadow-twin.png`});
    await page.locator('#rt01-close').click();
    assert.equal(await page.locator('#rt01-shade').evaluate(el=>el.classList.contains('open')),false);
    assert.deepEqual(errors,[]); assert.deepEqual(writes,[]);
    console.log(JSON.stringify({passed:true,errors,writes,entries:fixture.real_price_shadow.matched_entry_intents}));
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
