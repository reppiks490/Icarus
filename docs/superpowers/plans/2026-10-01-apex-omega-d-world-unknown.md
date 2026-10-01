# ICARUS APEX Ω Project D — World / Unknown Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build economic/world-state federation, structured counterfactual worlds, information propagation, unknown-force residuals, and anonymous ontology candidates.

**Architecture:** Project D maintains competing world hypotheses instead of one narrative. Residual phenomena remain anonymous until replicated evidence supports interpretation; SIBYL is optional and absence must not fail the world model.

**Tech Stack:** Python 3.10+, standard library, Projects A-C, existing ICARUS sibling snapshots through read-only adapters, pytest.

**Spec:** docs/superpowers/specs/2026-10-01-apex-omega-design.md

## Global Constraints

- Requires Projects A-C.
- World states are hypotheses with weights, assumptions, contradictions and falsifiers.
- World probabilities/weights must normalize without implying certainty.
- Unknown-force events describe residual structure but do not invent causes.
- Anonymous latent/ontology candidates remain semantically anonymous until evidence supports naming.
- SIBYL is optional; missing module => `UNAVAILABLE`, never startup failure.
- Knowledge delta: extend `docs/icarus/APEX_OMEGA.md` with Project-D capabilities.

## Review Focus

- A macro state and market response may disagree without one silently overwriting the other — Task 1.
- World-weight update with zero likelihood for every world must fail to explicit unresolved state, not divide by zero — Task 3.
- SIBYL missing/import failure must degrade only that adapter — Task 2.
- Unknown residual detection must not emit a human-readable cause by default — Task 4.
- Repeated latent pattern across one episode only must not qualify as replicated ontology evidence — Task 5.

---

### Task 1: Economic world-state federation

**Files:**
- Create: `icarus_engine/apex/macro_state.py`
- Create: `tests_engine/test_apex_macro_state.py`

**Interfaces:**
- `economic_world_state(evidence, *, as_of: str) -> dict[str, Any]`
- Domain slots: growth, inflation, rates, credit, labor, consumption, production, FX, commodities, liquidity, earnings, policy; each may be `UNAVAILABLE`.

- [ ] RED tests for independent economic/market-response state, contradictory evidence, stale evidence, unknown domains, and false authority.
- [ ] Run RED.
- [ ] Implement federation.
- [ ] Run GREEN.
- [ ] Commit `feat(apex): add economic world state`.

### Task 2: Read-only sibling adapters

**Files:**
- Create: `icarus_engine/apex/adapters.py`
- Create: `tests_engine/test_apex_adapters.py`

**Interfaces:**
- `safe_snapshot(name: str, producer: Callable[[], Mapping[str, Any]]) -> dict[str, Any]`
- `sibling_evidence(*, possibility=None, chronofold=None, pantheon=None, parallax=None, dreamstate=None, sibyl=None) -> list[dict[str, Any]]`
- Adapters are read-only and capture subsystem/schema/source revision when available.

- [ ] RED tests for isolated adapter failure, SIBYL absence, caller object mutation not occurring, false authority preservation, and malformed sibling snapshot quarantine.
- [ ] Run RED.
- [ ] Implement adapters.
- [ ] Run GREEN.
- [ ] Commit `feat(apex): add read-only sibling adapters`.

### Task 3: Structured world population

**Files:**
- Create: `icarus_engine/apex/worlds.py`
- Create: `tests_engine/test_apex_worlds.py`

**Interfaces:**
- `class WorldPopulation`
- `WorldPopulation.seed(worlds: Sequence[Mapping[str, Any]]) -> None`
- `WorldPopulation.update(observation: Mapping[str, Any]) -> dict[str, Any]`
- `WorldPopulation.split(world_id: str, branches: Sequence[Mapping[str, Any]]) -> list[str]`
- `WorldPopulation.merge_equivalent() -> int`
- `WorldPopulation.snapshot() -> dict[str, Any]`

- [ ] RED tests for normalized weights, impossible-all-worlds case, deterministic update/replay, bounded split, and equivalent-world merge.
- [ ] Run RED.
- [ ] Implement log-safe weight update and unresolved fallback.
- [ ] Run GREEN.
- [ ] Commit `feat(apex): maintain counterfactual world population`.

### Task 4: Unknown-force residual engine

**Files:**
- Create: `icarus_engine/apex/unknown_force.py`
- Create: `tests_engine/test_apex_unknown_force.py`

**Interfaces:**
- `unknown_force_event(*, observed: Mapping[str, Any], explained: Mapping[str, Any], evidence_ids: Sequence[str], as_of: str) -> dict[str, Any]`
- states: `KNOWN_KNOWN|KNOWN_UNKNOWN|UNKNOWN_KNOWN|UNKNOWN_UNKNOWN`.

- [ ] RED tests for no invented cause, bounded residual, insufficient explanation state, reproducible identity, and no event when residual is inside calibrated envelope.
- [ ] Run RED.
- [ ] Implement residual classification.
- [ ] Run GREEN.
- [ ] Commit `feat(apex): detect unexplained market force`.

### Task 5: Latent/ontology candidate lifecycle and information propagation

**Files:**
- Modify: `icarus_engine/apex/unknown_force.py`
- Modify: `icarus_engine/apex/causality.py`
- Create: `tests_engine/test_apex_ontology_information.py`

**Interfaces:**
- `latent_candidate(events: Sequence[Mapping[str, Any]], *, min_independent_episodes: int = 3) -> dict[str, Any]`
- `information_wave(edges, *, origin: str, as_of: str, max_depth: int = 8) -> dict[str, Any]`

- [ ] RED tests for episode independence, anonymous candidate naming, no semantic interpretation promotion, bounded propagation depth, and contradictory channel handling.
- [ ] Run RED.
- [ ] Implement latent candidate aggregation and information-wave traversal.
- [ ] Run GREEN.
- [ ] Update docs and commit `feat(apex): add latent discovery and information waves`.

### Task 6: Persist world and unknown-force state

**Files:**
- Modify: `icarus_engine/apex/store.py`
- Modify: `icarus_engine/apex/worlds.py`
- Modify: `icarus_engine/apex/unknown_force.py`
- Create: `tests_engine/test_apex_world_persistence.py`

**Interfaces:**
- Produces:
  - `ApexStore.record_world_state(world: Mapping[str, Any]) -> dict[str, Any]`
  - `ApexStore.world_states_as_of(as_of: str) -> list[dict[str, Any]]`
  - `ApexStore.record_unknown_force(event: Mapping[str, Any]) -> dict[str, Any]`
  - `ApexStore.unknown_force_events_as_of(as_of: str) -> list[dict[str, Any]]`

- [ ] Write RED tests for deterministic world identity, historical weight replay, unknown-force idempotence, anonymous latent candidate preservation, and corrupted-row quarantine.
- [ ] Run `python -m pytest tests_engine/test_apex_world_persistence.py -q` — Expected FAIL.
- [ ] Add additive `world_states` and `unknown_force_events` WAL tables and methods.
- [ ] Re-run — Expected PASS.
- [ ] Commit `feat(apex): persist world and unknown state`.

### Task 7: Project-D verification gate

- [ ] Run all Project-D tests — Expected PASS.
- [ ] Run Projects A-C tests — Expected PASS.
- [ ] Run `python -m pytest tests_engine/test_pantheon_aether.py tests_engine/test_chronofold.py -q` — Expected PASS.
- [ ] Explicitly verify startup/import succeeds when no `icarus_engine.sibyl` module exists.
