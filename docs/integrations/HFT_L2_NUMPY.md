# HFTBacktest L2 native NumPy binary staging — quarantined research

**Status:** proposed standalone offline bridge, stacked on draft ICARUS PR #488 (which itself depends on #486). Not deployed, not an actual HFTBacktest simulator run, and not empirical evidence of an execution edge.

## What the bridge does

The producer in #486 validates and exports market-by-price L2 events to eight-column CSV; the independent verifier in #488 re-reads the original physical-contract source and checks the entire staged CSV against an independently supplied original SHA-256. This bridge requires that verifier to succeed **before** it writes anything. It then streams the entire staged CSV to a fresh immutable research-only directory as a standard NumPy NPY v1.0 structured array with eight little-endian 8-byte fields: `ev` unsigned 64-bit, `exch_ts` signed 64-bit, `local_ts` signed 64-bit, `px` and `qty` float64, `order_id` unsigned 64-bit, `ival` signed 64-bit, `fval` float64. Record size is 64 bytes. There is no row ceiling and no truncation.

Upstream layout pinned for this research adapter: [nkaz001/hftbacktest Event definition at 5f3ec40](https://github.com/nkaz001/hftbacktest/blob/5f3ec40b2afb764e0fea112f941ed85523ef4e88/hftbacktest/src/types.rs) and [data documentation](https://github.com/nkaz001/hftbacktest/blob/5f3ec40b2afb764e0fea112f941ed85523ef4e88/docs/data.rst). The converter itself needs only Python standard library. CI installs pinned `numpy==2.2.6` to independently load and inspect the binary, including dtype, shape, values, event flags, zero MBO order IDs, and full row count.

```bash
python -m icarus_engine.external_hft_numpy \
  --source /authorized/data/physical_nqh2026_l2.csv \
  --staging /authorized/research/hft/staged_nqh2026 \
  --output /authorized/research/hft/native_nqh2026 \
  --contract-id NQH2026 --source-id authorized_vendor_receipt \
  --expected-input-sha256 <64_HEX_FROM_INDEPENDENT_RECEIPT> \
  --tick-size 0.25 --lot-size 1
```

The independent source hash must **not** be copied from the untrusted staging manifest. Output `hft-events.npy` and `native_manifest.json` include full SHA-256, source/staging linkage, physical contract, row counts, dtype, pinned upstream revision and explicit denials of source authenticity, entitlement, clock synchronization, complete book, queue/latency calibration, native HFTBacktest replay, empirical fills, training and execution authorization. The output directory must not exist; partial scratch output is deleted on failure. The adapter also rechecks the staged file hash and original source hash after conversion to detect input changes during processing. It does not claim protection against malicious concurrent replacement of the source filesystem or validation of vendor licensing.

## Acceptance gates still outstanding

Independent NumPy readback on Linux CI proves structural compatibility with the documented Event record layout; it **does not** prove HFTBacktest's installed Python/Rust version can ingest the file or simulate the venue. Real licensed depth data, exchange/arrival clock sync, book snapshot and sequence-gap policy, queue position, fees/latency model, actual fill reconciliation, holdout approval and owner Windows/WSL2 runtime remain unverified. MBO order IDs are always zero because this is MBP L2, never invented L3. Heikin Ashi display must not replace real-price fills. No model is trained or promoted; no broker connection is made; nothing is wired to live strategies, Brain, UI signals or champion rankings.
