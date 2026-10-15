# ICARUS 200-asset market and feed integration contract

**Date:** 2026-10-15
**Owner:** Codex (A200 specification)
**Status:** Contract for implementation handoff; shared registry/feed files remain unclaimed pending the parallel asset worker's reservation.

## Goal

Make a 200-instrument universe genuinely usable by the Pulse runtime. A symbol in a list is not a connected asset. Each asset must have a canonical identity, an eligible price source, a qualified historical/live bar path, market metadata used for sizing and session logic, and observable health. Data must be routed into Pulse without presenting coverage as strategy proof.

## Five distinct states

Every instrument has exactly one current lifecycle state:

1. **CATALOGED** — identity and instrument metadata are complete and source candidates are declared.
2. **SOURCE_CONNECTED** — the provider is reachable and the required entitlement is present.
3. **BARS_QUALIFIED** — historical and live bars pass schema, timestamp, ordering, freshness, gap, duplicate, session, and symbol-identity checks.
4. **PULSE_ENABLED** — the runtime has validated tick/lot value, currency, calendar/session, contract multiplier, costs, point scaling, and a compatible preset/input profile.
5. **STRATEGY_QUALIFIED** — that asset/setup has passed preregistered TUNE/HOLD and forward evidence requirements.

The first four states establish data and runtime readiness. They do not imply the fifth. A market feed, a data receipt, or 200 enabled symbols cannot make Pulse a champion.

## Canonical instrument record

Each row needs a stable internal `instrument_id` independent of ticker spelling and at least:

- display symbol, canonical provider symbol, venue/exchange, asset class, instrument type, underlying where applicable;
- quote currency, timezone, market calendar, session template, holiday schedule, and timezone-aware session boundaries;
- minimum price increment, lot/share/contract size, point value or contract multiplier, and source for each value;
- primary and fallback provider IDs, product codes, supported history intervals, supported live transport, entitlement state, and provider's terms/retention classification;
- corporate-action adjustment policy for equities/funds, and continuous/dated-contract plus roll policy for futures;
- execution profile: commission, exchange/regulatory costs, expected slippage model and their effective dates;
- feed status, last source event time, last received time, delay, missing/duplicate/reordered bar counters, and last validation receipt.

Every field affecting a price, timestamp, size, or return must be sourced or marked `UNKNOWN`; no guessed tick values, multipliers, calendars, or fallbacks are allowed. Provider symbols that refer to different economic instruments must not be merged under a ticker alias.

## Meaning of "fully connected"

The acceptance report counts instruments separately in these sets:

- `catalogued_count`;
- `entitlement_verified_count`;
- `historical_bars_qualified_count`;
- `live_bars_qualified_count`;
- `pulse_enabled_count`;
- `strategy_qualified_count`.

The release target is 200 distinct catalogued identities and source receipts proving the promised connection tier for each. It must report the other counts honestly. It must not say “200 connected” when only metadata exists or only a subset has bars. If credentials or entitlements are absent, the row remains present with an explicit blocked status and no synthetic fill-in.

## Price and analytical source separation

Pulse execution/research bars require a source that returns authentic OHLCV for that instrument, with bar interval, market timestamp, receive timestamp, source identity, and session definition. Analytical feeds (options flow, gamma exposure, dark-pool prints, analyst data, sentiment, fundamentals) are a separate typed context plane. They can inform a later preregistered feature experiment, but they cannot replace price bars or be represented as complete asset price history.

Feed selection must be capability-based per asset, not a single provider name assumed to cover every market. A source must declare `historical_bars`, `live_bars` or live events, resolutions, lookback, market coverage, timestamp basis, adjustment policy, delay, and entitlement/plan requirements. The provider is selected from qualified capabilities for the instrument and requested interval; if no source qualifies, Pulse remains disabled for that asset.

## Unusual Whales source assessment

The connected Unusual Whales API tools and public API documentation were inspected for this contract:

- Stock OHLC route: [`GET /api/stock/{ticker}/ohlc/{candle_size}`](https://api.unusualwhales.com/docs/operations/PublicApi.TickerController.ohlc). It supports 1m through 4h plus daily/weekly candles and caps responses at 2,500 rows. Intraday is newest-first and the newest bar can still be forming. Consumers must order by `start_time`, exclude or explicitly mark a still-forming bar, and account for the lookback cap.
- Intraday stock candle tools support regular, premarket, and postmarket sessions. Those session choices and the tool's returned windows do not establish unrestricted archival history or real-time entitlement for every one of 200 tickers.
- Futures route: [`GET /api/futures/{contract}/candles`](https://api.unusualwhales.com/docs/operations/PublicApi.FuturesController.candles) is documented for dated CME contracts. The API description says it requires Advanced API or a futures add-on. It does not by itself establish access to continuous histories, roll-adjusted bars, or all futures contracts.
- The API data-stream playbook describes a WebSocket at `wss://api.unusualwhales.com/socket?token=...`, requires a successful join acknowledgement, buffering/flush, reconnect, and rejoining. It recommends ticker-scoped channels; the global `option_trades` channel is described as 6–10 million records per day. Do not subscribe to that firehose for this integration.
- The official examples inspected were [net-premium ticks dashboard](https://github.com/unusual-whales/api-examples/tree/main/examples/net-prem-ticks-dashboard) and [multi-channel WebSocket stream](https://github.com/unusual-whales/api-examples/tree/main/examples/ws-multi-channel-multi-output). They demonstrate a useful options-flow/context layer and buffering patterns.

**Conclusion:** Unusual Whales is valuable as an options/flow/context provider for supported symbols. Its published OHLC limits and product/entitlement constraints do not make it the universal canonical bar feed for 200 mixed instruments. Its role and bar use must be qualified per product. No new key or paid entitlement was requested or added for this assessment.

## Bar contract at the Pulse boundary

Before a provider bar enters aggregation or strategy state, validate:

- exact canonical instrument identity and a declared provider mapping;
- finite prices/volume, `low <= min(open, close) <= max(open, close) <= high`, valid price tick, and nonnegative volume where applicable;
- UTC event/bar start and end, receive time recorded separately, monotonic order, non-overlap, expected interval, and forming/closed status;
- provider session and market-calendar alignment; missing bars are gaps, never synthesized flat bars;
- no duplicate bar is applied twice; reconnect/backfill replay is idempotent;
- a source switch produces an explicit provenance boundary and never silently blends incompatible adjustments, sessions, or symbols.

Every accepted batch carries a source receipt with provider, instrument, interval, requested window, received range, row count, dropped/duplicate/gap counts, checksum, entitlement state, and fetch/receive times. Raw provider terms determine whether bars may be stored; licensed raw rows must remain outside public git.

## 200-asset rollout

1. Parallel worker supplies its exact 200 identities, asset classes, provider codes, current branch/PR, and file reservations.
2. Resolve metadata conflicts and source coverage in a manifest; accept no row whose execution-critical metadata is unknown.
3. Validate provider capability and actual account entitlement per row. A provider's API documentation alone is not account entitlement.
4. Load a representative slice from every asset class into an isolated feed test and verify raw timestamp/session/identity contracts.
5. Enable progressively by asset and provider health, with concurrency/rate limits and clear quarantine for stale, denied, malformed, or gapped feeds.
6. Run identical Pulse logic as research-only across enabled assets. Keep asset and portfolio exposure, correlated positions, fees, and risk limits explicit; do not infer one asset's evidence from another.
7. Require preregistered, out-of-sample and prospective evidence per candidate setup before calling any asset/setup qualified.

## Acceptance tests for the implementation

- Exactly 200 unique stable identities, no accidental alias/duplicate count, and all required metadata either sourced or blocking Pulse enablement.
- For every row, a capability and entitlement result distinguishes historical, live, delayed, and unsupported paths.
- Test every source adapter against recorded fixtures for ordering, pagination, rate-limit retry/backoff, malformed records, timezones, DST/session edges, empty/denied responses, symbol mismatch, duplicates, gaps, and reconnect replay.
- A provider outage or entitlement failure quarantines only affected assets; it cannot switch silently to synthetic or stale bars.
- End-to-end readback proves each enabled source receipt reaches the correct Pulse asset without cross-symbol contamination.
- A 200-asset soak verifies bounded memory, subscription/request counts, API limits, freshness reporting, recovery, and deterministic restart behavior.
- Results report source/connection counts and data limitations; they never modify champion or execution-authority state.

## Parallel-work reservation

This document claims only itself. The asset worker owns its current instrument source/catalog files until a file-level handoff is agreed. Codex takes the Pulse runtime/feed adapters and end-to-end consumer path only after its source IDs, schema, and branches are known. Unusual Whales is treated as a source candidate with the limits above, not silently assigned as the canonical feed.
