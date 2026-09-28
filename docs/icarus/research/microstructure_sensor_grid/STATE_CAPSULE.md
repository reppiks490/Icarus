# Microstructure Sensor Grid — State Capsule

Last productive run: ICARUS-MICRO-20260928T0650Z
Run manifest: runs/MICROSTRUCTURE_20260928T0650Z.md

## Last observed venue state

- Bybit BTCUSDT linear book time: 2026-09-28T06:51:38.602Z
- Linear BBO: 83093.20 / 83093.30
- Bybit BTCUSDT spot book time: 2026-09-28T06:51:38.553Z
- Spot BBO: 83130.00 / 83130.10
- Linear funding: -0.00002075; next 2026-09-28T08:00:00Z
- TickerLayer BTCUSD BBO time: 2026-09-28T06:51:53.273Z
- Composite BBO: 83143.32 / 83143.33
- Latest CFTC observation date: 2026-09-22; scheduled release date: 2026-09-25
- Gold source time: 2026-09-28T01:51:44Z; stale-status conflict retained

## Known corpus IDs

- MICRO-BYBIT-BTCUSDT-LIN-L2-20260928T065138602Z
- MICRO-BYBIT-BTCUSDT-SPOT-L2-20260928T065138553Z
- MICRO-TL-BTCUSD-BBO-20260928T065153273Z
- MICRO-BYBIT-BTCUSDT-LIN-1M-20260928T0333Z-0652Z
- MICRO-USGB-XAU-SPOT-20260928T015144Z
- CFTC-COT-CME-FUTURES-2026-09-22
- CFTC-COT-CMX-FUTURES-2026-09-22
- CME-CONTRACT-METADATA-RETRIEVED-2026-09-28
- CME-MBO-SEMANTICS-RETRIEVED-2026-09-28

## Persistent quality gates

- Keep observation, source update, retrieval and release times separate.
- Never merge BTCUSD, BTCUSDT spot and BTCUSDT linear without explicit mapping.
- Treat latest in-progress candle as provisional.
- Do not infer queue, sweeps or iceberg behavior from static MBP snapshots.
- Do not sum CFTC consolidated and contract-specific rows.
- Require exact contract month before joining live CME prices, volume, OI or settlement.
- Preserve venue/source disagreements and entitlement failures.

## Access state

- Bybit, TickerLayer, U.S. Gold Bureau, official web and GitHub: usable.
- FactorWeave: blocked by HOBBY-tier requirement.
- FMP COT: blocked by Premium/Ultimate/Enterprise requirement.
- CME live MDP/MBO, options analytics and cross-venue OI/liquidation feeds: not exposed.

## Next target

Licensed CME active-contract market data and synchronized multi-venue BTC derivatives snapshots with raw payload hashing.
