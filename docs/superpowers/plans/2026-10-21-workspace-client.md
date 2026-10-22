# Workspace Context Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Provide an explicit browser client bound to one immutable main/CC1–CC4 identity before migrating the shared renderer.

**Architecture:** A small browser factory consumes server bootstrap and an injected fetch transport. Explicit operations select canonical scoped routes, authenticate requests, validate workspace/revision/job identity, and bound response lifetime. It owns no runtime, provider or mutable page-selection state. This delivery ends before a CC renderer switch; renderer/module integration follows with the same approved specification.

**Tech Stack:** Browser JavaScript, Node's browser-compatible fetch primitives, pytest, existing Python HTTP server.

**Spec:** `docs/superpowers/specs/2026-10-18-four-workspace-delivery.md`, owner-approved amendment; backend dependencies are the workspace configuration/API/jobs plans.

## Global Constraints

- “No scoped request retries against parent routes.”
- “Backend selection is explicit: look up the requested workspace runtime and then its asset.”
- “A stale revision returns a conflict without changing state.”
- “Downloads stay scoped.”
- “Shared market data, isolated controls.”
- “Live broker arming is disabled.”
- Preserve the existing dedicated renderer and saved records until common-renderer dependencies pass.

## Review Focus

- Missing/invalid bootstrap must throw; no inferred main identity.
- Five deliberately different same-symbol sources must remain distinct, including historical job exports after configuration advances.
- A slower earlier response, wrong workspace/revision, timeout or cancellation must never supply a valid observation.
- An input draft keeps its original expected revision; a status poll must not substitute a newer revision at submission.
- Downloads require bearer authentication and verified CSV identity headers; navigation must preserve workspace and admitted symbol syntax.

---

### Task 1: Explicit client and transport boundary

**Files:** Create `icarus_engine/workspace-client.js`, `tests_engine/test_workspace_client.py`; modify `.github/workflows/test.yml`.

**Interfaces:** `IcarusWorkspaceClient.create(bootstrap, options)` returns a frozen client. `bootstrap.id` is exactly `main`, `cc1`, `cc2`, `cc3` or `cc4`; capability metadata is defensively copied and frozen. Options supply `fetch`, same-origin `origin`, `token` getter and bounded `timeoutMs` (default 10000). Never read a scope from mutable URL/hash/localStorage.

Produce `read(resource, options={})`, `configure(asset, changes, expectedRevision)`, `backtest(asset, params, expectedRevision)`, `control(action, asset=null)`, `job(id, options={})`, `compare(id, csv, tolerance=1)`, `csv({asset,job})`, `shared(path)`, `href(asset=null)`, and `close()`. Reads cover status/assets/inputs/chart/trades/performance/configuration. Main uses its established routes; workspace reads use only their canonical `/api/command-centers/{id}` routes. Configuration reads select the root snapshot's `profile`. Trades normalize the scoped envelope to the renderer's row array after validation.

JSON calls throw a typed `WorkspaceClientError` for HTTP errors, unavailable operations, malformed identity, stale responses, deadlines and cancellation. Workspace revision must be a nonnegative integer; ordinary observations cannot regress behind an observed revision. Jobs retain the accepted source revision and can be read/exported after current configuration advances. Each channel has a request sequence; callers may name independent consumer channels. No failed scoped call retries another route.

`configure`/`backtest` require the explicit revision supplied by the editor/caller. Reject conflicting selector fields before transport. Controls distinguish canonical asset versus whole-workspace routes. Unsupported methods throw before transport. The client does not reinterpret unchanged configuration as rewarm, or guess whole-workspace reset/preset semantics; those remain integration work.

`csv` returns `{blob, filename}`. Verify workspace/revision headers before consuming the body; historical jobs use their accepted revision. `href` returns `/` or `/dashboards/{id}` plus an optional canonical asset query. `shared` accepts an explicit read-only evidence/catalog allowlist and returns its payload; other parent-bound services remain unavailable.

- [x] Add Node-driven behavior tests with injected transport for immutable bootstrap, all five route selections, selected trade normalization and missing-runtime refusal. Assert one failed request produces exactly one scoped transport call.
- [x] Add wrong/negative/fractional revisions, wrong workspace, delayed response ordering, timeout, cancellation/close and no status-to-draft revision substitution tests.
- [x] Add explicit asset/whole controls, foreign job identity, accepted-source revision retention, CSV authentication/header validation and scoped href tests.
- [x] Run `python -m pytest tests_engine/test_workspace_client.py -q -o addopts=''`; observe missing factory/behavior failures.
- [x] Implement the factory and narrow operations. Keep legacy renderer calls unchanged in this task.
- [x] Run client tests and existing dashboard JavaScript checks; add Windows selection and commit the independently testable client.

### Task 2: Bootstrap and main-page initialization

**Files:** Modify `icarus_engine/server.py`, `icarus_engine/dashboard.html`, `tests_engine/test_workspace_client.py`, `tests_engine/test_workspace_api.py`.

**Interfaces:** The server injects immutable `window.IcarusWorkspace` before `/workspace-client.js` and every linked UI module. The main route receives `{id:'main', capabilities:...}`. The factory is instantiated once as `window.IcarusClient` with the original native fetch transport and existing token getter. Bootstrap contains no token or operator-private configuration. Serve the static client route. CC routes retain their dedicated renderer until the following renderer-integration plan is complete.

- [x] Write failing real HTTP bootstrap-order, identity, no-token and static-client route cases, plus a Node/browser-compatible initialization check.
- [x] Run the new cases, implement server injection and early initialization, then require green with dashboard/auth/route checks.
- [x] Verify current UI behavior remains unchanged while the explicit client is available. Record fresh source hashes and reviewed branch receipts.

## Following integration boundary

The approved specification still requires all runtime and separate-module callers to use the client, draft-revision capture, explicit `*` settings semantics, scoped rewarm, safe asset lifecycle, parent/global mutation refusal, contextual unavailable panels, shared-evidence labels, stale chart/trade clearing, persistent-performance/corpus/A200/connections preservation and desktop/mobile browser parity. This plan does not mark any of those complete or authorize switching CC HTML early.

## Execution record

Native execution continues under the owner's approved design and repeated explicit continue instruction; no new routine approval is pending. The earlier execution ledger already records that preference. Review helpers stopped at their reported usage limits; do not replace that missing final review with an invented approval. Keep Icarus2's separate federation cycle and all stopped automation boundaries intact.

Task1 evidence: initial missing-client RED1failure; initial13Node behavior cases green. Self-review reproduced2CSV/native-preset defects and2admission-receipt revision defects, then fixed them. Current client17cases plus existing dashboard JS checks passed86tests in2.23s; direct node --check also passed after adding the parse selection. No renderer switch or final independent reviewer approval is implied.

Task2 evidence:2missing-bootstrap/static-route failures observed before implementation; client/API/dashboard/command-center selection191passed in65.08s. Real Chromium startup1passed (installed /usr/bin/chromium; default Playwright browser cache absent), confirming frozen main context, authenticated main source900 and no page errors. Fresh full suite3671passed,4skipped,111subtests in228.09s, exit0. Dedicated CC pages remain until the following renderer migration. Root self-review only; independent reviewer remains unavailable at its prior usage limit.
