# Icarus recovery status

**Current status — 2026-10-25.** The [Prime as-is restart handoff](PRIME_AS_IS_RESTART.md) is the single operator procedure. Paper runtime source `2fd305598cdbaf1937c3c4214a6f5a72ef13e15a` is integrated by merged PR #462 at `8c1dbf0d989894683d9daaefe6f1a4b6bcf4cc25`. Its exact-head hosted checks passed, and merge-triggered engine run [40202103435](https://github.com/reppiks490/Icarus/actions/runs/40202103435) passed on Linux and Windows. This cloud workspace cannot restart or observe the owner's PC; current `/healthz` warmth, sustained uptime, and physical phone pairing remain unverified. Live broker arming, order execution, and live trading are excluded.

**Restart coverage:** Main and selected CC assets use actual captured Main NQ defaults. ETH / COINBASE:ETHUSD and SOL / COINBASE:SOLUSD each use a 30-minute chart, session filtering off, and quantity 25; every other asset inherits the current Main NQ settings. The candidate includes selected-workspace readers, client-disconnect/runtime-expiry handling, dashboard refresh/scroll fixes, narrowly scoped retry for controls rejected before execution by a busy-workspace lock, historical provider context, a guarded Intuition Ω research bridge, optional manual GRU research, and read-only discovery receipts. Exact boundaries and adapter status are in the [adapter matrix](ICARUS_ADAPTER_STATUS.md); the complete backup/capture/apply/launch/verification procedure is in the restart guide.

Older status paragraphs and checkpoints below are historical evidence with their original test counts; they are not alternate restart instructions or current release gates.

Engine PR #216's unique offline archive intake was reconstructed on current Engine main in PR #249 and merged at `2f9a10c516d7294d875a9e808bd669e208ed0e0c`; the stale #216 is closed and its branch retained. Focused tests (107) and the full Engine suite (1,455 tests, 17 subtests) passed locally. Exact-main offline run `40171645677` and exact-head hosted checks passed, including all eight archived profiles. This proves neither live feed access nor provider freshness.

**Current operator commands: [the Prime as-is restart guide](PRIME_AS_IS_RESTART.md).**
It preserves the existing private root and uses explicit feed/assets. This cloud
session cannot start the owner's PC.

**System-wide strategy/data qualification: NO-GO.** This is distinct from the tested paper restart code. No strategy is execution-qualified; external provider authentication, licensing, freshness, and historical coverage have evidence-backed limits in the Engine federation ledger. A successful source build does not establish live feed health, owner-PC runtime, sustained uptime, or physical phone connectivity.

**Latest panel delivery:** [adapter status matrix](ICARUS_ADAPTER_STATUS.md) and
[archived panel checkpoint](archive/restarts/2026-10-25/pre-final/ICARUS_PANEL_RESTARTS.md). The core four controls
are selected-runtime adapters; the other listed subsystem surfaces have selected
read adapters, with their mutation/automation limits explicit in the matrix.
Icarus 2's owner-assisted receipt026 records the earlier `38d5328` paper
application starting on the PC with successful main health probes; this is
separate from installing the new panel source or proving sustained operation.

The 2026-10-20 two-worker direction superseded that period's old five-name selection
board. Its claims and updates remain on the existing
[`icarus-owner-actions` coordination bus](https://github.com/reppiks490/icarus-owner-actions/blob/main/coordination/START_HERE.md),
session `icarus1-20261020-system-recovery`. Icarus 2 registered separately as
`icarus2-20261020-federation-integration` at `2026-10-20T18:13:50.114225Z`.
Its first PLAN explicitly preserves Icarus 1's runtime recovery paths and claims
nonoverlapping federation/integration work. Registration is not completion.

The published core/accounting checkpoint `91fb8c7` passed all six hosted
workflows, including Linux/Windows tests and the unchanged visual contract. Its
full suite passed **3,790 tests, four skipped, 111 subtests**. The common-dashboard
follow-up now serves the same renderer at main and CC1–CC4, with a server-frozen
identity and independent selected data/actions. Its fresh source verification and
hosted receipts are recorded separately below and in the evidence inventory.
That earlier source checkpoint did not include an observed PC restart. Subsequent
owner-assisted paper startup is recorded separately; no live activation occurred.

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
2. **Common dashboard surface — implemented; operating parity remains open.**
   Main and CC1–CC4 serve the same trading renderer and modules. The server fixes
   each page's identity; URL parameters cannot select another runtime. Actual
   desktop/mobile browser cases exercise distinct same-symbol prices, journals,
   inputs and navigation. `serve(..., shared_dashboard=False)` preserves the
   dedicated renderer for rollback. Connections remains a shared inventory.
   The eleven previously unimplemented surfaces now have selected-runtime read
   adapters, and the first four paper controls use isolated workspace state and
   owner/revision/confirmation gates; see the [adapter matrix](ICARUS_ADAPTER_STATUS.md).
   Read adapters do not supply the disabled mutation/automation paths described
   there. Operating parity, release, and actual PC verification remain open.
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
   eight failed on the original route before the repair. This chart-only phase preceded
   the common-renderer integration recorded below.

10. **Workspace-owned configuration — foundation implemented and reviewed.**
    Schema 2 preserves legacy values and an immutable private original-file backup.
    Per-asset inputs, chart settings and shared-library preset selection stay in
    that workspace's record. Revision checks prevent lost concurrent edits;
    rejected transactions restore exact saved bytes, runner/chart/event state and
    cached display values. Parent per-asset writers are explicitly unavailable to
    workspaces. Removing a configured asset requires explicit disposition of its
    override. The owner approved the shared-dashboard design; this foundation
    now has typed core controls and revision-preserving editors in the common
    renderer, verified with a test-only CC preview. The actual CC route switch
    remains gated on panel integration. Existing additions still warm asynchronously after commit; staged warmup rollback for
    newly added assets is not established by these tests.

11. **Scoped trading API, controls and jobs — implemented and locally verified.**
    Status, inputs, charts, trades and CSV use the selected workspace and revision.
    Per-asset controls stay distinct from whole-workspace controls; conflicting
    selectors and stale configuration edits fail before mutation. Configuration
    jobs and frozen backtests own their reads, CSV and comparisons; a foreign or
    parent job cannot be read through another workspace. Transactions in one
    workspace no longer block siblings; a busy snapshot becomes unavailable.
    Invalid preset costs and local file admission failures now fail safely.
    The common renderer now uses these typed core paths; CC production routes
    retain the dedicated renderer until panel dependencies pass.
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

13. **Responsive settings drawer — reproduced and verified in hosted CI.**
    Desktop variables are consumed only by desktop CSS, so delayed viewport
    callbacks cannot leave desktop placement active on mobile. A second failure
    came from a fixed drawer inside a filtered/transformed header with a nonzero
    origin; measured viewport coordinates are now converted to that padding-edge
    origin. Both deterministic browser regressions and the unchanged cinema
    contract pass. Published68acaec0 passed all six hosted workflows. Historical
    fb98/d3 visual failures remain recorded separately.

14. **Explicit module transport and server context guard — verified foundation.**
    Tagged calls and same-origin CC page requests cannot silently read or mutate
    main or another workspace. Authentication stays in place; shared readers are
    explicit and unsupported actions reject without changes. The browser client
    preserves native HTTP responses for modules, validates selected identities,
    and cancels old observations. Cached back-navigation pages retain a usable
    immutable client instead of restoring a permanently closed one. Full suite:
    **3,736 passed, four skipped,111 subtests**; root native review only. The
    preceding responsive0fbfbd9 passed all six hosted workflows, including the
    previously failing visual contract. Core calls now use typed transport;
    the later panel migration and CC renderer switch are recorded below.

15. **Common trading core — integrated into all five routes.**
    Status, chart, trade history, configuration, controls, jobs, comparisons and
    authenticated downloads use the immutable page client. Input drafts retain
    their original configuration revision and remain intact on rejection; fields
    are reserved before HTTP admission and through commit. Whole-workspace edits
    preserve unrelated overrides. Failed/expired observations clear caches while
    drafts survive. Owner/viewer permissions are supplied by the authenticated
    server. Numeric-leading futures roots are accepted. The unsafe duplicate
    Command Centers configuration writer is removed; ledger cards navigate and
    selected controls stay local. Shadow Twin reads the selected runtime.
    Browser tests now use the actual five server routes and distinct fixture sources.
    Explicit discard reloads the latest configuration after conflict; unrelated
    completed jobs preserve unsaved drafts and their original revision.

16. **Persisted-row accounting provenance — Icarus2 finding reproduced and repaired.**
    SQL SUM/COALESCE had converted NULL/text profit to trusted zero and admitted
    future closures. The journal summary and detailed performance reader now use
    one raw-row validator before aggregation, with the manager's shared as-of
    clock. Invalid ledgers return unknown realized P&L and a reason; valid empty
    ledgers remain zero and healthy sibling amounts remain independent. Root
    reproduced3failures/2valid controls before repair. Synthetic test journals
    only; the owner's real journals were not inspected. The inherited100,000-row
    detail-reader bound now also limits trusted summary rows. An extreme-magnitude
    detail-curve floating-sum discrepancy remains a separate lower-priority finding.

17. **Read-only cached market diagnostics — selected route and UI integrated.**
    A tested adapter reads the concrete Databento owner's existing symbol buffers
    under its lock and returns detached bounded rows. It cannot start sessions,
    request history or claim a complete MBO book. Other providers, including
    Yahoo's unlocked metadata cache, return explicit unavailable diagnostics.
    The selected panel route holds the configuration lock while choosing its runner.
    Session metadata without health evidence displays UNOBSERVED. A server-health
    tile is explicitly shared; it does not certify a selected feed session.

18. **Shared evidence and persisted Performance — preserved in the common surface.**
    Main and all four workspaces use the same Performance component with their own
    persisted journals, including removed instruments. Shared corpus receipts show
    the selected consumer, archived expansion retains exact missing micros, and
    the 200-identity research catalog preserves qualification and authority checks.
    Connections stays accessible. Research history requires an explicit owner
    action and is owner-protected by the server; tests use synthetic responses.
    Linked modules use explicit workspace transport. Shared evidence has visible
    provenance; unsupported runtime readers never fall back to main.

## Conditions for a meaningful restart

All rows must have current evidence before a restart is called ready.

| Gate | Required evidence | Current state |
| --- | --- | --- |
| Installed release and startup | Exact repos/refs, interpreter/module origins, data root, one intended launcher, state backups and reversible rollback | PC not observed |
| Four-dashboard parity | Same main trading UI/components, charts, panels and configurable inputs; browser evidence for CC1–CC4; mutations isolated to the chosen ledger | Common renderer and selected readers implemented; mutation/automation limits, release and PC verification remain |
| Accounting | Persistent independent journals, known totals, stale/missing/runtime failure cases, partial closures and restart persistence; simulated vs broker basis explicit | Current source suite passed; owner-PC symptom and restart persistence remain unverified |
| Data and consumers | Per-source credential/auth/rights/ingestion/freshness/consumer evidence; no collected-but-unread required source silently treated complete | Audit open; peer packet refreshed; provider-level external blockers and end-to-end freshness remain explicit |
| Subsystems | Current suites and cross-system checks plus actual runtime links/consumer receipts for each required subsystem | Selected read paths and four paper control families are connected in source; external runtime links and full mutation/automation paths remain unverified or intentionally disabled |
| Accuracy comparison | Reproducible before/after metric on matched real inputs/configuration; regression explained and required behavior verified | Open |
| Futures and firms | Exact contract economics/feeds, supported paper/read-only account connection, effective program policy, fees/risk/reconciliation tests and visible access | Open |
| Recovery rehearsal | Isolated stop/start, saved config and journal recovery, failure handling, panel refresh and rollback observed without altering the owner's running system | Open |
| Hosted and operator verification | Required checks on the proposed release head, fresh disposition of earlier rejected jobs, actual PC/runtime evidence | PR #462 exact-head Linux/Windows, browser, contract, configuration, PyTorch-contract, and federation checks passed on `9a44dc1c6d20088bac1df013e6ec09e`; merge-triggered engine run [40202103435](https://github.com/reppiks490/Icarus/actions/runs/40202103435) passed on Linux and Windows. Owner-PC warm health, sustained uptime, and phone pairing remain unverified. |

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
- Common renderer and contextual panels: **3,833 passed, four skipped,
  111 subtests** in429.28s, exit0, with37source/test/workflow hashes frozen.
  Required browser/JS selection114passed, plus4API/browser cases; the original
  eight dedicated Performance viewport/workspace cases passed separately using
  installed Chromium. Unchanged cinema passed with no page errors or writes.
  The initial full exposed five old test transport assumptions; explicit client
  mocks/wiring assertions were aligned and53affected-module tests plus86subtests
  passed before the fresh full. Actual server routes cover main/CC1–CC4 at desktop
  and mobile sizes, fixed identity and full-page navigation. Source review is root
  native only. New-head hosted results were pending at source publication; use
  PR462 and the canonical coordination summary for later exact-head receipts.
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
accuracy result. Optional local skips are listed per phase. Main and CC1–CC4 now
share the renderer; unavailable panels remain explicit unfinished integrations.

## Current as-is operator delivery

The owner subsequently authorized prioritizing a usable current paper startup
without claiming full readiness. [START_HERE.md](../../START_HERE.md) is the
canonical full PC/Git Bash command page; README, COMMANDS and SETUP point to it.
The launcher requires explicit feed/main assets, verifies its source/interpreter,
uses the chosen existing private root, refuses an occupied port without killing
another process and opens the browser under an owned foreground supervisor.
A stopped-state backup and separate source worktree preserve rollback; a saved
local shortcut works without an active ChatGPT session.

This phase passed **3,852 tests, four skipped, 111 subtests** in423.13s, exit0,
with five changed source/test/workflow paths frozen. Four launcher regressions
passed after failing first. Actual contained shell→plant→engine startup served
all five identities and the four-ledger API, then owned shutdown exited0.
Icarus2's exact reviewed463/464 test blobs are incorporated, with their paths
included in the intended Windows coverage. This is cloud/synthetic evidence,
not a PC restart, cold Windows install, sustained service or open-position
recovery certificate. No broker was armed. See the evidence inventory for source
and log hashes, prior canceled visual result and separate Icarus2 browser proof.

## Next-worker handoff

The historical four-panel batch and its verification/restart limits are tracked in
[the archived panel notes](archive/restarts/2026-10-25/pre-final/ICARUS_PANEL_RESTARTS.md) and the
`workspace_first_four_panels_followup` entry in the evidence inventory. New
services use each selected runtime and its own subsystem state; their analytics
read cached market buffers without opening provider sessions. Source remains on
the recovery branch. That historical batch did not close the other eleven adapters; the current adapter matrix records their read paths and remaining write/automation limits. The final
full runtime suite, including required Chromium cases, passed **3,895 tests, four
skipped, 111 subtests** in462.60s, exit0, with the eight changed code/test files
frozen at `2c1b627`. Earlier248 component,92 routing/context and37 final panel
checks remain separate receipts. Windows selection includes the new module;
new-head hosted results are recorded separately. The contained actual launcher
check then exposed a POSIX TIME_WAIT false occupied-port refusal on immediate
restart. A controlled socket regression failed first; the bounded launcher fix
retains active-listener refusal and leaves Windows checks unchanged. Forty-two
launcher/panel cases pass. Actual shell→plant→engine→owned shutdown→same-root
restart serves all sixteen selected panel endpoints on both starts, preserves
forecasts and the selected evidence digest, and exits0 twice. This synthetic
file-only Linux fixture blocks external network/credential-file access and does
not certify a repeat Windows PC restart.

Icarus 2's events026–031 add owner-assisted startup evidence and the distinct
animation candidate PR466. Its runtime run39720172498 passed, but visual
run39720172573 failed the later DOM-churn pointer assertion at
`tests_engine/browser_depth.cjs:217`. That source has not been integrated into
this panel batch. Preserve its existing patch and Brain claim while diagnosing
the exact failing fixture and sustained observation expiry; do not overwrite or
label the candidate all-green.

Icarus 1 retains runtime recovery/release judgment and this evidence record.
Icarus2's latest focused handoff is recorded in
`icarus-owner-actions:coordination/handoffs/icarus2-prime-return-20261021.md`.
It preserves unpublished renderer work, leaves the accounting repair to this
session, and reports Engine226/Icarus463/owner-actions51 for exact-head review.
Those reports are not root review or release approval. Older broad integration
loops are paused; the permanent Icarus2 identity remains registered. No competing
runtime edits were made for the persisted-row finding.

Do not merge old PR stacks by title or by a dated “done” note. Compare their exact
heads with the recorded runtime baseline, preserve required independent research,
and record whether each change remains required, is already integrated, needs a
rebase or has an external blocker. The open-PR inventory is discovery evidence;
unreviewed entries remain unreviewed.

The bounded next-work list is [Icarus2 remaining-access continuation](ICARUS2_NEXT_12_DAYS.md). Keep the as-is launch separate from full-system NO_GO.

Final presentation follow-up: required hosted workspace browser43cases passed, then the delayed-resize settings drawer failed its viewport bound. A forced containing-header regression reproduced the failure locally. Mobile CSS now releases that containing block;4targeted browser cases and122UI/world/JS cases passed, plus unchanged cinema errors[]/writes[]. The3852full-suite receipt remains the preceding startup phase; exact source/log receipts are separate.

Final Windows coverage follow-up: seven hosted workflows on `debf6e180eb41db120a139f92a694f60f6994916` succeeded, including the required UI/browser workflow and Linux runtime job. Windows job119526608283 exposed nine newly selected archive-intake tests assuming supported admission on a host where the production no-follow file-open guard intentionally refuses. The existing POSIX privacy case already skipped. Ordinary runtime/restart coverage passed; Windows private archive intake is a real remaining limitation, distinct from normal CSV/file/Yahoo startup.

The bounded follow-up preserves production source and every original acceptance assertion. Ten admission cases now declare their required safe-open capability; four rejection cases remain runnable, and a new cross-platform test proves missing capability refuses before any private runtime directory or receipt is created, preserving input bytes. Linux focused intake/restart/launcher coverage passed124cases; missing-capability simulation passed5cases with10explicit skips after reproducing10failures on POSIX. The two new recovery modules now run in an early named Windows CI step; the overall79unique-module selection is unchanged. Exact new-head hosted results belong to the coordination summary, not the preceding receipt. Public command documentation also explains this Windows limitation, the foreground shutdown before saving a shortcut, and that `icarus_agent --help` starts a service rather than displaying help.
