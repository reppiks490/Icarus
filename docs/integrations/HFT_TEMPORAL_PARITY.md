# HFTBacktest 2.4.4 — synthetic native temporal replay parity

**Status: isolated draft research-only validation, stacked on PR #492.** This gate tests **synthetic event-time causality** and deterministic replay scheduling in an actual pinned HFTBacktest Python/Rust simulator. It does not establish authentic market data, exchange-clock synchronization, realistic fills, profitable strategies or live execution authority.

## Scope and method

`icarus_engine.external_hft_temporal_parity` accepts **no file paths, provider credentials or live data arguments**. It constructs two independently source-to-staging-to-NPY-verified five-event synthetic L2 fixtures for illustrative contract NQH2026. Both have identical header and first three events. The second fixture changes only the fourth and fifth depth updates (bid and ask removals) strictly after the early probe. Every fixture is checked through the independent native verifier and causal audit; the latter must remain `REPLAY_READINESS_BLOCKED`.

The module invokes HFTBacktest **2.4.4** on isolated data using only `BacktestAsset`, `HashMapMarketDepthBacktest`, `elapse`, `depth`, `position`, and `close`. It compares the same synthetic book at elapsed 2.5 seconds under one large step versus 0.5+1+1 seconds. It also checks the mutated future events cannot affect the early state. At 3.5 seconds it compares a one-step replay with 0.5+1+1+1 seconds and requires that the fourth-event mutation has affected the later state. The 3.5-second probe intentionally remains before the end-of-data boundary. No order APIs are invoked.

A passing receipt is `SYNTHETIC_NATIVE_TEMPORAL_PARITY_ONLY`, with both SHA-256 source and native hashes, boolean parity gates, and every empirical/training/execution authority denied. It must never override the canonical causal audit's refusal or become a Brain champion/edge metric. All fixtures are fabricated test data.

## Reproduction

Only in an isolated environment with the pinned open-source dependencies `hftbacktest==2.4.4`, `numpy==2.2.6`, `numba==0.61.2`:

```bash
python -m unittest tests_engine.test_external_hft_temporal_parity -v
python -m icarus_engine.external_hft_temporal_parity
```

The dedicated GitHub Actions job installs these packages on an **ephemeral Ubuntu runner only**, never on the owner's PC/WSL2 environment. Ordinary standard-library-only ICARUS tests skip native execution if HFTBacktest is absent.

## Hard limits

This checks two fixed synthetic traces only; deterministic scheduling here is not a general proof of event-time correctness. There is no initial full-book snapshot, independently synchronized exchange/local clocks, exchange sequence-gap recovery, source licensing proof, L3 queue identity, calibrated order latency/fees/slippage, real-price fill reconciliation, protected holdout, or trained strategy. The test never submits an order and does not validate broker controls. Existing paused workflows, PC restart hold, model training and live broker arming remain untouched. Next gates: independently verified authorized market-depth source, snapshots and venue-clock mapping, replay under multiple controlled event patterns, conservative execution model calibration and real-price paper-fill reconciliation.
