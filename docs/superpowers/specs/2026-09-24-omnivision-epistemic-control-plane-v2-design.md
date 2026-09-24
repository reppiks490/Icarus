# OMNIVISION Epistemic Control Plane v2 — Design

Date: 2026-09-24  
Status: written design awaiting user review  
Branch: `codex/exotic-research-loop`  
Supersedes for future evolution: `docs/superpowers/specs/2026-09-23-omnivision-federated-research-mesh-design.md`  
Does not supersede owner-hard constraints in `ASTRA_DO_NOT.md`.

## Intent

Evolve OMNIVISION from a cross-domain research mesh into an epistemic control plane for ICARUS: a system that governs what the engine is allowed to claim it knows, how that knowledge was obtained, when it became knowable, how many attempts produced it, what contradicts it, how uncertainty changes under regime shift, and what evidence would invalidate it.

The objective is not maximal complexity. The objective is maximal evidence quality per unit of research complexity.

A component is valuable only when it does at least one of the following:

- reduces material uncertainty;
- adds genuinely incremental information;
- exposes a previously hidden failure mode;
- improves reproducibility or provenance;
- improves calibration or abstention;
- survives falsification better than the component it replaces;
- makes the system simpler without reducing validated capability.

Deletion, consolidation, and abstention are first-class evolutionary actions.

## Existing foundation and mandatory gate

The current branch already contains the OMNIVISION foundation:

- strict `WorldEvent` contract;
- immutable `AdvisoryLedger` support for `world_state`;
- ledger-to-observation bridge;
- point-in-time world-state inference;
- immutable evidence IDs;
- cross-source contradiction preservation;
- deterministic hypothesis forge;
- bounded novelty screen;
- timestamp-safe placebo and walk-forward falsification;
- research-only candidate artifacts;
- end-to-end tests.

That foundation is currently recorded as `implemented_unverified` because the originating chat surface could not execute the runtime test suite.

### Phase 0 hard gate

No v2 product code may land until all of the following have executable evidence:

1. scoped OMNIVISION tests execute;
2. full relevant `tests_engine` regression suite executes;
3. package/import compatibility is checked;
4. temporal-leakage audit completes;
5. provenance/revision audit completes;
6. execution-separation audit confirms no research path can authorize live execution;
7. any failures are fixed with tests and re-reviewed;
8. exact commands, exit codes, and results are checkpointed to GitHub.

Inspection alone is not a pass.

## Hard boundaries

- `execution_authorized=false` remains invariant for OMNIVISION research artifacts.
- No Pulse rewrite.
- No autonomous credential acquisition.
- No sandbox escape, credential discovery, access-control bypass, stealth persistence, unauthorized access, or prohibited scraping.
- No fabricated observations, publication times, ticks, fills, revisions, or source availability.
- Inputs must be public, licensed, connected, or explicitly user-authorized.
- Observed, derived, latent/inferred, hypothesized, contradicted, stale, invalidated, and unknown states remain distinct.
- Inference never upgrades itself into an observation.
- Source opinion, attention, sentiment, analyst rank, and media tone are labeled as such and never silently converted into factual world state.
- Current data is never backfilled into a historical decision timestamp unless the source proves it was available then.
- Owner-hard repository rules remain authoritative.

## Research basis

The design adopts three evidence-backed ideas without binding ICARUS to any single external library.

### Search-aware performance evaluation

Bailey and López de Prado's Deflated Sharpe Ratio explicitly addresses selection bias, backtest overfitting, and non-normal returns. The v2 trial ledger therefore records the search process itself rather than evaluating only the winning candidate.

### Adaptive uncertainty under shift

Adaptive conformal inference provides a useful model for maintaining coverage under changing data-generating conditions. OMNIVISION will use the principle of continuously recalibrated uncertainty and explicit abstention under shift, not blindly import a particular algorithm.

### Explicit data lineage

OpenLineage separates Run, Job, and Dataset identities and supports extensible facets plus explicit lineage edges. OMNIVISION will remain dependency-light but model provenance in a compatible spirit: immutable entities, explicit transformations, exact input/output edges, and run-scoped metadata.

## Source-capability evidence from this design cycle

These observations are capability evidence, not trading signals.

| Source/plugin | Observed state in this cycle | Design consequence |
| --- | --- | --- |
| StackerScan | Gold and silver spot endpoint returned timestamped data | Metals adapter can be modeled as a healthy read-only market source |
| U.S. Gold Bureau | Health and gold spot calls were rejected by source IP allowlist | Source registry needs `blocked_by_source_policy`, not a generic failure |
| Bybit | Public BTCUSDT spot query returned price/change/volume | Crypto adapter needs explicit venue, market type, timestamp, and disclaimer metadata |
| Twelve Data | Authenticated; QQQ quote returned exchange, MIC, timestamp, session state | Adapter contract must preserve venue/session identity and current-vs-historical semantics |
| FMP | Treasury-rate endpoint returned dated yield-curve observations | Macro/rates adapter must preserve release date and maturity schema |
| Massive | Futures catalog exposed contracts, OHLC, quotes, trades, and snapshots | Futures adapter can separate reference data, bars, quotes, trades, and snapshots rather than flatten them |
| Bigdata.com | Market tearsheet returned timestamped cross-asset snapshot with source attribution | Aggregated research products must preserve their underlying-source identity and aggregation status |
| The Fly | Initial market-brief request hit a rate limit; later request succeeded | Adapter health must model rate limits, cooldown, retry class, and stale fallback |
| Zacks | Trending attention plus dated/current rank-style fields were returned | Attention/opinion/rank signals must be epistemically separated from observed company fundamentals |
| DataBlue | Stable Google News API schema was available | News adapter requires query provenance, publication metadata, dedupe, and source-quality controls |
| Blockscout | Session unlock required; Ethereum chain registry resolved after session use; service announced a future auth change | Capability registry needs authentication mode, version, and `valid_until/review_after` metadata |
| Cheat Database | Large unrelated gaming dataset was reachable | Relevance gate must reject syntactically valid but semantically irrelevant sources |
| Scite | Literature evidence retrieved; later call hit account usage limit | Research-source health must model entitlement/quota exhaustion separately from evidentiary quality |
| treg | Skill exposes endpoint price/reliability/routing discipline; no direct treg MCP call surfaced in this chat | Source selection should track cost, reliability, freshness, and input compatibility before spending |
| Stock Market Summary | Skill requires current-source verification and distinction between real-time/delayed/session data | Current-market adapters must never collapse timing/session metadata |

## Architecture

```text
AUTHORIZED / LICENSED / CONNECTED SOURCES
        |
        v
Source Capability Registry
  - access class
  - auth/entitlement
  - health
  - rate/quota state
  - timing/revision semantics
  - cost/reliability
  - relevance class
        |
        v
Canonical Evidence Gateway
  - schema validation
  - source allowlist
  - entity normalization
  - publication/availability clocks
  - immutable revision identity
        |
        v
AdvisoryLedger / Evidence Store
        |
        +----------------------+
        |                      |
        v                      v
Provenance DAG           World-State Graph
  - dataset lineage        - observed
  - transforms             - derived
  - trial/run identity     - latent
  - hashes                 - contradicted
        |                  - unknown
        +----------+-----------+
                   |
                   v
          Epistemic State Engine
  - confidence decomposition
  - calibration
  - staleness / half-life
  - abstention
  - contradiction budget
                   |
                   v
             Hypothesis Forge
                   |
                   v
       Search-Aware Trial Ledger
  - every attempted hypothesis
  - parameter lineage
  - family/search identity
  - rejected/deferred results
                   |
                   v
          Falsification Gauntlet
  - leakage-safe replay
  - placebo / permutation
  - multiple-testing controls
  - perturbation / ablation
  - regime and source stress
                   |
                   v
        Regime / Causal Validator
                   |
                   v
       Proof-Carrying Candidate
                   |
                   v
          Integration Governor
  - shadow only
  - staged canary research
  - rollback criteria
  - execution_authorized=false
```

## 1. Source Capability Registry

Every external source has a versioned capability record before it can produce accepted evidence.

Required fields:

- `source_id`
- `provider`
- `domain_classes`
- `access_class`: public, licensed, connected, user_authorized
- `epistemic_role`: primary_observation, aggregator, analyst_opinion, media, derived_market_data, negative_control
- `auth_mode`
- `entitlement_state`
- `health_state`
- `rate_limit_state`
- `cost_class`
- `reliability_evidence`
- `timing_semantics`
- `revision_semantics`
- `freshness_policy`
- `valid_until` or `review_after` when capability may expire
- `allowed_entities/assets`
- `forbidden_uses`

Health states are explicit:

- healthy
- degraded
- rate_limited
- quota_exhausted
- blocked_by_source_policy
- entitlement_missing
- schema_changed
- stale
- disabled

A source being unreachable is not evidence that the underlying fact does not exist.

## 2. Relevance and semantic firewall

Before evidence normalization, a relevance gate evaluates whether a source is admissible for the stated hypothesis.

The gate prevents:

- unrelated datasets from entering the graph merely because they are machine-readable;
- analyst opinion from being stored as direct factual observation;
- media attention from being confused with economic state;
- aggregate products from being treated as primary-source releases;
- duplicate vendors from creating artificial evidence multiplicity.

The Cheat Database capability check in this cycle is the canonical negative-control case: reachable and valid data, but inadmissible to market-state research absent an explicit hypothesis that legitimately depends on it.

## 3. Provenance DAG

The flat evidence ledger remains immutable storage; v2 adds a lineage layer.

Node classes:

- SourceCapability
- RawEvidence
- NormalizedObservation
- DerivedFeature
- LatentEstimate
- DatasetSnapshot
- Hypothesis
- Trial
- ValidationResult
- Candidate
- IntegrationDecision

Edge classes:

- produced_by
- normalized_from
- derived_from
- contradicts
- supersedes
- tests
- falsifies
- supports
- duplicates
- depends_on
- invalidates

Every edge carries:

- deterministic ID;
- creation/run ID;
- as-of time;
- transformation/version identity;
- evidence hashes;
- code/config hash where applicable.

The DAG must support exact backwards tracing from any candidate to raw evidence and exact forward tracing from invalidated evidence to every dependent artifact.

## 4. Epistemic state engine

Every claim has a class:

1. observed
2. derived
3. latent
4. hypothesized
5. contradicted
6. stale
7. invalidated
8. unknown

Confidence is decomposed rather than represented by one opaque scalar.

Minimum dimensions:

- source confidence
- timing confidence
- entity-resolution confidence
- transformation confidence
- model/calibration confidence
- cross-source agreement
- regime validity
- staleness penalty

The engine returns both aggregate confidence and the decomposition.

### Abstention

The system abstains when:

- calibrated coverage falls outside tolerance;
- contradiction budget is exceeded;
- source freshness falls below the hypothesis requirement;
- required variables are unresolved;
- current regime is outside validated support;
- trial/search corrections invalidate apparent significance;
- provenance is incomplete.

Abstention is a successful safety result, not a model failure.

## 5. Information half-life and staleness

Each variable/source pair can define an evidence half-life or expiry policy.

Staleness is based on domain semantics, not one global timeout.

Examples:

- tick/quote evidence: very short;
- scheduled macro release: stable until revised or superseded;
- corporate filing: durable but revision/correction aware;
- analyst opinion: time-bounded opinion;
- weather forecast: horizon-specific and rapidly decaying;
- chain state: block-height specific.

No stale observation is silently reused as current state.

## 6. Search-Aware Trial Ledger

Every meaningful candidate evaluation is recorded, including failures.

Required trial metadata:

- trial_id
- hypothesis_id
- hypothesis_family_id
- parent_trial_ids
- generation_method
- feature/parameter configuration
- dataset snapshot hashes
- train/validation/holdout boundaries
- code/config hash
- decision timestamp
- evaluation metrics
- cost/slippage assumptions where relevant
- result status
- rejection reason
- multiple-testing family membership

The ledger prevents a research agent from presenting only the best surviving branch of a large hidden search.

Search-aware evaluation may include Deflated Sharpe Ratio, Probability of Backtest Overfitting, false-discovery controls, or other methods when their assumptions are satisfied. No single statistic is mandatory for every hypothesis.

## 7. Novelty and negative knowledge

The existing Pearson screen remains a foundation check, not the final novelty system.

Progressive novelty layers:

1. exact hash/config duplication;
2. deterministic feature equivalence;
3. Pearson/Spearman overlap;
4. residual/prediction similarity;
5. mutual or conditional information where sample size and estimator reliability are adequate;
6. attribution/behavior overlap by regime;
7. incremental information against the current accepted feature set.

The system maintains a feature/hypothesis cemetery containing:

- rejected hypotheses;
- duplicate ideas;
- leakage failures;
- unstable relationships;
- invalidated source assumptions;
- regimes where a signal failed;
- evidence required before resurrection.

A rejected idea may only be reopened when new evidence materially changes its premise.

## 8. Falsification gauntlet v2

Applicable gates include:

- point-in-time replay;
- revision-aware replay;
- embargo/purge when the label structure requires it;
- placebo timing shifts;
- permutation/randomization controls;
- multiple-testing/search correction;
- locked holdout protection;
- parameter perturbation;
- source removal/ablation;
- contradictory-source stress;
- stale/missing-source stress;
- regime holdouts;
- cross-period testing;
- cross-asset portability when economically justified;
- transaction-cost/slippage stress when a candidate implies trading behavior;
- adversarial outliers and event shocks;
- historical-analogue counterexamples;
- bootstrap/confidence intervals where assumptions justify them.

A candidate does not pass because one impressive metric survives. It passes only when the evidence package satisfies the acceptance contract for its hypothesis family.

## 9. Calibration and adaptive uncertainty

Calibration is evaluated separately from predictive performance.

For predictions that expose intervals/probabilities, v2 tracks:

- nominal coverage;
- realized coverage;
- calibration error;
- conditional/regime coverage;
- rolling drift;
- interval width or decision sharpness;
- abstention rate.

Adaptive conformal-style mechanisms may be evaluated for online recalibration under distribution shift, but only after baseline calibration tests exist and assumptions are documented.

## 10. Regime and changepoint intelligence

Regimes are not labels invented after seeing performance.

Candidate regime variables may include:

- volatility state;
- liquidity state;
- correlation structure;
- trend persistence;
- rates/macro state;
- event intensity;
- source quality/coverage;
- physical-market stress;
- crypto/on-chain liquidity when relevant.

The system must distinguish:

- regime detection inputs;
- regime assignment time;
- transition uncertainty;
- model/feature validity by regime.

A relationship may strengthen, weaken, invert, disappear, or become nonlinear. The ledger preserves historical regime versions.

## 11. Causal discipline

The engine distinguishes prediction from causal claims.

Every causal hypothesis declares:

- treatment/exposure;
- outcome;
- pre-treatment confounders;
- possible mediators;
- possible colliders;
- identification strategy;
- counterfactual assumption;
- falsification/negative-control strategy.

Evidence hierarchy:

1. randomized or natural experiment where feasible;
2. credible quasi-experimental design;
3. calibrated observational design with explicit assumptions;
4. descriptive association.

Association is never relabeled as causation because it predicts well.

## 12. Research-budget allocation

Compute and data spend are allocated by expected information gain, not novelty theater.

Priority increases when an experiment can:

- challenge a load-bearing assumption;
- resolve a high-impact contradiction;
- reduce uncertainty in an integration candidate;
- distinguish between competing mechanisms;
- invalidate a large family of weak hypotheses.

Priority decreases when:

- the candidate is redundant;
- source quality is low;
- expected effect cannot matter economically;
- the experiment cannot change an integration decision;
- a cheaper test can reject the idea first.

Where a source has explicit monetary cost, source selection records expected cost, reliability, input compatibility, and fallback ordering before spending.

## 13. Proof-carrying candidate

A v2 candidate package contains:

- candidate_hash
- hypothesis and family IDs
- raw evidence IDs
- provenance-DAG root
- dataset snapshot hashes
- source capability versions
- trial ledger summary including number of related attempts
- novelty results
- calibration results
- falsification results
- regime support
- contradiction state
- known failure modes
- uncertainty decomposition
- incremental information estimate
- computational/data cost
- rollback conditions
- invalidation conditions
- `integration_ready`
- `execution_authorized=false`

Missing proof fields block integration readiness.

## 14. Integration Governor

Promotion states:

```text
rejected
deferred
research_only
validated_research
shadow_candidate
canary_research
integration_candidate
```

None of these states grant order execution.

Promotion requires monotonic evidence: later stages may add constraints or revoke readiness but may not erase prior failures or contradictions.

Any invalidated load-bearing evidence recursively marks dependent candidates for re-review through the provenance DAG.

## 15. Counterfactual failure mining

Failures become research inputs.

The engine records:

- failed forecasts;
- failed trades from existing research datasets when available;
- failed hypotheses;
- source outages;
- calibration breaks;
- regime mismatches;
- candidate regressions.

For each failure cluster it asks:

1. what evidence was available at the decision time;
2. what assumption failed;
3. what evidence would have prevented the error;
4. whether that evidence was observable, derivable, or unknowable;
5. whether a reusable guard can be tested.

The output is a falsifiable prevention hypothesis, not a post-hoc story.

## 16. Audit program before each major promotion

Independent audit lanes:

1. architecture/interface
2. security/trust boundary
3. point-in-time/temporal leakage
4. provenance/revision
5. statistical/search bias
6. calibration/uncertainty
7. causal claims
8. contradiction handling
9. source-health and quota behavior
10. negative-control/relevance
11. adversarial robustness
12. test quality/mutation resistance
13. performance/complexity
14. backwards compatibility
15. execution separation
16. documentation/resumability

Each finding records:

- severity;
- load-bearing status;
- exact evidence;
- remediation;
- validation;
- independent review disposition.

A finding cannot disappear merely because it is inconvenient.

## 17. Source-adapter admission contract

A new adapter is admitted only when it proves:

- legal/authorized access class;
- stable source identity;
- explicit timing semantics;
- revision behavior;
- entity mapping;
- unit/schema definition;
- historical availability policy;
- rate/quota behavior;
- error classification;
- retry policy;
- provenance URI/reference;
- point-in-time replay behavior;
- tests for future-data rejection;
- tests for malformed/untrusted data;
- relevance classification.

Vendor redundancy is useful only when sources are epistemically independent. Two vendors relaying the same upstream feed do not count as two independent confirmations.

## 18. GitHub control plane

Durable state remains GitHub-first.

Required homes:

- `.icarus_loop/state.json` — current delta, source capability states, unresolved findings, checkpoints;
- design specs — architectural intent;
- implementation plans — executable task sequence;
- tests/code — executable evidence;
- trial/evidence artifacts — machine-readable records when implemented;
- audit ledger — findings/remediation status when implemented.

Every cycle loads only the minimum delta required.

## 19. Evolution sequence

### Stage 0 — Foundation verification and remediation

Run existing tests and extreme audits. Fix before expansion.

### Stage 1 — Capability registry + provenance DAG + trial ledger

Establish the control plane before adding more source breadth.

### Stage 2 — Calibration, confidence decomposition, abstention, staleness

Make epistemic limits measurable.

### Stage 3 — Negative knowledge + stronger novelty + search-aware statistics

Control research multiplicity before accelerating discovery.

### Stage 4 — Regime/changepoint and causal-validation layers

Add context dependence only after trial accounting is reliable.

### Stage 5 — Authorized domain adapters

Admit real sources one family at a time through the source-admission contract.

Initial priority should favor sources with strong point-in-time semantics and high research value, not the greatest number of available connectors.

### Stage 6 — Shadow system integration

Produce proof-carrying candidates and validate system-level interactions without live execution authority.

## Testing strategy

All implementation uses TDD.

Minimum v2 test classes:

- capability state transitions;
- auth/quota/rate-limit distinction;
- future-knowledge rejection;
- revision replay;
- provenance DAG integrity;
- recursive invalidation;
- source duplication detection;
- irrelevant-source negative control;
- opinion-vs-observation separation;
- trial-count preservation;
- holdout non-reuse;
- search-family accounting;
- calibration drift;
- abstention triggers;
- regime assignment as-of;
- causal-claim labeling;
- cemetery resurrection gate;
- proof-package completeness;
- candidate non-execution;
- GitHub resume/checkpoint integrity.

Property/invariant tests should cover:

- no artifact with incomplete provenance can become integration-ready;
- no evidence with `available_at > decision_at` can influence historical decisions;
- no source outage changes a past accepted observation;
- no candidate can set `execution_authorized=true`;
- invalidated evidence propagates to dependents;
- source duplication cannot increase confidence as if independent.

## Acceptance criteria

The v2 architectural program is successful when:

- existing foundation is runtime-verified;
- every external source is governed by a capability record;
- provenance is traceable end to end;
- every research attempt belongs to a trial family;
- search intensity affects evidentiary hurdles;
- uncertainty is calibrated and decomposed;
- abstention is implemented and tested;
- negative knowledge prevents repeated dead ends;
- regime validity is point-in-time;
- causal claims carry identification assumptions;
- source outages, quotas, and schema changes are explicit states;
- proof-carrying candidates are independently reviewable;
- integration remains research-only;
- another high-capability agent can resume from GitHub alone.

## Explicit non-goals

v2 does not:

- promise an unbeatable or unbreakable trading system;
- infer inaccessible private facts;
- use complexity as evidence of edge;
- auto-install arbitrary plugins or credentials;
- auto-promote research into trading;
- optimize only for historical P&L;
- replace scientific judgment with one metric;
- treat all connector outputs as equally trustworthy;
- use a data source merely because it is available.

## Design decisions locked by this spec

- Runtime verification precedes v2 implementation.
- Source capability state is versioned and expiring, not assumed permanent.
- Search history is part of the evidence.
- Provenance lineage is explicit and dependency-light.
- Confidence is decomposed.
- Abstention is first-class.
- Negative knowledge is durable.
- Relevance is gated before normalization.
- Duplicate vendors do not automatically increase certainty.
- Causality requires an identification story.
- Integration candidates carry proof, failure history, and rollback conditions.
- Execution authority remains false.

## References

Bailey, D. H., & López de Prado, M. (2014). The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality. *The Journal of Portfolio Management, 40*(5), 94–107. DOI: 10.3905/jpm.2014.40.5.094.

Gibbs, I., & Candès, E. J. (2021). Adaptive Conformal Inference Under Distribution Shift. arXiv. DOI: 10.48550/arXiv.2106.00170.

OpenLineage. (2026). OpenLineage specification and facets documentation, version observed during this design cycle: 1.53.0.

## Knowledge delta

This spec is the canonical v2 architectural intent.  
The prior Federated Research Mesh spec remains historical context for the implemented foundation.  
Cycle state and the written-spec review gate are persisted in `.icarus_loop/state.json`.  
No engine code is changed by this design cycle.
