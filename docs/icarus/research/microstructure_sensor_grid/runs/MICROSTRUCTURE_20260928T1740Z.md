# Microstructure Sensor Grid — Collection Run

Run ID: ICARUS-MICRO-20260928T1740Z
Base checkpoint: ICARUS-MICRO-20260928T1730Z
Scope: collection and provenance only.

## PRIMARY EVOLUTION — DURABLE BINANCE TRADE TAPE

The prior checkpoint had Binance aggregate-trade metadata plus transient DataBlue full-result handles, but not durable raw repository copies.

This run closes that gap using the three full DataBlue result attachments surfaced in the conversation. The embedded base64 payload from each attachment was read directly and written as an immutable Git blob without relying on the truncated chat rendering.

Persisted raw source payloads:
- snapshots/BINANCE_BTCUSDT_AGGTRADES_RAW_20260928T1740Z.json
- snapshots/BINANCE_ETHUSDT_AGGTRADES_RAW_20260928T1740Z.json
- snapshots/BINANCE_SOLUSDT_AGGTRADES_RAW_20260928T1740Z.json

Normalized summary:
- snapshots/BINANCE_AGGTRADES_SUMMARY_20260928T1740Z.json

## RAW TAPE COVERAGE

BTCUSDT:
- 100 aggregate-trade records.
- aggregate IDs 3468308318 through 3468308417.
- event-time window 1790616370910–1790616378321 ms, span 7411 ms.
- observed price range 83956.5–83964.4.
- summed quantity 8.4 BTC.
- m=true quantity 3.085 BTC; m=false quantity 5.315 BTC.
- largest aggregate quantity 1.693 BTC at aggregate ID 3468308365.

ETHUSDT:
- 100 records.
- IDs 3102913945–3102914044.
- time window 1790616385113–1790616392041 ms, span 6928 ms.
- price range 2703.88–2704.30.
- summed quantity 180.063 ETH.
- m=true quantity 100.431 ETH; m=false quantity 79.632 ETH.
- largest aggregate 40.733 ETH at aggregate ID 3102913953.

SOLUSDT:
- 100 records.
- IDs 1101446810–1101446909.
- time window 1790616381552–1790616406117 ms, span 24565 ms.
- price range 119.69–119.77.
- summed quantity 4879.01 SOL.
- m=true quantity 3732.48 SOL; m=false quantity 1146.53 SOL.
- largest aggregate 751.92 SOL at aggregate ID 1101446853.

No trading interpretation is attached to these quantities. The Binance m flag is preserved raw; the summary reports only m=true versus m=false totals.

## PROVENANCE / HASH STATUS

Raw source Git blobs:
- BTCUSDT fdb540cbda8b86b805f53acce27bfae35dc95341
- ETHUSDT 6332ad88005b35f9f265f66e71cf1ba01472dceb
- SOLUSDT b26652d2e3eede38cd3b5adf8f9bd62d107014ff

The source payloads are exact decoded contents of the DataBlue full-result attachments, not reconstructed from truncated chat text.

Local decoded combined-corpus SHA-256 used during verification:
- ed8ffd7257b4dd9d4f2f773366866c48fc97d546bb7cb59a40621395b007f260

## QUALITY FLAGS

- DQ-AGGTRADE-NOT-ORDER-MESSAGE
- DQ-NO-MBO
- DQ-NO-LIQUIDATION-HISTORY
- DQ-SHORT-TAPE-WINDOW
- DQ-RAW-SOURCE-NOW-DURABLE
- DQ-M-FLAG-PRESERVED-NO-DIRECTIONAL-INFERENCE

## PERSISTENT PRIOR COVERAGE

The 1730Z checkpoint remains authoritative for:
- Binance depth, funding, current OI and 5-minute OI history.
- exact 2026-09-25 settlements for ten CME December contracts.
- bounded delayed Cboe same-day IV/OI/Greeks.
- known failures/entitlement limits.

## SUPERPOWERS STATUS

The user selected @Superpowers, but this runtime still exposes no callable Superpowers tool/connector. No usage claim is made.

## NEXT COLLECTION TARGETS

1. Extend durable Binance aggregate-trade tape windows beyond 100 records and align to book snapshots.
2. Find a lawful liquidation event stream.
3. Exact CME contract open interest.
4. Full Cboe next-expiry term/skew extraction.
5. CME options-on-futures Greeks.
6. Licensed CME MDP 3.0 MBO/MBP.
