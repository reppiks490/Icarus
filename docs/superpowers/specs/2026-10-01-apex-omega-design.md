# ICARUS APEX Ω — World Dynamics Intelligence Architecture

Status: **Design specification — approved in conversation, pending written-spec review before implementation plan**

Repository: `reppiks490/Icarus`  
Design base: `528bf702cbfb3cc490fbf39acef3f9f875850c82`  
Date: 2026-10-01  
Authority: research/shadow only

## 1. Purpose

APEX Ω is the federated intelligence layer that turns ICARUS from a collection of advanced research subsystems into one auditable computational world-model.

Its job is to reconstruct, without fabricating unavailable information:

```text
World
→ Information
→ Beliefs
→ Constraints
→ Participant decisions
→ Capital/hedging/forced flows
→ Liquidity and market state
→ Feedback into participants and world
```

APEX Ω must answer five operator questions simultaneously:

1. What is the world doing?
2. What mechanisms does ICARUS currently think are producing it?
3. What competing explanations remain viable?
4. What would falsify the dominant explanation?
5. How reliable is ICARUS itself right now?

Price prediction is an output of this process, not the architecture's organizing principle.

## 2. Design principles

1. **Federate instead of duplicate.** Existing Ψ, Chronofold, PANTHEON/AETHER, PARALLAX/DREAMSTATE, Adaptive Brain, Performance Proof, Champion/Challenger, DAEDALUS and AEGIS retain ownership of their native responsibilities.
2. **Evidence before authority.** APEX may combine evidence but may not manufacture evidence or silently promote inference into observation.
3. **Causal time is mandatory.** Event time, receipt time, calculation time and decision time remain distinct.
4. **Disagreement is first-class state.** Conflicting subsystems are not averaged into false consensus.
5. **Evidence ancestry matters.** Five outputs derived from one source are not five independent confirmations.
6. **Unknown is valid output.** Missing data remains `UNAVAILABLE`; unexplained phenomena remain unexplained until evidence supports an interpretation.
7. **Research cannot self-authorize execution.** `production_decision_authorized=false` and `execution_authorized=false` remain invariant throughout APEX.
8. **Complexity must earn its existence.** New models are admitted only when independent information/reliability gain justifies compute, dependency and failure-surface cost.
9. **Human authority remains external.** APEX can recommend, object, quarantine and abstain; it cannot rewrite its governing constraints.
10. **Replayability over narrative.** Every consequential belief must be reconstructible from durable evidence and exact code/data provenance.

## 3. Existing-system boundary

APEX Ω consumes but does not reimplement:

- **ICARUS Ψ** — latent pressure, microstructure elasticity, leadership, future-space diagnostics.
- **Chronofold Ξ** — causal spacetime / multiverse / geometry / navigation research.
- **PANTHEON** — adversarial faculties, epistemics, ontology surprise, structural constraints, research attention.
- **AETHER** — bounded independent research swarm and research ecology.
- **PARALLAX** — observed counterfactual twin evidence.
- **DREAMSTATE** — bounded policy hypotheses built from qualified PARALLAX evidence.
- **Adaptive Brain** — shared candidate/evidence qualification and shadow routing.
- **Performance Proof** — settled outcome evidence and replay proof.
- **Champion/Challenger** — comparable empirical shadow tournaments.
- **DAEDALUS / AEGIS** — protected scientific validation and adversarial falsification.
- **SIBYL** — optional future-lightcone adapter when the subsystem actually exists on the running revision. APEX must degrade gracefully when absent.

APEX owns only the missing cross-system intelligence: participant reconstruction, force/cascade synthesis, causal world-state federation, evidence ancestry, belief lineage, model credibility, unknown-force analysis, self-model, conscience, reality gap and bounded architectural evolution.

## 4. High-level architecture

```text
                         HUMAN AUTHORITY
                              │
                    CONSTITUTION / KERNEL
                              │
                 EPISTEMIC IMMUNE SYSTEM
                              │
                    SCIENTIFIC GOVERNOR
                              │
              ┌───────────────┴────────────────┐
              │                                │
        WORLD DYNAMICS                    SELF MODEL
              │                                │
      ECONOMIC DIGITAL TWIN             MODEL ECOLOGY
              │                                │
      INSTITUTIONAL MECHANICS            REALITY GAP
              │                                │
       PARTICIPANT ECOLOGY              SELF-EVOLUTION LAB
              │                                │
       BELIEF / GAME MODEL                     │
              │                                │
        CAUSAL DYNAMICS ───────────────────────┘
              │
        MARKET DYNAMICS
              │
        MARKET MICROSTRUCTURE
              │
     OBSERVATION / EVIDENCE FABRIC
              │
           REAL WORLD
```

## 5. Repository decomposition

The scope is intentionally decomposed so each unit has one clear responsibility and can be tested independently.

```text
icarus_engine/apex/
    __init__.py
    contracts.py
    evidence.py
    ancestry.py
    beliefs.py
    credibility.py
    participants.py
    crowdhunt.py
    institutional.py
    force_field.py
    liquidity.py
    cascade.py
    causality.py
    expectations.py
    worlds.py
    macro_state.py
    criticality.py
    unknown_force.py
    information_gain.py
    epistemics.py
    conscience.py
    reality_gap.py
    self_model.py
    evolution.py
    adapters.py
    store.py
    kernel.py

icarus_engine/apex-ui.js
docs/icarus/APEX_OMEGA.md
tests_engine/test_apex_*.py
```

Integration-only modifications are expected in:

```text
icarus_engine/server.py
icarus_engine/dashboard.html
icarus_engine/brain.py
icarus_bridge/mcp_server.py
tests_engine/test_dashboard_js.py
tests_engine/test_mcp_server.py
```

Existing sibling subsystem internals should not be modified unless a proven interface defect makes it necessary.

## 6. Canonical evidence contract

Every APEX evidence item must include:

```json
{
  "evidence_id": "content-addressed id",
  "kind": "observed|derived|reconstructed|inferred|unavailable",
  "subject": "typed subject id",
  "value": {},
  "source": {
    "subsystem": "psi|chronofold|pantheon|...",
    "source_repo": "owner/repo",
    "source_commit": "40-char sha",
    "source_record_id": "immutable native id"
  },
  "observed_at": "UTC timestamp",
  "received_at": "UTC timestamp",
  "calculated_at": "UTC timestamp",
  "valid_from": "UTC timestamp",
  "valid_until": null,
  "confidence": 0.0,
  "quality": 0.0,
  "dependencies": [],
  "contradictions": [],
  "falsifiers": [],
  "execution_authorized": false,
  "production_decision_authorized": false
}
```

Rules:

- booleans cannot be coerced to numbers;
- NaN/Inf fail closed;
- confidence/quality must already lie in declared bounds;
- observed evidence requires a concrete source record;
- reconstructed/inferred evidence must preserve source dependencies;
- unavailable evidence may not contribute positive confidence;
- historical/as-of reads may use only evidence observed and received at or before the as-of boundary;
- immutable evidence identity excludes wall-clock-only metadata that would destroy retry idempotence.

## 7. Evidence ancestry DAG

APEX maintains a DAG from raw observations through transforms to beliefs.

The ancestry engine computes:

- nominal supporting count;
- effective independent evidence-family count;
- shared-source overlap;
- feature/data/model lineage overlap;
- semantic duplicate detection;
- dependency depth;
- contradiction ancestry.

Consensus strength is discounted when branches converge on the same underlying evidence.

A belief must never become stronger merely because the same evidence was repackaged by several agents.

## 8. Belief object

Every consequential APEX conclusion is represented as a durable belief:

```text
belief_id
claim
scope
as_of
source_revision
state = proposed|supported|strongly_supported|contradicted|invalid|quarantined

observations[]
derived_evidence[]
assumptions[]
dependencies[]
contradictions[]
falsifiers[]

nominal_confidence
independence_adjusted_confidence
calibration_bucket
credibility_weight
epistemic_uncertainty
aleatoric_uncertainty

authority
```

Belief state transitions are append-only audit events.

## 9. Participant State Observatory

APEX reconstructs state for participant classes, including:

- discretionary retail;
- breakout/momentum retail;
- leveraged retail;
- systematic trend/CTA;
- volatility-control;
- options dealers;
- market makers/liquidity providers;
- arbitrageurs;
- leveraged funds;
- asset managers;
- passive/index flows;
- crypto leveraged cohorts;
- large observable on-chain cohorts when legitimately sourced;
- unidentified/unknown cohorts.

For participant class `i`, price region `p`, horizon `h` and time `t`:

```text
Z(i,p,t,h) =
entry_density
directional_exposure
stop_density
liquidation_vulnerability
break_even_density
profit_take_density
forced_action_propensity
migration_velocity
persistence
decay
confidence
```

These are reconstructed distributions unless a legitimate source directly observes the quantity.

## 10. CROWDHUNT Ω

Retail hunting remains a dedicated side quest inside the participant model.

It estimates:

- long/short entry density;
- long/short trapped-position density;
- stop density above/below;
- breakout-order density;
- pain gradient;
- forced-exit pressure;
- crowd migration;
- persistence/decay;
- evidence independence;
- explicit falsifiers.

CROWDHUNT may never claim exact retail positions without account-level/source evidence.

## 11. Institutional Mechanics Engine

The institutional engine models mechanically induced flows, including where evidence exists:

- margin mechanics;
- options/futures expiry;
- settlement;
- index/rebalance mechanics;
- ETF creation/redemption;
- volatility targeting;
- systematic trend thresholds;
- dealer hedging;
- collateral/funding constraints;
- basis convergence;
- portfolio risk-budget rebalancing.

The engine must distinguish explicit known mechanics from inferred institutional behavior.

## 12. Inverse Participant Engine

APEX may infer a bounded family of objectives/constraints that could explain observed behavior:

```text
probable time horizon
risk sensitivity
leverage sensitivity
liquidity sensitivity
hedging requirement
loss threshold
rebalancing rule
activation conditions
```

This is inverse modeling, not mind-reading. Multiple plausible objective sets remain separate hypotheses.

## 13. Recursive Expectation Graph

APEX can represent bounded beliefs-about-beliefs:

`B_i(B_j(...))`.

Requirements:

- explicit recursion-depth cap;
- uncertainty penalty at each inferred level;
- source evidence at the root;
- no unbounded narrative recursion;
- disagreement preserved.

## 14. Market Ecology Engine

Participant relations are typed:

- competition;
- crowding;
- hedging dependence;
- liquidity dependence;
- information dependence;
- capital dependence;
- stabilizing feedback;
- destabilizing feedback.

These relations are evidence-backed graph edges, not metaphors promoted to facts.

## 15. Liquidity Topology

Liquidity is modeled as a field `L(p,t,h)`, including where observable:

- depth;
- spread;
- replenishment;
- resilience;
- absorption;
- vacuum regions;
- adverse-selection response;
- recovery speed.

Missing depth/order-book data remains unavailable. Proxy liquidity metrics must be labeled as proxies.

## 16. Market Pressure Tensor

The unified pressure representation is:

`F(p,t,h,i,d)`

where:

- `p`: price region;
- `t`: time;
- `h`: horizon;
- `i`: participant/mechanism;
- `d`: direction.

The tensor supports questions such as:

> Which mechanism is expected to generate the greatest marginal pressure if price enters region X within horizon H?

No tensor element can exceed the authority of its evidence ancestry.

## 17. Cascade Topology

APEX constructs a directed cascade graph.

Each edge includes:

```text
source state
target state
activation condition
estimated delay
historical support
current support
independence
confidence
conditional intensity
falsifier
```

Examples may include stop activation → volatility expansion → liquidity deterioration → systematic threshold → additional forced flow, but the actual graph is evidence-driven.

Where appropriate, self-exciting event-process models may estimate clustering intensity; they must not be mislabeled as causal proof.

## 18. Reflexivity and criticality

APEX identifies positive and negative feedback cycles and estimates:

- loop membership;
- loop gain;
- damping;
- activation distance;
- current support;
- stability class.

Market-state classes:

```text
STABLE
COMPRESSED
METASTABLE
CRITICAL
CASCADE
REORGANIZING
UNKNOWN
```

Criticality diagnostics may include validated analogues of rising autocorrelation, variance expansion, slower recovery, cross-asset synchronization, liquidity fragility and feedback-gain change. No single statistic establishes criticality.

## 19. Multi-timescale causal graph

APEX maintains `C(i,j,τ)`, where causal support can differ by horizon.

Every causal edge records:

- source and target;
- horizon;
- temporal precedence;
- proposed mechanism;
- observational support;
- intervention/natural-experiment support where available;
- confounders;
- contradictory evidence;
- falsifiers;
- status:
  `correlated|temporally_supported|mechanistically_supported|intervention_supported|contradicted|unknown`.

Prediction improvement alone cannot upgrade an association to causal status.

## 20. Economic World State

APEX federates macro/economic evidence into versioned world-state hypotheses covering, where sourced:

- growth;
- inflation;
- rates/yield curve;
- credit;
- labor;
- consumption;
- production;
- FX;
- commodities/energy;
- liquidity/financial conditions;
- earnings expectations;
- policy/event state.

Economic state and market response remain distinct. A macro interpretation cannot be forced to explain price merely because it sounds plausible.

## 21. Information Propagation Engine

Information is modeled as a propagation network across markets/domains:

- origin;
- first responder;
- propagation delay;
- secondary responders;
- attenuation/amplification;
- feedback;
- unresolved channels.

This reuses Ψ/PANTHEON/Chronofold evidence where available rather than replacing those systems.

## 22. Structured counterfactual worlds

APEX maintains a weighted population of worlds:

```text
W =
market state
participant state
liquidity state
macro state
causal graph
constraints
assumptions
counterfactual branch history
weight
```

World updates:

- incompatible worlds lose weight or die;
- ambiguous worlds survive;
- branches split only when an uncertainty materially changes downstream state;
- equivalent branches may merge;
- a new world may be spawned when surviving worlds cannot explain observations.

This is a structured world-particle model, not a claim that the future is enumerable.

## 23. Attractors and bifurcations

APEX may identify candidate system-state basins such as:

- range equilibrium;
- trend equilibrium;
- volatility regime;
- liquidity-stress state;
- deleveraging state.

A bifurcation candidate exists when small changes in a controlling variable produce materially different reachable states. It remains a hypothesis until replicated and calibrated.

## 24. Unknown-Force Hunter

APEX computes model residuals between observed behavior and the explanatory envelope of existing world models.

Unknown-force states:

```text
KNOWN_KNOWN
KNOWN_UNKNOWN
UNKNOWN_KNOWN
UNKNOWN_UNKNOWN
```

An unknown-force event contains descriptors, not invented causes.

Repeated residual structures may create anonymous latent-variable candidates such as `latent_state_014`.

Semantic interpretation occurs only after independent replication and evidence supports a label.

## 25. Ontology Evolution

When the existing representation repeatedly cannot encode a replicated phenomenon:

1. record representation failure;
2. create an anonymous ontology candidate;
3. derive falsifiable predictions;
4. test across independent episodes/regimes;
5. admit, revise or retire the concept.

PANTHEON EX NIHILO should be reused as the primary representation-surprise faculty.

## 26. Active Information Gain

APEX ranks missing observations by expected value of information:

`VOI(X) = expected uncertainty/decision improvement - acquisition/compute cost`.

Outputs must distinguish:

- high-value missing data;
- unavailable data;
- available but low-value data;
- redundant data.

This drives sensor/research attention rather than indiscriminate ingestion.

## 27. Compute Attention Economy

Potential analyses are prioritized by:

```text
opportunity
× uncertainty reduction
× potential impact
× urgency
÷ computational cost
```

Heavy simulations are not always-on by default.

The compute governor must expose why expensive work was scheduled.

## 28. Aleatoric vs epistemic uncertainty

APEX separately estimates:

- aleatoric uncertainty: irreducible outcome randomness;
- epistemic uncertainty: missing information/model inadequacy.

These values must be calibration-backed. They may remain unmeasured until evidence supports decomposition.

## 29. Epistemic Immune System

The immune system detects and penalizes:

- shared-source contamination;
- circular reasoning;
- agent imitation;
- semantic duplicate evidence;
- future leakage;
- data leakage;
- selection bias;
- survivorship bias;
- multiple-testing abuse;
- regime overfitting;
- confidence inflation;
- source staleness;
- model monoculture.

It can quarantine a belief or model without destroying its historical audit record.

## 30. Model Monoculture Detector

Model diversity is measured using:

- data overlap;
- feature overlap;
- architecture overlap;
- training-history overlap;
- residual correlation;
- failure correlation.

Nominal model count and effective independent model count are both exposed.

## 31. Credibility economy

Each model/faculty receives dynamic research credibility based on:

```text
calibration
recency
regime match
evidence independence
data quality
replication
reality gap
historical overconfidence
```

Credibility influences research weighting only. It cannot bypass protected validation or authority gates.

## 32. Reality-Gap Monitor

For model/subsystem `i`:

`R_i(t) = D(predicted_i, observed)`.

States:

```text
NORMAL
DRIFTING
DEGRADED
INVALID
QUARANTINED
UNMEASURED
```

Growing reality gap automatically lowers model research authority.

## 33. Self Model and Capability Graph

APEX maintains explicit state for ICARUS itself:

- capabilities;
- data dependencies;
- model dependencies;
- calibration;
- known weaknesses;
- compute usage;
- latency;
- recent failures;
- current authority;
- exact code revision.

Capabilities have prerequisite graphs. If a prerequisite disappears, dependent conclusions are automatically degraded rather than continuing silently.

## 34. Synthetic Conscience

The conscience is not a claim of consciousness. It is a machine-enforced decision-audit institution composed of independent judges:

- Truth Judge;
- Uncertainty Judge;
- Risk Judge;
- Consistency Judge;
- Provenance Judge;
- Authority Judge.

Each produces its own verdict and evidence. Disagreement between judges is preserved.

Possible outputs:

```text
PASS
WARN
OBJECT
VETO
UNMEASURED
```

A research conclusion may be strong while the risk or authority judge still vetoes action.

## 35. Cognitive Dissonance Detector

APEX detects incompatible internal assumptions.

Example:

```text
World model: liquidity fragile
Execution model: assumes normal liquidity
Candidate strategy: requires reliable exits
```

This becomes a structured contradiction with affected downstream beliefs/capabilities.

## 36. Constitution / formal invariant kernel

Programmatic invariants:

1. no future evidence;
2. no broker authority from APEX;
3. no production authorization from research confidence;
4. no inferred → observed relabeling;
5. no NaN/Inf propagation;
6. no source-free observed claim;
7. no hidden authority escalation;
8. no mutation of immutable evidence/outcome history;
9. no candidate promotion around required protected gates;
10. no silent suppression of contradictory evidence.

These invariants live in code, not prompts.

## 37. Scientific Governor

The governor manages research attention, not trading.

It ranks:

- unresolved hypotheses;
- candidate experiments;
- anomalies requiring replication;
- over-researched hypotheses;
- theories due for retirement;
- observations with maximum discriminative information value.

## 38. Automated experiment design

Given competing hypotheses `H1...Hn`, APEX can propose the observation or replay experiment expected to best distinguish them.

Experiment proposals must specify:

- hypotheses;
- observable predictions;
- discriminating observation;
- success/failure criteria;
- dataset/clock/cost contract;
- multiple-testing family;
- expected information gain.

Execution of external/paid experiments remains externally authorized.

## 39. Theory Library and Temporal Knowledge Graph

APEX preserves:

- supported theories;
- rejected theories;
- conditional theories;
- regime-specific theories;
- unresolved theories;
- obsolete theories;
- negative results.

Every fact/belief has a validity interval so historical reconstruction can answer:

> What could ICARUS legitimately have known at time T?

without future leakage.

## 40. Proof-carrying beliefs

Downstream systems consume compact proof packets containing:

```text
claim
scope
evidence ids
ancestry root ids
assumptions
calibration
contradictions
falsifiers
source revisions
model revision
causal-time boundary
authority
```

Consumers may fail closed if required proof fields are absent.

## 41. Bounded self-evolution

APEX may propose architectural/model changes but cannot directly deploy them.

Pipeline:

```text
propose
→ sandbox
→ replay/backtest
→ adversarial test
→ ablation
→ calibration
→ complexity analysis
→ independent review
→ human-controlled promotion
```

No self-modifying production path exists.

## 42. Architectural complexity tax

Every proposed model/subsystem receives a complexity-adjusted value:

```text
independent information gain
× reliability gain
÷
(compute cost + dependency cost + failure-surface cost)
```

A larger model can lose to a smaller one.

APEX should support pruning, distillation and retirement when they preserve evidence quality while reducing complexity.

## 43. Persistence

Initial implementation should preserve the repository's low-dependency pattern.

Preferred durable store:

`research/apex.sqlite3`

SQLite WAL tables should include:

- evidence;
- evidence_dependencies;
- beliefs;
- belief_events;
- participant_states;
- force_fields;
- cascade_edges;
- causal_edges;
- world_states;
- unknown_force_events;
- model_credibility;
- reality_gap;
- conscience_verdicts;
- theory_records.

Schema migrations must be additive/backward compatible.

## 44. HTTP API

Read-only:

```text
GET /api/apex
GET /api/apex/participants
GET /api/apex/crowdhunt
GET /api/apex/forces
GET /api/apex/cascades
GET /api/apex/causality
GET /api/apex/worlds
GET /api/apex/epistemics
GET /api/apex/self
GET /api/apex/conscience
```

Authenticated research mutations:

```text
POST /admin/apex/evidence
POST /admin/apex/outcome
POST /admin/apex/model-observation
POST /admin/apex/experiment
```

These endpoints may mutate research evidence only.

They may not:

- submit/modify orders;
- arm a broker;
- flatten or change a live/paper position;
- mutate strategy inputs;
- authorize production models.

## 45. MCP surface

MCP tools should expose:

- APEX world state;
- participant/crowd map;
- force/cascade topology;
- belief lineage;
- evidence ancestry;
- reality gap;
- conscience state;
- unknown-force events;
- provenance-bearing evidence ingest;
- matured outcome ingest.

All responses preserve false production/execution authority flags.

## 46. Trader UI

Add one APEX Ω dashboard tab with panels:

```text
WORLD
PARTICIPANTS
CROWDHUNT
FORCES
LIQUIDITY
CASCADES
CAUSAL GRAPH
COUNTERFACTUAL WORLDS
UNKNOWN FORCE
EPISTEMIC HEALTH
MODEL HEALTH
CONSCIENCE
```

The UI must show confidence, independence, missing data and contradictions, not merely a single bullish/bearish number.

## 47. Failure behavior

APEX must fail closed but remain observable.

Examples:

- missing sibling subsystem → `UNAVAILABLE`, not startup failure;
- malformed external evidence → reject mutation, preserve prior state;
- persistence write failure → do not publish unpersisted "durable" state;
- corrupted row → quarantine/report row; do not reinterpret silently;
- subsystem snapshot exception → mark that adapter degraded while allowing unrelated adapters to operate;
- unavailable code provenance → reject provenance-required mutations;
- source-time after as-of boundary → exclude from historical reconstruction;
- calculation error → publish explicit component failure status, not invented neutral value.

## 48. Test contract

Implementation is not complete until regression coverage demonstrates at least:

### Causal-time integrity
- future observed_at rejected/excluded;
- future received_at rejected/excluded for as-of state;
- observed/received/calculated times remain distinct;
- deterministic historical replay.

### Truth semantics
- inferred cannot become observed;
- unavailable cannot contribute confirming confidence;
- proxies remain labeled proxies;
- missing order-book/OI/liquidation data cannot be invented.

### Evidence independence
- shared ancestry lowers effective support;
- semantic duplicates do not inflate consensus;
- monoculture reduces effective model diversity.

### Persistence
- duplicate ingestion idempotent;
- immutable identity stable across retry;
- WAL store survives reopen/replay;
- corrupted/incomplete rows fail closed.

### Numerical safety
- bool-as-number rejected;
- NaN/Inf rejected;
- fractional integer where prohibited rejected;
- all confidence/quality values bounded.

### Participant/cascade logic
- insufficient evidence yields unknown/early state;
- contradictory evidence survives fusion;
- cascade edge cannot become causal solely from correlation;
- unknown-force detector emits no invented cause.

### Epistemics/self-model
- rising reality gap reduces credibility;
- missing capability prerequisite degrades dependent capability;
- internal contradictory assumptions generate conscience/consistency objection.

### Authority
- every APEX snapshot has `production_decision_authorized=false`;
- every APEX snapshot has `execution_authorized=false`;
- no APEX route calls broker/order APIs;
- no APEX mutation changes strategy inputs or positions.

### Integration
- missing SIBYL degrades gracefully;
- Ψ/PANTHEON/PARALLAX/DREAMSTATE/Chronofold adapters are read-only from APEX;
- dashboard renders empty/partial states truthfully;
- MCP schema parity;
- Linux and Windows causal-time tests.

## 49. Delivery decomposition

Because APEX Ω is larger than a safe single implementation batch, implementation is decomposed into six independently testable projects. Each project must receive its own implementation plan before code changes begin.

### Project A — Epistemic Kernel
Contracts, evidence store, ancestry DAG, belief graph, proof packets, constitution invariants, persistence.

### Project B — Participant/Force Layer
Participant State Observatory, CROWDHUNT Ω, institutional mechanics, liquidity topology, market pressure tensor.

### Project C — Causal/Cascade Layer
Causal graph, multi-horizon causality, cascade topology, reflexivity, criticality, expectation graph.

### Project D — World/Unknown Layer
Economic world state, structured counterfactual worlds, unknown-force hunter, latent/ontology candidates, information propagation.

### Project E — Self/Science Layer
Credibility economy, reality gap, self model, capability graph, conscience, active information gain, scientific governor, bounded self-evolution proposals.

### Project F — Integration Surface
Adaptive Brain registration, HTTP API, MCP, trader UI, durable evolution receipt, cross-platform integration tests.

Projects A→F are dependency ordered. Later projects may begin only when the interfaces they consume are stable and verified.

## 50. Success criteria

APEX Ω is successful when ICARUS can produce one coherent world-state snapshot that:

- traces every consequential conclusion to exact evidence ancestry;
- distinguishes observation/reconstruction/inference/unavailable;
- reconstructs participant and forced-flow states without pretending to possess hidden account-level data;
- maintains competing causal explanations and worlds;
- detects unresolved residual/ontology failure without inventing causes;
- measures which models are currently credible or drifting;
- exposes what information would most reduce uncertainty;
- identifies internal contradictions;
- issues independent conscience verdicts;
- preserves deterministic historical replay;
- remains research/shadow only;
- fails closed when evidence/provenance/causal time are insufficient.

## 51. Explicit non-goals

APEX Ω does not promise:

- omniscience;
- certainty about hidden participant positions;
- guaranteed prediction accuracy;
- literal physical laws of markets;
- unrestricted autonomous self-modification;
- automatic production deployment;
- hidden broker authority;
- invented order flow, depth, funding, OI, liquidation or institutional positions.

Its objective is stronger: maximize justified understanding while preserving explicit uncertainty.

## 52. Staleness conditions

This specification must be reviewed if any of the following change materially before implementation:

- the canonical `main` interfaces for Adaptive Brain, Ψ, Chronofold, PANTHEON, PARALLAX or DREAMSTATE;
- the authority boundary for research subsystems;
- repository persistence conventions;
- dashboard/MCP server architecture;
- SIBYL lands with an interface incompatible with the optional adapter assumed here.

