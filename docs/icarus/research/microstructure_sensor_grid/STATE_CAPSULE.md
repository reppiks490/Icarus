# Microstructure Sensor Grid — State Capsule

Last productive run: ICARUS-MICRO-20260928T1653Z
Run manifest: runs/MICROSTRUCTURE_20260928T1653Z.md

## Latest crypto state

- BTCUSDT linear book: 2026-09-28T16:53:19.603Z; BBO 83613.20 / 83613.30.
- ETHUSDT linear book: 2026-09-28T16:53:22.237Z; BBO 2683.47 / 2683.48.
- SOLUSDT linear book: 2026-09-28T16:53:24.804Z; BBO 119.090 / 119.100.
- Funding: BTC +0.00006537; ETH +0.0001; SOL +0.0001.
- Next funding timestamp: 2026-09-29T00:00:00Z.

## Latest 1-minute crypto coverage

All returned series: 60 bars, 2026-09-28T15:54:00Z–16:53:00Z, no timestamp gaps.
- BTC range 83200.3–84174.3; returned volume sum 5547.314 BTC; RV60m 0.543051%.
- ETH range 2669.58–2698.28; returned volume sum 76513.68 ETH; RV60m 0.625360%.
- SOL range 118.22–120.34; returned volume sum 466894.4 SOL; RV60m 0.880130%.
RV formula: sqrt(sum(log(close_t/close_t-1)^2)), non-annualized.

## ETF/reference state

- QQQ/SPY/IWM: 20 returned 1-minute bars with continuous timestamps over their 12:33–12:52 provider display windows.
- DIA: 20 observations spanning 12:29–12:52 with preserved gaps at 12:37→12:40, 12:48→12:50 and 12:50→12:52.
- IWM minute coverage is now available; prior credit-cap gap closed.
- ETF proxies remain distinct from NQ/ES/YM/RTY futures.

## Access-state changes

- TickerLayer US100/US500/US30 and XAUUSD quote calls: 403 plan restriction.
- TickerLayer Russell index symbol discovery: no match.
- Bybit and Twelve Data selected endpoints: usable.
- GitHub: usable.

## Persistent CME/CFTC state

- Equity-index customary September 2026 roll: 2026-09-14; expiry 2026-09-18.
- December customary roll: 2026-12-14; expiry 2026-12-18.
- CME Daily VOI preliminary versus subsequent Daily Bulletin official/final distinction remains active.
- Latest collected CFTC observation: 2026-09-22, futures-only and futures+options combined kept separate.

## New artifact IDs

- MICRO-BYBIT-BTCUSDT-LIN-L2-20260928T165319603Z
- MICRO-BYBIT-ETHUSDT-LIN-L2-20260928T165322237Z
- MICRO-BYBIT-SOLUSDT-LIN-L2-20260928T165324804Z
- CRYPTO-LINEAR-1M-BTCETHSOL-20260928T1554Z-1653Z
- ETF-REFERENCE-1M-QQQ-SPY-DIA-IWM-20260928T1653Z

## Persistent quality gates

- Keep source event/update/retrieval/release times separate.
- Never infer MBO queue behavior from static price-level depth.
- Never interpolate missing bars silently.
- Mark newest incomplete bars provisional.
- Keep ETF references separate from futures.
- Require exact CME contract/security identifiers.
- Preserve preliminary/final VOI revisions.
- Keep CFTC futures-only and combined populations separate.
- Preserve provider-plan failures and symbol mapping gaps.

## Persisted snapshots

- snapshots/CRYPTO_LINEAR_DEPTH_1M_20260928T1653Z.json
- snapshots/ETF_REFERENCE_1M_20260928T1653Z.csv

## Next collection targets

1. Exact-contract CME December 2026 equity-index VOI/settlement and active GC/MGC records.
2. Licensed CME MDP 3.0 MBO/MBP + trade summary.
3. Second crypto derivatives venue with depth/funding/OI/liquidations/trade tape.
4. CME/Cboe options chain data.
5. Raw payload/checksum preservation where permitted.
