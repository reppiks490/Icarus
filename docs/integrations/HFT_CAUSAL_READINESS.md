# Source-anchored HFT L2 causal-readiness audit (read-only research)

**Status:** draft, stacked on Icarus #490 → #489 → #488 → #486. This is a strictly isolated offline diagnostic, **not** an actual HFTBacktest simulator run, native replay acceptance, complete book reconstruction, or proof of any trading edge. No provider collection, licensed market data, broker access, model training, machine restart or UI/runtime changes.

## Why this gate exists

The existing MBP L2 converter emits observed price-level updates and trades but does not contain an independently verified initial full-book snapshot, venue sequence-gap policy, or calibrated latency/queue/fill assumptions. A valid NPY event structure can therefore be *perfectly* byte-correct and still be unsuitable for evaluating actual fills. This tool makes that refusal machine-readable while extracting useful **as-of, observed-only** diagnostics.

It calls the independent source→staging→native verifier from #490, which requires a separately trusted original source SHA-256. It then reads **every** native event in arrival order (no arbitrary row cap), reconstructs only levels explicitly observed since the first record, counts trades without two observed sides, tracks zero-quantity level removals, computes minimum positive observed spread in ticks, counts observed locked/crossed conditions, and measures per-event exchange→local arrival lag and consecutive clock gaps. It rechecks original/staged/native hashes after the audit to catch mutation.

A bid/ask map built from an incomplete feed is **not** an exchange best bid/offer or NBBO. Locked/crossed and trade-without-book counts are diagnostics about the partial observed map, not claims that a venue's actual book was crossed, that an exchange trade was invalid, or that a market order could fill at those prices.

## CLI

```bash
python -m icarus_engine.external_hft_causal_audit \
  --source /authorized/data/physical_contract_mbp_l2.csv \
  --staging /authorized/research/hft/staged_nqh2026 \
  --native-dir /authorized/research/hft/native_nqh2026 \
  --contract-id NQH2026 --source-id authorized_vendor_receipt \
  --expected-input-sha256 <INDEPENDENT_ORIGINAL_SHA256> \
  --tick-size 0.25 --lot-size 1 \
  --diagnostic-latency-threshold-ns 1000000
```

The latency threshold is **diagnostic only**, not an automatic quality or trading gate. No files are created, modified or promoted. Output status is always `REPLAY_READINESS_BLOCKED`, with `authority_granted=NONE`, `simulator_executed=false`, `training_approved=false`, `execution_authorized=false` and explicit `blocking_gates`.

## Mandatory outstanding gates

1. Independently prove original market-data rights, physical contract, timestamp origin, sequence semantics, exchange/local clock synchronization and permitted publication.
2. Independently verify initial full-book snapshot, snapshot-to-delta continuity, session/roll calendar, and missing-packet handling; **do not infer snapshots from observed updates**.
3. Validate an installed, version-pinned HFTBacktest runtime on a supported host using synthetic fixtures first, then authorized market data under approved isolation.
4. Calibrate queue, order latency, exchange fees, slippage, market impact, and conservative fills; compare to real-price independent fills.
5. Pre-register experiments, keep all trials and protected holdouts separate; obtain independent empirical approval before any Brain/gauge admission. No live broker arming.

The upstream event format remains pinned to `nkaz001/hftbacktest@5f3ec40b2afb764e0fea112f941ed85523ef4e88`. These tests are synthetic structural/causal regressions only, not market data or real execution evidence.
