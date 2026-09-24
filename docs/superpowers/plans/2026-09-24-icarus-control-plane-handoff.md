# ICARUS Control-Plane Findings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the evidence-backed ICARUS control-plane/subsystem findings into verified, minimal repository changes without crossing sibling ownership boundaries.

**Architecture:** Keep the ICARUS repository as the coordinator/execution owner and repair defects in the repository that canonically owns them. Do not copy sibling implementations into ICARUS. Each defect is independently reproducible, test-first, fail-closed, and revision-pinned.

**Tech Stack:** Python, pytest/unittest as used by each repository, SQLite where already canonical, JSON/canonical SHA-256 contracts, GitHub sibling repositories.

**Spec:** `docs/icarus-control-plane/README.md`, `docs/icarus-control-plane/SUBSYSTEM_ROTATION_FINDINGS.md`, `docs/icarus-control-plane/UNIFIED_CYCLE_RUNBOOK.md`

## Global Constraints

- `execution_authorized=false`
- No synthetic bars presented as empirical evidence.
- No invented trainer slots/features.
- No Pulse rewrite.
- Fail closed on missing provenance/ownership/time semantics.
- Do not weaken holdout/provenance/integrity gates to make tests pass.
- Pin every repository revision before reproduction.
- Do not silently mix cross-revision evidence.

## Review Focus

1. A descendant data snapshot reuses previously exposed protected observations without detection.
2. A historical gap/recovery transition changes AION replay but escapes integrity verification.
3. An AION microstructure packet confuses event hashes with source-manifest identity.
4. An ATHENA-bound aggregate has identical numbers but materially degraded contributor lineage.
5. Missing NEXUS/ORACLE canonical evidence accidentally creates an inferred adapter/authority path.

---

### Task 1: Revalidate repository snapshots

**Files:**
- Read: `docs/icarus-control-plane/HANDOFF_STATE.json`
- Read current sibling repo heads before changing anything.
- Modify handoff docs only if evidence revisions changed.

**Interfaces:**
- Consumes: pinned revisions recorded in handoff.
- Produces: exact compatibility verdict for every finding.

- [ ] **Step 1:** Fetch current heads for ICARUS, AION and DAEDALUS.
- [ ] **Step 2:** Compare with handoff revisions.
- [ ] **Step 3:** If different, inspect only the affected files/diffs and classify each finding as still reproducible, superseded, or cross-revision/unverified.
- [ ] **Step 4:** Do not implement a finding whose decisive evidence no longer matches the current canonical revision.
- [ ] **Step 5:** Record exact revisions used by each subsequent task.

---

### Task 2: AION gap-history integrity

**Repository:** `reppiks490/aion-parallax-research`

**Files expected from pinned evidence:**
- Modify: `aion/store.py`
- Test: `tests/test_memory.py`
- Update project docs/ADR required by AION repository conventions.

**Interfaces:**
- Consumes: `source_gap_history`, `gaps_asof()`, `verify_chain()`.
- Produces: deterministic authenticated gap-transition ledger consumed by replay.

- [ ] **Step 1: Write failing mutation test**

Add a test that creates a contiguous depth source, records a gap, confirms integrity before corruption, corrupts the persisted historical transition using a controlled fixture path, then requires `verify_chain()` to raise an integrity error.

- [ ] **Step 2: Run focused test and verify RED**

Run the exact repository test command for that test. Record the failure proving current verification misses the tamper.

- [ ] **Step 3: Add recovered-transition case**

Create a second test where a gap is later recovered and current `source_gaps` is empty; tamper the historical recovery transition and require integrity verification to fail.

- [ ] **Step 4: Implement deterministic gap hash chain**

Persist/recompute a deterministic digest for every gap-history transition using ledger order and canonical fields:
`source_id, available_ns, state, previous_sequence, observed_sequence` plus previous gap hash.

- [ ] **Step 5: Make replay fail closed on unverified gap ledger**

Do not allow `gaps_asof()`-dependent replay to continue under a failed integrity check in verification-sensitive paths.

- [ ] **Step 6: Run focused tests, then full AION suite**

Only claim fixed after fresh full output is clean.

---

### Task 3: DAEDALUS protected-evidence source lineage

**Repository:** `reppiks490/daedalus-research-os`

**Files expected from pinned evidence:**
- Modify: `src/daedalus/identity.py`
- Modify: `src/daedalus/holdout.py`
- Modify: `src/daedalus/pipeline.py`
- Potentially modify: `src/daedalus/corpus.py`
- Tests: existing holdout/identity/corpus test modules or new focused regression module.
- Update the repository's audit/current/handoff documentation required by its conventions.

**Interfaces:**
- Consumes: reviewed source identity + immutable file snapshot.
- Produces: stable logical source lineage across snapshots and protected-interval contamination guard.

- [ ] **Step 1: Write append-only descendant RED test**

Version 1 has a protected tail exposed. Version 2 is an exact append-only descendant with a different full-file SHA. Require that observations previously protected in v1 cannot silently enter v2 development evidence.

- [ ] **Step 2: Write historical-mutation RED test**

Change/insert/delete a historical observation. Require fail-closed lineage review rather than automatic carry-forward.

- [ ] **Step 3: Define explicit stable `source_lineage_id`**

Do not derive it solely from current file hash. Preserve current `snapshot_sha256` separately.

- [ ] **Step 4: Verify snapshot relation**

Support explicit states:
`SAME_SNAPSHOT`, `APPEND_ONLY_DESCENDANT`, `MUTATED_OR_REORDERED`, `UNKNOWN`.

- [ ] **Step 5: Project prior protected intervals into verified descendants**

Previously protected observations remain excluded from future development.

- [ ] **Step 6: Fail closed for ambiguous ancestry**

Do not guess based on filename/path similarity.

- [ ] **Step 7: Run ResourceWarning-as-error tests, full suite and static audit**

Use repository canonical commands and record exact outputs.

---

### Task 4: ARGUS provenance contract — blocked until repo recovery

**Repository:** UNKNOWN

**Interfaces:**
- Consumes: AION microstructure evidence packet.
- Produces: provenance-verified microstructure state only.

- [ ] **Step 1:** Locate and pin canonical ARGUS repo/commit.
- [ ] **Step 2:** Establish owner-approved ingress schema.
- [ ] **Step 3:** Reproduce whether legacy `source_hashes` is interpreted as source identity.
- [ ] **Step 4:** Add a failing test for ambiguous event-hash/source-manifest semantics.
- [ ] **Step 5:** Add reviewed source-manifest identity separately from event hashes.
- [ ] **Step 6:** Prove candle/proxy evidence cannot be promoted to true trade/depth.
- [ ] **Step 7:** Run full applicable suite.

Do not implement ARGUS behavior in ICARUS while the canonical repo remains unknown.

---

### Task 5: ATHENA uncertainty-lineage contract — blocked until repo recovery

**Repository:** UNKNOWN

**Interfaces:**
- Consumes: AION state input with aggregates + contributor lineage.
- Produces: uncertainty/risk/abstention state that cannot gain authority from missing/degraded evidence.

- [ ] **Step 1:** Locate and pin canonical ATHENA repo/commit.
- [ ] **Step 2:** Reproduce current state-input schema and lineage consumption.
- [ ] **Step 3:** Add an equal-numeric-aggregate test where one packet has degraded lineage.
- [ ] **Step 4:** Require degraded/missing lineage to produce uncertainty >= clean packet and authority <= clean packet.
- [ ] **Step 5:** Update AION export only through a reviewed versioned contract; do not silently change legacy semantics.
- [ ] **Step 6:** Run full applicable suite.

---

### Task 6: NEXUS canonical admission

**Repository:** UNKNOWN

- [ ] **Step 1:** Locate canonical repository/handoff.
- [ ] **Step 2:** Pin responsibility, input/output contracts, sibling exclusions, clocks, provenance, replay and failure semantics.
- [ ] **Step 3:** Add admission test: a name/config entry alone must resolve to `UNVERIFIED`, zero authority and zero inferred adapters.
- [ ] **Step 4:** Only after those pass may an integration adapter be designed.

---

### Task 7: ORACLE canonical admission

**Repository:** UNKNOWN

- [ ] **Step 1:** Locate canonical repository/handoff.
- [ ] **Step 2:** Pin responsibility, owned contracts, sibling exclusions, clocks, provenance, replay and uncertainty semantics.
- [ ] **Step 3:** Add admission test: plausible schema without canonical ownership remains `UNVERIFIED`.
- [ ] **Step 4:** No routing/qualification/execution influence before verification.

---

### Task 8: Control-plane implementation choice

The repaired unified cycle currently exists as an external ChatGPT scheduling design, not repo runtime code.

- [ ] **Step 1:** Decide explicitly whether the control plane remains external or becomes a repo-native tool.
- [ ] **Step 2:** If external, keep this runbook as the canonical reconstruction specification and do not add scheduler code.
- [ ] **Step 3:** If repo-native is approved, create a separate design first for durable cycle state, lock/duplicate suppression, immutable repo snapshot pinning, canonical serialization, digest chain, recovery, and dry-run safety.
- [ ] **Step 4:** Do not couple the control plane to broker/execution authority.
- [ ] **Step 5:** Require tests proving a stage cannot consume a different policy epoch/revision and cannot silently promote missing predecessor evidence.

## Completion gate

Do not call this plan complete because documentation exists.

Completion requires each implemented task to have:
- compatible pinned source revision,
- reproduced pre-fix failure,
- independent regression oracle,
- focused green test,
- full applicable suite,
- documented provenance/revision,
- no new execution authority.

NEXUS/ARGUS/ATHENA/ORACLE remain blocked until their current canonical implementations are recovered.


## Task 8 implementation status — 2026-09-24

Decision: scheduler remains external; receipt verification becomes repo-native.

Implemented on `chatgpt/icarus-control-plane-runtime-20260924`:
- versioned policy/schema contract documents,
- deterministic strict JSON canonicalization,
- receipt SHA-256 verification,
- S1->S5 predecessor digest validation,
- policy epoch and pinned-snapshot consistency checks,
- stage maturity ceilings,
- S4 oracle provenance requirements,
- evidence-lineage duplicate-origin checks,
- read-only `icarus-control` CLI,
- adversarial regression tests,
- separate evidence-branch storage rule.

Fresh CI run `36064742770` passed on Linux and Windows, including the full Linux engine suite, new control tests, CLI smoke, plant setup and doctor, plus Windows focused tests and setup. A later documentation/matrix commit requires one final-head CI check before Task 8 technical acceptance.
