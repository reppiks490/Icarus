# ICARUS ASCENDANCY — Open-World Autonomous Intelligence Architecture

**Date:** 2026-10-01  
**Status:** Proposed design for implementation  
**Repository:** `reppiks490/Icarus`  
**Target branch:** `feat/unified-intelligence-spine`

## 1. Intent

ICARUS ASCENDANCY turns the existing ICARUS federation into a continuously self-improving research organism whose job is to:

1. observe the market and its own behavior;
2. discover where its current representations fail;
3. search for or invent alternate representations, models, mechanisms, and architectures;
4. reconstruct useful ideas from external systems without blindly copying them;
5. compete native, foreign, generated, and hybrid candidates under one causal evidence contract;
6. falsify aggressively;
7. measure conditional incremental information rather than raw standalone performance;
8. promote only what survives protected validation;
9. retire redundant, decayed, fragile, or dominated components;
10. preserve ancestry, negative results, contradictions, and causal provenance;
11. repeat indefinitely as a bounded research process.

“Indefinitely autonomous” means the research loop can continue without manual prompting when its scheduler/runtime is active and inputs are available. It does **not** mean unlimited compute, unbounded self-modification, removal of safety boundaries, guaranteed discovery, guaranteed profitability, or automatic broker authority.

“Holy grail logic” is treated as a search objective: discover unusually strong, robust, portable market mechanisms. No component may claim such status without evidence.

## 2. Architectural principle

No named subsystem is permanent.

Every subsystem, candidate, foreign lens, generated model, or composite architecture is treated as a revocable contributor with measurable:

- unique information;
- redundancy;
- calibration;
- stability;
- causal integrity;
- regime coverage;
- latency and compute cost;
- operational reliability;
- maintenance burden;
- failure modes;
- drift;
- evidence ancestry;
- protected outcome quality.

Core status is earned and can later be lost.

## 3. ASCENDANCY control plane

ASCENDANCY sits above and between the existing systems rather than replacing their internal implementations.

```
                                ICARUS ASCENDANCY
                                        |
         +------------------------------+------------------------------+
         |                              |                              |
   REALITY ENGINE                 ADVERSARY ENGINE               INVENTION ENGINE
         |                              |                              |
         +----------------------+-------+------------------------------+
                                |
                        UNIVERSAL CLAIM BUS
                                |
                +---------------+----------------+
                |                                |
        ARCHITECTURE GENOMES              CANDIDATE FOUNDRY
                |                                |
                +---------------+----------------+
                                |
                         COMPETITIVE ARENA
                                |
                   FALSIFICATION / VALIDATION
                                |
                     INFORMATION CONTRIBUTION
                                |
                 +--------------+--------------+
                 |                             |
              RETIRE                        ABSORB
                                               |
                                         ICARUS N+1
                                               |
                                               +--> repeat
```

ASCENDANCY is research/shadow infrastructure by default and preserves the repository’s existing explicit authority boundaries.

## 4. Universal Intelligence Claim

All major contributors must be adaptable into one canonical claim envelope while retaining their native state.

Required fields:

- source;
- source version / exact commit;
- source kind: native, foreign_lens, generated, hybrid, human, experiment;
- asset;
- semantic key;
- observed_at;
- received_at;
- calculated_at;
- valid_from / valid_until where applicable;
- regime;
- horizon;
- stance or distribution;
- confidence;
- evidence class;
- evidence lineage;
- dependencies;
- contradictions;
- falsifiers;
- source health;
- cost/latency metadata;
- details.

Evidence classes remain aligned with APEX:

- observed;
- derived;
- reconstructed;
- inferred;
- unavailable.

Unavailable evidence cannot contribute positive confirmation.

## 5. Unified Intelligence Spine

The spine is the first execution layer of ASCENDANCY.

Responsibilities:

- normalize heterogeneous subsystem outputs into canonical claims;
- preserve source identity;
- group semantically comparable claims;
- discount shared ancestry;
- preserve disagreement;
- expose structural novelty;
- expose structural redundancy;
- provide causal as-of reads;
- never equate structural novelty with predictive edge.

The existing preliminary `icarus_engine/unified_intelligence.py` branch work is considered exploratory until rebuilt/validated under this design and TDD plan.

## 6. Architecture Genome

ICARUS topology becomes an explicit research object.

A genome contains:

- nodes;
- node versions;
- edges;
- adapters;
- arbitration rules;
- gating rules;
- feature transforms;
- regime routing;
- latency tier placement;
- resource limits;
- experimental metadata;
- parent genomes;
- mutation history.

Genomes never directly mutate the production topology.

## 7. Architecture Compiler

The compiler converts a valid research genome into an isolated runnable graph.

Requirements:

- contract validation before construction;
- cycle checks where cycles are prohibited;
- explicit dependency availability;
- latency-tier compatibility;
- deterministic construction;
- no implicit production bindings;
- no broker credentials in generated research runtimes;
- reproducible runtime identity hash;
- fail-closed behavior for unavailable dependencies.

Most architectural experiments should change composition data, not source code.

New source code is generated only when the candidate requires a genuinely new mechanism.

## 8. Candidate Foundry

The foundry accepts candidates from:

- existing ICARUS subsystems;
- F4D3 and later foreign lenses;
- public research;
- user-provided research;
- residual/unknown-unknown findings;
- parameter mutations;
- representation mutations;
- architecture mutations;
- interaction discoveries;
- generated mathematical hypotheses.

Each candidate must declare before protected evaluation:

- hypothesis;
- mechanism;
- expected advantage;
- required observations;
- falsifiers;
- parent lineage;
- code/data revision;
- complexity cost;
- intended regimes;
- comparison baseline.

Candidates without falsifiers remain exploratory and cannot advance.

## 9. Foreign Lens Framework

External systems are represented as removable lenses, not permanent peers.

Initial example:

`Eyes Through F4D3`

A foreign lens has:

- confirmed concepts;
- directly implied concepts;
- inferred concepts;
- unknowns;
- reconstructed transforms;
- provenance;
- confidence;
- version history.

Its original reconstruction remains immutable as a baseline.

Derived variants may include:

- F4D3 x Chronofold;
- F4D3 x Psi;
- F4D3 x APEX;
- F4D3 x ARGUS;
- F4D3 x multi-system hybrids.

This makes it possible to distinguish value from the original lens versus value invented by ICARUS after interaction.

## 10. Competitive Arena

Every candidate competes on identical causally valid data.

Arena dimensions include:

- predictive/outcome quality;
- calibration;
- drawdown;
- expected shortfall / tail behavior;
- stability;
- regime breadth;
- cross-instrument transport;
- transaction-cost sensitivity;
- latency sensitivity;
- data-quality sensitivity;
- parameter-basin robustness;
- dependence-adjusted effective sample;
- multiple-testing-adjusted evidence;
- OOD/drift resilience;
- deterministic replay;
- complexity;
- compute cost;
- unique information contribution.

No single scalar “best model” score is required. The default selection structure is Pareto-based plus explicit protected qualification gates.

## 11. Conditional Incremental Information

ASCENDANCY must distinguish:

```
Information(source; outcome)
```

from:

```
Information(source; outcome | rest of ICARUS)
```

The second quantity is the core contribution question.

The implementation may use multiple practical estimators depending on data type, but every reported result must include:

- estimator;
- sample;
- horizon;
- conditioning set;
- regime;
- confidence interval or uncertainty;
- leakage controls;
- effective sample;
- validation boundary.

A source with strong standalone behavior but near-zero conditional contribution is redundant.

## 12. Mechanism Extractor

When a candidate wins, ASCENDANCY must not assume the entire candidate is necessary.

It performs:

- feature ablation;
- subsystem ablation;
- interaction ablation;
- timing ablation;
- parameter perturbation;
- latency perturbation;
- cost perturbation;
- regime isolation;
- alternative representation tests.

The output is a mechanism decomposition:

- necessary;
- sufficient-looking but unproven;
- redundant;
- interaction-dependent;
- regime-dependent;
- unexplained residual.

Only surviving mechanisms advance.

## 13. Invention Engine

The invention engine generates falsifiable research candidates from typed transformation families.

Initial families:

- state-space models;
- Bayesian filters;
- spectral analysis;
- wavelets;
- nonlinear dynamics;
- information theory;
- graph models;
- causal models;
- topology;
- geometry;
- stochastic processes;
- control theory;
- game theory;
- optimization;
- multiscale transforms;
- representation learning;
- ensemble/disagreement transforms;
- market-clock transforms.

The engine may compose transformations, but each generated candidate must remain reproducible and bounded.

Generation does not imply promotion.

## 14. Unknown-Unknown Engine

This engine searches for structured failure shared across current models.

Inputs include:

- prediction residuals;
- calibration residuals;
- disagreement;
- reconstruction error;
- OOD scores;
- regime ambiguity;
- unexplained volatility;
- unexplained reactions;
- missing-reaction diagnostics;
- cross-asset relationship breaks;
- source divergence.

It detects:

- residual clusters;
- change points;
- synchronized model failures;
- unexplained lead/lag;
- persistent conditional bias;
- new covariance structure;
- representation collapse.

Each persistent phenomenon receives an identity and becomes a research object with:

- first seen;
- last seen;
- affected assets/regimes;
- supporting evidence;
- known failed explanations;
- candidate latent variables;
- next decisive experiment.

## 15. Mutation hierarchy

ASCENDANCY supports three mutation classes:

### Level 1 — Parameter mutation

Example: fixed cycle period versus neighboring periods.

### Level 2 — Representation mutation

Example: wall-clock time versus activity time or information time.

### Level 3 — Architecture mutation

Examples:

- split node;
- merge nodes;
- replace node;
- reroute dependency;
- change arbitration;
- add new latent state;
- remove redundant contributor.

Level 3 changes remain research-only until separately promoted.

## 16. Heredity

Every candidate and genome preserves:

- parents;
- mutations;
- source commits;
- data versions;
- experiments;
- outcomes;
- rejected branches;
- survival reason;
- retirement reason.

The system must be able to answer:

- where did this idea come from?
- which parent contributed the useful mechanism?
- which mutation created the improvement?
- what failed?
- under which regime?
- what evidence would reverse the conclusion?

## 17. Extinction and decay

Every contributor has a lifecycle:

```
DISCOVERED
RECONSTRUCTED
CHALLENGER
VALIDATED
CONTRIBUTOR
CORE
DECAYING
REDUNDANT
QUARANTINED
RETIRED
```

Retirement can be triggered by:

- sustained zero incremental information;
- calibration decay;
- regime collapse;
- reproducibility failure;
- provenance failure;
- latency/cost dominance;
- superior replacement;
- source degradation.

Raw evidence and historical results remain immutable after retirement.

## 18. Autonomous research loop

When scheduler/runtime prerequisites are available:

```
observe
-> settle outcomes
-> identify failures/gaps
-> prioritize information gain
-> search/invent candidates
-> construct isolated runtime
-> replay/train
-> falsify
-> validate
-> measure incremental contribution
-> extract mechanism
-> promote/retire in research state
-> update dashboard
-> repeat
```

The loop must be resumable, idempotent, budget-aware, and able to survive connector/provider outages without fabricating evidence.

## 19. Resource governance

Autonomy must be resource-bounded.

Every experiment records:

- estimated compute cost;
- actual compute cost when measurable;
- provider cost when applicable;
- wall-clock duration;
- expected information value;
- cancellation reason;
- timeout state.

The scheduler prioritizes expected information gain per constrained resource.

No “infinite” loop may mean uncontrolled resource consumption.

## 20. Authority

ASCENDANCY may autonomously:

- observe;
- ingest evidence;
- generate hypotheses;
- build research candidates;
- build research genomes;
- run replay/backtests;
- run falsification;
- retire research candidates;
- rank research priority;
- update research dashboards;
- preserve artifacts.

ASCENDANCY may not, by this design alone:

- place broker orders;
- cancel broker orders;
- change live positions;
- change live sizing;
- silently replace the production strategy;
- bypass protected qualification;
- convert inference into observation;
- fabricate unavailable market data.

Existing authority flags remain explicit.

## 21. Persistence

A durable ASCENDANCY store must preserve:

- claims;
- genomes;
- candidate lineage;
- experiments;
- arena results;
- residual phenomena;
- mechanism decompositions;
- contribution estimates;
- retirement decisions;
- scheduler runs;
- resource accounting;
- dashboard event timeline.

SQLite WAL is acceptable for initial local implementation, aligned with current ICARUS persistence patterns.

## 22. HTTP / MCP surface

Initial read surfaces:

- `GET /api/ascendancy`
- `GET /api/ascendancy/arena`
- `GET /api/ascendancy/genomes`
- `GET /api/ascendancy/candidates`
- `GET /api/ascendancy/unknowns`
- `GET /api/ascendancy/invention`
- `GET /api/ascendancy/lineage`
- `GET /api/ascendancy/contributions`
- `GET /api/ascendancy/autonomy`

Research mutations must use authenticated admin/MCP routes and preserve false execution/production authority.

## 23. Dashboard — mandatory first-class surface

Everything material in ASCENDANCY must be visible in the ICARUS dashboard. No hidden “backend-only” evolution is considered complete.

Create an **ASCENDANCY** top-level tab with the following sections.

### A. Autonomy Core

Shows:

- research loop status;
- current cycle;
- scheduler state;
- active experiment;
- queued experiments;
- last completed experiment;
- interruption/recovery state;
- provider/source degradation;
- resource budgets;
- research throughput;
- blocked reasons.

### B. Architecture Genome

Interactive topology representation of:

- current ICARUS research genome;
- active challenger genomes;
- parent/child lineage;
- mutations;
- node status;
- retired nodes;
- changed edges;
- current experimental differences.

### C. Competitive Arena

Shows:

- incumbent;
- challengers;
- Pareto frontier;
- protected-gate state;
- OOS/holdout status;
- robustness diagnostics;
- regime performance;
- costs;
- latency;
- calibration;
- effective sample;
- multiple-testing state.

### D. Edge Foundry

Shows:

- newly generated hypotheses;
- candidate mechanism;
- origin;
- expected advantage;
- falsifiers;
- current stage;
- experiment status;
- result;
- rejection reason;
- surviving mechanism.

### E. Unknown Unknowns

Shows:

- active unexplained phenomena;
- residual clusters;
- synchronized model failures;
- affected assets/regimes;
- candidate explanations;
- experiments underway;
- unresolved duration;
- confidence that the residual is structured rather than noise.

### F. Foreign Lenses

Shows:

- Eyes Through F4D3;
- future external methodologies;
- reconstruction confidence;
- confirmed / implied / inferred / unknown concept counts;
- standalone contribution;
- conditional contribution;
- redundancy;
- interaction gains;
- descendants;
- retirement status.

### G. Mechanism Laboratory

Shows ablations and mechanism extraction:

- candidate full model;
- removed mechanism;
- delta;
- confidence;
- regime;
- interaction effects;
- necessary/optional/redundant status.

### H. Invention Engine

Shows:

- transformation families being explored;
- generated candidate count;
- killed candidate count;
- survivors;
- novelty;
- experiment budget;
- search frontier;
- failed idea memory.

### I. Evolution Tree

Shows:

- candidate/genome ancestry;
- mutations;
- promotion events;
- decay;
- retirement;
- resurrected ideas;
- negative-result lineage.

### J. Information Contribution Matrix

Pairwise and conditional contribution diagnostics among major systems.

Examples:

- Chronofold conditional on Psi;
- Psi conditional on APEX;
- F4D3 conditional on all native systems;
- hybrid conditional on parents.

Must distinguish structural novelty from outcome-validated incremental information.

### K. Truth / Epistemic Panel

Shows:

- observed vs derived vs reconstructed vs inferred vs unavailable;
- evidence ancestry;
- contradictions;
- stale evidence;
- leakage risk;
- source independence;
- unmeasured metrics.

### L. Research Event Timeline

Every significant autonomous event:

- discovered;
- hypothesized;
- tested;
- failed;
- survived;
- promoted in research;
- degraded;
- retired;
- recovered after outage.

## 24. Dashboard truth rules

The UI must never display:

- “holy grail found” without a defined and satisfied evidence contract;
- “autonomous” when the scheduler is not active;
- “learning” merely because code exists;
- 100% unless tied to the exact closed sample;
- missing values as zero;
- inferred values as observed;
- predicted incremental information when only structural novelty was measured.

Use statuses such as:

- UNMEASURED;
- UNAVAILABLE;
- WARMING;
- EXPLORATORY;
- VALIDATING;
- REJECTED;
- QUALIFIED_SHADOW;
- RETIRED;
- DEGRADED.

## 25. Failure behavior

ASCENDANCY fails locally, visibly, and conservatively.

Examples:

- candidate runtime crashes -> candidate FAILED, organism continues;
- source unavailable -> source UNAVAILABLE, no neutral fabricated value;
- invalid genome -> rejected before compile;
- stale evidence -> excluded;
- future evidence in historical replay -> rejected;
- insufficient sample -> UNMEASURED;
- provider outage -> queued/retryable state;
- generated code failure -> quarantined branch, never production;
- disagreement -> preserved.

## 26. Testing strategy

Required coverage includes:

- canonical claim validation;
- causal as-of filtering;
- shared-ancestry discounting;
- disagreement preservation;
- structural novelty labeling;
- architecture genome validation;
- compiler determinism;
- invalid topology rejection;
- candidate lifecycle;
- foreign-lens quarantine;
- arena comparison isolation;
- protected holdout preservation;
- conditional contribution bookkeeping;
- unknown-unknown persistence;
- heredity;
- extinction;
- authority invariants;
- persistence/restart recovery;
- API authentication;
- dashboard rendering of missing/unavailable states;
- dashboard integration tests;
- no production/broker path from ASCENDANCY.

## 27. Delivery sequence

Implementation should be staged so every phase yields working software:

1. canonical claim + spine;
2. durable store;
3. genome + compiler;
4. candidate foundry;
5. arena;
6. conditional contribution;
7. mechanism extractor;
8. unknown-unknown engine;
9. invention engine;
10. heredity/extinction;
11. autonomous scheduler;
12. API/MCP;
13. complete ASCENDANCY dashboard;
14. F4D3 foreign-lens adapter;
15. end-to-end replay and protected validation.

Dashboard work begins early enough that each backend phase becomes visible as it lands; it is not deferred until the end.

## 28. Success criteria

ASCENDANCY is considered architecturally implemented only when ICARUS can, without manual prompting during a running research cycle:

1. identify a current model failure or open research question;
2. generate or ingest a challenger;
3. construct a reproducible research runtime;
4. evaluate it on causally valid historical data;
5. falsify or validate it under existing protected rules;
6. measure what it adds conditional on existing ICARUS;
7. preserve the complete lineage and result;
8. retire or advance it in research state;
9. show the entire process truthfully in the dashboard;
10. resume after restart without losing state.

No success criterion requires or implies guaranteed profit, guaranteed market prediction, automatic live execution, or unrestricted self-modification.

## 29. Reversal conditions

This design should be revised if evidence shows:

- the universal claim contract destroys essential subsystem semantics;
- architecture-genome experiments cannot remain reproducible;
- contribution estimators are too unstable to support retirement decisions;
- autonomous search creates excessive false discoveries despite controls;
- dashboard complexity prevents truthful operator understanding;
- resource cost materially exceeds information gained.

The architecture should evolve when these conditions are observed rather than defending this design because it was once approved.
