# Microstructure Sensor Grid — Collection Run

Run ID: ICARUS-MICRO-20260928T1642Z
Collection window represented: 2026-09-28T07:15:07Z–2026-09-28T16:42:00Z
Repository base before write: main @ 95ae2be0569baf07fea7888beb41d86e8e01d406
Scope: collection and provenance only. No scoring, recommendations, execution, backtesting, optimization, model promotion, or downstream-system mutation.

## CONTINUITY / RECOVERY STATUS

Two earlier productive writes (07:15Z and 16:36Z) were interrupted before their repository transactions completed. Direct remote verification at the start of this run showed neither run file existed and STATE_CAPSULE.md still pointed to ICARUS-MICRO-20260928T0650Z. This checkpoint therefore recovers the verified in-chat observations and adds a fresh reference-market slice. No prior unverified write is claimed.

## NEW / RECOVERED MICROSTRUCTURE SOURCES

### Recovered 07:15Z normalized connector observations

- BTCUSDT linear BBO @ 07:15:07.202Z: 83048.30 x 1.653 / 83048.40 x 4.394.
- BTCUSDT spot BBO @ 07:15:07.753Z: 83082.5 x 0.596321 / 83082.6 x 0.186017.
- BTCUSDT funding: -0.00001867 (-0.001867%), next settlement then 08:00Z.
- ETHUSDT linear BBO @ 07:15:10.437Z: 2646.06 x 30.27 / 2646.07 x 86.66.
- ETHUSDT spot BBO @ 07:15:10.758Z: 2647.60 x 1.85951 / 2647.61 x 13.01527.
- ETHUSDT funding: -0.00003038 (-0.003038%).
- SOLUSDT linear BBO @ 07:15:14.204Z: 118.520 x 394.1 / 118.530 x 273.9.
- SOLUSDT spot BBO @ 07:15:14.680Z: 118.57 x 17.505 / 118.58 x 32.4568.
- SOLUSDT funding: +0.0000978 (+0.00978%).
- TickerLayer BTCUSD composite BBO @ 07:15:18.386Z: 83079.05 x 10.01825 / 83079.06 x 0.49946.
- TickerLayer BTCUSD last trade @ 07:15:19.092Z: 83050.70 x 0.00066802.

These recovered records are timestamped historical observations from successful connector calls in this loop. They were not re-retrieved and are labeled as recovered, not current.

### Fresh 16:36Z crypto spot/perpetual snapshot

Full normalized returned depth and funding are persisted in:
snapshots/CRYPTO_BOOKS_FUNDING_20260928T163645Z.json

| Corpus ID | Provider | Instrument | Event time UTC | BBO |
|---|---|---|---|---|
| MICRO-BYBIT-BTCUSDT-LIN-L2-20260928T163645002Z | Bybit | BTCUSDT linear perpetual | 16:36:45.002 | 83935.40 x 0.230 / 83935.50 x 5.395 |
| MICRO-BYBIT-BTCUSDT-SPOT-L2-20260928T163645553Z | Bybit | BTCUSDT spot | 16:36:45.553 | 83972.1 x 0.463845 / 83972.2 x 0.086887 |
| MICRO-BYBIT-ETHUSDT-LIN-L2-20260928T163646837Z | Bybit | ETHUSDT linear perpetual | 16:36:46.837 | 2691.92 x 120.41 / 2691.93 x 10.00 |
| MICRO-BYBIT-ETHUSDT-SPOT-L2-20260928T163647358Z | Bybit | ETHUSDT spot | 16:36:47.358 | 2692.85 x 13.24442 / 2692.86 x 10.03296 |
| MICRO-BYBIT-SOLUSDT-LIN-L2-20260928T163648404Z | Bybit | SOLUSDT linear perpetual | 16:36:48.404 | 119.720 x 59.0 / 119.730 x 406.0 |
| MICRO-BYBIT-SOLUSDT-SPOT-L2-20260928T163649083Z | Bybit | SOLUSDT spot | 16:36:49.083 | 119.76 x 45.4438 / 119.77 x 46.7478 |
| MICRO-TL-BTCUSD-BBO-20260928T163651048Z | TickerLayer composite | BTCUSD | 16:36:51.048 | 83955.15 x 0.74913 / 83955.16 x 13.63319 |
| MICRO-TL-ETHUSD-BBO-20260928T163652145Z | TickerLayer composite | ETHUSD | 16:36:52.145 | 2692.12 x 21.8499 / 2692.13 x 11.192 |
| MICRO-TL-SOLUSD-BBO-20260928T163652768Z | TickerLayer composite | SOLUSD | 16:36:52.768 | 119.74 x 205.108 / 119.75 x 374.626 |

Returned Bybit books again contained 10 levels/side despite a 50-level request. These are aggregated price levels, not MBO.

### Derived provenance checks, not raw market data

- BTC linear vs spot mid basis: -36.70 USDT, -4.3705 bps; source timestamps separated by 551 ms.
- ETH linear vs spot mid basis: -0.93 USDT, -3.4536 bps; separation 521 ms.
- SOL linear vs spot mid basis: -0.04 USDT, -3.3399 bps; separation 679 ms.
- Returned 10-level normalized depth imbalance:
  - BTC linear -0.166524; BTC spot +0.396569.
  - ETH linear +0.802981; ETH spot +0.187111.
  - SOL linear +0.142072; SOL spot +0.225079.
These values describe only the returned static slice and do not identify queue position, hidden orders, cancellations, sweeps, or future behavior.

## FUNDING COVERAGE

Fresh Bybit linear-perpetual funding observed during the 16:36Z slice:
- BTCUSDT +0.0001 (+0.0100%).
- ETHUSDT +0.0001 (+0.0100%).
- SOLUSDT +0.0001 (+0.0100%).
- Connector-provided next settlement timestamp for all three: 1790640000000 ms = 2026-09-29T00:00:00Z.

This preserves a time-series transition from the recovered 07:15Z observations (BTC and ETH negative; SOL +0.00978%) to +0.0100% across all three. No causal or trading interpretation is attached.

## ETF / CASH-REFERENCE PLANE

Twelve Data authentication succeeded. Current full-quote reference snapshots at provider last_quote_at 1790613720 = 2026-09-28T16:42:00Z:

| Proxy | Futures family reference | Close/last field | Day high | Day low | Volume | Previous close | Market open |
|---|---|---:|---:|---:|---:|---:|---|
| QQQ | NQ/MNQ / Nasdaq-100 | 737.65 | 741.41 | 731.65 | 479,708 | 744.50 | true |
| SPY | ES/MES / S&P 500 | 767.095 | 769.535 | 763.74 | 814,394 | 771.34998 | true |
| DIA | YM/MYM / Dow | 515.09 | 516.49 | 513.40 | 30,127 | 517.48999 | true |
| IWM | RTY/M2K / Russell 2000 | 280.155 | 281.41 | 278.80 | 911,145 | 281.97 | true |

These are ETF proxies/reference markets, not CME futures prices.

### One-minute reference bars

Normalized returned 1-minute bars are persisted in:
snapshots/ETF_REFERENCE_1M_20260928T1642Z.csv

- QQQ: 30 returned bars from 12:12–12:41 exchange-local display time; continuous 1-minute timestamps; high 740.355, low 735.32, summed returned volume 118,953.
- SPY: 30 returned bars from 12:12–12:41; continuous 1-minute timestamps; high 769.535, low 765.32, summed returned volume 177,633.
- DIA: 30 returned observations spanning 12:07–12:41; high 516.49, low 513.96, summed returned volume 10,705. Returned clock gaps are present from 12:12→12:16 and 12:37→12:40. No interpolation was performed.
- IWM 1-minute series retrieval was blocked after the connection exhausted its per-minute API-credit allowance. IWM quote coverage remains available but 1-minute coverage is incomplete.

Twelve Data U.S. market-state response reported NYSE/NASDAQ/ARCA and several other U.S. venues open at collection time. Its exchange_schedule endpoint was separately attempted for NASDAQ and NYSE and blocked because that endpoint requires Ultra or Enterprise.

## CME ROLL / REVISION METADATA

Official CME roll-date reference:
https://www.cmegroup.com/trading/equity-index/rolldates.html

For U.S. equity-index quarterly futures:
- September 2026 expiration: 2026-09-18.
- Customary September roll date: 2026-09-14.
- December 2026 expiration: 2026-12-18.
- Customary December roll date: 2026-12-14.
- CME states the customary lead month after roll is the second-nearest expiration.

This is a symbol-mapping gate: after the September customary roll, December is ordinarily the lead month, but every market-data join still requires the exact source contract symbol/security identifier.

Official CME VOI revision rule:
https://www.cmegroup.com/market-data/volume-open-interest.html
- End-of-day Daily Volume and Open Interest Report is preliminary.
- Official data is released in the Daily Bulletin the following morning.

Daily Bulletin timing reference:
https://www.cmegroup.com/market-data/daily-bulletin.html
- Preliminary bulletin updates around 12:00 a.m. CT next business day.
- Final bulletin updates around 10:00 a.m. CT next business day.

No exact active-contract CME VOI/settlement values were inferred from reference pages.

## CFTC POSITIONING — NEW FUTURES + OPTIONS COMBINED CORPORA

Observation date: 2026-09-22. These are delta-adjusted option-and-futures combined populations and are distinct from the previously persisted futures-only series.

CME source:
https://www.cftc.gov/dea/options/deacmesof.htm

COMEX source:
https://www.cftc.gov/dea/options/deacmxsof.htm

| Market / code | Combined OI | Non-commercial long | Non-commercial short | Spreads |
|---|---:|---:|---:|---:|
| Bitcoin / 133741 | 22,952 | 17,698 | 14,993 | 3,794 |
| Micro Bitcoin / 133742 | 39,911 | 23,866 | 29,887 | 7,360 |
| E-mini S&P 500 / 13874A | 2,715,529 | 220,522 | 331,446 | 558,649 |
| Micro E-mini S&P 500 / 13874U | 139,379 | 24,676 | 37,090 | 5,362 |
| Nasdaq Mini / 209742 | 329,896 | 87,822 | 31,409 | 36,129 |
| Micro E-mini Nasdaq-100 / 209747 | 122,452 | 37,238 | 74,462 | 2,665 |
| Russell E-mini / 239742 | 424,881 | 82,354 | 157,917 | 16,410 |
| Micro E-mini Russell 2000 / 239747 | 33,875 | 15,777 | 11,007 | 118 |
| Gold / 088691 | 571,291 | 246,102 | 28,355 | 170,114 |
| Micro Gold / 088695 | 98,429 | 41,214 | 65,127 | 5,153 |

Population/revision checks:
- Do not sum combined and futures-only COT datasets.
- Micro Gold combined OI is 98,429 while futures-only OI is 98,428, demonstrating that even nearly identical rows can differ because the combined population includes delta-adjusted options.
- NQ combined OI 329,896 differs materially from prior futures-only 286,321; MNQ combined 122,452 differs from futures-only 119,984.

## GOLD ACCESS STATE

A fresh U.S. Gold Bureau call was attempted and failed:
FORBIDDEN — Unauthorized: request not from allowed IP address.

No current gold spot value was collected. The prior persisted gold observation remains historical and was not forward-filled. This is recorded as connector access-state drift.

## ORDER-FLOW / DEPTH COVERAGE

New:
- BTC/ETH/SOL spot + linear-perpetual 10-level normalized price books.
- QQQ/SPY/DIA 1-minute cash-reference bars; IWM quote-only due provider credit cap.

Still absent:
- live CME MBO/MBP packets;
- order IDs / PriorityID / queue changes;
- exchange packet sequence numbers;
- individual crypto trade tape;
- liquidations and venue OI;
- CME block tape and auction imbalance;
- options IV/skew/term structure/Greeks.

No sweep, iceberg, spoofing, or large-trade signatures were inferred from static snapshots.

## LATENCY / FRESHNESS

- Bybit spot-perp timestamp separation: BTC 551 ms; ETH 521 ms; SOL 679 ms.
- TickerLayer references followed corresponding Bybit linear snapshots by roughly 4.4–6.0 seconds; retain as asynchronous references only.
- Twelve Data quote last_quote_at resolves to 16:42:00Z.
- ETF bar display timestamps are provider-formatted exchange-local clock values; quote epoch timestamp is the normalization anchor.
- CFTC remains weekly with intentional observation-to-publication lag.
- CME roll/VOI pages are reference metadata, not streaming market observations.

## GAPS / ACCESS LIMITS

- CME live MDP/MBO and contract-level current VOI/settlement were not exposed through a licensed connected feed.
- Twelve Data exchange_schedule endpoint requires Ultra/Enterprise.
- Twelve Data IWM 1-minute request exceeded the current per-minute credit allowance (9 credits used versus limit 8).
- U.S. Gold Bureau fresh spot call blocked by allowed-IP policy.
- FactorWeave futures/VX desired actions remain tier-gated from the prior verified state and were not repeatedly invoked.
- Massive authorization-gated path was not retried.
- No second crypto derivatives venue exposing comparable books/funding/OI/liquidations was available in the selected connected set.
- Normalized connectors did not expose provider-signed raw payload bytes/checksums.

## DUPLICATES / CONFLICTS / QUALITY FLAGS

- BTCUSD/ETHUSD/SOLUSD composite references are separate products from Bybit USDT spot/perpetual instruments.
- Spot and perpetual books are not duplicates.
- 50 requested Bybit levels yielded 10 returned levels: DQ-PARTIAL-DEPTH.
- DIA one-minute response contains clock gaps: DQ-SPARSE-BAR-RETURN.
- IWM minute series missing due credit cap: DQ-PROVIDER-CREDIT-GAP.
- Gold source unavailable in this run: DQ-GOLD-ACCESS-DRIFT.
- CFTC combined and futures-only populations differ: DQ-COT-POPULATION-DIFFERENCE.
- CME preliminary/final VOI revision semantics: DQ-CME-PRELIMINARY-FINAL-REVISION.
- Cross-provider quote comparisons are asynchronous: DQ-CROSS-SOURCE-TIME-SKEW.
- Exact futures contract joins require contract-month/security mapping: DQ-CONTRACT-ROLL-MAPPING.
- No raw upstream checksums: DQ-NORMALIZED-NO-RAW-HASH.

## CAPABILITY LEDGER

Successfully invoked this continuation:
- GitHub read/Git-data write surfaces.
- Bybit BTC/ETH/SOL order books and funding.
- TickerLayer BTC/ETH/SOL independent BBOs.
- Twelve Data authentication, QQQ/SPY/DIA/IWM quotes, QQQ/SPY/DIA 1-minute series, and U.S. market state.
- Official CME public web evidence for roll dates and VOI/Daily Bulletin revision semantics.
- Official CFTC public combined reports for CME and COMEX.

Invoked but blocked/partial:
- Twelve Data exchange_schedule: Ultra/Enterprise required.
- Twelve Data IWM 1-minute history: per-minute credits exhausted.
- U.S. Gold Bureau current spot: allowed-IP authorization failure.

Not invoked because redundant or previously blocked:
- FactorWeave tier-gated futures/VX endpoints.
- FMP paid COT endpoint; CFTC official source was superior.
- Massive auth-gated path.
- Additional generic web scrapers where official CME/CFTC sources were already sufficient.

Numeric effort control is not exposed; deepest available safe verification was used.

## PERSISTED ARTIFACTS

- docs/icarus/research/microstructure_sensor_grid/runs/MICROSTRUCTURE_20260928T1642Z.md
- docs/icarus/research/microstructure_sensor_grid/snapshots/CRYPTO_BOOKS_FUNDING_20260928T163645Z.json
- docs/icarus/research/microstructure_sensor_grid/snapshots/ETF_REFERENCE_1M_20260928T1642Z.csv
- docs/icarus/research/microstructure_sensor_grid/STATE_CAPSULE.md

## NEXT COLLECTION TARGETS

1. Licensed exact-contract CME December 2026 NQ/MNQ, ES/MES, YM/MYM, RTY/M2K market data plus active GC/MGC months.
2. CME MDP 3.0 MBO/MBP + trade-summary packets with SecurityID, packet sequence, event/sending time, OrderID/PriorityID.
3. Second crypto derivatives venue for synchronized books, funding, open interest, liquidations, and trade tape.
4. Cboe/CME option chains with exact snapshot time, bid/ask, IV, Greeks, volume, and OI.
5. Raw-byte preservation/checksums where licensing allows.
