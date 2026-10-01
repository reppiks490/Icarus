# ICARUS APEX Ω Project C — Causal / Cascade Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build multi-horizon causal claims, bounded recursive expectations, cascade topology, reflexivity, and criticality over verified APEX evidence/force state.

**Architecture:** Project C treats causality as typed evidence state rather than a correlation score. Cascade/reflexivity outputs reference causal edges plus activation evidence and preserve contradiction/falsifier state.

**Tech Stack:** Python 3.10+, standard library, Projects A-B interfaces, pytest.

**Spec:** docs/superpowers/specs/2026-10-01-apex-omega-design.md

## Global Constraints

- Requires verified Projects A-B.
- Causal status vocabulary is exactly `correlated|temporally_supported|mechanistically_supported|intervention_supported|contradicted|unknown`.
- Prediction improvement alone cannot promote an edge above correlated.
- Expectations recursion is depth bounded and uncertainty-discounted.
- Self-exciting/event-clustering statistics are never labeled causal proof.
- Criticality is multi-diagnostic and may remain `UNKNOWN`.
- Knowledge delta: extend `docs/icarus/APEX_OMEGA.md` with Project-C interfaces.

## Review Focus

- A high correlation with reversed time order must not become temporally supported — Task 1.
- Confounded/contradicted edge evidence must remain visible after new supportive evidence — Task 1.
- Recursive belief graphs must terminate at configured depth and accumulate uncertainty — Task 2.
- Cascade graph cycles must be represented as reflexive loops without infinite traversal — Task 4.
- One extreme criticality diagnostic must not alone force `CRITICAL` state — Task 5.

---

### Task 1: Multi-horizon causal graph

**Files:**
- Create: `icarus_engine/apex/causality.py`
- Create: `tests_engine/test_apex_causality.py`

**Interfaces:**
- `causal_edge(body: Mapping[str, Any]) -> dict[str, Any]`
- `class CausalGraph`
- `CausalGraph.add_edge(edge: Mapping[str, Any]) -> dict[str, Any]`
- `CausalGraph.edges_as_of(as_of: str, *, horizon_seconds: int | None = None) -> list[dict[str, Any]]`
- `CausalGraph.pathways(source: str, target: str, *, max_depth: int = 6) -> list[list[str]]`

- [ ] Write RED tests for time order, status promotion prerequisites, contradiction persistence, horizon isolation, and bounded path traversal.
- [ ] Run: `python -m pytest tests_engine/test_apex_causality.py -q` — Expected FAIL.
- [ ] Implement typed causal edges and graph.
- [ ] Re-run — Expected PASS.
- [ ] Commit `feat(apex): add multi-horizon causal graph`.

### Task 2: Recursive expectation graph

**Files:**
- Create: `icarus_engine/apex/expectations.py`
- Create: `tests_engine/test_apex_expectations.py`

**Interfaces:**
- `expectation_graph(evidence, *, max_depth: int = 3, depth_penalty: float = 0.65) -> dict[str, Any]`
- `expectation_paths(graph, *, participant: str) -> list[dict[str, Any]]`

- [ ] Write RED tests for max depth, confidence decay, missing root evidence, disagreement, and cycle truncation.
- [ ] Run RED.
- [ ] Implement bounded recursive expectations.
- [ ] Run GREEN.
- [ ] Commit `feat(apex): add expectation graph`.

### Task 3: Cascade topology

**Files:**
- Create: `icarus_engine/apex/cascade.py`
- Create: `tests_engine/test_apex_cascade.py`

**Interfaces:**
- `build_cascade_graph(*, forces, causal_graph, participant_state, liquidity_state, as_of: str) -> dict[str, Any]`
- `cascade_paths(graph, *, max_depth: int = 8) -> list[dict[str, Any]]`

- [ ] Write RED tests for activation requirements, unsupported edges remaining blocked, estimated-delay bounds, clustering-not-causality label, and deterministic path rank.
- [ ] Run RED.
- [ ] Implement cascade graph.
- [ ] Run GREEN.
- [ ] Commit `feat(apex): add cascade topology`.

### Task 4: Reflexivity loops

**Files:**
- Modify: `icarus_engine/apex/cascade.py`
- Create: `tests_engine/test_apex_reflexivity.py`

**Interfaces:**
- `reflexive_loops(graph: Mapping[str, Any], *, max_cycle: int = 6) -> list[dict[str, Any]]`
- Each loop exposes gain/support/damping/activation distance and does not imply literal physical feedback.

- [ ] Write RED tests for simple loop detection, duplicate-cycle canonicalization, finite traversal, and contradictory-edge damping.
- [ ] Run RED.
- [ ] Implement loop analysis.
- [ ] Run GREEN.
- [ ] Commit `feat(apex): detect reflexive feedback loops`.

### Task 5: Criticality classifier

**Files:**
- Create: `icarus_engine/apex/criticality.py`
- Create: `tests_engine/test_apex_criticality.py`

**Interfaces:**
- `criticality_state(*, liquidity, reflexivity, volatility_evidence, participant_concentration, cross_asset_evidence) -> dict[str, Any]`
- State vocabulary: `STABLE|COMPRESSED|METASTABLE|CRITICAL|CASCADE|REORGANIZING|UNKNOWN`.

- [ ] Write RED tests for missing diagnostics, single-signal non-escalation, multi-signal critical state, contradictory damping, and finite JSON output.
- [ ] Run RED.
- [ ] Implement conservative multi-diagnostic classifier.
- [ ] Run GREEN.
- [ ] Update docs and commit `feat(apex): classify market criticality`.

### Task 6: Persist causal and cascade state

**Files:**
- Modify: `icarus_engine/apex/store.py`
- Modify: `icarus_engine/apex/causality.py`
- Modify: `icarus_engine/apex/cascade.py`
- Create: `tests_engine/test_apex_causal_persistence.py`

**Interfaces:**
- Produces:
  - `ApexStore.record_causal_edge(edge: Mapping[str, Any]) -> dict[str, Any]`
  - `ApexStore.causal_edges_as_of(as_of: str, *, horizon_seconds: int | None = None) -> list[dict[str, Any]]`
  - `ApexStore.record_cascade_edge(edge: Mapping[str, Any]) -> dict[str, Any]`
  - `ApexStore.cascade_edges_as_of(as_of: str) -> list[dict[str, Any]]`

- [ ] Write RED tests for idempotent edge identity, contradiction-history preservation, horizon/as-of isolation, cycle-safe replay, and reopen determinism.
- [ ] Run `python -m pytest tests_engine/test_apex_causal_persistence.py -q` — Expected FAIL.
- [ ] Add additive `causal_edges` and `cascade_edges` WAL tables and methods.
- [ ] Re-run — Expected PASS.
- [ ] Commit `feat(apex): persist causal cascade state`.

### Task 7: Project-C verification gate

- [ ] Run all Project-C tests — Expected PASS.
- [ ] Run all Project A-B tests — Expected PASS.
- [ ] Run `python -m pytest tests_engine/test_chronofold.py tests_engine/test_parallax_dreamstate.py -q` — Expected PASS.
- [ ] Verify no causal-edge API uses the words `proven` or `caused` solely from correlation-state tests.
