# Four-workspace integration delivery

The owner requested three distinct separately accessible trading dashboards, then clarified that all four existing workspaces must share asset and corpus capabilities with aggregate P&L outside the individual dashboards. Preserve the four existing profiles and their independent journals; cc1, cc2 and cc4 already have distinct authorized configurations. This work connects those existing components instead of changing Pulse or qualifying new strategies.

## Verified starting point

Icarus consumer `7b42eaa528d3137e87f8ae10ea0896944eb4b62b` passed 3,211 tests, three existing skips and 111 subtests. Native Engine run `39115319263` at `a6054cb952c428c7cb2fa1cd9841e04f381666e6` restored all three retained corpora without acquisition. Primary consumed 32 selected datasets (4,633,264 source rows, 192,000 retained rows), with 12 actual warm assets per workspace. Secondary consumed DX/VXM strictly as archive context. Third consumed historical NQ and warmed all four profiles. No raw prices, secrets or simulated performance were exported in receipts. These are consumption proofs, not fresh-feed, strategy-profitability or brokerage-P&L evidence.

## Data and UI flow

Persist the exact safe native metadata receipts, their artifact identities and SHA-256 digests in a bundled evidence document. A bounded evidence reader validates schema, pinned revisions, per-dataset actual positive reads, disabled authority, coverage and truthful warmup fields before projecting dashboard-safe provenance. Invalid evidence remains visibly unavailable. Compute source age from last closed bar and the current clock; historical consumption must never appear as a live feed.

Provide `/dashboards/cc1` through `/dashboards/cc4` as addressable views of the existing workspace manager. Each view displays its own profile, runtime assets, feed limitations and corpus evidence. A common header outside the workspace view shows all-four persisted paper closures and open marks separately. Reuse existing manager accounting and label its simulation basis. Missing runtimes, marks, fees, external balances or broker reconciliation remain explicit. Do not call a simulated total a reconciled brokerage balance. Existing owner-token controls remain protected and scoped to the selected workspace. Link these routes from the current command-center UI.

Expose the same bounded evidence API to all four views. No raw provider payload is served by that endpoint. Preserve current authentication and host checks. Use direct DOM text assignment for untrusted labels and errors. A URL alone is not proof of deployment: separately verify the reachable backend or publish a truthful private hosted receipt interface when deployment capability permits.

## Shared asset selection

Remove the unconditional overwrite of saved workspace asset selections. Validate explicit selections against admitted canonical identities, keep duplicate/unknown symbols out, and apply asset changes through the existing runner lifecycle with rollback on failure. Existing default behavior remains available. Ten requested additional futures families and any supported micros must have exact identities, free research/data routes, visible delay/coverage limits, and separate execution qualification. Do not fabricate a micro series from its full-size contract. A200 must have real adapter, timezone, bar-receipt and corporate-action evidence before Pulse admission; catalog inclusion alone remains insufficient.

## Connection and rule boundary

Add a separate connections tab for broker/platform account records and prop-firm policy profiles. Keep platform, account environment and firm/program separate. Unknown rules block new strategy orders; live arming remains disabled. Credentials stay in an approved secret source and are never returned by status APIs. Do not turn a configured record into CONNECTED without actual account readback. Official FAQ sources, effective dates and unsupported clauses accompany executable rules. No guessed firm limits or generic profile is presented as verified firm compliance.

## Verification and rollback

Use negative controls for swapped dataset identities, missing consumer reads, historical freshness, duplicate workspaces/accounts and invalid numerical accounting. Verify dedicated routes through real HTTP handlers and test workspace-specific state/control isolation. Test saved asset selections across reload and lifecycle failures. Test firm rule boundaries and unknown/stale sources before enabling paper intents. Run applicable suites and independent reviews before publication. Keep each lane in a separate commit/worktree; revert that lane to roll back. Protected holdouts, empirical FR-1 gates, provider budgets and live execution are unchanged.


## Refined owner scope and accounting contract

Latest instruction: research eight no-charge prop integrations and all documented account types; defer TopstepX. Implement zero-cost local inventory for Apex, Lucid, My Funded Futures, Goat Funded Futures, Tradeify, Take Profit Trader, Earn2Trade and Bulenox. The catalog retains46 documented current/legacy program families and official source digests. This is not free evaluation enrollment or free remote API access. Exact agreements and complete FAQ semantics remain unverified, so all firm new intents stay blocked. No external accounts are fabricated or automatically enrolled.

Shared P&L uses `icarus.paper-pnl.v1`: exactly four unique cc1..cc4 ledgers, explicit USD simulation units, finite safe numeric values, fresh journal snapshots and oldest actual open-position mark evidence. Open marks older than90seconds are unavailable, including delayed archival marks. Known persisted realized results remain available when only open valuation is unknown. Cached stale flat views do not prove current flat positions. No FX conversion, audited fees or broker statement reconciliation is inferred. Frontends validate the versioned object, identity, currency, sums and age before showing figures. Eight-second request deadlines, sequence guards and independent expiry clear stale figures while retaining local configuration drafts.

A200 views share200 canonical equities and explicitly bounded, authenticated source requests; they cannot mutate Pulse or paper journals. Ten additional command-center futures families CL/NG/HG/6E/6J/6B/6A/ZN/ZB/BTCF and eight actual micro identities use exact existing archive files when available. Missing micro data is unavailable, never manufactured from full contracts. Offline expansion warmup does not change default trading selections or claim profitability, fresh licensed market-data access or execution authority.


Native expansion run39162615234 succeeded on all three caches at Engineced31fcfcdf75e4ff2f4181315f462aa5d59a76b and consumer19093b23a8b4853a6ee3e697029085986d871146. Primary artifact12148939831, receipt SHA25667c948545419792f86200af4139963943f3184a9f726150892921e71b458b8c2, proves24 warm assets per workspace including all ten added full families plus MCL/MBT. Six requested micro datasets are absent. The separate pinned expansion bundle/reader validates this lineage without replacing original three-corpus evidence. Every dedicated view shows actual coverage and missing micros; historical receipt evidence never grants a fresh feed or profitability claim.

## 2026-10-20 amendment: the same main trading dashboard in every workspace

**Design proposal; architectural implementation is not complete.** This amendment
extends the existing contract instead of creating a second dashboard authority.
The owner now requires CC1–CC4 to match the main trading dashboard, with working
configuration, charts and panels. The current independent workspace configuration
and journals remain authoritative; matching presentation must not replace them
with the main portfolio. A full system restart remains NO-GO under the current
[recovery record](../../recovery/ICARUS_RECOVERY_STATUS.md).

### Reuse choice

Use one `dashboard.html` renderer and its existing styles/components for `/` and
`/dashboards/cc1`–`cc4`. Bootstrap an immutable, server-bound dashboard context
before any UI module runs. Add explicit scoped backend handlers and one client
for API requests, commands, navigation and downloads.

Copying the main HTML into a second workspace template would create drift again.
Starting another `serve()` for each workspace would duplicate research services,
workspace managers and background workers while retaining shared persistence
hazards. Neither is the proposed implementation.

### Context, routing and identity

- The server selects a context from a canonical route, either `main` or exactly
  one of `cc1`–`cc4`. It emits a fixed, safely encoded bootstrap value before
  linked scripts. A workspace URL with missing or invalid bootstrap identity must
  stop with an unavailable view; it must never default to `main`.
- Keep full-page workspace navigation for the first delivery. This avoids mixing
  existing symbol-only chart/trade caches across ledgers. A future single-page
  switch would require cache keys and cancellation scoped by workspace and
  configuration revision.
- A context-aware client constructs allowed trading API/admin URLs. Export,
  solo-asset, backtest CSV and other generated URLs must use it too; intercepting
  `fetch()` alone is insufficient. Authentication stays on same-origin requests
  and follows the existing owner/viewer rules.
- Scoped responses must identify the selected workspace and configuration
  revision. Reject a mismatched response before rendering. Use request deadlines
  and sequence guards; failed, stale or out-of-order responses must not retain
  values presented as current. No scoped request retries against parent routes.
- Backend selection is explicit: look up the requested workspace runtime and
  then its asset. Do not temporarily rebind the shared parent `port`, clone a
  service tree, or fall through to a matching parent symbol when a workspace or
  asset is absent.

### Trading API and control contract

Extend the existing `/api/command-centers/{id}` and
`/admin/command-centers/{id}` namespace. Keep existing clients compatible while
adding the following capabilities with explicit ownership:

| Surface | Required scoped behavior |
| --- | --- |
| Status and overview | Project the selected workspace portfolio/runners, not parent status; preserve truthful unavailable and warmup states. |
| Chart | Use that workspace's runner; support the main chart's bounded page size and offset, source bars, overlays, fills and history metadata. |
| Trades/export | Read only that workspace's journal/runner; distinguish persistent post-cutover paper history from replay history. Downloads stay scoped. |
| Inputs/assets/presets | Show that workspace's effective configuration and admitted assets. The preset library may be shared read-only; applying it is workspace-owned. |
| Pause/resume/flatten | Distinguish one asset from the whole workspace. Reject conflicting selectors; never ignore an asset selector and act on every runner. Preserve partial-flatten receipts. |
| Rewarm/reset/preset/configuration | Use workspace-owned resolution, persistence, flat-position checks and rollback. Main `persist:true` handlers are not reusable workspace writers. |
| Add/remove assets | Use the existing guarded workspace lifecycle and preserve saved selections and sibling state. |
| Config jobs | Include workspace and asset scope in submission, conflict checks and polling. Reject a foreign workspace's job identifier. |
| Backtest/compare/export | Freeze the selected workspace's resolved inputs/chart/cost/source identity. Bind job records, reads, comparisons and downloads to the workspace. Explicit presets must not reload parent overrides. |
| Market/depth diagnostics | Resolve the selected runner and actual shared provider capability. A chart cannot establish missing depth, entitlement or execution qualification. |

Existing whole-workspace endpoints remain whole-workspace operations. Do not
silently interpret their bodies as new asset-specific commands. Validate canonical
symbols, query bounds and malformed/encoded paths before accessing a runner.

### Workspace-owned configuration

Current workspaces apply one chart/input set to every selected asset, while the
main Inputs panel exposes per-asset and `*` edits. Mapping an NQ edit to the
existing workspace-wide update would change unrelated assets. Full input/control
parity therefore requires validated per-asset overrides persisted inside the
workspace's own `command_centers/ccN.json` record.

Version the override schema explicitly. Existing records migrate without losing
values; an older writer must reject an unsupported schema instead of dropping
nested per-asset settings. A client submits the revision it edited, and the
server compares it with the current revision under the workspace mutation lock
before applying any change. A stale revision returns a conflict without changing
state; a client-side read-before-write check alone is insufficient.

The resolution chain preserves existing defaults and saved workspace-wide values,
then applies only that workspace's selected asset overrides. Main
`inputs.<SYMBOL>.json` files remain excluded. The migration from existing records
must retain all current selections, chart settings and input values, with no
implicit retuning or preset replacement. Unknown fields and invalid overrides
must fail before mutation.

Extend the existing atomic workspace update/reconfigure transaction: validate the
candidate, enforce the applicable position guard, build/warm replacements, persist
the workspace record, and publish one configuration revision. On construction,
warmup or write failure, retain the old runners and exact saved bytes. Initially
keep the existing conservative flat-workspace requirement for reconfiguration;
do not introduce a weaker open-position edit rule incidentally.

Inherited `Portfolio.rewarm_asset` is not a safe shortcut: it can resolve parent
asset overrides and write shared `inputs.<SYMBOL>.json`. Workspace rewarm/reset
must have an explicit workspace implementation.

### Shared evidence and runtime-derived subsystem panels

All five routes retain the same navigation and panel components. Corpus, A200,
provider receipts, connection inventory and research catalogs may remain shared
read-only evidence, visibly labeled as shared and with their original provenance.
Their presence must not be presented as a workspace-local operating subsystem.

Research, Possibility, Autopilot, Chronofold, Commissioning, Engine Control and
shadow comparison currently include parent-bound services or runtime reads.
Each call must be classified before reuse:

1. Repository/provider evidence can use the shared reader with a shared scope.
2. Portfolio-derived state needs a contextual read adapter or an explicit
   unavailable state for the selected workspace.
3. State-changing actions need a scoped implementation. Unsupported parent/global
   mutations must be rejected by the backend and disabled with a useful reason
   in workspace mode. Hiding a button is insufficient.

Commissioning's direct POST and shadow-twin's independent status poll must use the
same context boundary. The Command Center panel may navigate to another ledger;
it must not silently mutate another workspace while retaining the current page's
identity. No placeholder state may masquerade as a connected subsystem.

### Acceptance evidence

- Give main and all four workspaces deliberately different same-symbol prices,
  histories, settings and journal rows. Verify status, charts, overlays, trades,
  downloads, inputs, backtests and runtime-derived panels select the right scope.
- Verify two distinct real runner chart pages, offsets, bounds and history/fill
  annotations; a request for older bars must not return the latest page again.
- Remove one runtime while parent and siblings remain healthy. Its page must
  become unavailable without fallback; independently valid closed P&L in another
  ledger remains visible while incomplete combined totals stay unavailable.
- Exercise toolbar, command palette, per-asset controls, Commissioning and Engine
  Control with authorized and viewer tokens. Assert the intended scope and hash
  parent/sibling configuration and journals before/after mutations.
- Cover per-asset versus `*` input updates, existing-record migration,
  reconfiguration conflicts, open-position rejection, failures before and after
  persistence, rollback and reload. Preserve existing strict P&L behavior.
- Reject foreign job IDs, conflicting scope/body selectors and malformed paths.
  Test concurrent jobs in different workspaces and the same scope's conflict rule.
- Delay/fail responses and navigate scopes. Check identity validation, expiry,
  cancellation and stale chart/trade clearing.
- Compare desktop/mobile browser rendering of the same components at all five
  routes, allowing scope labels and deliberately different fixture data to vary.
  Preserve the dedicated views' existing corpus, A200, connections and persistent
  performance surfaces; do not remove them to make the comparison pass.

Engineering fixtures and synthetic offline bars do not establish trading
accuracy or a live connection. This amendment does not authorize broker arming,
provider purchases or the owner's full system restart.

### Delivery and rollback

Implement in dependency order: workspace persistence and scoped backend contracts;
context client and shared renderer; contextual panel/control integration; browser
parity and isolated recovery rehearsal. Keep the already-reproduced chart paging
repair independently reviewable. Do not switch CC routes to the shared renderer
before its API/control dependencies pass isolation tests. Reverting the renderer
switch must leave the existing dedicated routes and saved workspace state usable;
renderer-only rollback can retain the compatible scoped backend. A full backend
rollback must restore the operator-private configuration snapshot compatible with
that older backend, not allow an older writer to rewrite the new override schema.
Configuration migration must preserve that recoverable original.
