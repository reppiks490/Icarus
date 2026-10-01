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

### V3 robustness layer: time stability + parameter basins

The V3 layer distinguishes statistically eligible from robustly eligible hypotheses.

Chronological stability becomes evaluable after nine evidence-complete pairs. PARALLAX orders those pairs by immutable decision time and splits them into three contiguous chronological folds. It reports each fold's paired statistics, positive-fold fraction, and worst-fold mean.

These simple retrospective evidence folds are internal to PARALLAX and are not the ICARUS Xi CHRONOFOLD causal-navigation subsystem. V3 creates no dependency on, ownership overlap with, or substitute for CHRONOFOLD.

- Before nine pairs, temporal robustness is explicitly marked not yet evaluable and does not block exploratory research.
- Once evaluable, every chronological fold must retain a positive mean paired effect for the source to remain robust-ready.
- A statistically positive aggregate can therefore be withheld when the effect has disappeared or reversed in a later block.

For one-dimensional delay, stop, target, and size families, PARALLAX also constructs a local parameter basin whenever adjacent parameter values have enough paired evidence.

- A statistically eligible point with locally comparable neighbors but no statistically eligible, temporally coherent adjacent neighbor is labeled an isolated parameter spike and withheld from robust-ready mutation signals.
- Basin neighborhoods are restricted to the same non-axis parameter signature, so a stop multiplier does not borrow support from another setting that silently changes an entry filter or other hidden parameter.
- Locality is bounded by an axis-specific maximum gap; far-apart sampled points do not validate each other as neighbors.
- If a parameter family has multiple sufficiently observed points but none are locally comparable, the source is labeled sparse local coverage and withheld from robust-ready signals.
- Contiguous statistically eligible, temporally coherent settings form a basin. PARALLAX reports basin support count, width, adjacent supporting values, family coverage, and whether the point is isolated.
- If only one sufficiently observed point exists in the comparable family, basin robustness remains not yet evaluable rather than treating missing exploration as a failure.

This deliberately prefers plateaus over magic numbers. It is still a research robustness screen, not proof of causality or expected profit.

### V4 dependence layer: effective N + HAC + revision transport

V4 adds a stricter layer for evidence dependence without destroying V3 compatibility.

**Episode-aware effective sample size**

A decision may optionally place an `episode_id` inside its immutable context. When multiple evidence-complete paired decisions carry the same episode id, PARALLAX treats them as one effective observation for statistical screening by averaging their paired deltas inside that episode.

- raw paired evidence count remains visible;
- effective paired count becomes the number of distinct episodes;
- clustered-pair count and largest episode size are exposed;
- if no episode id is supplied, every immutable decision remains its own episode, preserving existing behavior;
- a large burst of correlated decisions from one market shock can no longer satisfy a minimum-sample gate merely by repetition.

**Newey-West / HAC uncertainty**

When at least six effective episode means are available, PARALLAX computes a Newey-West heteroskedasticity-and-autocorrelation-consistent standard error for the chronological effective sample.

- the lag is deterministic from effective N;
- the screen uses the HAC one-sided p-value and HAC 95% lower bound when evaluable;
- before HAC is evaluable, the existing paired normal approximation remains the screen;
- Benjamini-Hochberg FDR consumes the dependence-adjusted p-value when HAC is active;
- both naïve and HAC diagnostics remain visible for audit.

This prevents serially correlated positive runs from appearing more certain simply because adjacent outcomes resemble one another.

**Cross-revision transportability**

PARALLAX also compares the same exact asset/regime/comparison-contract/branch/parameter hypothesis across distinct ICARUS source commits.

It does **not** pool effect sizes across revisions. Instead it reports:

- evaluable revision count;
- supporting robust revision count;
- strongly contradictory revision count;
- supporting and contradictory revision identities;
- whether revision transport is stable.

Transportability becomes evaluable after at least two independently sampled source revisions. A strongly contradictory revision—defined conservatively as a dependence-adjusted 95% upper bound at or below zero—blocks robust readiness for the matching mutation family. Missing or merely underpowered revisions do not count as contradictions.

Storage: research/parallax.sqlite3 using SQLite WAL. V2 performs backward-compatible schema migration for comparison-contract and strata fields; V3 and V4 add computed diagnostics without a destructive storage migration.

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

### V3 robustness authority

DREAMSTATE V3 consumes robust_candidate_eligible, not merely the primary FDR-qualified flag.

- A source can remain statistically significant yet be automatically retired if chronological fold stability becomes negative.
- A source can remain statistically significant yet be withheld or retired if it becomes an isolated parameter spike once neighboring settings are evaluable.
- Early sources are not rejected merely because temporal folds or neighboring parameter points do not yet have enough evidence; those robustness dimensions remain explicitly unevaluable.
- Policy contracts, Adaptive Brain mirrors, and candidate search accounting carry temporal/basin diagnostics so downstream reviewers can see why a source is robust-ready or withheld.

Robustness clearance does not replace the protected OOS, holdout, cost, replay, calibration, OOD/drift, or independent-verification gates.

### V4 dependence authority

DREAMSTATE V4 carries the dependence diagnostics from the exact current PARALLAX source into every candidate rather than recomputing or weakening them.

Candidate policy contracts, Adaptive Brain mirrors, and search accounting expose:

- raw paired N and effective paired N;
- episode-clustered pair count and largest episode size;
- HAC evaluability, lag, standard-error interval, and dependence-adjusted screen lower bound;
- cross-revision transport evaluability;
- supporting and contradictory revision counts.

DREAMSTATE still creates candidates only from `robust_candidate_eligible` PARALLAX sources. Because the live source is re-read before every validation update, later episode clustering, HAC uncertainty, temporal instability, parameter-basin collapse, or a strong contradictory source revision can retire an active shadow candidate.

Cross-revision transport does not merge or average separate code revisions. Revision boundaries remain immutable evidence boundaries.

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

### Downstream evidence boundary

PARALLAX/DREAMSTATE robustness is an upstream research-admission screen. It does not replace the separate Performance Proof ledger or Champion/Challenger shadow tournament now present in ICARUS. A robust-ready or even qualified-shadow DREAMSTATE candidate still requires independently settled proof records and the downstream tournament's own comparable-scope/sample/coverage gates before it can be treated as a shadow champion. None of these stages grants production or execution authority.

---

## Trader interface

The existing PARALLAX / DREAMSTATE tab now exposes V4 dependence and V3 robustness intelligence without changing the dashboard/server ownership surfaces currently used by other ICARUS workstreams.

The tab includes total twin decisions, comparison-contract readiness, statistical-ready and robust-ready hypothesis counts, blocked-hypothesis diagnostics, raw versus effective paired N, episode-cluster counts, HAC-adjusted lower bounds, FDR q-values, chronological fold stability, worst-fold mean, parameter-basin support/spike state, cross-revision transport/contradiction state, paired evidence coverage, context strata, non-pooled regret status, revision-isolated ablation attribution, branch-kind replay coverage, DREAMSTATE candidates, family trial budgets, candidate gate state, source revision, and explicit shadow-only authority.

The interface continues to read GET /api/parallax and GET /api/dreamstate. No new dashboard or engine-server route is required for V4. The existing storage/API schema versions remain backward-compatible; snapshots expose separate robustness_version markers for the computed V4 overlay.

---

## Mutation APIs

Existing authenticated endpoints remain unchanged: POST /admin/parallax/decision, POST /admin/parallax/outcome, POST /admin/dreamstate/refresh, POST /admin/dreamstate/evaluate, and POST /admin/dreamstate/retire.

When a PARALLAX decision omits source_commit, the existing server integration fills it only from a provably exact clean local ICARUS Git revision. Dirty or unknown checkouts fail closed.

Every accepted PARALLAX outcome continues to trigger a DREAMSTATE re-screen. A committed PARALLAX outcome remains authoritative even if the downstream DREAMSTATE refresh encounters an operational error.

These APIs manipulate research evidence only. They do not edit strategy inputs, arm a broker, submit an order, change a position, or promote a policy into production.

---

## Truth contract

PARALLAX/DREAMSTATE V4 deliberately refuses these invalid shortcuts:

- unobserved counterfactual outcomes are not fabricated;
- missing evidence does not count as a statistical pair;
- effects are not pooled across source revisions or comparison contracts;
- regret is not averaged across incomparable utility/evidence scopes;
- paired ablation is not labeled causal proof;
- a low p/q value is not labeled guaranteed alpha;
- an aggregate effect that fails chronological stability is not promoted as robust;
- an isolated winning parameter surrounded by evaluable losing neighbors is not promoted as robust;
- far-apart parameter points or settings with different hidden non-axis parameters cannot manufacture a false basin;
- a sampled parameter family with no local comparable support is not mislabeled a plateau;
- unevaluable temporal/basin evidence is labeled early rather than silently assumed good or bad;
- context-specific evidence is not silently generalized beyond observed strata;
- an opposite-side branch does not auto-create an inversion strategy;
- compound success does not prove each component;
- repeated decisions from the same declared market episode do not inflate effective sample size;
- serial dependence does not retain the naïve confidence interval once HAC is evaluable;
- cross-revision effects are not pooled to manufacture a larger sample;
- a strongly contradictory exact code revision blocks robust readiness for the matching mutation;
- repeated searches do not bypass family budgets or multiple-testing controls;
- source-signal decay may retire a shadow candidate;
- successful research does not silently mutate live ICARUS behavior;
- qualified_shadow does not mean production-approved.

PARALLAX remains a source of falsifiable counterfactual evidence. DREAMSTATE remains a bounded source of candidate hypotheses. DAEDALUS, AEGIS, Adaptive Brain, and explicit human-controlled deployment boundaries remain responsible for protected qualification and any future production decision.
