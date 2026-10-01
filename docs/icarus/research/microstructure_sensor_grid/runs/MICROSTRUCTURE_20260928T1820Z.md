# Microstructure Sensor Grid — Collection Run

Run ID: ICARUS-MICRO-20260928T1820Z
Base checkpoint: ICARUS-MICRO-20260928T1740Z
Scope: collection and provenance only. No scoring, optimization, recommendations, execution, backtesting, or downstream model mutation.

## EVOLUTION SUMMARY

This run materially advances two collection planes:

1. Binance aggregate-trade coverage expanded from 100 to 1,000 continuity-verified records for BTCUSDT and ETHUSDT.
2. Exact CME prior-day open interest was collected from official settlement pages for nine of the ten target December 2026 contracts.

SOL 1,000-record paging and exact MGC prior-day OI remain unresolved and are preserved as explicit gaps.

## BINANCE 1,000-RECORD TAPE COVERAGE

Persisted summary:
- snapshots/BINANCE_AGGTRADES_1000_SUMMARY_20260928T1820Z.json

BTCUSDT:
- 1,000 consecutive aggregate IDs: 3468349446–3468350445.
- zero aggregate-ID gaps.
- event-time window: 1790619394996–1790619482873 ms (87.877 seconds).
- observed price range: 83,862.0–83,938.1.
- summed quantity: 70.719 BTC.
- m=true quantity: 32.768 BTC.
- m=false quantity: 37.951 BTC.
- largest aggregate: 10.721 BTC at aggregate ID 3468349838.

ETHUSDT:
- 1,000 consecutive aggregate IDs: 3102957908–3102958907.
- zero aggregate-ID gaps.
- event-time window: 1790619397088–1790619490937 ms (93.849 seconds).
- observed price range: 2,694.08–2,698.10.
- summed quantity: 1,141.027 ETH.
- m=true quantity: 623.273 ETH.
- m=false quantity: 517.754 ETH.
- largest aggregate: 90.685 ETH at aggregate ID 3102957935.

SOLUSDT:
- ten deterministic 100-record paging jobs were attempted.
- all were cancelled/deleted upstream before completion.
- prior 100-record durable raw tape remains authoritative.

Important provenance limitation:
- BTC and ETH 100-record source pages were complete conversation attachments and continuity was validated locally.
- This checkpoint persists the validated combined summary, but does not falsely claim a single combined raw 1,000-record repository blob.

## CME EXACT PRIOR-DAY OPEN INTEREST

Persisted:
- snapshots/CME_PRIOR_DAY_OI_20260925.csv

Official CME settlement pages, trade date Friday 25 Sep 2026:

| Contract | Settlement | CME estimated volume | Prior day OI |
|---|---:|---:|---:|
| NQZ6 | 30,889.25 | 534,590 | 271,967 |
| MNQZ6 | 30,889.25 | 2,486,228 | 131,840 |
| ESZ6 | 7,803.75 | 1,567,642 | 1,898,072 |
| MESZ6 | 7,803.75 | 1,114,922 | 125,245 |
| YMZ6 | 52,163 | 75,068 | 86,106 |
| MYMZ6 | 52,163 | 124,017 | 19,036 |
| RTYZ6 | 2,859.3 | 171,653 | 417,419 |
| M2KZ6 | 2,859.3 | 75,633 | 33,179 |
| GCZ6 | 4,321.2 | 140,092 | 317,452 |
| MGCZ6 | 4,321.2 | unavailable | unavailable |

MGC:
- official Micro Gold settlement page returned "There is currently no settlement data for this product."
- the Micro Gold overview page also did not expose a DEC 26 contract-level OI row.
- no OI was inferred.

## CME VOLUME CONFLICT / REVISION PROVENANCE

The official settlement pages label their volume column "Est. Volume".
The already-persisted Massive historical session aggregates expose a separate session-volume field.

Examples:
- NQZ6 CME estimated volume 534,590 vs Massive session volume 534,379.
- MNQZ6 2,486,228 vs 2,486,225.
- ESZ6 1,567,642 vs 1,566,409.
- MESZ6 1,114,922 vs 1,114,860.
- YMZ6 75,068 vs 75,050.
- RTYZ6 171,653 vs 171,638.
- GCZ6 140,092 vs 121,016.

These are preserved as distinct observations, not silently reconciled. The CME page itself identifies the value as estimated volume; Massive's historical session row is a different provider/data product.

## OPTIONS TERM-STRUCTURE STATUS

- Massive individual next-expiry option snapshots for QQQ/SPY/IWM were tested and remain NOT_ENTITLED.
- Cboe raw CDN access became intermittently unavailable through DataBlue in this run.
- prior bounded same-day Cboe IV/OI/Greeks remain valid as previously persisted.
- full next-expiry term/skew remains incomplete.
- no absent contract was inferred from extractor failure.

## QUALITY FLAGS

- DQ-BTC-ETH-1000-CONTINUITY-VERIFIED
- DQ-SOL-PAGING-CANCELLED
- DQ-CME-ESTIMATED-VOLUME
- DQ-CME-VOLUME-PROVIDER-CONFLICT
- DQ-MGC-OI-UNAVAILABLE
- DQ-OPTIONS-TERM-NOT-ENTITLED
- DQ-CBOE-CDN-ACCESS-DRIFT
- DQ-AGGTRADES-NOT-MBO

## CAPABILITY LEDGER

Successfully invoked:
- DataBlue Binance public aggregate-trade endpoint.
- Firecrawl rendered extraction of official CME settlement pages.
- Massive options endpoint discovery and individual next-expiry snapshot probes.
- GitHub repository surfaces.

Invoked but blocked/partial:
- SOL deterministic DataBlue pages: jobs cancelled/deleted.
- MGC official settlement page: no settlement data exposed.
- Massive option-contract snapshots: NOT_ENTITLED.
- Cboe CDN via DataBlue: intermittent network/circuit-breaker failure.

## NEXT COLLECTION TARGETS

1. Persist combined raw 1,000-record BTC/ETH pages as a single repository corpus if a lossless cross-tool file path is exposed.
2. Retry SOL 1,000-record paging under a healthy DataBlue session.
3. Find an official MGC contract-level OI source or keep it missing.
4. Reliable full next-expiry Cboe chain extraction.
5. Lawful liquidation event stream.
6. Licensed CME MDP 3.0 MBO/MBP.
