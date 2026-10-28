# NautilusTrader 1.231.0 QuoteTick — quarantined research integration

**Status:** draft, source-integrity and native structural roundtrip only. **Not** a market-data collector, NautilusTrader backtest, L2 book reconstruction, order simulator, execution-quality measurement, model trainer, Brain input, or live broker interface.

## Upstream compatibility and license

Pinned stable upstream release: `nautechsystems/nautilus_trader@v1.231.0` (2026-08-02), with documented `QuoteTick(instrument_id, bid_price, ask_price, bid_size, ask_size, ts_event, ts_init)` and `QuoteTick.to_dict/from_dict`. Sources: [QuoteTick documentation](https://github.com/nautechsystems/nautilus_trader/blob/v1.231.0/docs/concepts/data/quote_tick.md), [upstream Python quote unit tests](https://github.com/nautechsystems/nautilus_trader/blob/v1.231.0/python/tests/unit/model/test_quote.py). The upstream project is licensed under LGPL-3.0; ICARUS does not vendor or copy its source. The GitHub Actions runner installs a public prebuilt wheel at exactly `1.231.0`. This is **not** a claim that the owner Windows/WSL2 environment has the same package or capacity.

## Input contract

An independently authorized **physical futures contract + venue** top-of-book quote CSV, exactly:

```csv
sequence,instrument_id,event_ts_ns,arrival_ts_ns,bid_price,ask_price,bid_size,ask_size
```

`instrument_id` must be a real contract/venue identifier such as `NQH2026.CME`, not `NQ1!` or a continuous synthetic ticker. The source and license are **caller declarations**, not independently verified. Every record must match that instrument, have a strictly increasing sequence, nondecreasing exchange/arrival timestamps in UTC Unix nanoseconds, nonnegative reception latency, bid < ask, positive sizes, equal bid/ask price precision and equal size precision, and declared tick/lot-grid alignment. No missing bid or ask is silently filled from a previous row. A crossed/locked quote, out-of-order source or unsynchronized clock must use a separately audited adapter, not this one. The converter has no arbitrary row cap.

```bash
python -m icarus_engine.external_nautilus_quote_bridge stage \
  --input /authorized/quotes/physical_nqh2026.csv \
  --output /authorized/research/nautilus/staged_nqh2026 \
  --instrument-id NQH2026.CME --source-id approved_vendor_receipt \
  --producer-revision <ACTUAL_FULL_40_HEX_GIT_REVISION> \
  --tick-size 0.25 --lot-size 1
```

A fresh, previously nonexistent output directory receives `quotes.jsonl` and `manifest.json`. The CLI prints the manifest's own SHA-256 separately; the manifest includes full source/export hashes, source revision, instrument, row/clock bounds, and explicit **false** authenticity, license, snapshot, fill, training, and execution authority flags. The staging output is not a Nautilus catalog and is never inserted into runtime state.

## Native read-only verification

Independently pin the **three hashes** (original source, exported JSONL, manifest) and expected source/contract/revision from an authenticated source outside the untrusted staging directory. Then:

```bash
python -m icarus_engine.external_nautilus_quote_bridge verify-native \
  --source /authorized/quotes/physical_nqh2026.csv \
  --staging /authorized/research/nautilus/staged_nqh2026 \
  --instrument-id NQH2026.CME --source-id approved_vendor_receipt \
  --producer-revision <ACTUAL_FULL_40_HEX_GIT_REVISION> \
  --expected-source-sha256 <INDEPENDENT_64_HEX_SOURCE_DIGEST> \
  --expected-export-sha256 <INDEPENDENT_64_HEX_EXPORT_DIGEST> \
  --expected-manifest-sha256 <INDEPENDENT_64_HEX_MANIFEST_DIGEST>
```

The verifier rejects unexpected files, symlinks, modified bytes, mismatched provenance, duplicate JSON keys, authority escalation, missing/extra records, or native representation/precision drift. Every row is compared to its original source and roundtripped through the actual pinned `nautilus_trader.model.QuoteTick` Python/Rust native object. No arbitrary sample ceiling. It writes **nothing** and never creates a broker, account, strategy, order or backtest engine.

## Evidence and remaining gates

The dedicated workflow uses synthetic fixtures only. A passing workflow establishes **native QuoteTick structural parity**, not verified source authenticity, licensed market coverage, clock synchronization, book completeness, continuous-contract roll integrity, queue position, slippage, commissions, real-price fill parity, holdout approval or profitability. It does not prove a working NautilusTrader simulator on the owner machine.

**No empirical admission:** `execution_authorized=false`, `training_approved=false`, and `fill_parity_verified=false` are mandatory even on success. Before using actual ICARUS data, separately verify vendor rights and provenance, actual contract/venue metadata, clock offset and exchange sequence continuity, source coverage, and trusted reference snapshots. Before Brain or UI admission, add independent consumer validation, actual-native simulation without live controls, conservative real-price fill reconciliation, and protected holdout review.

This work is isolated from the HFTBacktest draft stack (#488–#493), the owner-PC phone pairing/restart stop point, Engine provider collectors, and all scheduled/paused agents. No new provider requests, spending, model training, broker arming, live orders, or production deployment.
