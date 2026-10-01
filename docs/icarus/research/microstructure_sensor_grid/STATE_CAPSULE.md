# Microstructure Sensor Grid — State Capsule

Last productive run: ICARUS-MICRO-20260928T1820Z
Run manifest: runs/MICROSTRUCTURE_20260928T1820Z.md

## Binance tape state

BTCUSDT:
- 1,000 consecutive aggregate IDs 3468349446–3468350445.
- zero ID gaps.
- 87.877-second event window.
- price range 83862.0–83938.1.
- total quantity 70.719 BTC.
- largest aggregate 10.721 BTC.

ETHUSDT:
- 1,000 consecutive aggregate IDs 3102957908–3102958907.
- zero ID gaps.
- 93.849-second event window.
- price range 2694.08–2698.10.
- total quantity 1141.027 ETH.
- largest aggregate 90.685 ETH.

SOLUSDT:
- 1,000-record paging attempted; ten jobs cancelled/deleted upstream.
- previous durable 100-record raw tape remains latest.

The 1,000-record BTC/ETH continuity summaries are persisted. Do not claim a combined raw 1,000-record repo blob yet.

## CME prior-day OI state

Official CME 2026-09-25 DEC 26 prior-day OI:
- NQZ6 271967
- MNQZ6 131840
- ESZ6 1898072
- MESZ6 125245
- YMZ6 86106
- MYMZ6 19036
- RTYZ6 417419
- M2KZ6 33179
- GCZ6 317452
- MGCZ6 unavailable from official settlement/overview pages.

CME settlement-page volume is explicitly estimated volume and differs from previously persisted Massive session volume for several contracts. Preserve both.

## Options state

- bounded same-day Cboe Greeks/IV/OI remain persisted.
- Massive next-expiry individual snapshots remain NOT_ENTITLED.
- Cboe CDN access showed network/circuit-breaker drift this run.
- full term/skew remains incomplete.

## Persistent quality gates

- Aggregate-trade IDs must be continuity checked.
- Aggregate trades are not MBO.
- Do not infer SOL data from failed pages.
- Do not infer MGC OI.
- Keep CME estimated volume separate from Massive session volume.
- Preserve source/update/retrieval and entitlement failures.
- Never infer full options term structure from bounded same-day slices.

## New artifacts

- snapshots/BINANCE_AGGTRADES_1000_SUMMARY_20260928T1820Z.json
- snapshots/CME_PRIOR_DAY_OI_20260925.csv

## Next targets

1. Lossless combined raw BTC/ETH 1,000-trade repository corpora.
2. SOL 1,000-trade paging retry.
3. MGC exact OI.
4. full next-expiry options term/skew.
5. liquidation event data.
6. CME MDP 3.0.
