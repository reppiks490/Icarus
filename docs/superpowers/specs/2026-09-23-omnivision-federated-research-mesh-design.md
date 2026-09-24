# OMNIVISION Federated Research Mesh — Design

Date: 2026-09-23  
Status: user-approved architecture; implementation plan pending user review of this written spec  
Branch: `codex/exotic-research-loop`

## Intent

Extend ICARUS into a research-only, cross-domain discovery system that can ingest authorized/public/licensed evidence beyond financial data, infer latent world state without fabricating observations, generate falsifiable hypotheses, attack those hypotheses with independent tests, and emit integration candidates for ICARUS and counterpart systems.

Success means the system finds genuinely novel, reproducible information while preserving temporal integrity, provenance, uncertainty, and reversibility. It must not gain execution authority.

## Hard boundaries

- `execution_authorized=false` remains invariant.
- No Pulse rewrite.
- No sandbox escape, credential discovery, access-control bypass, stealth persistence, scraping prohibited sources, or unauthorized access.
- Inputs are public, licensed, user-authorized, or connected sources only.
- Observed, derived, inferred, and unknown states remain distinct.
- Inference never upgrades itself into an observation.
- No synthesized ticks, fills, publication times, or other fabricated evidence.
- Existing owner-hard rules in `ASTRA_DO_NOT.md` remain authoritative.

## Architecture

```text
AUTHORIZED SOURCES
    ↓
Domain Adapters
    ↓
Canonical Observation Contract
    ↓
AdvisoryLedger / Immutable Provenance
    ↓
OMNIVISION World-State Graph
    ├─ observed state
    ├─ derived state
    ├─ latent estimates
    ├─ contradictions
    └─ unresolved gaps
    ↓
Hypothesis Forge
    ↓
Falsification Gauntlet
    ↓
Regime / Cross-Domain Validation
    ↓
Shadow Integration Candidates
    ↓
ICARUS / NEXUS / DAEDALUS research interfaces
```

The mesh is federated: source adapters remain independent, the immutable evidence layer is canonical, inference is isolated from acquisition, and validation is isolated from integration.

## Components

### 1. Domain adapters

Adapters translate approved sources into a canonical event/observation schema. Initial domains may include:

- macro and central-bank data
- weather/climate
- shipping/logistics
- energy/grid/refinery/storage
- agriculture and physical commodities
- geopolitics/sanctions/regulation
- patents/science/technology diffusion
- cybersecurity and infrastructure outages
- labor and industrial activity
- transportation/mobility
- corporate operations and public filings
- public-health events with economic relevance
- market and cross-asset data already supported by ICARUS

Each adapter declares source identity, legal/access class, publication/availability semantics, units, revisions, entity mapping, freshness rules, and failure behavior.

No adapter may silently downgrade timing or provenance requirements.

### 2. Canonical observation contract

Every observation carries at minimum:

- source
- domain
- entity
- variable
- value or structured payload
- observation/event time
- first-available time
- receipt time when relevant
- confidence/quality metadata
- revision identity
- provenance URI/reference

Availability time is the anti-leakage clock. Event time alone is never sufficient for historical replay.

### 3. Immutable evidence layer

Existing `AdvisoryLedger` remains the source of truth for accepted external evidence. OMNIVISION integrates through an explicit adapter rather than bypassing source allowlists, timing checks, revision logic, or immutable records.

The ledger stores evidence. The world-state graph stores or reconstructs relationships over evidence. The two responsibilities remain separate.

### 4. World-state graph

The existing `icarus_engine/world_state.py` kernel becomes the deterministic inference layer.

It maintains:

- latest known observations as-of a timestamp
- coverage of required variables
- source contradictions
- transmission edges between variables
- explicit latent estimates
- unresolved unknowns

Every latent estimate includes supporting evidence IDs, mechanisms, and confidence. Missing evidence without a defensible transmission path remains unresolved.

### 5. Hypothesis Forge

The forge creates testable research hypotheses from:

- contradictions
- newly observed events
- persistent latent gaps
- regime changes
- cross-domain lead/lag candidates
- repeated ICARUS failure clusters
- interactions among previously weak signals
- novel information that is non-redundant with existing features

A hypothesis must declare a measurable target, causal or descriptive mechanism, expected lag/horizon, required variables, falsification criteria, eligible assets/regimes, and data-availability assumptions.

### 6. Novelty and redundancy filter

Before expensive validation, a candidate is compared with existing ICARUS information using:

- correlation
- rank correlation
- mutual information or conditional information gain where appropriate
- feature-attribution overlap
- prediction/residual similarity
- behavioral overlap by regime

A renamed duplicate is rejected or deferred before consuming scarce validation budget.

### 7. Falsification Gauntlet

Candidates are attacked rather than rewarded for attractive backtests.

Applicable tests include:

- as-of replay
- placebo timing shifts
- randomized/permute controls
- multiple-hypothesis correction
- parameter perturbation
- execution-cost stress
- missing/stale-source stress
- source contradiction stress
- regime holdouts
- walk-forward validation
- cross-asset portability
- cross-period stability
- ablation
- adversarial outlier/event tests
- historical-analogue counterexamples

Failure results are first-class evidence and feed future hypothesis generation.

### 8. Regime and transmission layer

A candidate is not classified as simply "working" or "not working." Evidence is conditioned on observable regimes such as volatility, liquidity, correlation structure, trend persistence, macro state, event intensity, and data quality.

Transmission relationships are versioned and may strengthen, weaken, invert, or disappear over time.

### 9. Shadow integration candidates

Passing research becomes a machine-readable candidate, not a production change.

Each candidate declares:

- inputs and outputs
- required history
- latency tolerance
- valid regimes
- evidence IDs and dataset hashes
- validation results
- known failure modes
- expected incremental information
- dependency boundaries
- rollback/kill conditions
- `execution_authorized=false`

No candidate mutates live strategy behavior automatically.

## Bridging "seen" and "unseen"

The system uses four explicit epistemic classes:

1. **Observed** — directly supplied by a validated source.
2. **Derived** — deterministic transformation of observed evidence.
3. **Latent** — model-based estimate supported by explicit transmission edges.
4. **Unknown** — insufficient defensible evidence.

The bridge is uncertainty-aware inference, not hidden access. A latent value can guide what to research next, but it cannot masquerade as an observation.

High-value gaps become active acquisition questions: what authorized evidence would most reduce uncertainty? Research budget is allocated toward expected information gain.

## Adaptive loop

Each cycle:

1. Activate required plugins.
2. Load only GitHub delta, failing tests, unresolved findings, affected dependency boundaries, and validation evidence.
3. Select one bounded unresolved objective.
4. Inspect only the minimum required source/code context.
5. Generate or refine hypotheses.
6. Acquire only authorized evidence.
7. Normalize timing/provenance.
8. Run novelty filtering.
9. Run falsification/validation appropriate to the hypothesis.
10. Record accepted, rejected, deferred, or contradictory findings.
11. Emit integration candidate only when acceptance gates pass.
12. Verify relevant tests/checks.
13. Checkpoint concise durable state to GitHub.

The loop does not repeatedly reread unchanged repository content.

## Plugin policy

Every cycle activates at minimum:

- Superpowers process discipline
- Brainstorming when creative or architectural work is involved
- Astral Orchestrator
- Akinator
- Baton Pass

Optional cycle plugins are activated only when they add concrete capability: TDD, systematic debugging, parallel agents, review, verification, cloud research, or infrastructure analysis.

Each checkpoint records the plugins actually used and their concrete contribution.

## GitHub as persistent control plane

Canonical durable state lives in:

- `.icarus_loop/state.json` — current bounded state, checkpoints, open findings
- this design spec — architectural intent and invariants
- future implementation plan — ordered implementation tasks
- tests and code — executable evidence
- issues/PRs only when they improve traceability

Conversation is not the source of truth.

## Failure handling

- Adapter failure: isolate source, preserve prior evidence, record freshness degradation.
- Timing ambiguity: mark unavailable/unknown; never guess publication time.
- Contradictory sources: preserve both and reduce certainty; do not choose a winner without evidence.
- Inference failure: return unresolved.
- Validation failure: record why; do not promote.
- Test/CI failure: stop dependent promotion and checkpoint the exact failing boundary.
- Repository drift: resume from latest GitHub state/diff and reconcile before continuing.

## Testing strategy

Implementation must use TDD for each bounded component.

Required coverage includes:

- future-knowledge rejection
- malformed/untrusted source rejection
- source allowlist preservation
- revision semantics
- observation vs latent separation
- contradiction preservation
- missing-data behavior
- deterministic inference
- novelty rejection
- walk-forward boundaries
- holdout non-reuse
- candidate non-execution
- persistence/resume from GitHub state

Integration tests verify that evidence can flow from an approved adapter through the ledger and world-state graph into a research candidate without granting execution authority.

## Acceptance criteria

The architectural phase is complete when:

- source adapters have an explicit contract
- AdvisoryLedger integration preserves existing invariants
- world-state inference remains deterministic and epistemically labeled
- hypotheses are machine-readable and falsifiable
- novelty screening exists
- at least one falsification path and walk-forward path are implemented
- failures are persisted as useful evidence
- candidates remain research-only
- tests run in a real execution environment and exact results are checkpointed
- another agent can resume from GitHub without this conversation

## Explicit non-goals

This phase does not:

- execute trades
- change Pulse
- autonomously obtain credentials
- bypass paywalls or access controls
- scrape prohibited sources
- conceal network activity
- fabricate unavailable data
- optimize solely for backtest profit

## Knowledge delta

Canonical architecture added at this path. Durable cycle state remains in `.icarus_loop/state.json`. No other repository knowledge layer is required for this design stage; implementation-stage documentation will follow actual code changes rather than speculate ahead of them.
