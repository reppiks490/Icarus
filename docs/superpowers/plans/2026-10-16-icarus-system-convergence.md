# ICARUS System Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Converge ICARUS futures identity/execution, discovery, asset-centric paper state, and Brain provenance behind one fail-closed evidence model.

**Architecture:** A typed futures catalog becomes the single authority for futures identity/economics, with runtime assets and execution contracts derived from it. A deterministic capability index, asset command-center backend state, and provenance-bearing Brain evidence consume those canonical definitions without touching currently-colliding UI paths.

**Tech Stack:** Python 3.11, dataclasses, pytest, existing ICARUS runtime/CI, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-16-icarus-system-convergence-design.md`

## Global Constraints

- Live execution remains disabled.
- Continuous research identities and dated execution identities stay separate.
- Unknown/dated futures identities fail closed and never become spot crypto.
- UI collision paths in the active dashboard workstream are not modified on this branch.
- No product is reported paper-tradeable without an execution specification and resolver support.
- Missing/stale evidence is a blocker, not neutral input.

## Review Focus

- Product-specific roll rules must not be guessed from another asset family; unsupported resolver families remain explicitly unqualified.
- Micro roots must retain independent economics and correct full-equivalent ratios.
- Provider/TV identities must be unique even where the canonical root differs from the provider root (`BTCF` → `BTC=F`).
- Capability-index hashing must be deterministic across dict ordering/process runs.
- Brain regime/evidence timestamps must reject look-ahead and stale required sources.

---

### Task 1: Canonical 32-root futures authority

**Files:**
- Create: `icarus_engine/futures_catalog.py`
- Modify: `icarus_engine/assets.py`
- Modify: `icarus_futures/contracts.py`
- Create: `tests_engine/test_futures_catalog.py`

**Interfaces:**
- Produces: `FuturesProduct`, `FUTURES_PRODUCTS`, `futures_product(root)`, `execution_qualified_products()`.
- `assets.py` consumes the catalog to construct futures `AssetSpec` records.
- `contracts.py` consumes the catalog to construct `ContractSpec` records and resolver support.

- [ ] **Step 1: Write the failing catalog tests**
  Assert exact 32-root coverage, identity uniqueness, economic consistency, micro-parent ratios, and no mutation of the existing fail-closed symbol behavior.
- [ ] **Step 2: Run `python -m pytest tests_engine/test_futures_catalog.py -q` and observe failure**
  Expected: import/module failure because `icarus_engine.futures_catalog` does not exist.
- [ ] **Step 3: Implement `futures_catalog.py`**
  Define typed product records for all 32 roots and explicit `execution_qualified` / `execution_blocker` fields so unverified resolver families cannot silently route.
- [ ] **Step 4: Derive `assets.REGISTRY` futures records from the catalog**
  Preserve current public `AssetSpec` API and alias/fail-closed behavior.
- [ ] **Step 5: Derive execution `SPECS` from execution-qualified catalog records**
  Preserve current resolver behavior for existing families; add only resolver families whose rules are explicitly represented.
- [ ] **Step 6: Run focused and regression tests**
  `python -m pytest tests_engine/test_futures_catalog.py tests_engine/test_futures.py -q` → PASS.
- [ ] **Step 7: Commit**

### Task 2: Deterministic canonical capability index

**Files:**
- Create: `icarus_engine/system_index.py`
- Create: `tests_engine/test_system_index.py`

**Interfaces:**
- Consumes: `REGISTRY`, `FUTURES_PRODUCTS`, execution `SPECS`.
- Produces: `build_system_index() -> dict`, `system_index_json() -> str`, `system_index_markdown() -> str`, `system_index_sha256() -> str`.

- [ ] **Step 1: Write failing deterministic-index tests**
  Assert schema version, 32 futures records, per-root execution qualification/blockers, live authorization false, stable JSON/hash, and human projection coverage.
- [ ] **Step 2: Run test and observe failure**
- [ ] **Step 3: Implement deterministic compiler**
  Build records entirely from runtime registries with sorted keys/roots; hash canonical JSON excluding the hash field itself.
- [ ] **Step 4: Run focused tests**
- [ ] **Step 5: Commit**

### Task 3: Asset-centric backend command-center state

**Files:**
- Create: `icarus_engine/asset_command_center.py`
- Create: `tests_engine/test_asset_command_center.py`

**Interfaces:**
- Consumes: system index / futures catalog.
- Produces: `AssetCommandState`, `build_asset_command_state(root, runtime=None)`, `build_all_asset_command_states()`.

- [ ] **Step 1: Write failing gating tests**
  Assert all futures roots get a state record; `paper_tradeable` is false whenever execution qualification is false; live authorization is always false; blockers are explicit and stable.
- [ ] **Step 2: Run test and observe failure**
- [ ] **Step 3: Implement backend state**
  Include identity, economics, authorization, blockers, and optional runtime/statistics fields without adding order logic.
- [ ] **Step 4: Run focused tests**
- [ ] **Step 5: Commit**

### Task 4: Brain evidence provenance and causal regime validation

**Files:**
- Create: `icarus_engine/brain_evidence.py`
- Create: `tests_engine/test_brain_evidence.py`

**Interfaces:**
- Produces: `EvidenceSource`, `RegimeSnapshot`, `BrainEvidence`, `validate_brain_evidence(evidence, decision_time, now=None)`.

- [ ] **Step 1: Write failing provenance/causality tests**
  Reject missing required hash/revision, event/retrieval timestamps after decision time where causal availability is required, stale required sources, and regime snapshots observed after decision time.
- [ ] **Step 2: Run test and observe failure**
- [ ] **Step 3: Implement immutable evidence records and validator**
  Return explicit validation errors/blockers; never coerce missing evidence to neutral values.
- [ ] **Step 4: Run focused tests**
- [ ] **Step 5: Commit**

### Task 5: Exact-head regression and completion evidence

**Files:**
- Modify only if a test reveals a defect in owned, non-colliding paths.

- [ ] **Step 1: Run focused convergence tests**
  `python -m pytest tests_engine/test_futures_catalog.py tests_engine/test_system_index.py tests_engine/test_asset_command_center.py tests_engine/test_brain_evidence.py tests_engine/test_futures.py -q`.
- [ ] **Step 2: Run full Linux suite through existing GitHub Actions `tests` workflow**
- [ ] **Step 3: Inspect failing jobs/logs and repair owned defects; rerun**
- [ ] **Step 4: Verify exact PR head SHA and combined status**
- [ ] **Step 5: Publish completion/handoff event to `icarus-owner-actions` with exact PR/SHA/test evidence and remaining external blockers**
