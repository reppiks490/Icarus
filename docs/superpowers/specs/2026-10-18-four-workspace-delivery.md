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

Latest instruction: research eight no-charge prop integrations and all documented account types; defer TopstepX. Implement zero-cost local inventory for Apex, Lucid, My Funded Futures, Goat Funded Futures, Tradeify, Take Profit Trader, Earn2Trade and Bulenox. The catalog retains42 documented current/legacy program families and official source digests. This is not free evaluation enrollment or free remote API access. Exact agreements and complete FAQ semantics remain unverified, so all firm new intents stay blocked. No external accounts are fabricated or automatically enrolled.

Shared P&L uses `icarus.paper-pnl.v1`: exactly four unique cc1..cc4 ledgers, explicit USD simulation units, finite safe numeric values, fresh journal snapshots and oldest actual open-position mark evidence. Open marks older than90seconds are unavailable, including delayed archival marks. Known persisted realized results remain available when only open valuation is unknown. Cached stale flat views do not prove current flat positions. No FX conversion, audited fees or broker statement reconciliation is inferred. Frontends validate the versioned object, identity, currency, sums and age before showing figures. Eight-second request deadlines, sequence guards and independent expiry clear stale figures while retaining local configuration drafts.

A200 views share200 canonical equities and explicitly bounded, authenticated source requests; they cannot mutate Pulse or paper journals. Ten additional command-center futures families CL/NG/HG/6E/6J/6B/6A/ZN/ZB/BTCF and eight actual micro identities use exact existing archive files when available. Missing micro data is unavailable, never manufactured from full contracts. Offline expansion warmup does not change default trading selections or claim profitability, fresh licensed market-data access or execution authority.
