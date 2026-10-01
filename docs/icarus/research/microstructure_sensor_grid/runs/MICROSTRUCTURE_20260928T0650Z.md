# Microstructure Sensor Grid — Collection Run

Run ID: ICARUS-MICRO-20260928T0650Z
Retrieval window: 2026-09-28T06:51:38Z–2026-09-28T06:52:xxZ
Scope: collection and provenance only; no scoring, recommendations, execution, backtest, optimization, or downstream mutation.

## NEW MICROSTRUCTURE SOURCES

### Venue snapshots

| Corpus ID | Provider / venue | Instrument | Source event time (UTC) | Granularity | Raw observations | Access |
|---|---|---|---|---|---|---|
| MICRO-BYBIT-BTCUSDT-LIN-L2-20260928T065138602Z | Bybit | BTCUSDT linear perpetual | 2026-09-28T06:51:38.602Z | returned top 10 price levels/side (50 requested) | best bid 83093.20 x 3.944 BTC; best ask 83093.30 x 0.787 BTC; spread 0.10 USDT | public plugin; provider warns data may be delayed/incomplete |
| MICRO-BYBIT-BTCUSDT-SPOT-L2-20260928T065138553Z | Bybit | BTCUSDT spot | 2026-09-28T06:51:38.553Z | returned top 10 price levels/side (50 requested) | best bid 83130.00 x 0.266682 BTC; best ask 83130.10 x 0.222303 BTC; spread 0.10 USDT | public plugin; provider warns data may be delayed/incomplete |
| MICRO-TL-BTCUSD-BBO-20260928T065153273Z | TickerLayer composite | BTCUSD | 2026-09-28T06:51:53.273Z | top of book | bid 83143.32 x 1.54487; ask 83143.33 x 7.73283 | connected quote service; composite venue mapping |
| MICRO-BYBIT-BTCUSDT-LIN-1M-20260928T0333Z-0652Z | Bybit | BTCUSDT linear perpetual | 2026-09-28T03:33:00Z–06:52:00Z | 200 one-minute OHLCV candles | high 83489.4; low 82650.0; start open 83184.1; end close 83106.8; volume 8375.889 BTC | public plugin |
| MICRO-USGB-XAU-SPOT-20260928T015144Z | United States Gold Bureau | XAU spot, USD/oz | source timestamp 2026-09-28T01:51:44Z | top of book | bid 4173.08; ask 4187.46; connector marked areStale=false | connected spot service; timeliness conflict noted |

### Derived, explicitly non-raw observations

- Bybit linear mid 83093.25 versus Bybit spot mid 83130.05: perpetual-minus-spot basis = -36.80 USDT, or -4.43 bps. Source timestamps differ by 49 ms.
- Returned 10-level linear depth: bid 6.518 BTC, ask 0.805 BTC; normalized imbalance (bid-ask)/(bid+ask) = +0.780.
- Returned 10-level spot depth: bid 0.421370 BTC, ask 0.361504 BTC; normalized imbalance = +0.076.
- TickerLayer composite mid 83143.325 was 13.275 USD (+1.60 bps) above the Bybit spot mid 14.720 seconds earlier. Preserve as a venue/time/basis disagreement, not an error.
- The latest 06:52 one-minute candle was still inside its formation minute at retrieval and is flagged provisional.

## NEW DATASET / CORPUS IDS

1. MICRO-BYBIT-BTCUSDT-LIN-L2-20260928T065138602Z
2. MICRO-BYBIT-BTCUSDT-SPOT-L2-20260928T065138553Z
3. MICRO-TL-BTCUSD-BBO-20260928T065153273Z
4. MICRO-BYBIT-BTCUSDT-LIN-1M-20260928T0333Z-0652Z
5. MICRO-USGB-XAU-SPOT-20260928T015144Z
6. CFTC-COT-CME-FUTURES-2026-09-22
7. CFTC-COT-CMX-FUTURES-2026-09-22
8. CME-CONTRACT-METADATA-RETRIEVED-2026-09-28
9. CME-MBO-SEMANTICS-RETRIEVED-2026-09-28

## INSTRUMENT / TIMEFRAME COVERAGE

Official CME contract metadata collected:

| Root | Contract unit | Minimum tick | Tick value | Source |
|---|---:|---:|---:|---|
| NQ | USD 20 x Nasdaq-100 | 0.25 index point | USD 5.00 | https://www.cmegroup.com/markets/equities/nasdaq/e-mini-nasdaq-100.contractSpecs.html |
| MNQ | USD 2 x Nasdaq-100 | 0.25 | USD 0.50 | https://www.cmegroup.com/markets/equities/nasdaq/micro-e-mini-nasdaq-100.html |
| ES | USD 50 x S&P 500 | 0.25 | USD 12.50 | https://www.cmegroup.com/markets/equities/sp/e-mini-sandp500.html |
| MES | USD 5 x S&P 500 | 0.25 | USD 1.25 | https://www.cmegroup.com/markets/equities/sp/micro-e-mini-sandp-500.html |
| YM | USD 5 x DJIA | 1.00 | USD 5.00 | https://www.cmegroup.com/markets/equities/dow-jones/e-mini-dow.contractSpecs.html |
| MYM | USD 0.50 x DJIA | 1.00 | USD 0.50 | https://www.cmegroup.com/education/courses/micro-e-mini-futures/micro-e-mini-futures-products-overview |
| RTY | USD 50 x Russell 2000 | 0.10 | USD 5.00 | https://www.cmegroup.com/education/courses/learn-about-e-mini-russell-2000-futures/reasons-to-trade-e-mini-russell-2000-futures-over-russell-2000-etf |
| M2K | USD 5 x Russell 2000 | 0.10 | USD 0.50 | https://www.cmegroup.com/markets/equities/russell/micro-e-mini-russell-2000.html |
| GC | 100 troy ounces | USD 0.10/oz | USD 10.00 | https://www.cmegroup.com/markets/metals/precious/gold.contractSpecs.html |
| MGC | 10 troy ounces | USD 0.10/oz | USD 1.00 | https://www.cmegroup.com/markets/metals/precious/e-micro-gold.contractSpecs.html |

CME equity-index futures standard session reference: Sunday–Friday 17:00–16:00 CT with daily 16:00–17:00 CT maintenance halt. Contract-specific holidays and special closes remain a calendar join requirement.

Bybit BTCUSDT instrument metadata: Trading; tick size 0.10 USDT; minimum and quantity step 0.001 BTC; maximum order quantity 1500 BTC; leverage range 1–150. Metadata is rules-only and not a recommendation.

## ORDER-FLOW / DEPTH COVERAGE

- Captured Bybit spot and linear price-level books. This is aggregated market-by-price depth, not market-by-order data. No participant identity is present.
- CME official MBO semantics collected: MBO exposes anonymous individual OrderID and PriorityID, full depth, and queue ordering; MBP consolidates quantity/order counts and is capped at ten price levels. CME-held native iceberg refreshes retain OrderID; synthetic/ISV-held refreshes arrive as new orders.
- No CME live MBO packet stream, queue events, trade summary messages, time-and-sales, block tape, or auction imbalance feed was available in this run.
- No sweep or large-trade labels were inferred from static books.

CME MBO source: https://www.cmegroup.com/articles/faqs/market-by-order-mbo.html

## DERIVATIVES / OPTIONS / OI / FUNDING COVERAGE

- Bybit BTCUSDT funding: -0.00002075 per interval (-0.002075%, plugin display -0.0021%); next settlement 2026-09-28T08:00:00Z. This is venue-specific, not cross-exchange funding.
- No direct Bybit open-interest, liquidation, trade tape, options IV/skew/term structure, or Greeks endpoint was exposed.
- FactorWeave VX term structure and market context calls failed because MCP access requires HOBBY tier or higher; no value was collected.
- FMP COT list call failed because the endpoint requires Premium/Ultimate/Enterprise; official CFTC pages were used instead.
- U.S. Gold Bureau top-of-book was collected, but its source timestamp lagged retrieval by approximately five hours despite areStale=false.

## CFTC / POSITIONING COVERAGE

Official futures-only reports observed 2026-09-22 and scheduled for release 2026-09-25 at 15:30 ET:

| Market / CFTC code | Open interest | Non-commercial long | Non-commercial short | Spreads | Notes |
|---|---:|---:|---:|---:|---|
| Bitcoin (5 BTC), 133741 | 22,315 | 17,658 | 14,902 | 3,307 | CME |
| Micro Bitcoin, 133742 | 35,597 | 23,629 | 29,654 | 3,583 | CME |
| E-mini S&P 500, 13874A | 1,890,653 | 218,043 | 351,271 | 34,061 | CME |
| Nasdaq Mini (NQ), 209742 | 286,321 | 88,507 | 32,357 | 4,624 | CME |
| Micro E-mini Nasdaq-100, 209747 | 119,984 | 36,802 | 74,844 | 1,351 | CME |
| Gold (100 oz), 088691 | 412,800 | 253,982 | 28,129 | 48,923 | COMEX |
| Micro Gold (10 oz), 088695 | 98,428 | 41,214 | 65,127 | 5,153 | COMEX |

Observation date and release date are intentionally separate. CFTC explains that Tuesday positions are generally released Friday; 2026 schedule lists September 25.

Sources:
- https://www.cftc.gov/dea/futures/deacmesf.htm
- https://www.cftc.gov/dea/futures/deacmxlf.htm
- https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm

## LATENCY / FRESHNESS

| Dataset | Source time | Retrieval relation | Status |
|---|---|---|---|
| Bybit linear vs spot books | 49 ms apart | near-synchronous | usable for instantaneous venue basis, subject to plugin delay disclaimer |
| TickerLayer BTCUSD BBO | 14.720 s after Bybit books | asynchronous | do not treat difference as pure venue spread |
| Bybit 1m bars | through 06:52Z | latest bar provisional | 200 timestamps; no duplicates; no non-60-second gaps |
| U.S. Gold Bureau | 01:51:44Z | ~5 hours behind run | freshness flag conflict |
| CFTC COT | observation 09/22; release 09/25 | weekly | expected publication lag, not stale error |

## GAPS

- NQ/MNQ, ES/MES, YM/MYM, RTY/M2K, GC/MGC live futures trades, quotes, book depth, roll curve, options IV/skew/Greeks, exchange volume/OI and block data were not available.
- CME MBO historical/live entitlement is absent; only public semantics were collected.
- BTC coverage lacks venue trade tape, liquidations, open interest, inverse contracts, options, cross-venue books and latency telemetry.
- No exchange calendar snapshot or holiday exception file was captured; only baseline session hours.
- No raw source payload archive was created because connectors returned normalized response objects, not downloadable signed files.

## CONFLICTS

1. BTCUSD composite mid exceeded Bybit spot mid by 1.60 bps at a 14.720-second offset. Retained without adjudication.
2. Bybit linear mid was 4.43 bps below Bybit spot mid at near-synchronous times. Retained as venue basis.
3. Gold connector asserted areStale=false while its source timestamp was ~5 hours old. Marked stale-status contradiction.
4. Requested Bybit depth was 50 levels per side; connector returned only 10 levels per side. Coverage is labeled returned-10, not requested-50.
5. CFTC COT aggregates positions across contract months; it is not directly comparable with a single active-contract open-interest series.

## DUPLICATES

- No duplicate timestamps in the 200 one-minute Bybit bar window.
- Spot and linear BTCUSDT records are distinct venue products, not duplicates.
- CFTC consolidated and contract-specific records must not be summed without mapping controls; this run stores only explicit contract rows plus source identities.
- No payload-level near-duplicate test was possible across normalized connectors because raw downloadable bodies were not exposed.

## LICENSING / ACCESS LIMITS

- Bybit and TickerLayer: connected normalized public data; provider disclaimers apply and redistribution terms were not surfaced.
- CME: public product and MBO documentation only; real-time/historical exchange market data requires appropriate licensing and entitlements.
- CFTC: public U.S. government reports.
- FactorWeave: HOBBY-tier gate blocked VX and market-context retrieval.
- FMP: Premium/Ultimate/Enterprise gate blocked COT retrieval.
- Massive, Twelve Data, CoinGecko, Exum/ExoScope, DataBlue, Firecrawl, Tavily, Exa and Parallel Search were exposed but not invoked because they did not improve the selected official/venue evidence set for this run.
- No direct CME, CFTC API connector, licensed MBO vendor, or options analytics feed was exposed.

## PROVENANCE / HASH STATUS

- Immutable identities use provider + instrument + data class + source timestamp/date.
- Source payload hashes: unavailable from Bybit, TickerLayer, U.S. Gold Bureau and web evidence connectors.
- Repository persistence uses Git blob/tree/commit content addressing. Blob and commit SHA values are recorded by the repository transaction.
- Raw versus derived status is explicit: BBOs/books/bars/COT rows are observed connector or official-source fields; basis, imbalance and continuity checks are derived in this run.
- No forward-fill, interpolation, security ranking, signal generation or recommendation was performed.

## DATA QUALITY FLAGS

- DQ-PARTIAL-DEPTH: requested 50, received 10 levels/side.
- DQ-PROVISIONAL-BAR: 06:52Z bar may be incomplete.
- DQ-CROSS-SOURCE-TIME-SKEW: TickerLayer vs Bybit comparison separated by 14.720 seconds.
- DQ-STALE-FLAG-CONFLICT: gold source time ~5 hours old while areStale=false.
- DQ-NORMALIZED-NO-RAW-HASH: connectors did not expose raw downloadable bodies.
- DQ-COT-AGGREGATION: weekly, multi-expiry aggregation; not active-contract OI.
- DQ-NO-CME-LIVE: official CME metadata only, not real-time market data.
- DQ-SYMBOL-MAPPING: BTCUSDT linear, BTCUSDT spot and BTCUSD composite are separate instruments/denominations.

## CAPABILITY LEDGER

Succeeded:
- Capability Orchestrator skill preflight.
- Superpowers usage guidance.
- Bybit: orderbook, funding, instrument metadata and one-minute bars.
- TickerLayer: independent BTCUSD BBO.
- U.S. Gold Bureau: XAU spot BBO.
- Native web research: official CME and CFTC sources.
- GitHub: repository discovery/read and persistence transaction.

Connected but blocked:
- FactorWeave VX term structure, market context and futures list: HOBBY tier required.
- FMP COT: Premium/Ultimate/Enterprise required.

Not exposed for the needed action:
- direct CME live/MDP/MBO feed, licensed historical MBO corpus, live CFTC API connector, options IV/Greeks feed, futures roll/term-structure feed, and venue-level liquidation/OI endpoints.

Numeric effort control was not exposed; the run used the deepest safe analysis available.

## PERSISTED LOCATIONS

- docs/icarus/research/microstructure_sensor_grid/runs/MICROSTRUCTURE_20260928T0650Z.md
- docs/icarus/research/microstructure_sensor_grid/STATE_CAPSULE.md

## NEXT COLLECTION TARGETS

1. Licensed CME MDP 3.0 MBO/MBP and trade-summary captures for NQ/MNQ, ES/MES, YM/MYM, RTY/M2K, GC/MGC with packet sequence, SecurityID, contract month and exchange timestamps.
2. CME daily volume/OI and settlement files by exact contract month, plus roll calendars and holiday exceptions.
3. BTC cross-venue synchronized trades/books, open interest, liquidations and funding from at least two derivative venues with source-clock offsets.
4. CME/Cboe options chains with bid/ask, IV, Greeks, OI, volume and exact snapshot timestamps.
5. Raw artifact preservation with provider-issued checksums or locally computed hashes where licensing permits.
