# ICARUS APEX Ω

APEX Ω is ICARUS's research/shadow **world-dynamics intelligence and epistemic-governance layer**. It federates existing ICARUS research systems into one evidence-bounded world model without converting hidden-state inference into observation or granting itself trading authority.

This document describes the installed Projects A–F runtime surface. The architecture specification and implementation plans remain under `docs/superpowers/`.

## Truth and authority contract

APEX recognizes exactly five evidence classes:

- `observed` — directly reported by a concrete source record;
- `derived` — deterministic transformation of source evidence;
- `reconstructed` — multi-source estimate of latent state;
- `inferred` — bounded hypothesis from incomplete evidence;
- `unavailable` — explicitly missing information.

Every consequential path preserves:

```text
observed_at
received_at
calculated_at
valid_from / valid_until
source repository
exact source commit
source record id
dependencies
contradictions
falsifiers
```

Historical reads require both `observed_at <= as_of` and `received_at <= as_of`.

APEX is permanently research/shadow only:

```text
execution_authorized=false
production_decision_authorized=false
```

It has no broker arming, order submission/cancellation, position mutation, sizing, strategy-input mutation, or production-promotion path.

## Installed Projects A–F

### Project A — Epistemic Kernel

Installed modules:

- `contracts.py` — strict finite evidence contracts, source provenance, content-addressed identity;
- `store.py` — SQLite WAL persistence at `research/apex.sqlite3`;
- `ancestry.py` — evidence-ancestry DAG, cycle detection, effective independent evidence families;
- `beliefs.py` — append-only proof-carrying belief ledger;
- `epistemics.py` / `credibility.py` — independence-adjusted confidence, credibility and hard authority invariants.

Important behavior:

- boolean-as-number, NaN and Inf fail closed;
- `unavailable` evidence cannot contribute confirming confidence;
- shared source ancestry cannot masquerade as independent confirmation;
- corrupt persisted rows are excluded/quarantined rather than silently normalized.

### Project B — Participant / Force Layer

Installed modules:

- `participants.py` — participant-state reconstruction across retail, systematic, dealer/liquidity, fund, passive, crypto and unknown cohorts;
- `crowdhunt.py` — CROWDHUNT Ω entry/stop/trap/forced-exit crowd topology;
- `institutional.py` — expiry, rebalance, volatility-control, CTA, dealer, collateral, basis and other mechanical-flow hypotheses;
- `liquidity.py` — liquidity topology with true depth separated from proxies;
- `force_field.py` — multi-horizon market-pressure tensor preserving opposing contributions.

Exact hidden account positions are never claimed unless a legitimate source actually observes them. Candle/volume proxies never become invented order-book depth.

### Project C — Causal / Cascade Layer

Installed modules:

- `causality.py` — typed multi-horizon causal graph;
- `expectations.py` — bounded beliefs-about-beliefs graph with recursion penalties;
- `cascade.py` — cascade topology and reflexive-loop diagnostics;
- `criticality.py` — conservative multi-diagnostic market criticality state.

Causal status is explicitly separated into:

```text
correlated
temporally_supported
mechanistically_supported
intervention_supported
contradicted
unknown
```

Correlation or prediction improvement alone cannot promote an edge into causal proof.

### Project D — World / Unknown Layer

Installed modules:

- `macro_state.py` — economic world state across growth, inflation, rates, credit, labor, consumption, production, FX, commodities, liquidity, earnings and policy;
- `worlds.py` — weighted counterfactual world population with bounded split/merge;
- `unknown_force.py` — explanatory residuals and anonymous latent-state candidates;
- `adapters.py` — fail-isolated, read-only sibling snapshots.

The unified kernel exposes `economic_world` separately from market response so macro hypotheses and price behavior can disagree without one overwriting the other.

Unknown-force events preserve `cause=null` until independent replicated evidence justifies an interpretation.

### Project E — Self / Science Layer

Installed modules:

- `reality_gap.py` — model-vs-reality divergence;
- `self_model.py` — capability/prerequisite graph;
- `conscience.py` — independent Truth, Uncertainty, Risk, Consistency, Provenance and Authority judges;
- `information_gain.py` — observation, experiment and compute-value ranking;
- `evolution.py` — bounded architecture-proposal evaluation with no deploy/promote API;
- `theory.py` — temporal theory library preserving positive and negative results.

Model credibility can fall when reality gap, regime mismatch or model monoculture rises. A historically strong model is not protected from present degradation.

The synthetic conscience is a machine-enforced audit institution, not a claim of consciousness.

### Project F — Integration Surface

`ApexKernel` assembles the installed layers and reads these existing systems through fail-isolated adapters:

- ICARUS Ψ;
- Chronofold Ξ;
- PANTHEON / AETHER;
- PARALLAX;
- DREAMSTATE;
- SIBYL Ω.

A failure in one sibling marks that adapter degraded; it does not fabricate a neutral value or take down unrelated APEX state.

APEX Ω is also registered in Adaptive Brain as the `omega`-owned `apex-omega` subsystem. Brain keeps only architectural/health ownership; full APEX state remains owned by the APEX API.

## Persistence

Primary durable store:

`research/apex.sqlite3`

SQLite WAL state includes:

- evidence;
- belief records/events;
- participant states;
- force fields;
- causal edges;
- cascade edges;
- counterfactual world states;
- unknown-force events;
- theory records/events;
- model credibility;
- reality gap;
- conscience verdicts.

Research outcomes, model observations that do not map to the structured reality-gap table, and experiment proposals are recorded in the APEX research event journal.

## HTTP surface

Authenticated read routes:

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

Optional query parameters include `asset` where the state is asset-specific and `as_of` for causal historical reconstruction.

Authenticated research mutations:

```text
POST /admin/apex/evidence
POST /admin/apex/outcome
POST /admin/apex/model-observation
POST /admin/apex/experiment
```

APEX admin routes use bounded strict JSON parsing and authenticate before body parsing.

## MCP surface

The ICARUS MCP bridge exposes:

```text
engine_apex_state
engine_apex_participants
engine_apex_crowdhunt
engine_apex_forces
engine_apex_cascades
engine_apex_causality
engine_apex_worlds
engine_apex_epistemics
engine_apex_self
engine_apex_conscience

record_engine_apex_evidence
record_engine_apex_outcome
record_engine_apex_model_observation
propose_engine_apex_experiment
```

All are thin wrappers around the authenticated APEX engine endpoints. The mutation wrappers accept JSON objects only and cannot target broker/order/control endpoints.

## Trader interface

The dashboard includes an **APEX Ω** tab backed by `icarus_engine/apex-ui.js`.

It renders:

- WORLD;
- PARTICIPANTS;
- CROWDHUNT;
- FORCES;
- LIQUIDITY;
- CASCADES;
- CAUSAL GRAPH;
- COUNTERFACTUAL WORLDS;
- UNKNOWN FORCE;
- EPISTEMIC HEALTH;
- MODEL HEALTH;
- CONSCIENCE.

The UI renders absent numeric/model values as `UNAVAILABLE` or `UNMEASURED`; it does not silently coerce missing state to zero.

## Failure semantics

APEX fails closed while remaining observable:

- missing sibling → `UNAVAILABLE`;
- sibling exception → local `DEGRADED`;
- malformed evidence → rejected mutation;
- future evidence → excluded from historical as-of state;
- corrupt durable row → excluded/quarantined;
- missing depth/OI/liquidation/funding/account-level position data → remains unavailable;
- model disagreement → preserved as disagreement;
- unresolved residual → anonymous unknown/latent state, not an invented cause.

## Verification

Primary APEX suite:

```bash
python -m pytest tests_engine/test_apex_*.py -q
```

Affected integration regression:

```bash
python -m pytest \
  tests_engine/test_brain.py \
  tests_engine/test_dashboard_js.py \
  tests_engine/test_mcp_server.py \
  tests_engine/test_possibility.py \
  tests_engine/test_chronofold.py \
  tests_engine/test_pantheon_aether.py \
  tests_engine/test_parallax_dreamstate.py \
  tests_engine/test_sibyl.py -q
```

The full repository test suite and the current Linux/Windows CI workflow remain mandatory before merging any APEX change to `main`.

## Non-goals

APEX Ω does not promise:

- omniscience;
- guaranteed prediction accuracy;
- exact hidden participant positions without source evidence;
- invented order flow, depth, OI, liquidations, funding or basis;
- literal market physics;
- automatic production deployment;
- autonomous broker authority;
- unrestricted self-modification.

Its purpose is to maximize justified, replayable understanding while keeping uncertainty, disagreement, provenance and human authority explicit.


## PANTHEON ECHO lineage verification

APEX Ω now exposes an internal `resolve_engine_evidence_lineage` contract for
PANTHEON ECHO. A PANTHEON observation may supply `engine_evidence_ids`; the
HTTP integration resolves those IDs against the causal APEX evidence store at
the observation's own `observed_at` boundary, walks the APEX evidence-ancestry
DAG, and replaces any caller-provided lineage tokens with verified root-source
identities.

Unknown evidence, future/unavailable dependencies, cycles, duplicate IDs, empty
evidence sets, or malformed mappings fail closed. The resolved map is stamped
into the observation's external subsystem evidence as `apex_lineage` with
`status=VERIFIED`. A caller cannot overwrite that reserved server-owned slot.

This is deliberately one-way: APEX owns provenance ancestry; PANTHEON owns ECHO
consensus diagnostics. It does not create a circular model dependency and does
not grant either system execution authority.
