# Microstructure Sensor Grid — Collection Run

Run ID: ICARUS-MICRO-20260928T1730Z
Base checkpoint: ICARUS-MICRO-20260928T1721Z
Scope: collection and provenance only. No scoring, ranking, recommendations, trading conclusions, execution, backtesting, optimization, or downstream-model mutation.

## EVOLUTION SUMMARY

This run extends three planes beyond the 1721Z checkpoint:

1. Binance USDⓈ-M: 5-minute open-interest history, ten funding settlements, and aggregate trade-tape access for BTCUSDT/ETHUSDT/SOLUSDT.
2. CME exact-contract history: complete official settlement fields for the 2026-09-25 session across NQZ6/MNQZ6, ESZ6/MESZ6, YMZ6/MYMZ6, RTYZ6/M2KZ6, GCZ6/MGCZ6.
3. Cboe delayed options: refreshed bounded same-day QQQ/SPY/IWM records with bid/ask, IV, OI, volume and Greeks. Full term structure remains uncollected.

## BINANCE DERIVATIVES EVOLUTION

Persisted:
- snapshots/BINANCE_OI_FUNDING_TAPE_20260928T1730Z.json

New data:
- 12 x 5-minute OI observations for BTCUSDT/ETHUSDT/SOLUSDT.
- 10 latest funding settlements for each symbol.
- Public aggregate-trade endpoint successfully returned 100 records per symbol.
- DataBlue agent-view output truncated those 100-record arrays, but returned transient full-result handles. Durable raw 100-trade payload archival is therefore still incomplete.
- Public REST liquidation-history probe at /fapi/v1/allForceOrders returned 404 for all three symbols and is not treated as a dataset.

Latest 5-minute OI endpoint values at timestamp 1790616300000:
- BTCUSDT 93,403.383 BTC; value field 7,844,115,112.603154 USDT.
- ETHUSDT 2,279,698.247 ETH; value field 6,172,077,406.772411 USDT.
- SOLUSDT 8,127,736.29 SOL; value field 974,271,749.0823 USDT.

No causal or directional interpretation is attached.

## CME EXACT-CONTRACT SETTLEMENT CORPUS

Persisted:
- snapshots/CME_SETTLEMENT_20260925.csv

All rows are exact December 2026 contracts and session_end_date 2026-09-25.

| Contract | Settlement | Volume | Transactions |
|---|---:|---:|---:|
| NQZ6 | 30,889.25 | 534,379 | 384,359 |
| MNQZ6 | 30,889.25 | 2,486,225 | 1,208,463 |
| ESZ6 | 7,803.75 | 1,566,409 | 455,563 |
| MESZ6 | 7,803.75 | 1,114,860 | 352,418 |
| YMZ6 | 52,163 | 75,050 | 52,262 |
| MYMZ6 | 52,163 | 124,017 | 67,466 |
| RTYZ6 | 2,859.3 | 171,638 | 91,390 |
| M2KZ6 | 2,859.3 | 75,633 | 40,138 |
| GCZ6 | 4,321.2 | 121,016 | 87,113 |
| MGCZ6 | 4,321.2 | 291,160 | 169,682 |

Important:
- These historical session rows contain settlement_price.
- The prior 2026-09-28 in-progress session aggregates did not contain populated settlement fields.
- Close and settlement remain distinct fields.
- Contract open interest is still not supplied by the accessible Massive aggregate endpoint.
- Massive real-time futures snapshot remains NOT_ENTITLED.

## CBOE OPTIONS EVOLUTION

Persisted:
- snapshots/CBOE_OPTIONS_SAMEDAY_20260928T1730Z.json

Official delayed Cboe chains are reachable for QQQ/SPY/IWM. Bounded records include bid/ask, sizes, IV, OI, volume, delta/gamma/theta/vega/rho and last-trade metadata.

The source files are multi-megabyte. Firecrawl explicitly warned that bounded query answers were generated from only the first processed portion of the page. Attempts to collect the nearest expiration after 2026-09-28 returned same-day contracts again, so:
- full skew is incomplete;
- term structure is incomplete;
- absence of a later-expiry record in the bounded answer is NOT evidence that the contract is absent upstream.

Massive's option-chain snapshot was separately tested and returned NOT_ENTITLED.

## SUPERPOWERS PLUGIN STATUS

The user explicitly selected @Superpowers. Runtime inventory found no callable tool or connector surface matching Superpowers in this chat, so it was not counted as used. No capability-use claim is made for it.

## QUALITY / PROVENANCE FLAGS

- DQ-BINANCE-AGGTRADE-TRANSIENT-RAW: 100-trade arrays returned but agent view truncated; full-result handles were transient.
- DQ-LIQUIDATION-ENDPOINT-404: guessed/public REST historical liquidation endpoint unavailable.
- DQ-CME-SETTLEMENT-HISTORICAL-FINAL: settlement populated for prior session only.
- DQ-CME-OI-MISSING: accessible futures aggregates do not expose contract OI.
- DQ-CBOE-DELAYED: options feed is delayed.
- DQ-CBOE-BOUNDED-PARTIAL: multi-megabyte source only partially processed by query extractor.
- DQ-CBOE-TERM-STRUCTURE-INCOMPLETE.
- DQ-MASSIVE-REALTIME-NOT-ENTITLED.
- DQ-NO-MDP3-MBO.

## ACCESS / CAPABILITY LEDGER

Successfully invoked:
- DataBlue public Binance REST endpoints.
- Massive Futures aggregate endpoints.
- Firecrawl bounded queries over official Cboe delayed option JSON.
- GitHub repository surfaces.

Invoked but unavailable / blocked:
- Binance /fapi/v1/allForceOrders: 404.
- Massive real-time futures snapshot: NOT_ENTITLED.
- Massive option-chain snapshot: NOT_ENTITLED.
- DataBlue LLM extraction: no LLM key configured.
- @Superpowers: selected by user but no callable runtime surface exposed.

Not retried:
- TickerLayer perpetual live data (known 403).
- U.S. Gold Bureau current request (known IP restriction).
- FactorWeave gated futures context.

## NEXT COLLECTION TARGETS

1. Durable raw storage of Binance aggregate-trade arrays and a lawful live liquidation stream if exposed.
2. Exact CME contract open interest from an official or licensed source.
3. CME MDP 3.0 MBP/MBO + trade-summary packets with SecurityID, sequence and exchange timestamps.
4. Cboe next-expiry bounded extraction through a source path that can traverse full chains reliably.
5. CME options-on-futures IV/Greeks through a licensed surface.
6. Provider raw bytes/checksums where access terms permit.
