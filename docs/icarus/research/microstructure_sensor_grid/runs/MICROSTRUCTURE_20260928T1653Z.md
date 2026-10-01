# Microstructure Sensor Grid — Collection Run

Run ID: ICARUS-MICRO-20260928T1653Z
Collection window: 2026-09-28T15:54:00Z–2026-09-28T16:53:24.804Z
Repository base before write: main @ 2290eeff519afad36a8ea89fe434e9d5ce9d0801
Scope: collection and provenance only; no scoring, recommendations, trade decisions, execution, backtesting, optimization, model promotion, or downstream-system mutation.

## NEW MICROSTRUCTURE SOURCES

Fresh Bybit linear-perpetual price-level books:

| Corpus ID | Instrument | Source event time UTC | BBO | Returned depth |
|---|---|---|---|---|
| MICRO-BYBIT-BTCUSDT-LIN-L2-20260928T165319603Z | BTCUSDT linear perpetual | 16:53:19.603 | 83613.20 x 7.333 / 83613.30 x 2.609 | 10 price levels/side from 50 requested |
| MICRO-BYBIT-ETHUSDT-LIN-L2-20260928T165322237Z | ETHUSDT linear perpetual | 16:53:22.237 | 2683.47 x 98.43 / 2683.48 x 0.97 | 10 levels/side |
| MICRO-BYBIT-SOLUSDT-LIN-L2-20260928T165324804Z | SOLUSDT linear perpetual | 16:53:24.804 | 119.090 x 661.7 / 119.100 x 10.0 | 10 levels/side |

Full normalized books, funding, and one-minute candles are persisted in:
snapshots/CRYPTO_LINEAR_DEPTH_1M_20260928T1653Z.json

### Returned-depth summaries

Derived only from the ten returned levels per side:
- BTCUSDT: bid quantity 9.814 BTC; ask 2.748 BTC; normalized imbalance +0.562490.
- ETHUSDT: bid 133.44 ETH; ask 2.72 ETH; normalized imbalance +0.960047.
- SOLUSDT: bid 14,635.7 SOL; ask 7,936.0 SOL; normalized imbalance +0.296819.

These do not establish MBO queue priority, hidden liquidity, cancellations, sweep execution, spoofing, or future behavior.

## FUNDING COVERAGE

At this checkpoint:
- BTCUSDT funding +0.00006537 (+0.006537%; connector display +0.0065%).
- ETHUSDT funding +0.0001 (+0.0100%).
- SOLUSDT funding +0.0001 (+0.0100%).
- Next connector funding timestamp: 2026-09-29T00:00:00Z.

BTC funding changed from the prior persisted +0.0100% observation. This is stored as a temporal state transition only.

## ONE-MINUTE LINEAR-PERPETUAL TIME-SERIES COVERAGE

All three Bybit series contain 60 consecutive one-minute bars from 15:54Z through 16:53Z with no non-60-second timestamp gaps.

| Instrument | Window high | Window low | Sum of returned base-volume field | Non-annualized realized volatility |
|---|---:|---:|---:|---:|
| BTCUSDT | 84,174.3 | 83,200.3 | 5,547.314 BTC | 0.543051% |
| ETHUSDT | 2,698.28 | 2,669.58 | 76,513.68 ETH | 0.625360% |
| SOLUSDT | 120.34 | 118.22 | 466,894.4 SOL | 0.880130% |

Realized-volatility formula:
sqrt(sum(log(close_t / close_t-1)^2)) across the returned one-minute closes; non-annualized.

The 16:53 bars were the newest returned bars and are flagged provisional because retrieval occurred during/near that minute.

## ETF / CASH-REFERENCE ONE-MINUTE COVERAGE

Twelve Data successfully returned 20 one-minute observations for all four ETF proxies, including IWM, closing the previous run's IWM credit-gap.

Full normalized rows are persisted in:
snapshots/ETF_REFERENCE_1M_20260928T1653Z.csv

| Proxy | Related futures family | Returned clock window | High | Low | Returned volume sum | Timestamp continuity |
|---|---|---|---:|---:|---:|---|
| QQQ | NQ/MNQ | 12:33–12:52 provider display time | 739.16 | 737.205 | 37,648 | continuous |
| SPY | ES/MES | 12:33–12:52 | 768.15 | 766.67 | 64,610 | continuous |
| DIA | YM/MYM | 12:29–12:52 | 516.48 | 514.73 | 5,187 | sparse |
| IWM | RTY/M2K | 12:33–12:52 | 280.72 | 279.76 | 66,463 | continuous |

DIA gaps preserved without interpolation:
- 12:37 -> 12:40 (180 seconds);
- 12:48 -> 12:50 (120 seconds);
- 12:50 -> 12:52 (120 seconds).

ETF instruments are reference/cash-market proxies, not CME futures substitutes.

## REFERENCE-INDEX / GOLD ACCESS CHECK

TickerLayer direct index/commodity calls were attempted this run:
- US100 index: 403, plan does not include requested data.
- US500 index: 403.
- US30 index: 403.
- XAUUSD commodity: 403.
- Russell index symbol discovery: no supported Russell match returned.

No value was inferred or substituted from these blocked surfaces. The authorized ETF proxy plane remains separate.

## ORDER-FLOW / DEPTH COVERAGE

New:
- fresh BTC/ETH/SOL linear 10-level books;
- synchronized one-hour one-minute linear-perpetual candle corpora;
- IWM minute coverage successfully added.

Still absent:
- CME live MDP 3.0 MBP/MBO;
- OrderID / PriorityID / exchange packet sequence;
- crypto individual trade tape;
- liquidations and venue open interest;
- block-trade feeds;
- options IV/skew/term structure/Greeks.

No queue, iceberg, sweep, large-trade or spoofing labels were inferred.

## LATENCY / FRESHNESS

- Bybit book source times span 16:53:19.603Z to 16:53:24.804Z.
- Candle windows are internally contiguous for BTC/ETH/SOL.
- Twelve Data ETF bar clock values are provider-formatted exchange-local display times; no unsupported UTC conversion is asserted in this artifact.
- Latest crypto candle is provisional.
- ETF sparse/continuous status is based on returned observations, not assumed zero-volume bars.

## GAPS / CONFLICTS / DUPLICATES

- TickerLayer direct index and XAUUSD data are plan-blocked.
- No direct Russell index instrument was available in TickerLayer symbol discovery.
- Bybit depth remains partial (10 returned vs 50 requested).
- Static price-level depth is not market-by-order.
- DIA missing minutes are preserved as missing observations.
- ETF and futures instruments remain distinct datasets.
- Prior funding values and current funding values are temporal observations, not contradictions.
- No upstream provider raw-byte checksum was exposed.

## LICENSING / ACCESS LIMITS

Succeeded:
- Bybit public normalized order-book, funding and one-minute kline endpoints.
- Twelve Data one-minute ETF reference series for QQQ/SPY/DIA/IWM.
- GitHub repository read/write surfaces.

Blocked:
- TickerLayer US100/US500/US30/XAUUSD: current plan unauthorized.
- TickerLayer Russell index discovery: no matching supported index.
- direct licensed CME MDP/MBO feed: not exposed.
- options analytics and cross-venue OI/liquidation feeds: not exposed.

Previously established provider tier/auth limits remain in the state capsule and were not repeatedly invoked where doing so would add no information.

## PROVENANCE / HASH STATUS

- Immutable source identity uses provider + exact instrument + data class + source timestamp/date.
- Raw connector payload bytes/checksums are not exposed.
- This run persists normalized connector records as Git blobs, giving content-addressed artifact hashes.
- Raw versus derived status is explicit.
- No forward-fill or interpolation was performed.
- No downstream model state was changed.

## DATA QUALITY FLAGS

- DQ-PARTIAL-DEPTH
- DQ-NO-MBO
- DQ-PROVISIONAL-LATEST-BAR
- DQ-SPARSE-BAR-RETURN-DIA
- DQ-ETF-NOT-FUTURES
- DQ-TICKERLAYER-PLAN-BLOCK
- DQ-NORMALIZED-NO-UPSTREAM-RAW-HASH
- DQ-SYMBOL-MAPPING

## CAPABILITY LEDGER

Successfully invoked:
- GitHub state/ref read.
- Bybit order-book, funding and 1-minute kline for BTCUSDT/ETHUSDT/SOLUSDT.
- Twelve Data one-minute series for QQQ/SPY/DIA/IWM.
- TickerLayer symbol discovery.

Invoked but blocked:
- TickerLayer US100, US500, US30 and XAUUSD quote surfaces: 403 plan restriction.

Not invoked this cycle because prior authoritative/reference state remained current enough for the incremental task:
- CFTC weekly positioning;
- CME roll-date/reference documentation;
- FMP paid COT;
- FactorWeave tier-gated futures context;
- Massive auth-gated path.

Numeric effort control is not exposed; deepest available safe verification was used.

## PERSISTED ARTIFACTS

- docs/icarus/research/microstructure_sensor_grid/runs/MICROSTRUCTURE_20260928T1653Z.md
- docs/icarus/research/microstructure_sensor_grid/snapshots/CRYPTO_LINEAR_DEPTH_1M_20260928T1653Z.json
- docs/icarus/research/microstructure_sensor_grid/snapshots/ETF_REFERENCE_1M_20260928T1653Z.csv
- docs/icarus/research/microstructure_sensor_grid/STATE_CAPSULE.md

## NEXT COLLECTION TARGETS

1. Exact CME active-contract December 2026 NQ/MNQ, ES/MES, YM/MYM, RTY/M2K plus active GC/MGC VOI/settlement.
2. Licensed CME MDP 3.0 MBP/MBO and trade-summary packets with SecurityID and packet sequence.
3. Second crypto derivatives venue with synchronized depth, funding, OI, liquidations and trade tape.
4. CME/Cboe option chains with exact timestamp, bid/ask, IV, Greeks, volume and OI.
5. Raw-byte archival/checksums where licensing permits.
