# ICARUS APEX Ω Project F — Full Integration Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Assemble Projects A-E behind one APEX Ω kernel and integrate truthful read/mutation surfaces into Adaptive Brain, HTTP, MCP, dashboard, documentation, and cross-platform regression coverage.

**Architecture:** Project F is orchestration only. `ApexKernel` owns no broker authority and reads sibling systems through Project-D adapters; server/MCP routes expose research state/ingest only. The dashboard displays world, participant, force, cascade, causal, unknown, epistemic, self and conscience state without collapsing them into a single trade signal.

**Tech Stack:** Python 3.10+, standard-library engine HTTP server, existing MCP bridge patterns, vanilla JS dashboard, Node syntax checks where available, pytest.

**Spec:** docs/superpowers/specs/2026-10-01-apex-omega-design.md

## Global Constraints

- Requires verified Projects A-E.
- `ApexKernel` must tolerate missing/degraded sibling subsystems.
- HTTP mutations are authenticated research evidence/outcome/model-observation/experiment inputs only.
- No APEX endpoint may alter positions, strategy inputs, broker state, or production candidate authority.
- UI must show unavailable/unmeasured/contradicted states explicitly.
- Adaptive Brain registration describes APEX but cannot promote its outputs to production.
- MCP parity preserves exact false authority flags.
- Linux and Windows causal-time behavior must be covered by CI-compatible tests.
- Knowledge delta: finalize `docs/icarus/APEX_OMEGA.md`, README discoverability, and repository-native evolution receipt.

## Review Focus

- One failing sibling snapshot must not make `GET /api/apex` return 500 if other components can still report — Task 1/2.
- Oversized/malformed admin JSON must fail with existing bounded advisory behavior and preserve prior state — Task 3.
- UI must not render unavailable numeric fields as zero — Task 4.
- MCP mutation wrappers must route only to APEX research endpoints and preserve exact payload types — Task 5.
- Mainline integration must be based on and verified against the exact then-current `main`, not stale green CI — Task 7.

---

### Task 1: Assemble the APEX Ω kernel

**Files:**
- Create: `icarus_engine/apex/kernel.py`
- Modify: `icarus_engine/apex/__init__.py`
- Create: `tests_engine/test_apex_kernel.py`

**Interfaces:**
- `class ApexKernel(base_dir, *, possibility=None, chronofold=None, pantheon=None, parallax=None, dreamstate=None, sibyl=None)`
- `ApexKernel.snapshot(*, as_of: str | None = None, asset: str | None = None) -> dict[str, Any]`
- `ApexKernel.ingest_evidence(body: Mapping[str, Any]) -> dict[str, Any]`
- `ApexKernel.record_outcome(body: Mapping[str, Any]) -> dict[str, Any]`
- `ApexKernel.record_model_observation(body: Mapping[str, Any]) -> dict[str, Any]`
- `ApexKernel.propose_experiment(body: Mapping[str, Any]) -> dict[str, Any]`

- [ ] RED tests for empty startup, degraded sibling isolation, deterministic as-of snapshot, false authority, and JSON-finite snapshot.
- [ ] Run RED.
- [ ] Implement orchestration only.
- [ ] Run GREEN.
- [ ] Commit `feat(apex): assemble Apex Omega kernel`.

### Task 2: Register APEX with Adaptive Brain

**Files:**
- Modify: `icarus_engine/brain.py`
- Modify: `tests_engine/test_brain.py`

**Interfaces:**
- Add subsystem id `apex-omega`, owner `omega`, job describing federated world-state/epistemic governance.
- Brain snapshot may include compact APEX health summary only; it must not duplicate full APEX state.

- [ ] RED test asserts subsystem registry contains APEX Ω and authority remains shadow/research only.
- [ ] Run targeted brain test RED.
- [ ] Add registry/compact-health integration.
- [ ] Run targeted brain test GREEN.
- [ ] Commit `feat(apex): register with Adaptive Brain`.

### Task 3: HTTP API and authenticated research mutations

**Files:**
- Modify: `icarus_engine/server.py`
- Create: `tests_engine/test_apex_server.py`

**Interfaces:**
- Instantiate `ApexKernel` after sibling engines needed by adapters exist.
- Read routes:
  - `/api/apex`
  - `/api/apex/participants`
  - `/api/apex/crowdhunt`
  - `/api/apex/forces`
  - `/api/apex/cascades`
  - `/api/apex/causality`
  - `/api/apex/worlds`
  - `/api/apex/epistemics`
  - `/api/apex/self`
  - `/api/apex/conscience`
- Authenticated POST routes:
  - `/admin/apex/evidence`
  - `/admin/apex/outcome`
  - `/admin/apex/model-observation`
  - `/admin/apex/experiment`

- [ ] RED tests for every route, auth rejection, malformed/oversized body, degraded sibling snapshot, and no strategy/position mutation.
- [ ] Run `python -m pytest tests_engine/test_apex_server.py -q` — Expected FAIL.
- [ ] Implement route mapping using existing `strict_json`, token/auth, `dumps_safe`, and error conventions.
- [ ] Run GREEN.
- [ ] Commit `feat(apex): expose research HTTP surface`.

### Task 4: APEX Ω trader-interface tab

**Files:**
- Create: `icarus_engine/apex-ui.js`
- Modify: `icarus_engine/dashboard.html`
- Modify: `tests_engine/test_dashboard_js.py`

**Interfaces:**
- Global `wireApex()` matching existing UI-module convention.
- Tab id/view `apex`.
- Panels: World, Participants, CROWDHUNT, Forces, Liquidity, Cascades, Causal Graph, Counterfactual Worlds, Unknown Force, Epistemic Health, Model Health, Conscience.

- [ ] RED dashboard tests assert script inclusion, tab, `wireApex()`, API path, authority text, explicit `UNAVAILABLE`/unmeasured handling, and all panel labels.
- [ ] Run targeted dashboard test RED.
- [ ] Implement UI with bounded rendering and escaping; never coerce null/unavailable numeric fields to zero.
- [ ] Run `python -m pytest tests_engine/test_dashboard_js.py -q` — Expected PASS.
- [ ] Commit `feat(apex): add trader intelligence panel`.

### Task 5: MCP research parity

**Files:**
- Modify: `icarus_bridge/mcp_server.py`
- Modify: `tests_engine/test_mcp_server.py`

**Interfaces:**
- Read wrappers:
  - `engine_apex_state()`
  - `engine_apex_participants()`
  - `engine_apex_cascades()`
  - `engine_apex_beliefs()` if HTTP exposes compact belief lineage through `/api/apex/epistemics`
  - `engine_apex_conscience()`
- Mutation wrappers:
  - `record_engine_apex_evidence(evidence_json: str)`
  - `record_engine_apex_outcome(outcome_json: str)`
  - `record_engine_apex_model_observation(observation_json: str)`
  - `propose_engine_apex_experiment(experiment_json: str)`

- [ ] RED tests pin exact GET/POST paths, reject non-object/malformed JSON, preserve false authority, and ensure no wrapper targets broker/order/control endpoints.
- [ ] Run targeted MCP tests RED.
- [ ] Implement wrappers using existing `_engine_get/_engine_post` patterns.
- [ ] Run `python -m pytest tests_engine/test_mcp_server.py -q` — Expected PASS.
- [ ] Commit `feat(apex): expose MCP research tools`.

### Task 6: Documentation, README, and durable evolution receipt

**Files:**
- Modify: `docs/icarus/APEX_OMEGA.md`
- Modify: `README.md`
- Create: `automation_intelligence/mcp_interface/events/<implementation-utc>_apex_omega_integrated.json`

**Interfaces:**
- Document exact installed routes, modules, persistence, evidence semantics, missing-SIBYL behavior, authority boundaries, test commands, and non-goals.
- README adds one concise APEX Ω discovery link, not a duplicate spec.
- Evolution receipt binds exact implementation commit/source and false authority.

- [ ] Add documentation/evolution-receipt assertions to existing integrity/evolution test style where appropriate.
- [ ] Run those tests RED before creating final docs/receipt.
- [ ] Write truthful installed-state docs only; no planned capability may be described as active.
- [ ] Run tests GREEN.
- [ ] Commit `docs(apex): publish Apex Omega integration contract`.

### Task 7: Whole APEX Ω verification and current-main reconciliation

**Files:**
- All APEX-owned/integration files only if verification finds defects.

**Interfaces:**
- Produces: exact-head verified integration candidate suitable for PR/merge to current main.

- [ ] **Reconcile current main before final verification**

Fetch/rebase or merge the exact then-current `main` into the APEX branch using repository policy. Resolve collisions by preserving newer sibling ownership and re-running affected tests.

- [ ] **Run the complete APEX suite**

Run: `python -m pytest tests_engine/test_apex_*.py -q`  
Expected: 0 failures.

- [ ] **Run affected subsystem regression**

Run: `python -m pytest tests_engine/test_brain.py tests_engine/test_dashboard_js.py tests_engine/test_mcp_server.py tests_engine/test_possibility.py tests_engine/test_chronofold.py tests_engine/test_pantheon_aether.py tests_engine/test_parallax_dreamstate.py -q`  
Expected: 0 failures.

- [ ] **Run full engine suite**

Run: `python -m pytest tests_engine -q`  
Expected: 0 failures.

- [ ] **Run repository doctor/control checks used by current CI**

Use the exact commands from the current `.github/workflows/test.yml`; every required Linux/Windows-compatible check must pass on the exact candidate head.

- [ ] **Authority diff audit**

Search changed code for broker/order/position/strategy-input mutation and any true execution/production authority. Any finding is a blocker unless it is pre-existing context not reachable from APEX.

- [ ] **Exact-head CI**

Push integration branch; wait for/inspect Linux and Windows workflow runs associated with the exact head. Stale green runs do not count.

- [ ] **Final collision check**

Verify current `main` is still an ancestor of the exact tested head immediately before merge. If not, reconcile and re-run affected/exact-head verification.

- [ ] **Merge only after exact-head green**

Create/review PR, merge to `main` only when exact-head checks are green and no unresolved Critical/Important review finding remains.

- [ ] **Post-merge main verification**

Fetch merged `main`, identify the merge/result commit, and inspect its CI/status. Report the exact commit and any remaining limitations truthfully.
