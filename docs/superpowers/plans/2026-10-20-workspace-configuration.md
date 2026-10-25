# Workspace Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Give each paper workspace persistent, revisioned per-asset settings without changing the parent or another workspace.

**Architecture:** Extend the existing workspace records and transactional runner reconfiguration. Keep schema validation separate from runtime construction; commit settings while holding the existing workspace transaction. This is the backend foundation for the approved common dashboard; its renderer switch follows only after scoped API/client contracts pass.

**Tech Stack:** Python, existing Portfolio/AssetRunner and JSON persistence, pytest, existing Windows/Linux GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-18-four-workspace-delivery.md`, approved 2026-10-20 amendment.

## Global Constraints

- “No scoped request retries against parent routes.”
- “Main `inputs.<SYMBOL>.json` files remain excluded.”
- “Unknown fields and invalid overrides must fail before mutation.”
- “Initially keep the existing conservative flat-workspace requirement for reconfiguration.”
- “On construction, warmup or write failure, retain the old runners and exact saved bytes.”
- “This amendment does not authorize broker arming, provider purchases or the owner's full system restart.”
- Preserve existing saved selections, chart/fill settings, inputs, paper journals and the strict four-ledger accounting contract.
- Use the existing Icarus 1 branch/session and do not edit Icarus 2's integration-brain paths.

## Review Focus

- A legacy record with unusual formatting must retain its original bytes in a private migration backup and after failed writes/replays (Tasks 1, 2).
- Two simultaneous editors with the same revision must produce one committed edit and one conflict, without lost values (Task 3).
- An NQ-only input/chart/preset edit must preserve ES, parent and sibling settings and never read/write the parent's per-asset override (Tasks 2, 3).
- A flat target with an open or pending sibling must remain conservatively nonconfigurable (Task 2).
- Future schemas, unknown fields, nonfinite values, unknown assets and removed assets must fail explicitly rather than silently drop data (Tasks 1, 3).

---

### Task 1: Versioned records and recoverable migration

**Files:** Create `icarus_engine/workspace_config.py`; modify `icarus_engine/paper_workspaces.py`; test `tests_engine/test_workspace_config.py`.

**Interfaces:** `normalize_workspace(profile: dict) -> dict` returns a defensive canonical copy containing `schema_version: 2`, nonnegative integer `config_revision`, and `asset_overrides: {symbol: {inputs?, chart?, preset?}}`. Preserve legacy defaults and values. Missing version means legacy; future/invalid versions fail. Input names/types and chart values are validated. `PaperWorkspaceManager` loads without rewriting existing records; its first successful migration saves an immutable private `<id>.pre-v2.json` original-byte backup.

- [x] Write `test_legacy_record_migrates_without_changing_values_or_bytes`, `test_future_schema_and_unknown_fields_fail_closed`, and invalid nested-input/chart/asset/preset cases. Assert the migrated in-memory fields and original file bytes, not serialized implementation details.
- [x] Run `python -m pytest tests_engine/test_workspace_config.py -q`; observe missing-version/missing-validation failures.
- [x] Implement normalization, legacy-load integration and immutable private migration backup. New records use schema 2. Existing files are only rewritten by a successful explicit update.
- [x] Run the new module plus `tests_engine/test_paper_workspaces.py`; require all pass.
- [x] Commit the schema/migration task with its regression evidence.

### Task 2: Effective per-asset resolution and transactional persistence

**Files:** Modify `icarus_engine/paper_workspaces.py`; extend `tests_engine/test_workspace_config.py`; adjust existing test doubles only for the added transaction callback.

**Interfaces:** `WorkspacePortfolio._resolved(spec, workspace=None)` resolves workspace-wide inputs/chart plus only `asset_overrides[spec.symbol]`, including its optional shared-library preset. `WorkspacePortfolio.reconfigure(candidate, *, persist=None)` stages changes and calls the optional zero-argument persistence callback before publishing runners/revision and releasing gated workers. `PaperWorkspaceManager.update` restores exact old file bytes on any failed save/replay/worker-start step. Inherited parent `rewarm_asset` is not used for scoped writes.

- [x] Write real two-asset runner tests proving an NQ edit changes only NQ, survives reload and ignores poisoned parent `inputs.NQ.json`. Include partial chart overrides and an explicit preset.
- [x] Write transaction failure tests for replay, persistence and worker start; assert old configuration, runner state/identity, exact saved bytes, unchanged sibling files and no main per-asset files written. Test an open/pending sibling blocks an NQ edit.
- [x] Run the new tests; observe missing overrides and/or rollback failures before implementing.
- [x] Implement effective resolution through the existing resolver and staged transaction; keep metadata/chart precedence and conservative flat guards. Use atomic same-directory writes for restored bytes too. Preserve existing lifecycle tests.
- [x] Run `python -m pytest tests_engine/test_workspace_config.py tests_engine/test_paper_workspaces.py tests_engine/test_paper_workspaces_runtime.py -q`; require all pass.
- [x] Commit the isolated resolution/transaction task.

### Task 3: Compare-and-swap revisions and explicit asset edits

**Files:** Modify `icarus_engine/workspace_config.py`, `icarus_engine/paper_workspaces.py`; extend `tests_engine/test_workspace_config.py`.

**Interfaces:** `WorkspaceRevisionConflict(ValueError)` identifies stale edits. `update(profile_id, body)` accepts `expected_revision` and validates it under the manager lock, increments only on success, returns identity and revision. Existing simple whole-workspace clients remain compatible only while no per-asset configuration exists; once overrides exist, missing revisions fail clearly. `update_asset(profile_id: str, symbol: str, body: dict)` requires `expected_revision`, accepts only `inputs`, `chart`, `preset`, `reset`, and that revision, updates only the admitted selected asset's override and delegates one transaction. Reset removes that asset's override, preserving workspace-wide settings. Missing or foreign assets never fall back to parent.

- [x] Write stale, missing, malformed/bool revision tests; use two real concurrent writers to prove exactly one success and one conflict from the same revision. Assert no mutation on rejection.
- [x] Write per-asset edit/reset/reload tests and reject unsupported body fields, unselected symbols, conflicting selectors and unsupported schema. Confirm legacy whole-workspace updates still preserve existing behavior before overrides exist.
- [x] Run the new tests; observe absent compare-and-swap/scoped-edit behavior.
- [x] Implement locked revision enforcement and explicit asset update, exposing revision in workspace snapshots/results. Never silently broaden an asset edit.
- [x] Run the full project runtime command `python -m pytest tests_engine -q --tb=short -o addopts=''`; require a green suite and record skips honestly. Add the new regression module to existing Windows selection.
- [x] Commit; obtain an independent review of all three tasks. Publish source/evidence to the existing draft PR, retain NO_GO, then start the scoped API/client delivery plan.

## Execution record

Owner approved the written shared-dashboard design and explicitly directed continued implementation. Execute inline with read-only specialist assistance and an independent final review; no additional routine approval checkpoint is required. Current upstream `25d560b1d67848e244e59095f9f9152c3d7ab09b` adds provider/federation receipts only; it was merged into this recovery branch without changing runtime source. Earlier source head `4368a33` passed all four hosted PR workflows. Keep prior verification receipts scoped to their exact source hashes.
