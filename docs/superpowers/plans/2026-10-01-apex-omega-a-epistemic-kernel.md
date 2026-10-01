# ICARUS APEX Ω Project A — Epistemic Kernel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the durable, causally correct APEX evidence/belief substrate that every later APEX Ω subsystem consumes.

**Architecture:** Project A is the foundation layer only: strict contracts → SQLite WAL persistence → evidence ancestry → belief lineage/proof packets → invariant enforcement. It does not implement participant, cascade, world, UI, MCP, or execution behavior.

**Tech Stack:** Python 3.10+, standard library only, sqlite3 WAL, pytest, existing ICARUS causal-time/provenance conventions.

**Spec:** docs/superpowers/specs/2026-10-01-apex-omega-design.md

## Global Constraints

- Engine code remains Python 3.10+ and standard-library only.
- Durable APEX state lives under `research/apex.sqlite3` using SQLite WAL.
- `observed_at`, `received_at`, `calculated_at`, and as-of boundaries remain distinct UTC timestamps.
- Evidence kinds are exactly `observed|derived|reconstructed|inferred|unavailable`.
- No inferred or reconstructed value may be relabeled observed.
- Missing/unavailable evidence contributes no confirming confidence.
- Booleans must not be accepted as numeric values; NaN/Inf fail closed.
- All APEX output carries `production_decision_authorized=false` and `execution_authorized=false`.
- No product/broker/strategy-input mutation is added in Project A.
- Duplicate evidence ingestion is content-addressed and idempotent.
- Historical/as-of reads may only use evidence observed and received by the requested boundary.
- Knowledge delta: create/update `docs/icarus/APEX_OMEGA.md` with installed Project-A truth contract and exact authority boundary.

## Review Focus

- Evidence with valid `observed_at` but future `received_at` must be absent from historical as-of reads — pinned in Task 2.
- Two transform nodes derived from one root source must not count as two independent evidence families — pinned in Task 3.
- Cyclic ancestry input must fail closed rather than hang traversal — pinned in Task 3.
- A persisted belief with an incomplete proof packet must remain readable but must not become `supported` — pinned in Task 4.
- Corrupt SQLite rows / malformed JSON must be reported as quarantined integrity failures rather than silently normalized — pinned in Task 2.

---

### Task 1: Strict APEX evidence contracts

**Files:**
- Create: `icarus_engine/apex/__init__.py`
- Create: `icarus_engine/apex/contracts.py`
- Create: `tests_engine/test_apex_contracts.py`

**Interfaces:**
- Consumes: standard-library mappings/timestamps only.
- Produces:
  - `EVIDENCE_KINDS: frozenset[str]`
  - `parse_utc(value: str, field: str) -> datetime`
  - `normalize_evidence(body: Mapping[str, Any]) -> dict[str, Any]`
  - `evidence_id(semantic: Mapping[str, Any]) -> str`
  - `authority_flags() -> dict[str, bool]`

- [ ] **Step 1: Write failing contract tests**

Add tests named:
- `test_apex_evidence_normalizes_exact_authority_and_four_clocks`
- `test_apex_evidence_rejects_bool_nan_inf_and_out_of_range_confidence`
- `test_unavailable_evidence_cannot_carry_positive_confidence`
- `test_observed_evidence_requires_concrete_source_record`
- `test_evidence_identity_ignores_nonsemantic_recorded_at_but_binds_source_revision`

Assert exact evidence kind vocabulary and false authority flags.

- [ ] **Step 2: Run the contract tests and observe RED**

Run: `python -m pytest tests_engine/test_apex_contracts.py -q`  
Expected: FAIL because `icarus_engine.apex.contracts` does not exist.

- [ ] **Step 3: Implement the contract API**

Implement the interfaces above. Use `json.dumps(..., sort_keys=True, separators=(",", ":"), allow_nan=False)` for semantic identity and SHA-256 for content addressing.

- [ ] **Step 4: Run the contract tests to GREEN**

Run: `python -m pytest tests_engine/test_apex_contracts.py -q`  
Expected: all Project-A contract tests PASS.

- [ ] **Step 5: Commit**

`git add icarus_engine/apex tests_engine/test_apex_contracts.py && git commit -m "feat(apex): add strict evidence contracts"`

### Task 2: SQLite WAL evidence store and causal as-of replay

**Files:**
- Create: `icarus_engine/apex/store.py`
- Create: `tests_engine/test_apex_store.py`

**Interfaces:**
- Consumes: `normalize_evidence()`, `evidence_id()`.
- Produces:
  - `class ApexStore(base_dir: str | os.PathLike[str])`
  - `ApexStore.record_evidence(body: Mapping[str, Any]) -> dict[str, Any]`
  - `ApexStore.evidence_as_of(as_of: str, *, subject: str | None = None) -> list[dict[str, Any]]`
  - `ApexStore.integrity_status() -> dict[str, Any]`
  - `ApexStore.close() -> None`

- [ ] **Step 1: Write failing persistence/as-of tests**

Add:
- `test_apex_store_is_wal_idempotent_and_reopens_deterministically`
- `test_as_of_requires_both_observed_and_received_time_not_after_boundary`
- `test_future_received_at_is_not_visible_even_if_observed_at_is_old`
- `test_corrupt_evidence_row_is_quarantined_and_reported`
- `test_duplicate_retry_returns_same_evidence_id_without_second_row`

- [ ] **Step 2: Run store tests RED**

Run: `python -m pytest tests_engine/test_apex_store.py -q`  
Expected: FAIL because `ApexStore` does not exist.

- [ ] **Step 3: Implement additive schema and WAL store**

Create `research/apex.sqlite3` relative to `base_dir`, enable WAL, foreign keys, busy timeout, and additive schema creation. Persist semantic JSON plus the distinct clocks. Historical selection requires `observed_at <= as_of AND received_at <= as_of`.

- [ ] **Step 4: Run store tests GREEN**

Run: `python -m pytest tests_engine/test_apex_store.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

`git add icarus_engine/apex/store.py tests_engine/test_apex_store.py && git commit -m "feat(apex): add causal evidence store"`

### Task 3: Evidence ancestry and effective independence

**Files:**
- Create: `icarus_engine/apex/ancestry.py`
- Create: `tests_engine/test_apex_ancestry.py`

**Interfaces:**
- Consumes: evidence records with `dependencies`, source subsystem/repo/commit/record identity.
- Produces:
  - `class EvidenceAncestry`
  - `EvidenceAncestry.add(evidence: Mapping[str, Any]) -> None`
  - `EvidenceAncestry.roots(evidence_id: str) -> frozenset[str]`
  - `EvidenceAncestry.effective_support(evidence_ids: Sequence[str]) -> dict[str, Any]`
  - `EvidenceAncestry.detect_cycle(evidence_id: str) -> bool`

- [ ] **Step 1: Write failing ancestry tests**

Add:
- `test_shared_root_counts_as_one_effective_family`
- `test_independent_roots_increase_effective_support`
- `test_semantic_duplicate_root_does_not_inflate_support`
- `test_ancestry_cycle_fails_closed_without_infinite_traversal`

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests_engine/test_apex_ancestry.py -q`  
Expected: FAIL due missing ancestry module.

- [ ] **Step 3: Implement DAG traversal and support summary**

Cycle detection is mandatory. Effective support returns nominal count, unique root count, overlap ratio, root IDs, and `integrity_ok`.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests_engine/test_apex_ancestry.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

`git add icarus_engine/apex/ancestry.py tests_engine/test_apex_ancestry.py && git commit -m "feat(apex): track evidence ancestry"`

### Task 4: Durable beliefs, proof packets, and append-only state transitions

**Files:**
- Create: `icarus_engine/apex/beliefs.py`
- Modify: `icarus_engine/apex/store.py`
- Create: `tests_engine/test_apex_beliefs.py`

**Interfaces:**
- Consumes: `ApexStore`, `EvidenceAncestry`.
- Produces:
  - `BELIEF_STATES: frozenset[str]`
  - `class BeliefLedger`
  - `BeliefLedger.propose(body: Mapping[str, Any]) -> dict[str, Any]`
  - `BeliefLedger.transition(belief_id: str, state: str, *, evidence_ids: Sequence[str], reason: str) -> dict[str, Any]`
  - `BeliefLedger.proof_packet(belief_id: str, *, as_of: str | None = None) -> dict[str, Any]`
  - `BeliefLedger.as_of(as_of: str) -> list[dict[str, Any]]`

- [ ] **Step 1: Write failing belief tests**

Add:
- `test_belief_transition_history_is_append_only`
- `test_supported_belief_requires_complete_evidence_ancestry_and_falsifier`
- `test_incomplete_proof_packet_cannot_transition_to_supported`
- `test_belief_as_of_does_not_leak_future_transition`
- `test_proof_packet_preserves_contradictions_and_false_authority`

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests_engine/test_apex_beliefs.py -q`  
Expected: FAIL due missing belief ledger.

- [ ] **Step 3: Implement belief tables and ledger**

Use immutable belief identity plus append-only `belief_events`; never update historical event rows in place.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests_engine/test_apex_beliefs.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

`git add icarus_engine/apex/beliefs.py icarus_engine/apex/store.py tests_engine/test_apex_beliefs.py && git commit -m "feat(apex): add proof-carrying beliefs"`

### Task 5: Constitution invariants and Project-A snapshot

**Files:**
- Create: `icarus_engine/apex/epistemics.py`
- Create: `icarus_engine/apex/credibility.py`
- Create: `docs/icarus/APEX_OMEGA.md`
- Create: `tests_engine/test_apex_epistemic_kernel.py`

**Interfaces:**
- Consumes: contracts, store, ancestry, beliefs.
- Produces:
  - `validate_authority_invariants(payload: Mapping[str, Any]) -> None`
  - `confidence_after_independence(nominal: float, support: Mapping[str, Any]) -> float`
  - `credibility_score(*, calibration: float | None, data_quality: float, independence: float, reality_gap: float | None) -> dict[str, Any]`
  - `epistemic_kernel_snapshot(store: ApexStore, *, as_of: str | None = None) -> dict[str, Any]`

- [ ] **Step 1: Write failing invariant/snapshot tests**

Add:
- `test_authority_invariant_rejects_true_execution_or_production_flag`
- `test_independence_adjustment_never_increases_nominal_confidence`
- `test_unmeasured_calibration_remains_unmeasured_not_perfect`
- `test_epistemic_snapshot_is_json_finite_and_false_authority`
- `test_empty_store_snapshot_is_truthful_not_error`

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests_engine/test_apex_epistemic_kernel.py -q`  
Expected: FAIL.

- [ ] **Step 3: Implement invariant/credibility helpers and documentation**

Document only Project A as installed; mark Projects B-F as planned, not implemented.

- [ ] **Step 4: Run Project-A suite**

Run: `python -m pytest tests_engine/test_apex_contracts.py tests_engine/test_apex_store.py tests_engine/test_apex_ancestry.py tests_engine/test_apex_beliefs.py tests_engine/test_apex_epistemic_kernel.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

`git add icarus_engine/apex docs/icarus/APEX_OMEGA.md tests_engine/test_apex_*.py && git commit -m "feat(apex): complete epistemic kernel"`

### Task 6: Project-A verification gate

**Files:**
- Modify only if verification exposes a defect: files owned above.

**Interfaces:**
- Consumes: all Project-A interfaces.
- Produces: verified base for Project B.

- [ ] **Step 1: Run scoped Project-A tests**

Run: `python -m pytest tests_engine/test_apex_contracts.py tests_engine/test_apex_store.py tests_engine/test_apex_ancestry.py tests_engine/test_apex_beliefs.py tests_engine/test_apex_epistemic_kernel.py -q`  
Expected: PASS with 0 failures.

- [ ] **Step 2: Run nearby brain/provenance regression**

Run: `python -m pytest tests_engine/test_brain.py tests_engine/test_code_provenance.py -q`  
Expected: PASS with 0 failures.

- [ ] **Step 3: Verify no product authority path was introduced**

Run: `git diff $(git merge-base main HEAD)..HEAD -- icarus_bridge icarus_engine | grep -E "submit_order|broker.*arm|execution_authorized.: true|production_decision_authorized.: true" && exit 1 || exit 0`  
Expected: exit 0.

- [ ] **Step 4: Commit only if fixes were required**

Commit message: `fix(apex): close epistemic kernel verification gaps`
