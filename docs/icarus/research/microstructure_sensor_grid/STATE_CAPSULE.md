# Microstructure Sensor Grid — State Capsule

Last productive run: ICARUS-MICRO-20260928T1708Z
Run manifest: runs/MICROSTRUCTURE_20260928T1708Z.md

## Latest cross-product crypto state

Near-synchronous Bybit spot / USDT-linear / USD-inverse observations:

BTC:
- spot BTCUSDT 83589.3 / 83589.4 @ 17:08:47.953Z
- linear BTCUSDT 83542.8 / 83542.9 @ 17:08:48.402Z
- inverse BTCUSD 83521.0 / 83521.1 @ 17:08:48.005Z
- linear funding +0.00006467

ETH:
- spot ETHUSDT 2682.66 / 2682.67 @ 17:08:49.358Z
- linear ETHUSDT 2681.61 / 2681.62 @ 17:08:49.237Z
- inverse ETHUSD 2679.78 / 2679.79 @ 17:08:49.466Z
- linear funding +0.0001

SOL:
- spot SOLUSDT 118.61 / 118.62 @ 17:08:50.480Z
- linear SOLUSDT 118.55 / 118.56 @ 17:08:50.404Z
- inverse SOLUSD 118.45 / 118.52 @ 17:08:50.551Z
- linear funding +0.0001

## Contract-unit gate

- Spot quantities: underlying token units.
- USDT-linear quantities: underlying token units.
- USD-inverse quantities: USD contract quantities.
- Official Bybit documentation says inverse quantity is denominated in USD contracts (1 contract = 1 USD), with position value = quantity / price and P&L settled in underlying coin.
- Never sum inverse depth quantity with spot/linear depth quantity without explicit conversion.

## Instrument-spec state

- BTCUSDT linear: tick 0.10, qty step 0.001 BTC, max leverage 150x.
- BTCUSD inverse: tick 0.10, qty step 1 USD contract, max leverage 100x.
- ETHUSDT linear: tick 0.01, qty step 0.01 ETH, max leverage 150x.
- ETHUSD inverse: tick 0.01, qty step 1 USD contract, max leverage 100x.
- SOLUSDT linear: tick 0.01, qty step 0.1 SOL, max leverage 100x.
- SOLUSD inverse: tick 0.01, qty step 1 USD contract, max leverage 50x.

## Access-state changes

- TickerLayer perpetual symbol discovery works for BTCUSDT/ETHUSDT/SOLUSDT and reports source_count 6 for each.
- TickerLayer perpetual snapshot/quote/last-trade calls are blocked: perpetuals access not enabled for this account.
- Second independent live derivatives feed remains unavailable.
- Bybit spot/linear/inverse and instrument-spec endpoints remain usable.
- GitHub remains usable.

## Persistent prior state

- 60 one-minute Bybit linear bars for BTC/ETH/SOL collected through 16:53Z with no timestamp gaps.
- ETF one-minute reference plane covers QQQ/SPY/DIA/IWM; DIA sparse gaps preserved.
- CME roll/VOI preliminary-vs-final gates remain active.
- Latest CFTC observation date collected: 2026-09-22, futures-only and combined populations kept separate.

## New artifact IDs

- CRYPTO-SPOT-LINEAR-INVERSE-BTCETHSOL-20260928T1708Z
- MICRO-BYBIT-BTCUSD-INVERSE-L2-20260928T170848005Z
- MICRO-BYBIT-ETHUSD-INVERSE-L2-20260928T170849466Z
- MICRO-BYBIT-SOLUSD-INVERSE-L2-20260928T170850551Z

## Persistent quality gates

- Preserve source timestamps and product identity.
- Never conflate quantity units across spot/linear/inverse.
- Never infer MBO queue behavior from price-level books.
- Never interpolate missing observations silently.
- Keep ETF references distinct from futures.
- Require exact CME contract/security identifiers.
- Keep CFTC futures-only and combined data separate.
- Preserve provider entitlement failures.
- Mark same-venue cross-product comparisons as non-independent observations.

## Persisted snapshots

- snapshots/CRYPTO_SPOT_LINEAR_INVERSE_20260928T1708Z.json
- snapshots/CRYPTO_LINEAR_DEPTH_1M_20260928T1653Z.json
- snapshots/ETF_REFERENCE_1M_20260928T1653Z.csv

## Next collection targets

1. Independent second crypto derivatives venue with live depth/funding/OI/liquidations/trade tape.
2. Exact-contract CME active-month VOI/settlement.
3. Licensed CME MDP 3.0 MBO/MBP/trade-summary.
4. CME/Cboe options chain.
5. Authorized inverse-funding history endpoint.
6. Raw payload/checksum preservation where permitted.
