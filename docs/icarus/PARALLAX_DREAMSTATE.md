# PARALLAX + DREAMSTATE

PARALLAX and DREAMSTATE are ICARUS research/shadow subsystems. They are intentionally separated from broker execution and production-strategy authority.

## PARALLAX V2 — observed counterfactual twin engine

PARALLAX records one immutable decision identity and a deterministic family of alternate branches against the same causal context. Decision identity now binds exact ICARUS source commit, asset, chosen action, regime, observation time, context, subsystem votes, comparison contract, and optional/derived context strata.

This closes an earlier identity ambiguity where two different actions or regimes could otherwise share the same contextual identity.

### Counterfactual lattice

For long/short decisions the default twin family includes actual, skip/abstain, opposite-side observation, 1/2/3/5-bar delays, 0.75x/1.25x/1.50x stop distances, 0.50x/1.50x size branches, 0.75x/1.25x/1.50x target distances, bounded compound branches, and one subsystem-ablation branch for each supplied subsystem vote.

Flat/abstain decisions do not invent hypothetical trade branches. They retain only the actual branch unless the caller explicitly supplies a custom branch family.

An opposite-side counterfactual remains an observation only. DREAMSTATE does not automatically turn it into an inversion strategy.

### Comparison contract

A counterfactual advantage is candidate-ready only when the decision has a complete comparison contract containing:

- utility_metric
- evaluation_horizon_bars
- dataset_id
- cost_model_id
- clock_id
- optional normalization

The contract is immutable through decision identity and receives a deterministic hash. Evidence from different contracts is never pooled into one mutation signal.

This prevents different horizons, transaction-cost assumptions, clocks, datasets, or utility definitions from being treated as one experiment.

### Context strata

A decision may provide up to eight explicit strata. If omitted, PARALLAX derives supported dimensions from context when present: session, daypart, volatility regime, liquidity regime, macro regime, and trend regime.

Mutation screens expose per-stratum evidence rather than silently assuming an effect generalizes beyond the contexts actually observed.

### Evidence-complete paired screening

A branch is never assigned a result merely because a model thinks it would have worked. Candidate screening requires evidence on both the actual path and alternate path under the same immutable decision/comparison contract. Pairs missing either path's evidence remain visible in coverage diagnostics but do not count toward candidate sample size.

### Statistical screen

PARALLAX V2 computes per exact asset/regime/source-revision/comparison-contract/branch hypothesis:

- evidence-complete paired sample count
- mean and median paired delta
- standard deviation and standard error
- approximate 95% interval
- one-sided normal screening p-value
- positive-pair fraction
- evidence-pair coverage
- context-strata statistics

The screen then applies Benjamini-Hochberg false-discovery-rate adjustment within the exact asset/regime/source-revision/comparison-contract family.

A candidate-ready mutation signal requires minimum paired evidence, a complete comparison contract, a lower confidence bound above the configured minimum effect, and an FDR-adjusted q-value at or below the configured threshold. DREAMSTATE's default source FDR ceiling is 0.10.

The p/q screen is a hypothesis-prioritization device, not causal proof, a guaranteed edge, or a profit forecast. Protected ICARUS validation remains downstream.

### Regret and attribution truth

PARALLAX no longer pools regret across incomparable evidence scopes. If multiple source revisions/contracts/regimes are present, regret is reported by comparable group and the global mean is intentionally left unset.

Subsystem-ablation attribution is isolated by subsystem, asset, regime, source commit, and comparison-contract hash. These are paired removal effects, not Shapley values and not standalone causal proof.

### Coverage diagnostics

The trader interface exposes branch-kind totals, observed counts, evidence-complete counts, evidence coverage, comparison-contract readiness, candidate-ready screens, and blocked-screen reasons. Missing replay evidence is visible instead of looking neutral.

Storage: research/parallax.sqlite3 using SQLite WAL. V2 performs backward-compatible schema migration for comparison-contract and strata fields.

---

## DREAMSTATE V2 — bounded counterfactual policy incubator

DREAMSTATE consumes only PARALLAX hypotheses that clear the comparison-contract, paired-evidence, lower-bound, and FDR screens. It converts those signals into versioned hypotheses, never direct production mutations.

Supported hypothesis families include execution-delay, stop-distance, target-distance, risk-normalized size, context-conditioned abstention, subsystem gating/reweighting, and bounded compound policies containing two or more observed counterfactual operations.

A compound result is treated as one indivisible hypothesis. DREAMSTATE does not infer that every component is independently useful from a successful compound branch.

### Policy contract

Each candidate exposes an explicit shadow policy contract containing asset, regime, exact source commit, comparison-contract hash and contract, observed context strata, mutation, immutable baseline fallback, reversibility, and explicit false authority flags for automatic activation, production decisions, execution, broker access, and risk authority.

A candidate's policy scope therefore cannot silently generalize from one evidence domain into another.

### Search accounting

Each candidate family is isolated by asset, regime, source commit, comparison-contract hash, and mutation family. Only one non-terminal candidate may exist per family at a time.

Each family has a hard 12-trial budget. Candidate metadata exposes current trial index, trials used, trials remaining, source paired evidence count, source pair coverage, source p-value, source FDR q-value, source strata count, and comparison-contract readiness.

A new revision after rejection/retirement requires strictly more paired evidence than the previous family revision. This prevents incremental sample-count changes from silently exploding the hypothesis search space.

### Source-signal decay

DREAMSTATE re-screens active source hypotheses whenever it refreshes. If the exact PARALLAX source hypothesis remains observed but no longer clears the current candidate screen, the active DREAMSTATE candidate is automatically retired in shadow state and the reason is preserved as evidence.

This does not roll back or alter ICARUS production behavior; DREAMSTATE has no production authority.

DREAMSTATE also re-checks the exact current PARALLAX source hypothesis immediately before accepting any new validation-gate update. This closes the interval between evidence deterioration and the next scheduled/manual refresh: stale source evidence cannot continue advancing a candidate simply because its original signal snapshot was stronger.

### Protected gates

Candidate stages are proposed -> study -> validated -> qualified_shadow, or terminal rejected / retired. The maximum possible stage inside DREAMSTATE is qualified_shadow.

Every candidate uses the same protected gate vocabulary as Adaptive Brain: causal time, provenance, out-of-sample evidence, protected holdout, multiple-testing control, costs/slippage/latency, ablation, calibration, OOD/drift, deterministic replay, and independent verification.

A failed gate is immutable for that candidate revision.

V2 adds fail-closed prerequisites for some gate claims: the multiple-testing gate cannot pass unless the source PARALLAX FDR screen is cleared and the comparison contract is complete; deterministic replay requires a complete comparison contract; and costs/slippage/latency requires a cost-bound complete comparison contract.

These prerequisites do not themselves prove the gate; they only prevent impossible gate claims.

Storage: research/dreamstate.sqlite3 using SQLite WAL.

---

## Adaptive Brain integration

DREAMSTATE mirrors each candidate into the existing Adaptive Brain candidate journal through record_brain_event. Mirrored events now carry paired evidence statistics, source p/q values, pair coverage, strata count, policy contract, family search accounting, and immutable source revision.

Adaptive Brain remains the shared fail-closed shadow-routing gatekeeper. PARALLAX and DREAMSTATE remain under AION PRIME ownership and have no broker authority.

---

## Trader interface

The existing PARALLAX / DREAMSTATE tab now exposes V2 intelligence without changing the dashboard/server ownership surfaces currently used by other ICARUS workstreams.

The tab includes total twin decisions, comparison-contract readiness, candidate-ready hypothesis count, blocked-hypothesis diagnostics, FDR q-values, paired evidence counts and coverage, context strata, non-pooled regret status, revision-isolated ablation attribution, branch-kind replay coverage, DREAMSTATE candidates, family trial budgets, candidate gate state, source revision, and explicit shadow-only authority.

The interface continues to read GET /api/parallax and GET /api/dreamstate. No new dashboard or engine-server route is required for V2.

---

## Mutation APIs

Existing authenticated endpoints remain unchanged: POST /admin/parallax/decision, POST /admin/parallax/outcome, POST /admin/dreamstate/refresh, POST /admin/dreamstate/evaluate, and POST /admin/dreamstate/retire.

When a PARALLAX decision omits source_commit, the existing server integration fills it only from a provably exact clean local ICARUS Git revision. Dirty or unknown checkouts fail closed.

Every accepted PARALLAX outcome continues to trigger a DREAMSTATE re-screen. A committed PARALLAX outcome remains authoritative even if the downstream DREAMSTATE refresh encounters an operational error.

These APIs manipulate research evidence only. They do not edit strategy inputs, arm a broker, submit an order, change a position, or promote a policy into production.

---

## Truth contract

PARALLAX/DREAMSTATE V2 deliberately refuses these invalid shortcuts:

- unobserved counterfactual outcomes are not fabricated;
- missing evidence does not count as a statistical pair;
- effects are not pooled across source revisions or comparison contracts;
- regret is not averaged across incomparable utility/evidence scopes;
- paired ablation is not labeled causal proof;
- a low p/q value is not labeled guaranteed alpha;
- context-specific evidence is not silently generalized beyond observed strata;
- an opposite-side branch does not auto-create an inversion strategy;
- compound success does not prove each component;
- repeated searches do not bypass family budgets or multiple-testing controls;
- source-signal decay may retire a shadow candidate;
- successful research does not silently mutate live ICARUS behavior;
- qualified_shadow does not mean production-approved.

PARALLAX remains a source of falsifiable counterfactual evidence. DREAMSTATE remains a bounded source of candidate hypotheses. DAEDALUS, AEGIS, Adaptive Brain, and explicit human-controlled deployment boundaries remain responsible for protected qualification and any future production decision.
