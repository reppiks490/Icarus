# NautilusTrader 1.221.0 native BacktestEngine synthetic smoke

**Status:** draft research-only integration stacked on Icarus #495 → #494 → #486. This lane invokes the actual pinned NautilusTrader low-level `BacktestEngine` inside ephemeral GitHub Actions. It does not invoke a strategy, order factory, execution algorithm, broker adapter, live node, provider collector, model trainer, Brain promotion path, or production runtime.

## What the smoke proves

The adapter first requires the existing source-to-native QuoteTick and arrival-time causal verification. The original source CSV, staged JSONL and manifest are independently SHA-256 pinned. The staged stream is rehashed again before replay. Only a dated physical contract identifier such as `NQH2026.CME` is accepted.

A temporary **synthetic test instrument definition** is then constructed solely to allow the native engine to replay the already verified QuoteTicks. Its activation/expiration bounds and multiplier are test metadata, not verified CME economics. Consequently `instrument_economics_verified=false` remains mandatory.

The engine is configured with:

- a simulated venue matching the contract's venue component,
- margin account state with a synthetic USD starting balance,
- the single synthetic futures instrument,
- the complete verified QuoteTick stream,
- **no Strategy, Actor, order, execution algorithm or broker client**.

The engine runs once, records iteration/boundary/cache counts, resets while retaining registered data, and runs the exact stream again. Both snapshots must match exactly. Orders and positions must remain zero. A 10,021-row fixture verifies that the actual native engine processes the complete stream rather than a sample.

## What it does not prove

A passing run is not execution-quality evidence. In particular it does **not** verify source authenticity or licensing, actual contract economics, exchange/reception clock synchronization, full order-book snapshots, queue position, fees, slippage, latency, realistic fills, profitability, protected holdout approval, model training, Brain admission, owner Windows/WSL2 installation, or live trading authority.

All of these remain false in the returned receipt:

`source_authenticity_verified`, `license_verified`, `instrument_economics_verified`, `exchange_clock_synchronized`, `initial_book_snapshot_verified`, `queue_model_calibrated`, `latency_model_calibrated`, `fill_parity_verified`, `empirical_edge_verified`, `training_approved`, `brain_admission_approved`, `execution_authorized`, and `live_broker_connected`.

No provider API is called and no data is collected by the workflow. Only synthetic fixtures are used.

## Acceptance evidence

The only acceptable compatibility proof is the exact PR head plus a successful dedicated workflow installing `nautilus_trader==1.221.0` from a public prebuilt wheel and running the parent provenance/causal suites and this native BacktestEngine suite. Broad application CI and independent review remain separate gates before any merge.

This is intentionally a zero-order smoke. Any later fill or strategy experiment must be a separate research lane with explicit synthetic/empirical labeling and cannot promote a strategy or bypass ICARUS holdout or live-execution restrictions.
