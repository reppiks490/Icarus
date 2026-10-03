# Existing ASCENDANCY governor qualification — 2026-10-03

This continuation qualifies the existing PR #302 implementation rather than
creating a second governor, executor, autopilot or work-order board.

Original source head: `68fcd0818f0953c7bb1cde8460f6dae7a82ecba7`.
Integrated canonical main: `a9623690732af6fd553321e56063b83e6253f6f6`,
including the merged durable forecast Spine feed from #308.

The original branch reproduced one failed executor test and 37 passes. Its
tampered action also invalidated the outer plan hash, so the plan guard correctly
fired before the asserted action guard. The corrected fixture signs an outer
plan around an intentionally stale inner action identity. The separate outer
plan-tampering assertion remains intact. Production identity guards are unchanged.

Current-main reconciliation preserves every prior configuration replay,
background process, acknowledgement and Spine repair. The ASCENDANCY renderer
now loads and renders both the Spine and all four existing governor-stack panels
with separate response indices. No existing work-order or evaluator route is
replaced by a parallel implementation.

Initial local integration: 293 tests passed across ASCENDANCY, Spine, dashboard,
configuration jobs and execution controls. Hosted full Linux and selected Windows
qualification and the exact published head must pass before merging #302.

## Actual autonomy boundary

The existing autopilot is bounded, persistent research bookkeeping. It re-plans
after safe administrative progress and becomes quiescent when progress requires
external evidence, independent review, protected holdout authority, research
mechanism work or qualification. Work orders route those requirements to existing
subsystem owners. Dispatch and a successful cycle are not experiment completion.

It does not run every scientific experiment, reconstruct F4D3, create unavailable
data, fabricate evaluator receipts, consume undeclared protected holdouts, or
grant live trading/production authority. These remaining system integrations
stay in the shared-chat continuation queue. Original resource/iteration bounds,
authority checks and trading-state mutation fingerprint remain authoritative.

The user authorized continuing system repairs and integration. This work does
not change external ChatGPT schedules, deploy onto the user's Windows machine,
or claim observed desktop/UI recurrence resolution. `execution_authorized=false`;
`production_decision_authorized=false`.

Independent review reproduced two runtime defects: concurrent manual/worker
execution could call the same handler twice and conflict on its receipt; replaying
a recovered quiescent cycle could leave status showing an older failure. New
regressions reproduced both failures. The executor now serializes in-process
check/transition/receipt calls. A separate durable latest-observation pointer
tracks current autopilot state without rewriting immutable cycles or counting
replay as progress, including after restart. Cross-process/crash retries still
require idempotent domain handlers; no exactly-once claim is made.
