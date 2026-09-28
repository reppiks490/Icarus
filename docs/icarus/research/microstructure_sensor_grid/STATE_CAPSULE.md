# Microstructure Sensor Grid — State Capsule

Last productive run: ICARUS-MICRO-20260928T1642Z
Run manifest: runs/MICROSTRUCTURE_20260928T1642Z.md

## Latest observed crypto venue state

- Bybit BTCUSDT linear book: 2026-09-28T16:36:45.002Z; BBO 83935.40 / 83935.50.
- Bybit BTCUSDT spot book: 2026-09-28T16:36:45.553Z; BBO 83972.1 / 83972.2.
- Bybit ETHUSDT linear/spot: 2691.92/2691.93 vs 2692.85/2692.86.
- Bybit SOLUSDT linear/spot: 119.720/119.730 vs 119.76/119.77.
- BTC/ETH/SOL linear funding at this snapshot: +0.0001 (+0.0100%) each; next connector timestamp 2026-09-29T00:00:00Z.
- TickerLayer composite references: BTCUSD 83955.15/83955.16; ETHUSD 2692.12/2692.13; SOLUSD 119.74/119.75.

## Reference-market state

- Twelve Data authenticated.
- Quote anchor last_quote_at: 2026-09-28T16:42:00Z.
- QQQ 737.65; SPY 767.095; DIA 515.09; IWM 280.155 (reference ETFs only, not futures).
- QQQ and SPY 30-bar one-minute windows continuous.
- DIA returned sparse minute observations with 12:12→12:16 and 12:37→12:40 clock gaps.
- IWM one-minute retrieval blocked by per-minute provider credit cap.

## CME / CFTC state

- U.S. equity-index customary September 2026 roll date: 2026-09-14; September expiration 2026-09-18.
- December 2026 customary roll: 2026-12-14; expiration 2026-12-18.
- CME Daily VOI is preliminary; Daily Bulletin provides subsequent official/final updates.
- Latest collected CFTC observation date remains 2026-09-22.
- New combined futures+options corpora collected for BTC/Micro BTC, ES/MES, NQ/MNQ, RTY/M2K, GC/MGC.
- Never sum or silently merge combined COT with futures-only COT.

## Known corpus / artifact IDs added this run

- MICRO-BYBIT-BTCUSDT-LIN-L2-20260928T163645002Z
- MICRO-BYBIT-BTCUSDT-SPOT-L2-20260928T163645553Z
- MICRO-BYBIT-ETHUSDT-LIN-L2-20260928T163646837Z
- MICRO-BYBIT-ETHUSDT-SPOT-L2-20260928T163647358Z
- MICRO-BYBIT-SOLUSDT-LIN-L2-20260928T163648404Z
- MICRO-BYBIT-SOLUSDT-SPOT-L2-20260928T163649083Z
- MICRO-TL-BTCUSD-BBO-20260928T163651048Z
- MICRO-TL-ETHUSD-BBO-20260928T163652145Z
- MICRO-TL-SOLUSD-BBO-20260928T163652768Z
- ETF-REFERENCE-1M-QQQ-SPY-DIA-20260928T1642Z
- CFTC-COT-CME-COMBINED-2026-09-22
- CFTC-COT-COMEX-COMBINED-2026-09-22

## Persistent quality gates

- Keep source event, provider update, retrieval and release times separate.
- Do not merge BTCUSD with BTCUSDT spot/perpetual without explicit mapping.
- Do not infer queue/sweeps/icebergs from static price-level snapshots.
- Require exact CME contract month/SecurityID for live joins.
- Preserve preliminary vs final CME VOI revisions.
- Preserve CFTC futures-only vs combined population differences.
- Preserve sparse ETF bars without interpolation.
- Treat ETF proxies as related reference markets, not futures replacements.
- Preserve access/tier/credit failures as provenance.

## Access state

Usable:
- Bybit, TickerLayer, Twelve Data core quote/time-series endpoints, official CME/CFTC web, GitHub.

Blocked / partial:
- U.S. Gold Bureau current request: allowed-IP authorization failure.
- Twelve Data exchange_schedule: Ultra/Enterprise required.
- Twelve Data IWM one-minute history: per-minute API-credit cap reached.
- FactorWeave desired futures/VX endpoints: previously tier-gated.
- FMP paid COT: unnecessary while official CFTC source is available.
- CME live MDP/MBO, full options analytics, and cross-venue OI/liquidation feeds: not exposed.

## Persisted snapshot files

- snapshots/CRYPTO_BOOKS_FUNDING_20260928T163645Z.json
- snapshots/ETF_REFERENCE_1M_20260928T1642Z.csv

## Next collection targets

1. Exact CME active-contract December 2026 NQ/MNQ, ES/MES, YM/MYM, RTY/M2K plus active GC/MGC VOI/settlement.
2. Licensed CME MDP 3.0 MBO/MBP/trade-summary packets with sequence and SecurityID.
3. Second crypto derivatives venue with synchronized depth/funding/OI/liquidations/trade tape.
4. CME/Cboe options chains with bid/ask, IV, Greeks, volume and OI.
5. Raw-byte/provider checksum archival where licensing allows.
