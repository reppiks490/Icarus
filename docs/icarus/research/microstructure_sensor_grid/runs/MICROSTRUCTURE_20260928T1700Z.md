# Microstructure Sensor Grid — Collection Run

Run ID: ICARUS-MICRO-20260928T1700Z
Scope: collection and provenance only; no scoring, recommendations, execution, backtesting, optimization, model promotion, or downstream-system mutation.

## NEW DERIVATIVES / CONTRACT-CONSTRUCTION COVERAGE

This run adds near-synchronous Bybit spot, USDT-linear perpetual, and USD-inverse perpetual observations for BTC, ETH, and SOL.

Full normalized snapshot:
- snapshots/CRYPTO_SPOT_LINEAR_INVERSE_20260928T1700Z.json

| Asset | Spot BBO | USDT-linear BBO | USD-inverse BBO | Max spot-to-derivative timestamp offset |
|---|---|---|---|---:|
| BTC | 83656.6 / 83656.7 | 83614.90 / 83615.00 | 83586.80 / 83586.90 | 252 ms |
| ETH | 2685.11 / 2685.12 | 2683.76 / 2683.77 | 2682.27 / 2682.28 | 508 ms |
| SOL | 119.04 / 119.05 | 118.970 / 118.980 | 118.86 / 118.96 | 1324 ms |

## DERIVED PRICE-BASIS CHECKS

Derived from BBO midpoints only; no trading conclusion:

- BTC: linear-minus-spot -4.9840 bps; inverse-minus-spot -8.3436 bps; inverse-minus-linear -3.3607 bps.
- ETH: linear-minus-spot -5.0277 bps; inverse-minus-spot -10.5770 bps; inverse-minus-linear -5.5518 bps.
- SOL: linear-minus-spot -5.8793 bps; inverse-minus-spot -11.3402 bps; inverse-minus-linear -5.4633 bps.

These are same-venue, different-product observations. They are not cross-venue lead-lag measurements.

## FUNDING

USDT-linear funding:
- BTCUSDT +0.00006796 (+0.006796%).
- ETHUSDT +0.0001 (+0.0100%).
- SOLUSDT +0.0001 (+0.0100%).
- Connector next funding timestamp: 2026-09-29T00:00:00Z.

The exposed funding endpoint is linear-perpetual only; inverse funding was not available through this connector and was not inferred.

## INVERSE CONTRACT METADATA

Bybit inverse instruments exposed:
- BTCUSD: tick 0.10 USD, qty step 1 contract, min order 1, max leverage 100.
- ETHUSD: tick 0.01 USD, qty step 1 contract, min order 1, max leverage 100.
- SOLUSD: tick 0.01 USD, qty step 1 contract, min order 1, max leverage 50.

Critical unit gate:
- spot/linear depth quantities are returned in base-asset units;
- inverse depth quantities are returned as contract counts;
- raw depth sizes are therefore not directly comparable across these product classes.

No contract-value field was exposed in the normalized response, so no inverse depth was converted into base-asset or USD-equivalent size.

## SECOND-VENUE ACCESS TEST

TickerLayer perpetual symbol discovery succeeded:
- BTCUSDT perpetual, source_count 6.
- ETHUSDT perpetual, source_count 6.
- SOLUSDT perpetual, source_count 6.

However, snapshot/quote/last-trade calls for all three returned 403:
"perpetuals access not enabled for your account".

Therefore TickerLayer cannot be counted as a second live derivatives feed in this run. Symbol discovery is metadata only.

## ORDER-FLOW / DEPTH COVERAGE

New:
- three-way product structure for BTC/ETH/SOL: spot vs linear perpetual vs inverse perpetual.
- inverse contract specifications and timestamped BBOs.

Still absent:
- independent second-venue derivative book;
- open interest and liquidation feeds;
- individual trade tape;
- MBO queue identifiers/events;
- options IV/skew/Greeks.

No sweep, iceberg, spoofing, queue, or large-trade classifications were inferred.

## LATENCY / FRESHNESS

Near-synchronous source timestamps:
- BTC spot/linear 49 ms apart; spot/inverse 252 ms.
- ETH spot/linear 279 ms; spot/inverse 508 ms.
- SOL spot/linear 1324 ms; spot/inverse 470 ms.

SOL linear comparison is less synchronous than BTC/ETH and is explicitly flagged for cross-product time skew.

## QUALITY FLAGS

- DQ-PARTIAL-DEPTH: 50 levels requested; 10 returned per side.
- DQ-INVERSE-UNIT-INCOMPATIBILITY: inverse contract counts cannot be merged with base-asset depth.
- DQ-CROSS-PRODUCT-TIME-SKEW: products are near-synchronous, not atomic.
- DQ-TICKERLAYER-PERPETUAL-403: symbol metadata exposed; live perpetual data disabled.
- DQ-NORMALIZED-NO-UPSTREAM-RAW-HASH.
- DQ-NO-SECOND-DERIVATIVES-VENUE.

## CAPABILITY LEDGER

Succeeded:
- Bybit spot, linear and inverse order books.
- Bybit inverse instrument metadata and price/24h fields.
- Bybit linear funding.
- TickerLayer perpetual symbol discovery.
- GitHub persistence surface.

Blocked:
- TickerLayer perpetual snapshot, BBO and trade calls: 403, perpetuals access not enabled.

Not invoked:
- ExoScope chart/browser UI because it does not expose the raw depth/OI/liquidation fields required for this collection gap.
- CoinGecko because aggregate spot market data would not close the derivatives-venue gap.
- previously tier/auth-blocked providers where no new capability state was indicated.

## PROVENANCE / HASH STATUS

- Provider, exact symbol, product class and source timestamp are preserved.
- Raw provider bytes/checksums unavailable; normalized records are persisted as content-addressed Git blobs.
- Derived midpoint/basis fields are separate from observed BBOs.
- No unit conversion was performed where contract value was unavailable.

## PERSISTED ARTIFACTS

- docs/icarus/research/microstructure_sensor_grid/runs/MICROSTRUCTURE_20260928T1700Z.md
- docs/icarus/research/microstructure_sensor_grid/snapshots/CRYPTO_SPOT_LINEAR_INVERSE_20260928T1700Z.json
- docs/icarus/research/microstructure_sensor_grid/STATE_CAPSULE.md

## NEXT COLLECTION TARGETS

1. A genuinely independent second crypto derivatives venue with synchronized depth, funding, OI, liquidations and trade tape.
2. Exact CME active-contract December 2026 equity-index VOI/settlement and active GC/MGC data.
3. Licensed CME MDP 3.0 MBO/MBP and trade-summary packets.
4. CME/Cboe options chains with exact timestamp, bid/ask, IV, Greeks, volume and OI.
5. Raw payload/checksum preservation where licensing allows.
