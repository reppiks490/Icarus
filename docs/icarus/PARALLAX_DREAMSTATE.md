# PARALLAX + DREAMSTATE

PARALLAX and DREAMSTATE are ICARUS research/shadow subsystems. They are intentionally separated from broker execution and production-strategy authority.

## PARALLAX — observed counterfactual twin engine

PARALLAX records one immutable decision identity and a deterministic family of alternate branches against the same causal context. The default twin family includes:

- actual decision
- skip / abstain
- opposite-side branch
- 1, 2, 3, and 5-bar delay branches
- 0.75x, 1.25x, and 1.50x stop-distance branches
- 0.50x and 1.50x size branches
- one subsystem-ablation branch for each supplied subsystem vote

A branch is never assigned a result merely because a model thinks it would have worked. An outcome becomes scoreable only after a replay/shadow worker supplies an observed utility, metrics, timestamp, and evidence. Once observed, the result is immutable.

For each decision PARALLAX computes actual utility, best observed branch, regret, branch coverage, and completion state. Across decisions it computes paired branch deltas and paired subsystem-ablation contribution estimates. Mutation evidence is emitted only after the configured minimum paired sample count is met and the approximate 95% lower confidence bound of the paired advantage is above zero.

These estimates are screening evidence, not standalone causal proof. The protected validation stack remains downstream.

Storage: `research/parallax.sqlite3` (SQLite WAL).

## DREAMSTATE — counterfactual policy incubator

DREAMSTATE consumes statistically screened PARALLAX mutation signals and converts them into versioned hypotheses, never direct production mutations.

Supported hypothesis families currently include:

- execution-delay experiments
- stop-distance scaling experiments
- risk-normalized size experiments
- context-conditioned abstention gates
- subsystem gating/reweighting reviews

An opposite-side counterfactual never automatically becomes an inversion policy.

Each candidate has a deterministic family ID, trial index, source commit, immutable PARALLAX signal, mutation specification, evidence list, and validation state. The trial index preserves family-level search lineage for later multiple-testing control.

Only one non-terminal candidate may exist per mutation family at a time. Each family also has a hard 12-trial revision budget. A new revision after rejection/retirement requires strictly newer paired evidence, preventing incremental sample-count changes from silently exploding the search space.

Candidate stages are:

`proposed -> study -> validated -> qualified_shadow`

or terminal `rejected` / `retired`.

The maximum possible stage inside DREAMSTATE is `qualified_shadow`. It has no code path that grants production-decision or execution authority.

Every candidate uses the same protected gate vocabulary as Adaptive Brain:

1. causal time
2. provenance
3. out-of-sample evidence
4. protected holdout
5. multiple-testing control
6. costs / slippage / latency
7. ablation
8. calibration
9. OOD / drift
10. deterministic replay
11. independent verification

A failed gate is immutable for that candidate revision. A repaired hypothesis must become a new revision rather than rewriting failed evidence.

Storage: `research/dreamstate.sqlite3` (SQLite WAL).

## Adaptive Brain integration

DREAMSTATE mirrors each candidate state into the existing Adaptive Brain candidate journal through `record_brain_event`. The Brain remains the shared fail-closed shadow-routing gatekeeper.

PARALLAX and DREAMSTATE are registered in the Brain subsystem fabric under AION PRIME. This does not make AION, PARALLAX, or DREAMSTATE execution authorities.

## Trader interface

The **PARALLAX / DREAMSTATE** trader tab exposes:

- twin decision and observed-outcome counts
- observed regret statistics
- branch coverage
- paired subsystem-ablation attribution
- statistically screened mutation signals
- DREAMSTATE candidate population
- gate completion / failure state
- source commit provenance
- explicit shadow-only authority state

The UI reads authenticated `/api/parallax` and `/api/dreamstate` endpoints.

## Mutation APIs

All mutation endpoints require the normal ICARUS admin bearer token and strict JSON parsing.

When a PARALLAX decision omits `source_commit`, the server fills it only from a provably exact clean local ICARUS Git revision; dirty or unknown checkouts fail closed. Every accepted PARALLAX outcome automatically re-runs the DREAMSTATE conservative screen, so candidate discovery is continuous without granting activation authority.

- `POST /admin/parallax/decision`
- `POST /admin/parallax/outcome`
- `POST /admin/dreamstate/refresh`
- `POST /admin/dreamstate/evaluate`
- `POST /admin/dreamstate/retire`

Read endpoints:

- `GET /api/parallax`
- `GET /api/dreamstate`

These endpoints manipulate research evidence only. They do not edit strategy inputs, arm a broker, submit an order, change a position, or promote a policy into production.

## Truth contract

The implementation deliberately refuses several attractive but invalid shortcuts:

- unobserved counterfactual outcomes are not fabricated;
- paired ablation is not labeled causal proof;
- a positive counterfactual screen is not labeled a validated strategy;
- repeated searches do not bypass the multiple-testing gate;
- successful research does not silently mutate live ICARUS behavior;
- `qualified_shadow` does not mean production-approved.

This design makes PARALLAX a source of falsifiable evidence and DREAMSTATE a source of candidate hypotheses, while DAEDALUS/AEGIS/Adaptive Brain remain responsible for protected qualification boundaries.
