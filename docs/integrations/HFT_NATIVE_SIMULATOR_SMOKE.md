# HFTBacktest 2.4.4 — isolated native simulator smoke

**Status: draft research-only integration.** This is a deliberately narrow native-runtime check downstream of ICARUS draft PRs #486 → #488 → #489 → #490 → #491. It is **not** an authorized strategy backtest, replay-quality certification, paper trade, broker integration, or market-data entitlement.

## What is actually executed

The new `icarus_engine.external_hft_simulator_smoke` module has **no external-data input arguments**. It generates five fixed, explicitly synthetic market-by-price depth/trade events for the illustrative physical contract `NQH2026` in a disposable temporary directory. It runs the existing independent source-to-CSV and source-to-NPY validation gates, then imports the pinned open-source **HFTBacktest 2.4.4** Python/Rust library and checks that its `event_dtype` exactly matches the eight-column 64-byte NPY ABI (names, types, offsets, alignment). It constructs `BacktestAsset` and `HashMapMarketDepthBacktest`, advances simulated time through the first three synthetic events, checks observed synthetic best bid/ask and zero position, and closes the backtester. It never calls any order submission API, runs a strategy, computes PnL or opens network connections.

The dedicated GitHub Actions job installs the open-source library **on an ephemeral Ubuntu runner only**, using `hftbacktest==2.4.4`, `numpy==2.2.6`, `numba==0.61.2`. It does not install anything on the owner's Windows/WSL2 PC. The upstream library is MIT-licensed; the versioned API and dtype are documented at https://github.com/nkaz001/hftbacktest/blob/master/py-hftbacktest/hftbacktest/types.py and https://github.com/nkaz001/hftbacktest/blob/master/py-hftbacktest/hftbacktest/__init__.py . The native package is not imported by the ordinary standard-library-only tests when unavailable.

```bash
# Only in an isolated environment with explicitly installed pinned dependencies:
python -m unittest tests_engine.test_external_hft_simulator_smoke -v
python -m icarus_engine.external_hft_simulator_smoke
```

## Claims explicitly denied

A successful synthetic native smoke proves only that **the pinned library can consume this synthetic NPY record ABI and advance its no-order simulator** in that particular CI environment. It does not establish a complete initial order-book snapshot, venue sequence continuity, synchronized clocks, real feed authenticity/rights, actual NQ futures exchange mechanics, calibrated queue/order latency, fees, slippage, real-price fill parity, strategy profitability, trained model suitability, holdout approval or live execution authority. The causal audit still returns `REPLAY_READINESS_BLOCKED`; it must not be overwritten by this smoke receipt. A CI runner is not evidence about the owner's WSL2 hardware.

**Future gates:** independently validated licensed source + initial snapshot, real exchange clock/sequence continuity, queue and latency calibration, paper fills reconciled with actual real-price prints, protected holdout protocol, and separate approval for any research promotion. Live broker arming remains disabled. No provider calls, licensed vendor payloads, credentials, new collection, model training, or schedule changes are authorized by this PR.
