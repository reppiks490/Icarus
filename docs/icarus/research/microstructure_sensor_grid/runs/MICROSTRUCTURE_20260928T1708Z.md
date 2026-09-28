# Microstructure Sensor Grid — Collection Run

Run ID: ICARUS-MICRO-20260928T1708Z
Collection window: 2026-09-28T17:08:47.953Z–2026-09-28T17:08:50.551Z
Scope: collection and provenance only. No coding, scoring, ranking, recommendations, execution, trading, backtesting, optimization, model promotion, or downstream-system mutation.

## NEW DERIVATIVES / MICROSTRUCTURE PLANE

This run adds a new same-venue, cross-contract construction corpus for BTC, ETH and SOL:
1. spot USDT pair;
2. USDT-linear perpetual;
3. USD-inverse perpetual.

Full normalized books, instrument rules, funding and unit metadata are persisted in:
snapshots/CRYPTO_SPOT_LINEAR_INVERSE_20260928T1708Z.json

### Near-synchronous BBO observations

| Asset | Product | Source time UTC | BBO | Quantity unit |
|---|---|---|---|---|
| BTC | BTCUSDT spot | 17:08:47.953 | 83589.3 / 83589.4 | BTC |
| BTC | BTCUSDT linear perpetual | 17:08:48.402 | 83542.8 / 83542.9 | BTC |
| BTC | BTCUSD inverse perpetual | 17:08:48.005 | 83521.0 / 83521.1 | USD contracts |
| ETH | ETHUSDT spot | 17:08:49.358 | 2682.66 / 2682.67 | ETH |
| ETH | ETHUSDT linear perpetual | 17:08:49.237 | 2681.61 / 2681.62 | ETH |
| ETH | ETHUSD inverse perpetual | 17:08:49.466 | 2679.78 / 2679.79 | USD contracts |
| SOL | SOLUSDT spot | 17:08:50.480 | 118.61 / 118.62 | SOL |
| SOL | SOLUSDT linear perpetual | 17:08:50.404 | 118.55 / 118.56 | SOL |
| SOL | SOLUSD inverse perpetual | 17:08:50.551 | 118.45 / 118.52 | USD contracts |

All three asset triplets were captured within sub-second source-time spreads:
- BTC: 449 ms.
- ETH: 229 ms.
- SOL: 147 ms.

## DERIVED CROSS-PRODUCT BASIS CHECKS

Derived only for provenance and contract-mapping diagnostics:

| Asset | Linear minus spot | Inverse minus spot | Inverse minus linear |
|---|---:|---:|---:|
| BTC | -46.50 USD-equivalent / -5.563 bps | -68.30 / -8.171 bps | -21.80 / -2.609 bps |
| ETH | -1.05 / -3.914 bps | -2.88 / -10.736 bps | -1.83 / -6.824 bps |
| SOL | -0.06 / -5.058 bps | -0.13 / -10.960 bps | -0.07 / -5.904 bps |

These are same-venue cross-product observations, not independent-venue lead/lag measurements and not trading signals.

## CONTRACT-UNIT / SETTLEMENT PROVENANCE

Official Bybit documentation verified through browser retrieval:

1. Introduction to Inverse Perpetual and Expiry Contracts
   https://www.bybit.com/en/help-center/article/Introduction-to-Inverse-Contract
   - inverse contracts are quoted in USD and settled in the underlying asset;
   - position/contract value is calculated in USD equivalent and settlement occurs in the underlying coin.

2. Order Cost (Perpetual and Expiry Contracts)
   https://www.bybit.com/en/help-center/article/Order-Cost-USDT-Contract
   - inverse order quantity is in USD;
   - Bybit states 1 inverse contract = 1 USD;
   - inverse contract value in the underlying coin depends on price.

3. P&L Calculations — Inverse Contracts
   https://www.bybit.com/en/help-center/article/Profit-Loss-calculations-Inverse-Contracts
   - inverse P&L is settled in coin type rather than USD.

4. FAQ — USDT Perpetual and Expiry Contracts
   https://www.bybit.com/en/help-center/article/FAQ-USDT-Perpetual-and-Expiry-Contracts
   - USDT perpetual margin/P&L settlement uses USDT, unlike inverse perpetual settlement in underlying cryptocurrency.

Accordingly:
- spot quantities are stored in underlying token units;
- USDT-linear book quantities are stored in underlying token units;
- USD-inverse book quantities are stored as USD contract quantities and MUST NOT be summed or compared directly with token quantities without an explicit conversion using the appropriate price.

No cross-unit depth aggregation was performed.

## INSTRUMENT SPECS

Bybit connector-reported trading parameters:

| Contract | Tick | Qty step | Minimum qty | Maximum leverage |
|---|---:|---:|---:|---:|
| BTCUSDT linear | 0.10 | 0.001 BTC | 0.001 BTC | 150x |
| BTCUSD inverse | 0.10 | 1 USD contract | 1 contract | 100x |
| ETHUSDT linear | 0.01 | 0.01 ETH | 0.01 ETH | 150x |
| ETHUSD inverse | 0.01 | 1 USD contract | 1 contract | 100x |
| SOLUSDT linear | 0.01 | 0.1 SOL | 0.1 SOL | 100x |
| SOLUSD inverse | 0.01 | 1 USD contract | 1 contract | 50x |

These are exchange rules/reference metadata only and are not recommendations.

## FUNDING COVERAGE

USDT-linear funding observed in the same run:
- BTCUSDT: +0.00006467 (+0.006467%; connector display +0.0065%).
- ETHUSDT: +0.0001 (+0.0100%).
- SOLUSDT: +0.0001 (+0.0100%).
- next connector funding timestamp: 2026-09-29T00:00:00Z.

The available Bybit funding connector only exposes USDT-linear symbols in this runtime. Inverse-perpetual funding was not collected; no value was inferred.

## SECOND-DERIVATIVES-FEED ACCESS CHECK

TickerLayer symbol discovery successfully identified:
- BTCUSDT perpetual, source_count 6;
- ETHUSDT perpetual, source_count 6;
- SOLUSDT perpetual, source_count 6.

However, snapshot, quote and last-trade calls for all three perpetuals returned:
403 Forbidden — perpetuals access not enabled for this account.

Therefore:
- TickerLayer perpetual symbol metadata is available;
- TickerLayer live perpetual market data is not available on this connection;
- the second independent live derivatives venue/provider gap remains open.

No fallback value was invented.

## ORDER-FLOW / DEPTH COVERAGE

New:
- Bybit spot, linear and inverse price-level books for BTC/ETH/SOL;
- explicit quantity-unit schema for each product;
- inverse contract rules and settlement semantics;
- near-synchronous cross-product timestamp offsets.

Still absent:
- market-by-order identifiers;
- queue changes/cancel-add-modify event streams;
- exchange packet sequence numbers;
- individual trade tape;
- open interest;
- liquidations;
- block trades;
- options IV/skew/Greeks;
- licensed CME MDP data.

No sweeps, icebergs, spoofing, or large-trade classifications were inferred.

## LATENCY / FRESHNESS

- BTC spot/linear/inverse source timestamps span 449 ms.
- ETH span 229 ms.
- SOL span 147 ms.
- These are sufficiently close for provenance-level cross-product comparison but are not atomic snapshots.
- TickerLayer perpetual market-data access failure has no market observation timestamp and is stored as an access event, not a market record.

## GAPS / CONFLICTS / DUPLICATES

- USDT-linear and USD-inverse contracts have different quantity/settlement conventions; raw depth quantities are not directly comparable.
- Same-venue spot/linear/inverse price differences are preserved separately.
- Bybit requested 50 book levels but normalized connector responses exposed 10 levels/side.
- TickerLayer symbol discovery and TickerLayer data entitlement differ: symbols visible, live perpetual data forbidden.
- No raw upstream packet/file checksum was exposed by market connectors.
- No independent second derivatives venue has yet been collected.

## LICENSING / ACCESS LIMITS

Succeeded:
- Bybit public normalized spot/linear/inverse order books;
- Bybit linear and inverse instrument specifications;
- Bybit USDT-linear funding;
- TickerLayer perpetual symbol discovery;
- official Bybit help-center browser verification;
- GitHub persistence surface.

Blocked:
- TickerLayer live perpetual quotes/snapshots/trades: plan entitlement disabled.
- CME live MDP/MBO: not exposed.
- cross-venue OI/liquidation feed: not exposed.
- options analytics: not exposed.

## DATA QUALITY FLAGS

- DQ-PARTIAL-DEPTH
- DQ-NO-MBO
- DQ-CROSS-CONTRACT-UNIT-MISMATCH
- DQ-CROSS-PRODUCT-NONATOMIC
- DQ-TICKERLAYER-PERPETUAL-ENTITLEMENT
- DQ-NORMALIZED-NO-UPSTREAM-RAW-HASH
- DQ-NO-INVERSE-FUNDING-ENDPOINT
- DQ-NO-SECOND-LIVE-DERIVATIVES-VENUE

## PROVENANCE / HASH STATUS

- Exact provider/product/source timestamp encoded in the snapshot.
- Unit system and settlement type explicitly recorded.
- Browser-verified primary-source URLs recorded for inverse-contract semantics.
- Raw provider payload bytes/signatures were not exposed.
- Git blob SHA provides content-addressed persistence for the normalized snapshot.
- No interpolation, forward-fill, product-unit coercion, or downstream model mutation occurred.

## PERSISTED ARTIFACTS

- docs/icarus/research/microstructure_sensor_grid/runs/MICROSTRUCTURE_20260928T1708Z.md
- docs/icarus/research/microstructure_sensor_grid/snapshots/CRYPTO_SPOT_LINEAR_INVERSE_20260928T1708Z.json
- docs/icarus/research/microstructure_sensor_grid/STATE_CAPSULE.md

## NEXT COLLECTION TARGETS

1. A genuinely independent second derivatives venue/provider with live depth, funding, OI, liquidations and trade tape.
2. Exact-contract CME December 2026 NQ/MNQ, ES/MES, YM/MYM, RTY/M2K plus active GC/MGC VOI/settlement.
3. Licensed CME MDP 3.0 MBP/MBO/trade summary with SecurityID, OrderID/PriorityID and packet sequence.
4. CME/Cboe option chains with timestamp, bid/ask, IV, Greeks, volume and OI.
5. Inverse-perpetual funding history through an authorized endpoint if exposed.
6. Raw-byte/provider checksum preservation where licensing permits.

Numeric effort control is not exposed; deepest available safe verification was used.
