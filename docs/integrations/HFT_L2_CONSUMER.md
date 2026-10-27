# HFTBacktest L2 staged-event independent consumer

**Status:** isolated research-only verification candidate, not deployed, not native HFTBacktest replay, not empirical execution evidence. Stacked on draft [ICARUS #486](https://github.com/reppiks490/Icarus/pull/486); this PR touches only the new consumer, its tests, this document and dedicated offline CI.

## Why independent verification matters

The existing `icarus_engine.external_hft_stage` producer emits a normalized eight-column CSV and a manifest. Its own success and hashes do **not** establish that the staged rows match the source, that the declared source is authentic, or that any fill is achievable. The new `icarus_engine.external_hft_verify` reads both the **original source** and staged directory, reconstructs every expected Event field without importing the producer, and refuses mismatches.

The caller **must supply the original source SHA-256 from an independently trusted receipt**. Copying the digest from the untrusted staging manifest back into the verifier is not independent anchoring. This check remains only structural: the trusted receipt itself needs separate source/rights verification.

```bash
python -m icarus_engine.external_hft_verify \
  --source /authorized/data/physical_nqh2026_l2.csv \
  --staging /authorized/research/hft/staged_nqh2026 \
  --contract-id NQH2026 \
  --source-id authorized_vendor_receipt \
  --expected-input-sha256 <64_HEX_DIGEST_FROM_INDEPENDENT_RECEIPT> \
  --tick-size 0.25 --lot-size 1
```

## Strict read-only admission

The verifier rejects symlinked source/staging/parent paths, unexpected staged files, duplicate JSON keys, unknown manifest keys, true/invalid authority flags, mismatched physical contracts/source identifiers, wrong tick/lot definitions, incorrect independent input digest, and output digest mismatches. It streams both CSV files completely with **no row cap**, checking exact headers, row counts, monotonic sequence and exchange/arrival timestamps, nonnegative arrival latency, valid event side/type flags, price and quantity grids, exact float64 output values, no synthetic MBO IDs, and every manifest count and first/last timestamp. A malformed/extra row or forged/rehashed output event is refused. The verifier writes no output files or state and executes no provider or simulator code.

Success returns a transient `STRUCTURALLY_VERIFIED_QUARANTINED` receipt with all authenticity, entitlement, clock-sync, snapshot, native replay, empirical fill, training and live execution flags **false**. There is no automated promotion to Brain, paper strategies, broker controls, UI signals or champion rankings.

## Proof and limits

Offline regression tests construct independent synthetic fixtures, exercise tampering including an adversary rehashing the output, and test producer-to-consumer roundtrip against the real `external_hft_stage` implementation on the repository CI runner. This is a **structural fixture**, not actual market data, native NumPy events, MBO order IDs, complete book state, actual exchange timestamps, queue calibration, realistic fills, backtested edge, licensed data or a Windows/WSL2 runtime test.

Further gates: independently authorized market-data receipt; instrument/venue tick, lot and time-unit verification; exchange/local clock synchronization; complete snapshot and sequence-gap policy; version-pinned HFTBacktest NumPy conversion and independent native readback; queue/latency/fee calibration against genuine fills; holdout preregistration; read-only Brain/UI evidence integration. Do not arm live trading, collect providers or promote models from this verifier.
