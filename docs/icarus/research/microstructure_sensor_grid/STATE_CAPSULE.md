# Microstructure Sensor Grid — State Capsule

Last productive run: ICARUS-MICRO-20260928T1740Z
Run manifest: runs/MICROSTRUCTURE_20260928T1740Z.md

## Binance raw trade-tape state

Durable repository raw payloads now exist for the previously transient aggregate-trade captures:
- BTCUSDT: 100 records, IDs 3468308318–3468308417, 7.411-second event-time span.
- ETHUSDT: 100 records, IDs 3102913945–3102914044, 6.928-second span.
- SOLUSDT: 100 records, IDs 1101446810–1101446909, 24.565-second span.

Raw payload Git blobs:
- BTCUSDT fdb540cbda8b86b805f53acce27bfae35dc95341
- ETHUSDT 6332ad88005b35f9f265f66e71cf1ba01472dceb
- SOLUSDT b26652d2e3eede38cd3b5adf8f9bd62d107014ff

The raw DataBlue payloads are persisted exactly as decoded from the attached full-result files. The prior transient-handle-only gap is closed.

## Latest tape summaries

BTCUSDT:
- price 83956.5–83964.4; total quantity 8.4 BTC.
- m=true 3.085; m=false 5.315.
- largest aggregate 1.693 BTC.

ETHUSDT:
- price 2703.88–2704.30; total 180.063 ETH.
- m=true 100.431; m=false 79.632.
- largest aggregate 40.733 ETH.

SOLUSDT:
- price 119.69–119.77; total 4879.01 SOL.
- m=true 3732.48; m=false 1146.53.
- largest aggregate 751.92 SOL.

No directional conclusion is attached to m=true/m=false totals.

## Persistent prior state

- Binance second-venue depth, funding, mark/index, current OI, 5-minute OI history and funding history remain available from 1730Z.
- exact 2026-09-25 CME settlements complete for NQ/MNQ, ES/MES, YM/MYM, RTY/M2K, GC/MGC.
- bounded delayed Cboe same-day option IV/OI/Greeks remain available.
- liquidation REST history remains unavailable.
- full Cboe term structure remains incomplete.
- exact CME contract OI and licensed MDP 3.0 remain gaps.

## Quality gates

- Preserve raw aggregate IDs, component first/last trade IDs, timestamps, prices, quantities and m flags.
- Aggregate trades are not MBO/order-message data.
- Do not infer queue state, hidden liquidity or liquidation events from aggregate trades.
- Do not assign a trading conclusion to m=true/m=false totals.
- Preserve short-window coverage limits.

## Access state

Usable:
- Bybit public selected endpoints.
- Binance public USDⓈ-M REST.
- DataBlue public scraping plus conversation full-result attachments.
- Massive historical futures aggregates.
- Cboe delayed option JSON bounded extraction.
- Twelve Data selected endpoints.
- GitHub.

Blocked / partial:
- liquidation history REST path 404.
- Massive real-time futures and option snapshots NOT_ENTITLED.
- TickerLayer perpetual data 403.
- CME MDP 3.0 not exposed.
- Superpowers no callable runtime surface.

## Next targets

1. Longer durable aggregate-trade windows synchronized to book events.
2. Lawful liquidation event stream.
3. Exact CME contract OI.
4. Reliable next-expiry Cboe skew/term data.
5. CME futures-option Greeks.
6. Licensed CME MDP 3.0.
