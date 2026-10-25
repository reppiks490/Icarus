# Scoped workspace jobs

Scope: implement only `icarus_engine/workspace_jobs.py`, its regression module,
and this plan. The approved 2026-10-20 amendment to
`docs/superpowers/specs/2026-10-18-four-workspace-delivery.md` is authoritative.
Root owns routing/integration and the full runtime suite. No provider calls,
automation, live trading, commits or changes to other paths are authorized here.

- [x] Write and observe failing offline regressions for scoped job ownership,
  frozen real replay sources, explicit workspace preset resolution, revisioned
  config acceptance/recheck, conflict/idempotency, bounded retention and failed
  worker startup.
- [x] Implement the exact `ScopedWorkspaceJobs(manager)` public methods requested
  by the integrating handler and typed `WorkspaceJobError(status, detail)`.
  Freeze replay configuration/tape synchronously under workspace/portfolio/runner
  locks; resolve explicit presets through the workspace before threading.
- [x] Run focused jobs/configuration/backtest regressions, inspect the diff against
  the amendment, and record fresh red/green evidence and limitations here.

Interfaces: `submit_config(workspace_id, symbol, body)`,
`submit_backtest(workspace_id, symbol, body)`, `get(..., full=True)`,
`export_csv(...)`, `compare(..., tolerance=1)`. Submission receipts contain job,
workspace_id, source config_revision and created. Only whole-workspace config
accepts `*`. Every submission requires a nonnegative integer expected_revision.
Config acceptance and transactional mutation both check it under the selected
workspace's mutation lock.

Ruling: use this approved subtask's three-file plan as the durable execution
record rather than creating skill scratch files outside the claimed paths.
Root explicitly owns full-suite verification and branch publication, so this
worker runs only the focused authorized suites. Cost if wrong: integration must
surface any wider regression before publication.

Preflight: foundation supplies locked update/update_asset transactions and a
workspace resolver excluding parent per-asset files. Existing backtest frozen
shim permits file-free worker replay when `preset` is omitted. Bars are frozen
dataclasses. No backtest source edit is required.

## Execution evidence

- Initial RED: scoped ownership test could not load the not-yet-created module
  (`workspace job service has not been implemented`, one setup error).
- Initial GREEN: all 26 new offline job tests passed. Tests exercise genuine
  `PaperWorkspaceManager`, `WorkspacePortfolio`, `AssetRunner` and frozen `Bar`
  replay; the deferred-thread fixture controls scheduling only.
- Additional RED: a real duplicate config request stalled behind the committing
  worker's global manager lock; a preset with negative commission was accepted
  instead of rejected (two assertion failures). Real concurrent replay across
  CC1/CC2 passed in that same run.
- Fix GREEN: registry-first lookup now reuses only already-accepted identical
  active work, including its revision; new edits still validate under the
  transaction lock. Effective frozen costs validate before acceptance.
  `python -m pytest tests_engine/test_workspace_jobs.py
  tests_engine/test_workspace_config.py tests_engine/test_backtest_validation.py
  -q -o addopts=''` passed 162 tests.
- Broader GREEN before the per-workspace lock follow-up: jobs, workspace config,
  paper workspaces/runtime, backtest validation/window modules passed 228 tests
  in 10.76 seconds. Constructor and `.start()` failures both free the reservation
  without acknowledging a job or changing saved configuration.
- Independent read-only specialist review reproduced the initial 26-test GREEN
  and confirmed the real config-retry defect plus global-lock serialization.
  Author self-review checked ownership before CSV/compare parsing, exact
  defensive snapshots, explicit-null identity, startup rollback, cap eviction,
  revision recheck and no parent job registry access.
- Further RED: a real CC2 configuration could not complete while CC1 held its
  replay transaction (one assertion failure). Root is changing the manager to
  expose `configuration_lock(workspace_id)` and to use it for each workspace
  transaction. This module will use that same lock for acceptance/freezing.

Source limits: all regression bars are deterministic local fixtures, never
provider receipts. Successful output is labeled engineering replay evidence,
paper-only and execution unauthorized. No accuracy, profitability, freshness,
restart readiness or deployment proof follows from these tests. Root owns the
full runtime suite, handler integration and eventual publication.

Root integration follow-up: helper stopped at its usage limit; Icarus1 retained ownership and completed per-workspace locking, preset-cost preflight/transaction validation, and HTTP integration. Focused jobs/config/API/lifecycle/backtest selection passed298 tests in40.97s after cost/query review fixes. HTTP/lifecycle selection passed73 tests in39.45s; the two additional admission I/O cases passed after observed disconnect failures. Final full-suite and review receipts follow in recovery-evidence.json. No completed system restart or broker connection is implied.

Final local full suite: 3650passed,4skipped,111subtests in223.72s, exit0. First full caught one legacy flatten error-field regression, repaired and verified with10focused cases before the fresh full run. Independent reviewer confirmed all reported fixes but its final whole-diff pass was interrupted by usage limit; do not call that a final independent clear. Source/log hashes and hosted boundaries are in recovery-evidence.json. Publication and current-head hosted checks remain separate.
