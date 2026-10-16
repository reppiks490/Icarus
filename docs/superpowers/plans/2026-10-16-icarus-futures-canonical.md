# ICARUS Canonical Futures Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all 32 recovered ICARUS futures roots share one canonical product authority and become structurally paper-resolvable without weakening continuous-research or broker safety boundaries.

**Architecture:** Add `icarus_futures.products` as the immutable source of product economics and identities. Generate analytical `AssetSpec` and execution `ContractSpec` views from the same catalog; keep dated resolution in `icarus_futures.contracts` and continuous-only fail-closed parsing in `icarus_engine.assets`.

**Tech Stack:** Python 3.10+, dataclasses, pytest, existing ICARUS engine/futures packages.

**Spec:** `docs/superpowers/specs/2026-10-16-icarus-futures-canonical-design.md`

## Global Constraints

- Preserve current owner policy: no live broker arming.
- Preserve continuous-only analytical futures identities.
- Unknown or dated futures-looking symbols must fail closed.
- Never infer a futures symbol as spot crypto.
- Broker-paper qualification remains separate from static contract resolution.
- Do not change strategy logic, Brain promotion authority, capital defaults, or risk sizing in this phase.

## Review Focus

- Monthly products near month-end must not resolve to a past roll boundary.
- FX/Treasury/crypto static roll rules must be explicitly tagged conservative rather than silently claimed exchange-perfect.
- Micro point values and ratios must never inherit full-size economics.
- Aliases for roots beginning with digits (`6E`, `6J`, `6B`, `6A`) must parse correctly.
- Existing callers expecting `AssetSpec` fields and current continuous-only errors must remain source-compatible.

---

### Task 1: Contract for the complete canonical futures universe

**Files:**
- Create: `tests_engine/test_futures_product_authority.py`

**Interfaces:**
- Consumes: current `icarus_engine.assets.REGISTRY`, current `icarus_futures.contracts.SPECS`.
- Produces: failing behavioral contract for `icarus_futures.products.PRODUCTS` and 32-root parity.

- [ ] **Step 1: Write the failing tests** asserting the exact 32-root set, product/runtime/execution parity, economics identity, micro-parent ratios, continuous parsing, dated resolution, and fail-closed dated/unknown futures behavior.
- [ ] **Step 2: Run `pytest tests_engine/test_futures_product_authority.py -q`** and confirm failure because `icarus_futures.products` does not exist / registries are incomplete.
- [ ] **Step 3: Commit the failing tests** as the RED checkpoint.

### Task 2: Add the immutable futures product authority

**Files:**
- Create: `icarus_futures/products.py`

**Interfaces:**
- Consumes: the spec's 32-root metadata and current canonical semantics.
- Produces: `FuturesProduct`, `PRODUCTS`, `product(root)`, and helpers for derived tick value / full-equivalent ratio.

- [ ] **Step 1: Implement `FuturesProduct` and the exact 32-root `PRODUCTS` catalog.**
- [ ] **Step 2: Run `pytest tests_engine/test_futures_product_authority.py -q`** and confirm remaining failures are only downstream registry/execution parity.
- [ ] **Step 3: Commit.**

### Task 3: Generate analytical assets from the product authority

**Files:**
- Modify: `icarus_engine/assets.py`

**Interfaces:**
- Consumes: `icarus_futures.products.PRODUCTS`.
- Produces: futures `AssetSpec` entries for every product, generated aliases, metadata fields `exchange`, `asset_class`, `micro_of`, `feed_mode`.

- [ ] **Step 1: Add the new metadata fields to `AssetSpec` without changing existing call signatures.**
- [ ] **Step 2: Replace duplicated futures registry literals with generated `AssetSpec` values from `PRODUCTS`; keep spot crypto entries explicit.**
- [ ] **Step 3: Generate continuous aliases for every futures root while preserving named aliases.**
- [ ] **Step 4: Run the focused test file and existing asset/activation tests.**
- [ ] **Step 5: Commit.**

### Task 4: Generate execution contract specs from the same authority

**Files:**
- Modify: `icarus_futures/contracts.py`

**Interfaces:**
- Consumes: `PRODUCTS`.
- Produces: complete `SPECS`, family-aware `contract_dates`, deterministic `resolve` for every 32-root product.

- [ ] **Step 1: Construct `SPECS` from `PRODUCTS`; derive tick value and ratio-to-full.**
- [ ] **Step 2: Generalize `contract_dates` for `equity`, `first_notice`, `fx`, `treasury`, and `crypto` roll kinds.**
- [ ] **Step 3: Keep `parse_continuous` and `resolve` fail-closed and deterministic for roots beginning with letters or digits.**
- [ ] **Step 4: Run `pytest tests_engine/test_futures_product_authority.py -q`.**
- [ ] **Step 5: Run the full `pytest` suite and record any unrelated baseline failures by name.**
- [ ] **Step 6: Commit.**

### Task 5: Exact-head verification and PR

**Files:**
- No production files beyond Tasks 2–4.

**Interfaces:**
- Consumes: completed branch.
- Produces: reviewable PR with exact-head CI evidence; no merge until checks are green.

- [ ] **Step 1: Open a draft PR against `main` describing scope, safety boundary, and test evidence.**
- [ ] **Step 2: Fetch exact-head workflow runs; inspect failing jobs/logs instead of assuming success.**
- [ ] **Step 3: Fix branch-caused failures test-first, rerun, and update the PR body with exact results.**
- [ ] **Step 4: Leave live execution disabled and call out broker-paper qualification as an external runtime gate.**
