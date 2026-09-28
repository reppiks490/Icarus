# Microstructure Sensor Grid — State Capsule

Last productive run: ICARUS-MICRO-20260928T1721Z
Run manifest: runs/MICROSTRUCTURE_20260928T1721Z.md

## Independent crypto derivatives venue state

Binance USDⓈ-M public REST is now a usable second venue for collection:
- BTCUSDT @ ~17:07:14Z BBO 83600.00/83600.10; funding +0.00006884; OI 93910.062 BTC.
- ETHUSDT @ ~17:07:26Z BBO 2684.00/2684.01; funding +0.00007693; OI 2274323.759 ETH.
- SOLUSDT @ ~17:07:36Z BBO 118.6900/118.7000; funding +0.00007131; OI 8169730.88 SOL.
- Binance order-book update IDs and event/transaction timestamps are persisted.
- No public REST liquidation history was captured.

## Bybit persistent state

Prior 17:08Z spot / USDT-linear / USD-inverse product plane remains valid as the latest persisted Bybit cross-product checkpoint.
Inverse contract-count unit gate remains active.

## CME exact-contract state

Massive session aggregates now cover all ten December 2026 targets for session_end_date 2026-09-28:
NQZ6, MNQZ6, ESZ6, MESZ6, YMZ6, MYMZ6, RTYZ6, M2KZ6, GCZ6, MGCZ6.

The session was in progress. Returned aggregate fields did not include populated official settlement or contract OI. Do not treat close as settlement.
Massive real-time snapshot is NOT_ENTITLED.

## Cboe option state

Official delayed Cboe JSON is reachable for QQQ, SPY and IWM.
Bounded same-day option records with bid/ask, IV, OI, volume and delta/gamma/theta/vega/rho are persisted.
- QQQ bounded strikes: 735-738 for 2026-09-28.
- SPY bounded strikes: 766-767 for 2026-09-28.
- IWM bounded strike: 279 for 2026-09-28.
- QQQ next expiration observed in a bounded query: 2026-09-29.
Full skew/term structure remains incomplete because multi-megabyte chains exceeded full-query processing.

## New artifacts

- snapshots/BINANCE_USDM_DEPTH_FUNDING_OI_20260928T1707Z.json
- snapshots/CME_TARGET_SESSION_20260928.csv
- snapshots/CBOE_OPTIONS_ATM_20260928T1721Z.json

## Persistent quality gates

- Preserve exact venue/product/source timestamps.
- Do not infer MBO from MBP depth.
- Do not infer cross-venue lead-lag from unsynchronized snapshots.
- Do not promote in-progress CME close to settlement.
- Do not infer contract OI where absent.
- Treat Cboe bounded option extraction as partial, delayed data.
- Keep full-chain absence distinct from bounded-query absence.
- Preserve entitlement/rate-limit/tooling failures.
- Never silently merge contradictory sources or product classes.

## Access state

Usable:
- Bybit public spot/linear/inverse.
- Binance public USDⓈ-M via authorized public scraping.
- Twelve Data selected reference endpoints.
- Massive Futures session aggregates.
- Cboe official delayed options JSON.
- Firecrawl bounded query.
- official CME/CFTC web.
- GitHub.

Blocked / partial:
- Massive real-time futures snapshot: NOT_ENTITLED.
- Massive option-chain snapshot: NOT_ENTITLED.
- TickerLayer perpetual live data: 403.
- TickerLayer direct indices/XAUUSD: plan restricted.
- U.S. Gold Bureau: prior IP restriction.
- DataBlue LLM extraction: no LLM API key.
- licensed CME MDP 3.0: not exposed.

## Next targets

1. Public/licensed liquidation event history.
2. Official previous-day CME settlement + contract OI for ten exact target contracts.
3. CME MDP 3.0 MBO/MBP/trade summaries.
4. Cboe next-expiry option slices for term structure.
5. CME futures options IV/Greeks where licensed.
6. Raw upstream payload/checksum preservation.
