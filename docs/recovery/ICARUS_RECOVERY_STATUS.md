# Icarus recovery status

**Restart decision: NO-GO.** This is the current recovery record for Icarus 1 and
Icarus 2. A full restart has not been performed. Source inspection,
engineering tests, hosted automation and the owner's PC runtime are separate
evidence levels. No source-only result establishes that the PC is repaired.

The owner's current two-worker direction supersedes the old five-name selection
board for this workstream. Claims and updates remain on the existing
[`icarus-owner-actions` coordination bus](https://github.com/reppiks490/icarus-owner-actions/blob/main/coordination/START_HERE.md),
session `icarus1-20261020-system-recovery`. Icarus 2 registered separately as
`icarus2-20261020-federation-integration` at `2026-10-20T18:13:50.114225Z`.
Its first PLAN explicitly preserves Icarus 1's runtime recovery paths and claims
nonoverlapping federation/integration work. Registration is not completion.

## Verified starting point

The [evidence inventory](recovery-evidence.json) records exact inspected revisions,
repository roles, commands, results and unresolved work. The first inventory
contains all 20 repositories returned by the connected GitHub account: 19
nonempty trees and one remote verified empty. Two entries reported as size zero
by GitHub still had a tracked reference file; their refs and trees were checked
instead of treating the size field as proof of emptiness. This is a repository and
entrypoint inventory, not a claim that every line, branch or historical artifact
has been verified. Unrelated projects remain separate.

| Responsibility | Authoritative source inspected |
| --- | --- |
| Trading engine, four paper workspaces, local plant, browser/API | `reppiks490/Icarus` at `10a9e2072cb93b5e09f5396340f9c2ba19dd6dd7` |
| Shared collection, provider contracts, persisted evidence, Sentinel | `reppiks490/Icarus-engine` at `df67307a6923c1ff2d02047c74591d4e2dbe8963` |
| Twelve subsystem implementations and hub contract checks | `reppiks490/divine-providence` at `27ae69c593ede3019957100cd401625bd2424f43` |
| Worker coordination and owner constraints | `reppiks490/icarus-owner-actions`; immutable session/events, compiled views checked separately |

Both Icarus repositories package modules named `icarus_engine` and
`icarus_bridge`. Inspect the installed module paths and interpreter when checking
the PC; installing both distributions in one environment can make import origin
ambiguous. No such installation collision has been observed on the PC yet.

## Confirmed defects and gaps

1. **Accounting API inconsistency — repaired in this branch, deployment unverified.**
   The all-workspace snapshot independently summed legacy values while its strict
   `paper_pnl` contract rejected stale/missing marks. It omitted `total_pnl`, could
   label incomplete valuation complete and could expose partial sums when a
   runtime was missing. Per-profile legacy values also disagreed with the strict
   contract. Both projections now use the same validator; incomplete valuation
   suppresses unverified capital/equity/net. A dedicated endpoint also discarded
   available-ledger realized P&L merely because a different workspace was absent;
   it now preserves the validator's independent row result. Regressions reproduce
   the failures before the repair. Missing evidence stays unavailable.

   **Limit:** both shipped UIs already consume the strict contract. This repair
   does not establish the cause of the owner's displayed P&L symptom.
2. **Dashboard parity — not complete.** `/` serves `dashboard.html`; CC1–CC4
   serve `workspace-dashboard.html`. Their styles, chart surfaces and panels are
   different. Existing tests establish route/isolation behavior, not identical
   presentation or feature parity. Share the main trading surface with explicit
   workspace context, preserve independent ledgers and controls, and verify it
   in a real browser before calling this complete.
3. **Installed restart/configuration parity — unverified.** The Git Bash
   `restart-command-centers.sh` helper explicitly selects file-only/offline mode;
   `start-yahoo.ps1` selects the Yahoo/Coinbase route. `start-plant.sh` is an
   NQ-only offline path. Saved selections can differ from defaults. No script
   should be used as a substitute for deciding the intended feed/configuration.
4. **Accuracy regression — reported, not reproduced.** CC1/CC3 default to 20m;
   CC2/CC4 to 5m. CC2 also overrides targets. The main engine and workspaces load
   separate input settings. These are comparison variables, not an explanation
   for the reported approximately 20% drop. Capture before/after source data,
   instruments, date windows, sessions, chart/fill modes, costs, config/model
   digests and the metric denominator. Replay identical authorized input without
   using protected holdouts or claiming an accuracy gain from synthetic tests.
5. **Futures/prop-firm operation — not complete.** Selectable futures, saved
   archive receipts, connection inventory and authenticated read-only account
   adapters exist. `PaperWorkspaceManager._connections` still explicitly reports
   no futures-broker or prop-firm adapter installed in these workspaces. Inventory
   is not a connected account or verified reconciliation. Exact missing micro
   histories stay unavailable; full-size bars must not be substituted. Current
   policies, account identity, fees and drawdown semantics still need an effective
   account/program integration review.
6. **Data freshness and consumption — partial evidence, not universal readiness.**
   Read the pinned Engine ingestion manifest, provider receipts and consumer
   paths. The inventory preserves all 55 manifest source entries and keeps their
   declarations distinct from observed health and actual consumer reads. Its
   Sentinel report generated `2026-10-20T17:36:54+00:00` records 69 OK,
   six blocked, six degraded, four failing and one unknown entry. Those classes
   have different meanings. A stored history file or successful collector is not
   evidence that every runtime/subsystem reads fresh, entitled data.
7. **Earlier hosted workflow failures — externally identified.** Four runs labeled failing
   by that Sentinel snapshot never started their jobs. GitHub check annotations
   for runs `39408129200`, `39380903441`, `39394829278`, `39418451662` state:
   “The job was not started because recent account payments have failed or your
   spending limit needs to be increased.” This is an account/billing execution
   rejection of those attempts, not a code exception. No billing change, paid rerun or provider
   acquisition was performed. Exact run/check evidence is in the inventory.
   The owner subsequently reported that two repos were temporarily private and
   are now public. Both Icarus repositories were independently confirmed public.
   At `2026-10-20T18:25:37Z`, a newer `cl-lab` run `39471755340`, created at
   `18:05:44Z`, was executing steps. No newer completed run was found yet for the
   other three lanes. A blanket current billing block is therefore **not
   established**; keep the historical failures separate from the new run's
   eventual result. No rerun or provider request was initiated by this check.
8. **Research tooling blocker.** A Firecrawl lookup was rejected with HTTP 402
   for insufficient credits. No research result was returned; no retry or
   purchase was performed. GitHub and direct public primary-source reads remain
   available independently.

9. **Workspace chart pagination — repaired in this branch.** The scoped chart
   endpoint ignored `offset`, so requesting an older page returned the latest
   bars again. It also capped requests at 1,000 bars while the main chart allowed
   5,000. The scoped route now forwards the same bounded page size and offset to
   the selected workspace runner. Twelve offline HTTP cases cover distinct
   pages, overlays/fills, history metadata, bounds and parent/sibling isolation;
   eight failed on the original route before the repair. This does not yet make
   the four dashboard renderers identical.

10. **Workspace-owned configuration — foundation implemented and reviewed.**
    Schema 2 preserves legacy values and an immutable private original-file backup.
    Per-asset inputs, chart settings and shared-library preset selection stay in
    that workspace's record. Revision checks prevent lost concurrent edits;
    rejected transactions restore exact saved bytes, runner/chart/event state and
    cached display values. Parent per-asset writers are explicitly unavailable to
    workspaces. Removing a configured asset requires explicit disposition of its
    override. The owner approved the shared-dashboard design; this foundation
    does not yet expose the new controls through the common renderer. Existing
    additions still warm asynchronously after commit; staged warmup rollback for
    newly added assets is not established by these tests.

11. **Scoped trading API, controls and jobs — implemented and locally verified.**
    Status, inputs, charts, trades and CSV use the selected workspace and revision.
    Per-asset controls stay distinct from whole-workspace controls; conflicting
    selectors and stale configuration edits fail before mutation. Configuration
    jobs and frozen backtests own their reads, CSV and comparisons; a foreign or
    parent job cannot be read through another workspace. Transactions in one
    workspace no longer block siblings; a busy snapshot becomes unavailable.
    Invalid preset costs and local file admission failures now fail safely.
    These APIs are not yet connected to the shared main dashboard renderer.
    Jobs remain bounded process-local records. The final independent whole-diff
    review was interrupted by its usage limit after confirming all three reported
    corrections; root inspected the diff and completed the full runtime suite.

12. **Explicit browser context — client and main bootstrap verified.**
    A frozen server identity initializes before every linked UI module. The
    client explicitly selects reads, controls, revisioned configuration, frozen
    jobs, comparisons, authenticated CSV and full-page navigation. It rejects
    mismatched identities/revisions and obsolete responses; cancellation and
    deadlines cannot fall back to main. A real Chromium startup check passed.
    The four CC renderers and legacy module calls still require migration.
    Per-asset edits now preserve unrelated runner engine/cutover/cache state;
    explicit revisioned rewarm jobs replay unchanged settings in the selected
    asset or whole workspace. The flat-workspace guard and exact rollback stay
    enforced. This repair does not explain the reported accuracy decline.

## Conditions for a meaningful restart

All rows must have current evidence before a restart is called ready.

| Gate | Required evidence | Current state |
| --- | --- | --- |
| Installed release and startup | Exact repos/refs, interpreter/module origins, data root, one intended launcher, state backups and reversible rollback | PC not observed |
| Four-dashboard parity | Same main trading UI/components, charts, panels and configurable inputs; browser evidence for CC1–CC4; mutations isolated to the chosen ledger | Open |
| Accounting | Persistent independent journals, known totals, stale/missing/runtime failure cases, partial closures and restart persistence; simulated vs broker basis explicit | Source repair under verification; PC symptom open |
| Data and consumers | Per-source credential/auth/rights/ingestion/freshness/consumer evidence; no collected-but-unread required source silently treated complete | Audit open; explicit external blockers retained |
| Subsystems | Current suites and cross-system checks plus actual runtime links/consumer receipts for each required subsystem | Local checks recorded separately; operating links unverified |
| Accuracy comparison | Reproducible before/after metric on matched real inputs/configuration; regression explained and required behavior verified | Open |
| Futures and firms | Exact contract economics/feeds, supported paper/read-only account connection, effective program policy, fees/risk/reconciliation tests and visible access | Open |
| Recovery rehearsal | Isolated stop/start, saved config and journal recovery, failure handling, panel refresh and rollback observed without altering the owner's running system | Open |
| Hosted and operator verification | Required checks on the proposed release head, fresh disposition of earlier rejected jobs, actual PC/runtime evidence | Current draft checks/new Engine lab observed separately; PC not connected |

Local suite success does not remove these gates. Live broker arming remains
disabled. Resetting or flattening positions is not a panel refresh.

## Verification completed in this cloud session

- Initial accounting-repair runtime suite: **3,463 passed, four skipped, 111 subtests passed**;
  process exit 0. The five-module accounting/API regression selection passed
  **133 tests**, process exit 0. Failing pre-repair regressions were observed
  before each accounting change. No strategy parameters were retuned.
- Chart-paging follow-up: **3,475 passed, four skipped, 111 subtests passed** in
  the full runtime suite, exit 0. Its focused selection passed **52 tests**;
  independent review reran the **12** new HTTP cases with no material findings.
  The initial accounting source hashes/receipts remain separate from this
  follow-up's source hashes and full-suite receipt. The 12 new chart cases are
  included in the Windows CI selection; YAML parsing and all 67 selected module
  paths were checked locally. A selection check does not establish a Windows pass.
- Approved workspace-configuration foundation: **3,533 passed, four skipped,
  111 subtests passed** in the final full runtime suite, exit 0. Its new module
  passes **58 tests** and an independent final review found no material issues.
  Review findings were reproduced before correction: cached rejected settings,
  incomplete chart/event rollback, unselected overrides, publication consistency
  and null-preset identity. The existing Windows job now selects this module;
  YAML and all **68** selected paths validate locally. Current source hashes and
  this receipt are separate from the initial accounting/chart receipts.
- Scoped API/control/job follow-up: **3,650 passed, four skipped, 111 subtests
  passed**, exit0, in223.72s. This includes real offline HTTP job ownership,
  frozen replay sources, CSV metadata, configuration/control scope, costs and
  per-workspace concurrency. The first full run caught one legacy flatten error
  field regression; the field was restored before the passing fresh full run.
  Windows selection now includes70 existing modules. Published6ac Linux passed,
  but Windows job118944172965 failed a fixture startup-reset race; its mechanism
  was reproduced and the genuine offline warmup fixture corrected. Current-head
  hosted Windows results remain pending. Independent review confirmed all three
  reported fixes; its final whole-diff check stopped at a usage limit.
- Context client and main bootstrap: **3,671 passed, four skipped, 111 subtests**
  in228.09s; focused191passed, real Chromium startup1passed. Root inspected the
  client; no independent final approval is claimed. Backend checkpointce6a15f
  passed all four hosted workflows, including Linux/Windows tests39595854165.
  Current client-head hosted execution remains a separate pending result.
- Selected replay/explicit rewarm follow-up: **3,699 passed, four skipped,
  111 subtests** in231.52s, exit0; focused350passed. Unrelated sibling replay
  was reproduced before the scope repair. Settings/replay share one exact-file
  rollback transaction; revision/job/auth/ownership and no-provider boundaries
  are covered. Root reviewed the diff; no fresh independent clear is claimed.
  Previous client-bootstrap e9a33b7 passed all six hosted workflows, including
  Linux/Windows tests39598192902. Current replay-head hosted checks are separate.
- Divine Providence: hub suite exit 0 (165 collected cases); all **12 subsystem
  suites** passed, totaling **2,179 passed test cases**. All 12 compile checks,
  five ASCENSION adversarial scripts and ten hub connection fixtures passed.
- Independent sibling repositories passed their own checks: DAEDALUS **59**,
  AION **24**, CSV Evidence Lab **17**, Causal Router **50** plus **42 subtests**.
- Repository source revisions, source/test file hashes, dependency versions,
  commands, log digests and verification limits are in the evidence inventory.
  The initial cloud attempts without the declared MCP/ML dependencies are not
  counted as application defects; the final runtime checks include those extras.

These Linux/Python 3.12 checks do not certify Windows, required hosted CI, the
owner's saved configuration, all licensed history, live consumers or a recovered
accuracy result. Four skipped runtime tests remain unverified here. The main UI
and CC1–CC4 have not yet been made identical.

## Next-worker handoff

Icarus 1 retains runtime recovery/release judgment and this evidence record.
Icarus 2 has registered its separate federation/integration session and should
consume the pinned recovery evidence through the existing coordination entrypoint.
A useful split
is Icarus 1 on the shared dashboard/startup/accounting path and Icarus 2 on
data-to-subsystem consumption, futures/accounts and matched accuracy evidence,
with independent cross-review of each other's changes. The detailed assignment
beyond Icarus 2's published claim remains a proposed split, not a completion claim.

Do not merge old PR stacks by title or by a dated “done” note. Compare their exact
heads with the recorded runtime baseline, preserve required independent research,
and record whether each change remains required, is already integrated, needs a
rebase or has an external blocker. The open-PR inventory is discovery evidence;
unreviewed entries remain unreviewed.
