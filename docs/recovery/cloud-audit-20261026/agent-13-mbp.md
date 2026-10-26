Readiness: NO-GO for direct Icarus ingestion; retain as an isolated reconstruction example.

Read-only CSV inspection found 5,886 input events, 5,840 generated rows, and 3,928 reference rows. Generated output contains 11 trades versus 46 in the reference. First divergence is output data row 6: cancellation sequence 1289631 has depth 0 instead of 1.

- `orderbook_reconstruction.cpp:68–90,298–326`: cancellations always decrement order count and erase the order, even for partial reductions. Actual input lines 467–470 contain T/F/C for sequence 56150102: order 68625181 decreases from 24 to 23 shares. Generated T correctly shows 23, but its additional C removes the entire price level; reference emits only T. Deferred trades overwrite earlier trades and discard unmatched sequences.
- `:289–344`: only the initial reset clears state; modifications have no implementation. State is neither partitioned by instrument nor backed by remaining per-order quantities. These limitations require correction before broader feeds.
- `:138–156,196–198`: depth is computed after deletion, defaulting missing levels to zero; receive timestamps are replaced with event timestamps. Receipt-time ordering and latency cannot be trusted.
- Icarus `icarus_engine/feeds/databento.py:423–474` expects SDK records with integer nanosecond timestamps and nested levels; CSV supplies ISO strings and flattened decimal prices. Engine `cl_lab/depth_resilience.py:35–85` expects DBN arrays, integer prices scaled by 1e9, F_LAST boundaries, and aggressor-side T records. This converter flips T side, incompatible with that interpretation.

Safe boundary: explicit offline adapter with separate reconstructed provenance, preserved receipt time, validated event grouping/side semantics, and reference reconciliation; never label this sample ARL equity as NQ futures depth. No tests, network, or source edits performed.
