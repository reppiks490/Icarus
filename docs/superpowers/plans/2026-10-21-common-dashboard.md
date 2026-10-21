# Common Workspace Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Serve the main trading components at main/CC1–CC4 with explicit workspace state/actions, preserved evidence/performance surfaces and real browser isolation proof.

**Architecture:** Consume the completed immutable context client and selected revisioned runtime APIs/jobs. Add a server context guard and explicit module transport adapter before migrating callers. Reuse the existing renderer/styles; classify shared evidence separately from selected runtime state, and reject unavailable actions without a parent fallback. Switch the CC renderer only after its dependencies pass.

**Tech Stack:** Existing Python HTTP server/WorkspaceAPI, browser JavaScript/CSS, pytest, Node and real Playwright Chromium.

**Spec:** `docs/superpowers/specs/2026-10-18-four-workspace-delivery.md`, owner-approved amendment. Dependencies: workspace configuration/API/jobs/context-client plans; source checkpointfb98ce6 full3699passed and responsive repair0fbfbd9.

## Global Constraints

- “No scoped request retries against parent routes.”
- “Existing whole-workspace endpoints remain whole-workspace operations.”
- “Downloads stay scoped.”
- “A stale revision returns a conflict without changing state.”
- “Hiding a button is insufficient.”
- “No placeholder state may masquerade as a connected subsystem.”
- “Live broker arming is disabled.”
- Preserve dedicated renderer rollback, private records, strict P&L, corpus/A200/connections and persisted paper performance. Do not clone feeds/services/schedulers or acquire provider data during engineering checks.

## Review Focus

- A raw/direct module request from a CC page must not read or mutate main, even if a caller bypasses the explicit helper.
- Inputs retain the editor's original revision; `*` applies overlapping input/chart edits deliberately across overrides without discarding unrelated settings.
- A historical job/download retains accepted identity after current configuration advances; owner/viewer boundaries remain intact.
- Missing/delayed responses clear market/chart/trade observations while retaining local input drafts; no cached parent observation fills a gap.
- All five pages expose the same components at desktop/mobile sizes; shared evidence and unavailable runtime panels have truthful labels.

---

### Task 1: Explicit module transport and backend context guard

**Files:** Create `icarus_engine/workspace_context.py`, `tests_engine/test_workspace_context.py`; modify `icarus_engine/workspace-client.js`, `icarus_engine/server.py`, `tests_engine/test_workspace_client.py`, `tests_engine/test_workspace_api.py`.

**Interfaces:** `IcarusClient.request(path, init={})` returns a bounded, authenticated Response for legacy modules. Main preserves native same-origin behavior. CC context permits an explicit read-only evidence/catalog allowlist and selected canonical API paths; parent-bound readers use scoped panel adapters or unavailable responses, and unsupported mutations use a scoped rejecting endpoint. It never blindly prefixes or retries parent URLs. High-level core operations continue using the typed client methods.

`guard_workspace_request(headers, path, method, server_port)` returns the validated context or raises `WorkspaceContextError(status, detail, workspace_id)`. A valid `X-Icarus-Workspace` and same-origin CC Referer constrain requests; they never choose a runtime implicitly. Reject mismatches and foreign scoped resources, parent runtime reads and unsupported global mutations. Preserve authenticated owner checks before write-body parsing. Shared/static navigation remains available. Scoped unavailable endpoints return truthful JSON and perform no action.

- [x] Write/observe failing Node cases for native main requests, selected reads, shared payloads, unsupported parent read/mutation routing, foreign scope rejection, response lifetime and HTTP error shape preservation.
- [x] Write/observe failing real HTTP cases for header/Referer mismatch, raw parent controls, foreign workspace actions, viewer/unauthenticated writes, selected canonical access and shared reads. Hash actual parent/sibling journals/settings before and after refused operations.
- [x] Implement the guard/adapter, retain existing authentication and unknown-path behavior, then run focused client/API/auth/execution/route checks.
- [x] Review exact route classifications and commit the independently testable boundary before changing CC HTML.

### Task 2: Core renderer reads, editor revisions, controls and downloads

**Files:** Create `icarus_engine/workspace-ui.js`; modify `icarus_engine/dashboard.html`, `icarus_engine/command-centers-ui.js`, `icarus_engine/shadow-twin-ui.js`, `tests_engine/test_workspace_client.py`, `tests_engine/test_workspace_dashboard_browser.py`, `tests_engine/test_dashboard_js.py`.

**Interfaces:** `IcarusWorkspaceUI` handles core action translation only. Status/chart/inputs/trades use typed client reads; configuration/backtest/rewarm/job/comparison calls use typed methods with explicit source revisions. Main retains its established contracts. CSV uses authenticated Blob downloads; solo links use full-page `client.href` navigation. Keep all runtime globals page-owned.

Inputs capture one consistent configuration/input revision on load and retain it with edits. Per-asset apply/reset/preset selects only that asset. `*` input/chart edits update workspace defaults and explicitly remove the same edited keys from selected asset overrides, preserving unrelated fields. Whole reset clears per-asset overrides while preserving saved workspace defaults. Whole preset updates the admitted assets' preset selections explicitly. Add/remove use one latest-snapshot CAS transaction, canonical admitted symbols, and explicit removed-override disposition. Default backtests omit preset rather than sending an unintended null.

Replace the Command Center's unsafe duplicate configuration writer with selected-page controls/navigation and the common Inputs surface. Other ledger cards navigate to their pages; no foreign mutation retains the current identity. Shadow comparison uses selected status. Invalidate failed/obsolete chart/trade/status caches and clear displayed values while retaining local draft data/revision.

- [ ] Add failing five-source core/action cases, per-asset versus `*` precedence preservation, draft conflict, job identity, auth/download and navigation cases.
- [ ] Implement the explicit core calls and action helper; remove raw parent paths from these core flows.
- [ ] Verify real HTTP/browser owner/viewer controls, file/journal scope, delayed responses and cached observation clearing; parse/check all changed JavaScript.

### Task 3: Contextual panels and preserved evidence surfaces

**Files:** Create `icarus_engine/workspace_market_data.py`, `icarus_engine/workspace-evidence-ui.js`, `tests_engine/test_workspace_market_data.py`; modify the already-claimed research/sources/market-data/brain/evolution/parallax/possibility/pantheon/sibyl/apex/ascendancy/learning/chronofold/commissioning/integrity/engine-control/autopilot/paper-pnl/workspace-performance UI modules, plus existing server/API/client/browser tests.

**Interfaces:** Separate module requests explicitly call `IcarusClient.request` or typed reads, including Commissioning's direct POST. Shared file/catalog/provider evidence has visible shared provenance. Portfolio-derived panels require selected adapters or an explicit unavailable state; unsupported controls are disabled with a reason and rejected by the server. Do not present missing capability metadata as a healthy session.

Market diagnostics may read only existing provider buffers under their owner locks, selected by the workspace runner's actual provider symbol. `Yahoo.meta()` may fetch, and Databento `trades()`/`depth_events()` may start subscriptions: do not invoke those methods from a read-only workspace adapter. Never fabricate ticks, complete MBO snapshots or missing micro histories. Keep global provider ownership and existing transports.

Extract/reuse dedicated-view corpus/A200 research receipts, connections navigation/inventory and persisted paper performance in the common surface. Shared catalog/history retain original qualification/receipt checks and explicit owner-request semantics; tests use offline fixtures. Main and all CC pages retain these components rather than removing them for parity.

- [ ] Add failing provider-call traps, distinct selected symbol buffers, missing-runtime and unknown-capability tests, plus module/direct-POST isolation cases.
- [ ] Implement contextual readers/unavailable states and shared labels; migrate every linked data/action consumer, preserving existing main behavior.
- [ ] Exercise all panel/navigation paths in Chromium, verify unsupported actions never mutate main, and retain shared evidence/performance features.

### Task 4: Common renderer switch and five-route browser acceptance

**Files:** Modify `icarus_engine/server.py`, `tests_engine/test_workspace_dashboard_browser.py`, relevant route/browser/Windows workflow selections and recovery evidence.

**Interfaces:** `serve(..., shared_dashboard=True)` selects common CC rendering only after Tasks1–3 pass. `shared_dashboard=False` preserves dedicated renderer rollback and compatible saved state. The server injects each route's immutable id before the same renderer/modules; query/hash/storage cannot change it. Connections remain explicitly shared/global navigation.

- [ ] Write failing desktop/mobile component-parity and request-capture cases at main/CC1–CC4 with different same-symbol prices/settings/history/journals; cover owner/viewer, downloads, jobs, missing runtimes, expiry and full-page navigation.
- [ ] Switch CC rendering behind the explicit rollback parameter and require all five browser cases, relevant existing presentation contracts and focused suites to pass.
- [ ] Run fresh full runtime suite and inspect exact source/CI receipts. Publish engineering evidence without claiming PC repair, accuracy recovery or broker operation.

## Execution record

Continue native work under the owner's existing approval and repeated continue instructions. The central recovery record remains authoritative; plans are implementation detail. Icarus2 owns separate federation paths. Final independent-review capacity remains explicitly limited; do not invent a clear or launch quota replacements. No release merge, deployment, full restart or live activation is included.

Task1 evidence: missing-policy/module/raw-context failures observed; final115client/policy/JS +9HTTP/lifecycle checks green, initial195HTTP/auth/control checks green. Fresh full3736passed,4skipped,111subtests in252.16s. Root reviewed scope classes/route selection. The restored-page client and same-workspace wrong-job/late-decode/null cases were reproduced and repaired before this full run. Native review availability stays explicit.

Task2 preflight: typed HTTP errors currently preserve only their message/status; preserve full partial-flatten receipts before toolbar wiring. Control acknowledgements describe completed events and must not be discarded merely because a newer status revision arrived; current market state still comes from fresh reads. Add the corresponding failing client/action tests before changing those semantics.
