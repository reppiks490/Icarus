# Scoped Workspace API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Expose the selected paper workspace's trading state and controls to the approved common dashboard, with explicit identity and no parent fallback.

**Architecture:** Add a focused `WorkspaceAPI` facade over the existing manager. Keep authentication, strict HTTP path parsing and transport in the existing server; return one workspace/revision identity with every scoped JSON response and CSV download. Reuse the completed workspace transaction for all configuration writes. Frozen backtests and asynchronous job ownership are a following independent subproject; the renderer switch waits for them too.

**Tech Stack:** Existing Python HTTP server, WorkspacePortfolio/Journal, JSON/CSV, pytest real HTTP fixtures, Windows/Linux CI.

**Spec:** `docs/superpowers/specs/2026-10-18-four-workspace-delivery.md`, approved 2026-10-20 amendment; configuration dependency `docs/superpowers/plans/2026-10-20-workspace-configuration.md`.

## Global Constraints

- “No scoped request retries against parent routes.”
- “Backend selection is explicit: look up the requested workspace runtime and then its asset.”
- “Existing whole-workspace endpoints remain whole-workspace operations.”
- “Do not silently interpret their bodies as new asset-specific commands.”
- “Main `inputs.<SYMBOL>.json` files remain excluded.”
- “Live broker arming is disabled.”
- Preserve existing strict four-ledger P&L, persisted performance, chart pagination and download behavior. No renderer switch in this subproject.

## Review Focus

- Same symbol with distinct parent/CC1/CC2/CC3/CC4 data must select the right source, including CSV (Task 1).
- Missing runtime or asset with a healthy parent must return unavailable/404, never fallback (Task 1).
- A whole-workspace pause/flatten body carrying an asset selector must be rejected, not broadened (Task 2).
- Viewer/unauthenticated writes, stale revisions and malformed/encoded paths must fail before state changes (Task 2).
- An asset flatten failure must report actual partial progress without mutating a sibling or implying a verified broker close (Task 2).

---

### Task 1: Scoped status, assets, inputs, trades and exports

**Files:** Create `icarus_engine/workspace_api.py`, `tests_engine/test_workspace_api.py`; modify `icarus_engine/server.py`; extend existing Windows test selection.

**Interfaces:** `WorkspaceAPI(manager)` owns no feed or service tree. `read(profile_id, resource, symbol=None, *, limit=100)` returns selected state with `workspace_id`, `config_revision`, `paper_only: true`, `execution_authorized: false`. Resources: `status`, `assets`, `inputs`, `trades`. `export(profile_id, symbol)` returns the selected runner's CSV plus workspace/revision metadata. Read under the manager commit lock; runner reads use their existing locks. Missing profile/resource/asset raises a typed API error with 404; missing runtime is 503. Status keeps the selected portfolio's native main-dashboard shape while attaching strict selected accounting and its revision. Inputs report selected effective/base values, sources, per-asset overrides, chart and capabilities, never read the parent's per-asset file.

HTTP routes: `/api/command-centers/{id}/status`, `/assets`, `/inputs/{symbol}`, `/trades/{symbol}`, `/export/{symbol}.csv`; preserve existing root snapshot, performance and chart routes. CSV uses `X-Icarus-Workspace` and `X-Icarus-Config-Revision` plus a workspace-prefixed attachment filename. Add identity/revision to existing chart/performance responses without changing their existing fields or bounds. Status authentication matches main status (owner/viewer read); writes remain owner-only.

- [x] Add real HTTP tests with five deliberately different same-symbol runner histories/trades/settings; assert selected status, inputs, trade rows and CSV content/headers.
- [x] Add absent runtime/asset, foreign query selector, path injection/encoding, invalid resources and chart identity cases. A healthy parent must remain untouched and never supply a missing workspace value.
- [x] Run `python -m pytest tests_engine/test_workspace_api.py -q`; observe new-route failures before implementation.
- [x] Implement the facade and strict route integration; preserve legacy field shapes and use truthful paper/replay history labels.
- [x] Run new module plus existing command-center, chart, P&L and performance routes; require green. Include the new module in Windows CI and commit.

### Task 2: Revisioned settings and explicit control scope

**Files:** Modify `icarus_engine/workspace_api.py`, `icarus_engine/paper_workspaces.py`, `icarus_engine/server.py`; extend `tests_engine/test_workspace_api.py`.

**Interfaces:** Add explicit `/admin/command-centers/{id}/assets/{symbol}/config`, `/pause`, `/flatten` endpoints. Config delegates `manager.update_asset`, including mandatory expected revision, returning 409 for `WorkspaceRevisionConflict`; invalid inputs are 400. Asset pause accepts exactly `{paused: bool}`; asset flatten accepts exactly `{confirm: true}` and pauses/flattens only that runner. Whole-workspace existing routes retain their semantics and reject unknown/conflicting selector fields. Extend manager control methods with explicit keyword asset scope while preserving conservative configuration guards and flatten receipts. Missing assets return unavailable before mutation. Never pass workspace requests to main `/admin` handlers.

- [x] Add authorized, viewer and unauthenticated HTTP cases; stale and missing revisions; malformed/duplicate path segments; whole-workspace bodies with misleading asset selectors. Hash parent/sibling saved state and journals around each rejected mutation.
- [x] Add real one-asset pause/resume/flatten cases with two assets and all four ledgers; prove sibling state is unchanged. Include mark failure and partial-flatten truth without broker claims.
- [x] Run new cases and observe missing/broadened-scope failures.
- [x] Implement explicit routing and guarded manager operations, mapping typed conflicts/unavailable errors to truthful HTTP responses.
- [ ] Run the full runtime suite and independent review; publish exact-head results. Then deliver scoped configuration/backtest jobs and the context client before any renderer switch.

## Execution record

Continue under the owner's approved design and explicit implementation instruction. No routine permission checkpoint, merge, deployment, full system restart, provider acquisition or live activation is included. Keep the Icarus 1 identity/session and Icarus 2's separate federation boundary. Shared preset libraries and repository evidence remain shared read-only; no completed connection is inferred from configuration.

### Scoped configuration/backtest HTTP delivery

- [x] Expose owner-only configuration jobs at `/admin/command-centers/{id}/config/async` and `/assets/{symbol}/config/async`, plus `/assets/{symbol}/backtest`. Require expected_revision and reject body/query scope conflicts.
- [x] Authenticate workspace-owned `/api/command-centers/{id}/jobs/{job}` and `/trades.csv`; retain the accepted source revision after current configuration changes. Compare only the selected workspace's completed backtest through `/admin/command-centers/{id}/jobs/{job}/compare`.
- [x] Observe missing HTTP route failures (11 failed / four passed), then verify real offline configuration commits, four selected replay sources, frozen job identity, foreign/main job refusal, CSV headers and owner/viewer boundaries.
- [x] Reproduce local preset read failure disconnects (two failures); return sanitized unavailable JSON without accepting jobs or changing configuration.
- [ ] Complete fresh full runtime suite and final independent review; publish exact source and CI receipts.

Per-workspace locks now protect transactions and admission. Busy snapshots expose unavailable valuation/inputs while unrelated workspaces remain responsive. Invalid effective preset costs fail before admission and during resolution; raw fractional tick costs are checked before coercion. The earlier globally blocking snapshot test now requires explicit unavailable state during the same commit boundary.

The published6ac Windows failure was independently reproduced as a fixture startup retry resetting seeded positions: file mode had no history and the five-second retry raced the test. The acceptance fixture now supplies deterministic real CSV warmup bars, asserts successful warmup and locks manual position seeding, retaining all isolation/control assertions. Fresh hosted Windows verification remains required.

Final local full suite: 3650passed,4skipped,111subtests in223.72s, exit0. First full caught one legacy flatten error-field regression, repaired and verified with10focused cases before the fresh full run. Independent reviewer confirmed all reported fixes but its final whole-diff pass was interrupted by usage limit; do not call that a final independent clear. Source/log hashes and hosted boundaries are in recovery-evidence.json. Publication and current-head hosted checks remain separate.
