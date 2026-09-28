# Microstructure Sensor Grid — Collection Run

Run ID: ICARUS-MICRO-20260928T1721Z
Scope: collection/provenance only. No coding, backtesting, optimization, scoring, trade decisions, orders, model promotion, or downstream-system mutation.

## NEW INDEPENDENT CRYPTO DERIVATIVES VENUE

A genuinely independent second venue is now captured: Binance USDⓈ-M Futures public REST.

Persisted artifact:
- snapshots/BINANCE_USDM_DEPTH_FUNDING_OI_20260928T1707Z.json

### Binance BTCUSDT
- depth transaction time: 2026-09-28T17:07:14.437Z
- update ID: 11681769027814
- 20-level BBO: 83600.00 / 83600.10
- returned 20-level bid qty: 3.720 BTC
- returned 20-level ask qty: 10.759 BTC
- normalized depth imbalance: -0.486152
- mark: 83603.55271014
- index: 83643.18608696
- mark-minus-index: -4.738387 bps
- funding: +0.00006884
- open interest: 93,910.062 BTC
- next funding timestamp: 2026-09-29T00:00:00Z

### Binance ETHUSDT
- depth transaction time: 2026-09-28T17:07:26.227Z
- update ID: 11681770217939
- BBO: 2684.00 / 2684.01
- returned bid qty: 143.548 ETH
- returned ask qty: 16.339 ETH
- depth imbalance: +0.795618
- mark: 2684.10712403
- index: 2685.27441860
- mark-minus-index: -4.347022 bps
- funding: +0.00007693
- open interest: 2,274,323.759 ETH

### Binance SOLUSDT
- depth transaction time: 2026-09-28T17:07:36.721Z
- update ID: 11681771524263
- BBO: 118.6900 / 118.7000
- returned bid qty: 41,684.65 SOL
- returned ask qty: 31,010.73 SOL
- depth imbalance: +0.146831
- mark: 118.71000000
- index: 118.75622035
- mark-minus-index: -3.892036 bps
- funding: +0.00007131
- open interest: 8,169,730.88 SOL

This closes the prior "second derivatives venue" gap for depth, funding and OI. Public REST liquidation history was not captured; no private/authenticated endpoint was sought.

## CROSS-VENUE STATUS

The previously persisted Bybit 17:08Z product plane and Binance 17:07Z observations are temporally close but not atomic. They are retained as cross-venue lead-lag candidates only, with a clock-skew gate; no causal lead-lag relationship is asserted.

## EXACT CME TARGET CONTRACT SESSION CORPUS

Massive Futures returned session aggregates for all ten target December 2026 contracts for session_end_date 2026-09-28:

| Contract | Open | High | Low | Close field | Transactions | Volume |
|---|---:|---:|---:|---:|---:|---:|
| NQZ6 | 30870 | 30920.75 | 30356.75 | 30568.75 | 363481 | 500472 |
| MNQZ6 | 30871.5 | 30920.75 | 30356.5 | 30569 | 1164536 | 2343241 |
| ESZ6 | 7796 | 7803 | 7726 | 7756.25 | 355435 | 1137987 |
| MESZ6 | 7795.75 | 7803.25 | 7726 | 7757.25 | 296351 | 901889 |
| YMZ6 | 52140 | 52153 | 51744 | 51931 | 42943 | 58465 |
| MYMZ6 | 52141 | 52154 | 51743 | 52055 | 60009 | 106134 |
| RTYZ6 | 2857.7 | 2858.8 | 2826.8 | 2851.1 | 72468 | 127582 |
| M2KZ6 | 2859.3 | 2859.3 | 2826.8 | 2851.2 | 42114 | 92140 |
| GCZ6 | 4315 | 4315.6 | 4143.1 | 4171.9 | 129885 | 185643 |
| MGCZ6 | 4315 | 4320 | 4143 | 4172 | 213934 | 373133 |

Persisted artifact:
- snapshots/CME_TARGET_SESSION_20260928.csv

Quality gate: this session was still in progress when collected. Massive's returned aggregate did not include a populated settlement_price or open-interest field, so the "close" column is NOT promoted to official settlement and no contract OI is inferred.

Massive real-time Futures Snapshot was separately attempted and returned NOT_ENTITLED. Exact contract VOI/official settlement therefore remains partially open.

## CBOE OPTIONS IV / GREEKS / OI CORPUS

Cboe official delayed JSON chains for QQQ, SPY and IWM were collected. The raw files are multi-megabyte, so bounded Firecrawl query extraction was used. Firecrawl explicitly warned that each source was too long to process in full.

Persisted artifact:
- snapshots/CBOE_OPTIONS_ATM_20260928T1721Z.json

### QQQ 2026-09-28 bounded strike slice
- 735C IV .2229, delta .7478, gamma .0980, OI 1,208, volume 259,229.
- 735P IV .2240, delta -.2522, gamma .0980, OI 7,590, volume 337,292.
- 736C IV .2154, delta .6449, gamma .1180, OI 1,349, volume 228,735.
- 736P IV .2173, delta -.3551, gamma .1180, OI 3,550, volume 221,610.
- 737C IV .2116, delta .5222, gamma .1292, OI 1,295, volume 219,618.
- 737P IV .2124, delta -.4778, gamma .1292, OI 5,171, volume 183,361.
- 738C IV .2091, delta .3929, gamma .1262, OI 1,267, volume 277,130.
- 738P IV .2100, delta -.6071, gamma .1262, OI 25,551, volume 177,483.
A bounded prior query identified 2026-09-29 as the next QQQ expiration, but a safe next-expiry contract slice was not extracted.

### SPY 2026-09-28 bounded slice
- 766C/P IV .1737; call delta .6247, put delta -.3753; OI 1,320 / 3,229.
- 767C/P IV .1686; call delta .4741, put delta -.5259; OI 2,600 / 3,308.

### IWM 2026-09-28 bounded slice
- 279C IV .2080, delta .8216, gamma .2259, OI 508, volume 20,912.
- 279P IV .2046, delta -.1784, gamma .2259, OI 1,897, volume 97,550.

These are a bounded local strike surface, not a complete skew or term-structure corpus. Term structure remains incomplete and is explicitly flagged.

## CAPABILITY / ACCESS LEDGER

Successfully invoked:
- Binance public USDⓈ-M endpoints through DataBlue for depth, premium/mark/index/funding and OI.
- Massive Futures aggregate API for all ten exact target contracts.
- Cboe official delayed options JSON through DataBlue for source/feed metadata.
- Firecrawl bounded-query extraction for Cboe QQQ/SPY/IWM option records.
- Official CME public web material for settlement methodology/reference context.
- GitHub read/write persistence.

Partial / blocked:
- Massive real-time Futures Snapshot: NOT_ENTITLED.
- Massive Option Chain Snapshot: NOT_ENTITLED.
- Massive Futures contract-batch metadata request: one exact-filter call was blocked by safety middleware; session aggregate calls succeeded.
- Massive per-plan rate limit interrupted the first aggregate batch; missing contracts were successfully collected on a later bounded batch.
- DataBlue LLM extraction: blocked because no LLM API key is configured.
- DataBlue async extraction-status reconciliation failed.
- Firecrawl structured JSON extraction failed; query mode succeeded.
- Cboe guessed per-contract JSON URL was not a valid/reachable endpoint.
- Cboe full-chain bounded query is explicitly partial due source size.

## DATA QUALITY FLAGS

- DQ-BINANCE-MBP-NOT-MBO
- DQ-CROSS-VENUE-CLOCK-NOTALIGNED
- DQ-NO-LIQUIDATION-REST-CAPTURE
- DQ-CME-SESSION-IN-PROGRESS
- DQ-CME-NO-SETTLEMENT-FIELD
- DQ-CME-NO-CONTRACT-OI-FIELD
- DQ-MASSIVE-REALTIME-NOT-ENTITLED
- DQ-CBOE-DELAYED
- DQ-CBOE-BOUNDED-EXTRACTION
- DQ-CBOE-TERM-STRUCTURE-INCOMPLETE
- DQ-CBOE-SOURCE-TIMESTAMP-TZ-UNEXPLICIT
- DQ-NORMALIZED-NO-UPSTREAM-RAW-HASH

## PROVENANCE / HASH STATUS

Source URLs, exact product symbols, exchange timestamps/update IDs and raw-vs-derived status are retained in the snapshot artifacts. Normalized public JSON was persisted as Git content-addressed blobs. No contradictory observation was overwritten or silently reconciled.

## NEXT COLLECTION TARGETS

1. Binance or another lawful public source for liquidation-event history that does not require private credentials.
2. Official prior-day CME contract settlement and contract-level OI for the ten target tickers.
3. Licensed CME MDP 3.0 MBO/MBP/trade-summary packets with SecurityID, sequence and exchange timestamps.
4. Cboe next-expiry bounded slices for QQQ/SPY/IWM to complete term structure.
5. Futures options / CME options Greeks and IV where licensed.
6. Raw upstream payload archival/checksums where licensing and tooling allow.

Numeric effort control is not exposed by this runtime; deepest available safe verification was used.
