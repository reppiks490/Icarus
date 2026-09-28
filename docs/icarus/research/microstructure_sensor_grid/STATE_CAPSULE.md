# Microstructure Sensor Grid — State Capsule

Last productive run: ICARUS-MICRO-20260928T1700Z
Run manifest: runs/MICROSTRUCTURE_20260928T1700Z.md

## Latest cross-product crypto state

Bybit near-synchronous product plane:
- BTC spot BTCUSDT 83656.6/83656.7; linear BTCUSDT 83614.90/83615.00; inverse BTCUSD 83586.80/83586.90.
- ETH spot ETHUSDT 2685.11/2685.12; linear ETHUSDT 2683.76/2683.77; inverse ETHUSD 2682.27/2682.28.
- SOL spot SOLUSDT 119.04/119.05; linear SOLUSDT 118.970/118.980; inverse SOLUSD 118.86/118.96.

Linear funding:
- BTC +0.00006796.
- ETH +0.0001.
- SOL +0.0001.
- next timestamp 2026-09-29T00:00:00Z.

## Inverse contract metadata

- BTCUSD inverse: tick 0.10, qty step 1 contract, min 1, max leverage 100.
- ETHUSD inverse: tick 0.01, qty step 1 contract, min 1, max leverage 100.
- SOLUSD inverse: tick 0.01, qty step 1 contract, min 1, max leverage 50.
- Inverse book sizes are contract counts; do not merge with base-asset spot/linear quantities without explicit contract-value normalization.

## Second-venue status

TickerLayer discovers BTCUSDT/ETHUSDT/SOLUSDT perpetual symbols (source_count 6 each), but perpetual snapshot/quote/trade calls return 403: perpetuals access not enabled. TickerLayer is not a usable second live derivative feed.

## Persistent prior coverage

- BTC/ETH/SOL 60-bar one-minute linear series through 16:53Z with no gaps.
- QQQ/SPY/IWM minute ETF references continuous in last collected window; DIA sparse.
- CME roll/VOI revision metadata and CFTC futures-only + combined populations preserved.

## Quality gates

- Do not merge inverse contract counts with base-asset quantities.
- Do not interpret same-venue product basis as cross-venue lead-lag.
- Keep source timestamps separate and flag non-atomic comparisons.
- Never infer MBO queue/sweeps/icebergs from static books.
- Keep ETF references separate from futures.
- Require exact CME contract identifiers.
- Preserve provider-plan failures and missing raw hashes.

## New artifact IDs

- CRYPTO-SPOT-LINEAR-INVERSE-BTCETHSOL-20260928T1700Z
- TICKERLAYER-PERPETUAL-ACCESS-STATE-20260928

## Persisted snapshot

- snapshots/CRYPTO_SPOT_LINEAR_INVERSE_20260928T1700Z.json

## Access state

Usable:
- Bybit spot/linear/inverse selected public endpoints.
- Twelve Data selected reference endpoints.
- GitHub.

Blocked:
- TickerLayer perpetual live data: 403.
- TickerLayer direct indices/XAUUSD: plan restricted.
- U.S. Gold Bureau current request: prior IP restriction.
- direct CME live MDP/MBO, options analytics, cross-venue OI/liquidations: not exposed.

## Next targets

1. Independent second crypto derivatives venue with depth/funding/OI/liquidations/trade tape.
2. Exact CME active-contract VOI/settlement.
3. Licensed CME MDP 3.0.
4. CME/Cboe options chains.
5. Raw payload/checksum archival where permitted.
