# Native NautilusTrader QuoteTick as-of-reception causality audit

**Status:** isolated research-only proposal, stacked on draft [Icarus #494](https://github.com/reppiks490/Icarus/pull/494), itself stacked on #486. Native runtime is only a pinned GitHub Actions public-wheel installation. Nothing here claims a working owner Windows/WSL2 model or local broker connection.

## Design and evidence boundary

`external_nautilus_causal_audit.audit_quote_asof` takes the original physical-contract CSV, the quarantined quote staging directory, separately authenticated SHA-256 values for source, export and manifest, explicit source identifier and producer revision, and a monotonically nondecreasing series of UTC Unix nanosecond observation times. It delegates whole-source provenance and **actual NautilusTrader 1.221.0 QuoteTick native roundtrip** to the independently existing verifier, then re-reads *every* staged row with a second hash pass to exclude post-verification mutations.

Only **arrival time** (`ts_init`) unlocks a quote for as-of observations; an earlier exchange timestamp (`ts_event`) never allows premature disclosure. Before the first arrival, no quote is available. Equal-time observation is allowed immediately when the quote arrives. Adjacent observation schedules must produce identical as-of snapshots for shared timestamps, and editing later synthetic events must not alter prior snapshots. Tests also cover 10,021 records without sample truncation and independently pinned source/export/manifest tampering.

This is **not** NautilusTrader `BacktestEngine` execution, depth-book replay, queue modeling or economic execution parity. It does not reconstruct L2, submit orders, simulate fills, calibrate latency, read live prices, run training, promote Brain/strategy/UI signals, or arm any broker. All provenance/license rights, initial snapshot, holdout, training, execution, latency, queue and empirical-edge flags remain false.

## Safe isolated use

A caller prepares a previously unoccupied staging directory using the already reviewed `external_nautilus_quote_bridge.stage_quotes`, records separately authenticated SHA-256 pins, then invokes:

```python
from pathlib import Path
from icarus_engine.external_nautilus_causal_audit import audit_quote_asof

receipt = audit_quote_asof(
    source=Path("/authorized/local/synthetic_quotes.csv"),
    staging=Path("/authorized/local/quarantined_quotes"),
    instrument_id="NQH2026.CME",
    source_id="synthetic_testing_only",
    producer_revision="a" * 40,
    expected_source_sha256="<INDEPENDENT_SHA256>",
    expected_export_sha256="<INDEPENDENT_SHA256>",
    expected_manifest_sha256="<INDEPENDENT_SHA256>",
    observation_ns=[1700000000000000500, 1700000000000001000],
)
```

The placeholders are not real digests; authoritative pins must originate outside untrusted staging. The observer writes nothing. Quotes are intentionally confined to an actual contract+venue, not the synthetic rolling `NQ1!` ticker.

## Acceptance and future gates

A focused GitHub Actions job installs exactly `nautilus_trader==1.221.0` from a publicly available prebuilt wheel on ephemeral Python 3.11, and runs both the parent structural suite and new synthetic causal suite. Cite the **exact source HEAD and actual workflow run**, not this design, as proof when CI completes.

To advance beyond this boundary: independent review and broad exact-head CI, actual authorized/licensed vendor source and contract metadata, exchange and reception clock-offset proof, initial book snapshots, a complete depth/trade event feed, true native backtest with zero broker routes, realistic real-price fill/queue/fee/latency reconciliation, protected holdout approval, and explicit owner permission. No empirical result or production readiness follows from these synthetic regressions.
