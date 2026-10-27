# Independent HFTBacktest L2 native NPY consumer — research quarantine

**Status:** proposed, isolated, read-only structural verifier stacked on Icarus draft PR #489, itself dependent on #488 and #486. Not merged or deployed; no provider calls, model training, strategy changes, simulator execution, or broker operations.

The producer in #486 validates a physical futures contract's MBP L2 event source. #488 independently checks the source-to-CSV mapping against a separately obtained original source SHA-256. #489 packs that staged data into a 64-byte-per-event NumPy NPY v1.0 binary, with an explicit research-only manifest. This fourth layer **independently reads** the entire native binary, checks its exact NPY header, pinned eight-field little-endian dtype, declared row count and file length, compares **every binary event byte** with independently verified staged/source values, checks full source/staging/native SHA-256 again, and refuses malformed manifests, duplicate keys, symlinks, unknown artifacts and all claimed training/execution authority.

The source SHA must come from an independent trusted receipt; do **not** take it from the untrusted staged or native manifest. Example:

```bash
python -m icarus_engine.external_hft_native_verify \
  --source /authorized/data/physical_nqh2026_l2.csv \
  --staging /authorized/research/hft/staged_nqh2026 \
  --native-dir /authorized/research/hft/native_nqh2026 \
  --contract-id NQH2026 --source-id authorized_vendor_receipt \
  --expected-input-sha256 <INDEPENDENT_ORIGINAL_SOURCE_SHA256> \
  --tick-size 0.25 --lot-size 1
```

The tool produces **only a printed read-only receipt**; it does not modify the source, staging or native artifacts. It requires only Python standard library and existing isolated ICARUS modules; no HFTBacktest import or dependency installation is needed. All test inputs are synthetic fixtures, including a full >10,000-record byte-parity check, not empirical market data. Native event flags are preserved, and MBO order IDs are zero for MBP L2. The upstream field layout remains pinned to [nkaz001/hftbacktest revision 5f3ec40](https://github.com/nkaz001/hftbacktest/blob/5f3ec40b2afb764e0fea112f941ed85523ef4e88/hftbacktest/src/types.rs).

## Explicit unverified gates

Passing source-to-native parity does **not** prove the vendor's data rights/authenticity, exchange/arrival clock synchronization, snapshot completeness, continuous-contract roll mapping, real-time queue priority, latency/fees/slippage, HFTBacktest's installed simulator replay, broker execution, real-price fill quality, predictive model performance, holdout approval, or local Windows/WSL2 behavior. The manifest's `numpy_independent_readback_verified=false` remains unchanged: it is a producer-issued authority denial, not a field this consumer can elevate. The read-only receipt can report `native_byte_parity_verified=true` while all trading, empirical, entitlement and training flags remain denied.

**Next engineering gate:** after exact-HEAD CI and independent review, run a separately pinned, isolated HFTBacktest replay on an authorized actual L2 dataset, with validated book snapshot/sequence-gap policy and conservative queue/latency/fee models. Compare independently with real-price fills and a separately protected holdout before any Brain/UI research admission. No live broker arming or UI defaults changes are authorized.
