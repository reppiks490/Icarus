# 26/50 — Quant compatibility

**Beneficial hybrid:** separately pinned NautilusTrader offline depth/fill challenger beside Icarus, preserving Icarus research gates. Reviewed snapshot `ea005a35de4c092bbeda1335732f690b96e39204` maps Databento MBO → `OrderBookDelta`/L3 and MBP-10 → `OrderBookDepth`/L2. Compare identical authorized input hashes, windows and costs; retain event sequence, nanosecond timestamps and snapshot boundaries. MBP-10 cannot establish order priority. LGPL-3.0 distribution obligations remain; isolate Python 3.13–3.14, Rust 1.99.1 when building (wheels need no Rust), versus Icarus Engine’s Python ≥3.11 standard-library core.

Icarus `freeze_replay_port`/`run_backtest` replay immutable cached bars, not depth events. `POST /admin/backtest` → `GET /api/backtest/{job}`/`trades.csv` provides baseline results; `/admin/backtest/compare` expects TradingView-shaped CSV, so an explicit adapter and fill-semantics reconciliation are required. Keep challenger results evidence-only, `execution_authorized=false`.

- **vectorbt:** pandas/NumPy/Numba bar research; Apache-2.0 plus Commons Clause sale restriction prevents treating it as unrestricted Apache code. Adds no depth parity.
- **mlfinlab:** cached README declares all-rights-reserved Business/Enterprise licensing; public repository is an issue portal. No executable API/runtime compatibility established.
- **quantopian-algos:** three legacy examples, no declared license; platform-specific scripts are unsuitable for direct import.

Evidence: [candidate review](/tmp/icarus-public-review/hybrid-engine-review.md), [mlfinlab README](/tmp/repo-readmes/hudson-and-thames__mlfinlab.md), [local review](starred-forked-repository-review-20261026.md), Engine `backtest.py`, `server.py`, `pyproject.toml`. Static review only; no installation, execution or compatibility claim.
