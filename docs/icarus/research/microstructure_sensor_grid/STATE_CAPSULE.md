# Microstructure Sensor Grid — State Capsule

Last productive run: ICARUS-MICRO-20260928T1730Z
Run manifest: runs/MICROSTRUCTURE_20260928T1730Z.md

## Independent crypto derivatives state

Binance USDⓈ-M remains the independent second venue.
New persisted coverage:
- 12 x 5-minute OI history observations for BTCUSDT, ETHUSDT, SOLUSDT.
- latest 10 funding settlements for each.
- aggregate-trade endpoint returned 100 records per symbol; durable repository snapshot retains metadata and transient full-result handles, not the full 100-record arrays.
- liquidation-history REST probe /fapi/v1/allForceOrders returned 404.

Latest OI history observation @ 1790616300000:
- BTCUSDT 93403.383 BTC.
- ETHUSDT 2279698.247 ETH.
- SOLUSDT 8127736.29 SOL.

## CME state

Exact prior-session settlement corpus now complete for session_end_date 2026-09-25:
- NQZ6/MNQZ6 settlement 30889.25.
- ESZ6/MESZ6 settlement 7803.75.
- YMZ6/MYMZ6 settlement 52163.
- RTYZ6/M2KZ6 settlement 2859.3.
- GCZ6/MGCZ6 settlement 4321.2.

Current-session/in-progress close must never be substituted for settlement.
Contract OI remains missing from accessible Massive aggregate endpoints.
Massive real-time futures snapshot remains NOT_ENTITLED.

## Cboe options state

- Official delayed QQQ/SPY/IWM chains remain reachable.
- Persisted bounded same-day records include IV, OI, volume and Greeks.
- Attempts to obtain nearest later expiration via bounded query returned same-day rows due source truncation limits.
- Full skew and term structure remain incomplete.
- Massive option-chain snapshot remains NOT_ENTITLED.

## Superpowers status

User selected @Superpowers, but runtime inventory exposes no callable Superpowers tool/connector in this chat. Do not claim it was invoked.

## New artifacts

- snapshots/BINANCE_OI_FUNDING_TAPE_20260928T1730Z.json
- snapshots/CME_SETTLEMENT_20260925.csv
- snapshots/CBOE_OPTIONS_SAMEDAY_20260928T1730Z.json

## Persistent quality gates

- Keep venue/product/timestamp identities separate.
- Preserve Binance update IDs and event times when available.
- Do not infer liquidation history from absent REST endpoints.
- Never replace settlement with close.
- Never infer contract OI from volume.
- Treat Cboe bounded extraction as partial delayed data.
- Never infer full-chain absence from extractor omission.
- Do not infer MBO/queue behavior from price-level depth.
- Preserve entitlement/tooling failures.

## Access state

Usable:
- Bybit spot/linear/inverse.
- Binance public USDⓈ-M REST.
- Massive historical futures aggregates.
- Cboe official delayed options JSON through bounded Firecrawl query.
- Twelve Data selected reference endpoints.
- official CME/CFTC web.
- GitHub.

Blocked / partial:
- Binance historical liquidation REST path: 404.
- Massive real-time futures snapshot: NOT_ENTITLED.
- Massive option-chain snapshot: NOT_ENTITLED.
- TickerLayer perpetual live data: 403.
- DataBlue LLM extraction: no LLM API key.
- U.S. Gold Bureau: prior IP restriction.
- CME MDP 3.0: not exposed.
- Superpowers: no callable runtime surface exposed.

## Next targets

1. Durable Binance trade-tape raw capture and lawful liquidation event stream.
2. Exact-contract CME open interest.
3. CME MDP 3.0.
4. Reliable next-expiry Cboe chain slices.
5. CME options-on-futures IV/Greeks.
6. Raw payload/checksum archival.
