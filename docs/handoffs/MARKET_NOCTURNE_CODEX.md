# ICARUS Market Nocturne — Codex handoff

## Assignment

Continue the autonomous visual observatory inside the existing ICARUS Main trading dashboard. Sudo wants an abstract, beautiful instrument for watching trades across the entire running portfolio. No setup or clicks should be required to start watching. Treat the active Windows computer as the deployment target. Deliver an animated example and a working phone link. The user requested a stopping point before further build-out.

## Checkpoint and recovery

A working component rendered in a browser. The screenshot showed platinum in focus, seven luminous nested market orbits, an execution tape, cross-market readings, and an instrument constellation labeled “9 / 35 with bars.” Browser accessibility inspection confirmed 35 individual instrument controls, a 28-reading field guide and an explicit Archive replay label. This was an accelerated historical preview. The private gateway timed out from the session. The actual live PC roster and installed revision were never independently observed.

Workspace maintenance subsequently removed the scratch checkout, preview checkout and render directory. No remote feature commit, PR, successful site publication, completed MP4 or passing integration test receipt was confirmed. This document is a reconstruction handoff. Look for surviving work before rebuilding. The conversation contains the original shell writes for the JS, CSS, integration, replay adapter, archive builder and film script if accessible.

## Where to resume

- Repository: https://github.com/reppiks490/Icarus . Inspected main revision 89a1ebfe3c2be774bf07ea7700ea7a0b2496dcc4. Local branch was feature/market-observatory. Check current HEAD, AGENTS.md, branch and PR history before editing.
- Coordination: reppiks490/icarus-owner-actions. Session codex-20261120-market-nocturne and plan event 20261121T-market-nocturne-plan. Check active ownership and record the eventual verification and handoff.
- Registered preview Site ID appgprj_6b010357823c8191aaae344a7bcacf82. Check its versions and source before attempting another publication. Preserve its audience. Umbra is a separate project.
- Desktop loopback port 8791. Documented mobile gateway port 8792. Previously known private HTTPS observer used port 8443. Consult current docs/PHONE_ACCESS.md. Cloud localhost and a GitHub catalog cannot verify the running PC. Read workspace identity, roster and a fresh timestamp through an authorized observation route. Keep credentials out of reports. Avoid restarting or arming the engine.

## Native integration

Modify icarus_engine/dashboard.html and the exact static asset allowlist in icarus_engine/server.py. Implement icarus_engine/market-nocturne.js and market-nocturne.css. Mount on the default Overview and an Observatory tab through the existing workspaceViewController lifecycle. Release observers, timers and animation frames on disposal and scope change. Use existing IcarusClient status, chart and trade caches. No independent market polling. Extend the overview’s bounded chart refresh to the Observatory. A read failure or expired workspace must clear affected evidence.

The JS interface was IcarusNocturne.mount(host), returning update(assets,charts,trades,meta) and dispose(). charts[symbol+'80'] supplies completed [ts,o,h,l,c,v] bars, overlays and emulator fills. trades[symbol] supplies closed pieces. Asset state supplies scores, position and regime. Scope the whole scene to assets from the selected status response. In these records live=true distinguishes runtime paper activity from warm-up paper. Never label either as a broker execution.

## Visual behavior and 28 implemented readings

1. Orrery uses normalized completed close paths for each orbit.
2. Volatility changes the spread of fine luminous filaments.
3. Wavefield overlays separately normalized market profiles in stacked rows.
4. Candlelight gives the focused market a candlestick microscope.
5. Relative volume compares the last observation with the earlier window mean.
6. Breadth counts rising, falling and flat markets.
7. Window return ranks leaders and laggards.
8. Local drawdown measures distance below the window high.
9. Range seat locates the close inside its observed high–low window.
10. Opening gap compares the latest open with the preceding close.
11. Upper and lower wick fractions describe the most recent candle.
12. Range expansion compares the last range with previous ranges.
13. Positive return correlation identifies the closest positive relationship.
14. Negative return correlation identifies the strongest inverse relationship.
15. Pair sample size reports exact shared return intervals. Require matching chart type, timeframe, last timestamp and at least 12 intervals; omit constant series.
16. Timestamp-aligned VWAP is drawn in gold.
17. TIDE high and low form violet guides.
18. Chart basis and fill basis have separate labels.
19. Chart close minus observed real close reveals transformed-price divergence.
20. The time-ordered execution tape shows symbol, side, size, price and provenance.
21. Fill rings mark emulator prices and times on the candles.
22. The latest closed piece shows direction, recorded result and holding duration.
23. Signed paper position shows exposure in instrument units.
24. Long and short scores appear alongside the effective entry gate.
25. The engine supplies the current regime.
26. Feed labels distinguish warming, stale, closed, delayed, paused, errors and archive data.
27. A roster grid shows every scoped symbol, with miniature traces or explicit missing bars.
28. An automatic director rotates projections approximately every 11.5 seconds and focuses newly arrived runtime paper fills. Hold, resume and next are optional.

Visual language: near-black navy canvas, violet, mint, amber and rose filaments, tilted orbital geometry, a warm central light, restrained serif title, compact monospace telemetry. Default frame shows up to seven paths, while the roster includes every symbol. Pause drawing offscreen and honor reduced motion. Escape data strings. Keep keyboard focus stable while prices refresh.

## Roster and evidence

The source registry returned 35 symbols: NQ, BTC, MNQ, MES, ES, YM, MYM, RTY, M2K, GC, MGC, SI, SIL, PL, PA, MBT, ETH, SOL, CL, NG, HG, 6E, 6J, 6B, 6A, ZN, ZB, BTCF, MHG, MCL, MNG, M6E, MJY, M6B, M6A. Use this as a comparison fixture only. Production should derive membership from the current workspace.

The replay used 18 September 2026, 13:35–17:35 UTC, sourced from reppiks490/multi-level-csv, including “Full csv candles only.zip” (Git blob 0087eb2f10deb91bc54bb8de0bf331c59a5735ba). Select minute-grid, strictly increasing, finite and internally valid OHLC observations. Do not invent volume or fill gaps. The broad archive experiment produced 22 instruments. The final demonstrated roster mapped nine series: PL, BTC, SI, GC, YM, PA, BTCF, NQ and ES. BTC spot used the Bitstamp archive. All other roster tiles showed No bars. Matched futures with observed volume were replayed through native AssetRunner.on_sub_bar with one-minute real bars, real fill basis, Inputs(), fixed scale 1 and registered tick sizes. These are illustrative paper settings, not the owner’s active presets. The archive builder found 19 emulator fills. The replay filters bars, overlays, scores, fills and trades against its current clock to prevent future observations leaking into the display.

## Verification and delivery

First recover or reproduce the branch in a clean checkout. Run the repo’s tests_engine/test_workspace_dashboard_browser.py cases for 35-asset retention and selected-source isolation. Add targeted tests for correlation interval alignment, missing volume, stale responses, roster changes, automatic fill focus, scrolling, hold/resume, workspace expiry and rendering at iPhone width. Verify no additional network polling or trade-state writes. Capture desktop and phone views. The prior test run was initiated but its final results were lost.

The film script intended a 31-second H.264 MP4 at 960 × 1024 and 20 fps, rendering the real UI with an accelerated archive clock. Show orbital motion, a change to Wavefield, a palladium paper entry at 14:19 UTC and Candlelight focusing on its fill. End on the roster. Confirm the encoded file opens and verify the fill is visible before delivering. Commit the source to a reviewable branch, record the SHA and tests, then publish the private archive preview if still requested. Report live-PC verification separately. Stop after delivering the verified animation, review link and explicit deployment status.
