# ICARUS APEX Ω Project B — Participant / Force Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build evidence-bounded participant reconstruction, CROWDHUNT Ω, institutional mechanics, liquidity topology, and the unified market-pressure tensor.

**Architecture:** Project B consumes only Project-A proof-carrying evidence/belief interfaces. Every participant/force output is a distribution with provenance and uncertainty; no hidden account-level position, order book, OI, liquidation, funding, or institutional mandate is invented.

**Tech Stack:** Python 3.10+, standard library, Project-A APEX contracts/store/ancestry, pytest.

**Spec:** docs/superpowers/specs/2026-10-01-apex-omega-design.md

## Global Constraints

- Requires verified Project A interfaces.
- Participant outputs are `reconstructed` or `inferred` unless direct source evidence justifies `observed`.
- Missing market microstructure fields remain `UNAVAILABLE`.
- Liquidity proxies are labeled proxies and cannot masquerade as true depth.
- All pressure values bind evidence IDs, as-of time, horizon, participant class, direction, and confidence.
- `execution_authorized=false`; `production_decision_authorized=false`.
- No broker/order/strategy mutation.
- Knowledge delta: extend `docs/icarus/APEX_OMEGA.md` with Project-B installed interfaces and limitations.

## Review Focus

- Empty evidence must produce an explicit early/unavailable participant state, not zero-position certainty — Task 1.
- Two evidence sources from the same ancestry family must not double participant confidence — Task 1.
- Liquidity without depth data must expose proxy status instead of numeric depth — Task 4.
- Institutional mechanics must distinguish explicit rule evidence from inferred behavior — Task 3.
- Force-field aggregation must preserve opposing forces rather than netting them into a false one-sided certainty — Task 5.

---

### Task 1: Participant State Observatory

**Files:**
- Create: `icarus_engine/apex/participants.py`
- Create: `tests_engine/test_apex_participants.py`

**Interfaces:**
- Consumes: Project-A evidence records and independence summaries.
- Produces:
  - `PARTICIPANT_CLASSES: tuple[str, ...]`
  - `participant_state(evidence: Sequence[Mapping[str, Any]], *, asset: str, as_of: str, horizon_seconds: int) -> dict[str, Any]`
  - `participant_states_by_class(...) -> list[dict[str, Any]]`

- [ ] **Step 1: Write RED tests**

Add tests for empty state, long/short evidence separation, shared-ancestry confidence discount, time/horizon binding, and unknown participant class handling.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests_engine/test_apex_participants.py -q`  
Expected: FAIL.

- [ ] **Step 3: Implement bounded reconstruction**

Return density/support descriptors and intervals; do not fabricate point positions when evidence supports only a broad region.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests_engine/test_apex_participants.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

`git add icarus_engine/apex/participants.py tests_engine/test_apex_participants.py && git commit -m "feat(apex): reconstruct participant state"`

### Task 2: CROWDHUNT Ω

**Files:**
- Create: `icarus_engine/apex/crowdhunt.py`
- Create: `tests_engine/test_apex_crowdhunt.py`

**Interfaces:**
- Consumes: participant-state evidence for retail cohorts.
- Produces:
  - `crowd_map(..., price_grid: Sequence[float]) -> dict[str, Any]`
  - `crowd_pain_gradient(crowd_state: Mapping[str, Any], price_grid: Sequence[float]) -> list[dict[str, Any]]`
  - fields for entry, stop, trapped, breakout, forced-exit, migration, persistence, decay, falsifiers.

- [ ] **Step 1: Write RED tests**

Cover long/short separation, stop-density not inferred from entry alone, pain-gradient monotonicity only when evidence supplies adverse-distance relation, and exact false authority flags.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests_engine/test_apex_crowdhunt.py -q`

- [ ] **Step 3: Implement crowd surface**

Use price buckets and evidence-weighted support; expose `UNAVAILABLE` fields where evidence does not support an estimate.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests_engine/test_apex_crowdhunt.py -q`

- [ ] **Step 5: Commit**

`git add icarus_engine/apex/crowdhunt.py tests_engine/test_apex_crowdhunt.py && git commit -m "feat(apex): add CROWDHUNT Omega"`

### Task 3: Institutional Mechanics Engine

**Files:**
- Create: `icarus_engine/apex/institutional.py`
- Create: `tests_engine/test_apex_institutional.py`

**Interfaces:**
- Produces:
  - `institutional_mechanics(evidence: Sequence[Mapping[str, Any]], *, asset: str, as_of: str, horizon_seconds: int) -> dict[str, Any]`
  - mechanism statuses `observed_rule|derived_constraint|inferred_behavior|unavailable`.

- [ ] **Step 1: Write RED tests**

Cover explicit expiry/rebalance rule evidence, inferred CTA threshold evidence, unsupported dealer-gamma data remaining unavailable, and malformed mechanism input rejection.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests_engine/test_apex_institutional.py -q`

- [ ] **Step 3: Implement typed mechanics**

Mechanics must preserve source type and falsifier; no institution identity may be inferred from anonymous flow alone.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests_engine/test_apex_institutional.py -q`

- [ ] **Step 5: Commit**

`git add icarus_engine/apex/institutional.py tests_engine/test_apex_institutional.py && git commit -m "feat(apex): model institutional mechanics"`

### Task 4: Liquidity topology

**Files:**
- Create: `icarus_engine/apex/liquidity.py`
- Create: `tests_engine/test_apex_liquidity.py`

**Interfaces:**
- Produces:
  - `liquidity_topology(evidence: Sequence[Mapping[str, Any]], *, asset: str, as_of: str, price_grid: Sequence[float]) -> dict[str, Any]`
  - explicit `depth_status`, `proxy_fields`, resilience/replenishment/fragility descriptors.

- [ ] **Step 1: Write RED tests**

Cover true depth evidence, proxy-only evidence, no-evidence state, stale depth exclusion, and boolean/nonnumeric depth rejection.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests_engine/test_apex_liquidity.py -q`

- [ ] **Step 3: Implement topology**

Never synthesize depth from candles or volume.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests_engine/test_apex_liquidity.py -q`

- [ ] **Step 5: Commit**

`git add icarus_engine/apex/liquidity.py tests_engine/test_apex_liquidity.py && git commit -m "feat(apex): map liquidity topology"`

### Task 5: Market Pressure Tensor

**Files:**
- Create: `icarus_engine/apex/force_field.py`
- Create: `tests_engine/test_apex_force_field.py`

**Interfaces:**
- Consumes: participant states, CROWDHUNT, institutional mechanics, liquidity topology.
- Produces:
  - `pressure_tensor(..., price_grid: Sequence[float], horizons: Sequence[int]) -> dict[str, Any]`
  - `dominant_forces(tensor: Mapping[str, Any], *, limit: int = 10) -> list[dict[str, Any]]`

- [ ] **Step 1: Write RED tests**

Cover opposing forces surviving separately, no-evidence cells remaining unavailable, confidence capped by weakest required evidence, and deterministic ordering.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests_engine/test_apex_force_field.py -q`

- [ ] **Step 3: Implement tensor**

Store force contributions by participant/mechanism/direction; compute net pressure only as an additional derived view.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests_engine/test_apex_force_field.py -q`

- [ ] **Step 5: Update APEX documentation and commit**

Update `docs/icarus/APEX_OMEGA.md`; then commit `feat(apex): add participant force field`.

### Task 6: Persist participant and force state

**Files:**
- Modify: `icarus_engine/apex/store.py`
- Modify: `icarus_engine/apex/participants.py`
- Modify: `icarus_engine/apex/force_field.py`
- Create: `tests_engine/test_apex_participant_persistence.py`

**Interfaces:**
- Produces:
  - `ApexStore.record_participant_state(state: Mapping[str, Any]) -> dict[str, Any]`
  - `ApexStore.participant_states_as_of(as_of: str, *, asset: str | None = None) -> list[dict[str, Any]]`
  - `ApexStore.record_force_field(field: Mapping[str, Any]) -> dict[str, Any]`
  - `ApexStore.force_fields_as_of(as_of: str, *, asset: str | None = None) -> list[dict[str, Any]]`

- [ ] **Step 1: Write RED durability tests**

Cover append-only participant-state identity, idempotent force-field retry, historical as-of replay, source-evidence lineage retention, and reopen/replay determinism.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests_engine/test_apex_participant_persistence.py -q`  
Expected: FAIL because Project-B durable tables/methods do not exist.

- [ ] **Step 3: Add additive WAL tables and persistence methods**

Add `participant_states` and `force_fields` tables without destructive migration. Persist exact source evidence IDs and distinct as-of/calculated clocks.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests_engine/test_apex_participant_persistence.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

`git add icarus_engine/apex/store.py icarus_engine/apex/participants.py icarus_engine/apex/force_field.py tests_engine/test_apex_participant_persistence.py && git commit -m "feat(apex): persist participant force state"`

### Task 7: Project-B verification gate

- [ ] Run: `python -m pytest tests_engine/test_apex_participants.py tests_engine/test_apex_crowdhunt.py tests_engine/test_apex_institutional.py tests_engine/test_apex_liquidity.py tests_engine/test_apex_force_field.py -q` — Expected PASS.
- [ ] Run Project-A suite — Expected PASS.
- [ ] Run: `python -m pytest tests_engine/test_possibility.py tests_engine/test_pantheon_aether.py -q` — Expected PASS.
- [ ] Verify `git diff $(git merge-base main HEAD)..HEAD` contains no broker/order/strategy mutation.
