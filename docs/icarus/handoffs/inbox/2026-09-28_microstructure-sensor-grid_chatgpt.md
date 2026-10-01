# Microstructure Sensor Grid — historical loop handoff

SOURCE_LOOP=Microstructure Sensor Grid
PRODUCER=ChatGPT historical-loop migration
CAPTURE_DATE=2026-09-28
PINNED_REPO_REVISION=449aef107bb868d1f18ab7eddc2bf4c3398f783b
EXECUTION_AUTHORIZED=false
SENSITIVITY=PUBLIC_SAFE
CLASSIFICATION=COLLECTION_PIPELINE
SNAPSHOT_STATUS=ACTIVE_AT_MASTER_HANDOFF
OWNERSHIP=Venue microstructure / derivatives / options collection

## Mission
Collect venue-native microstructure, derivatives, order-flow, options and settlement evidence with exact timestamps and venue semantics, without trade conclusions.

## Durable repo evidence
- 069f4e638aaaf08d563a58d33c09f9f413989bbf — extended Binance OI/funding tape, CME settlements, Cboe Greeks.
- f35705948be2040f3219fb87c10dff2193fcc003 — durably archived Binance aggregate-trade tapes.

1730Z artifacts included BINANCE_OI_FUNDING_TAPE_20260928T1730Z.json, CME_SETTLEMENT_20260925.csv and CBOE_OPTIONS_SAMEDAY_20260928T1730Z.json.

1740Z fixed a persistence gap by committing complete 100-record Binance USDⓈ-M aggregate-trade arrays for BTCUSDT, ETHUSDT and SOLUSDT plus summary.

## Known gaps
Exact CME contract OI unavailable; Binance historical liquidation route returned 404; full Cboe next-expiry term/skew incomplete; Cboe delayed/bounded. Field m is preserved raw and not interpreted as a trading signal.

## Next
Extend trade tapes and align to books; lawful liquidation stream; exact CME OI; complete Cboe term/skew.

## Preservation boundary
Repository evidence outranks chat summaries. Historical test counts/hashes are historical evidence unless re-run on the current revision. No sibling system is merged or overwritten. No broker/order authority is granted. EXECUTION_AUTHORIZED=false.
