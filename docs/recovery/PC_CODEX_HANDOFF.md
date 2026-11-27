# Local Codex takeover — 26 October 2026

Open Codex on the Windows PC at `C:\Users\tripl\Icarus-as-is`. Give it this file
and `cloud-audit-20261026/README.md` / `ROOT_TRIAGE.md`. Codex should perform the commands directly;
the owner does not need to manage the task inventory manually.

This is a preparation handoff. It does not certify all historical branches,
adapters, corpora, live providers, or Windows runtime behavior as complete.
Preserve the running desktop engine, its settings, journals and local changes.
Live broker arming remains disabled.

## Source candidates

- Application branch: `codex/icarus-cloud-readiness-20261026` in `reppiks490/Icarus`.
- Standalone Engine: `codex/icarus-engine-cloud-readiness-20261026`, PR #260.
- Optional Divine engine-client security fix: `codex/icarus-loopback-client-20261026`, Divine Providence PR #61.
- Cooperation evidence: `codex/icarus-cloud-coordination-20261026`, owner-actions PR #71.

Check the actual PR head and hosted checks before using a candidate. These are
review branches, not instructions to merge or restart automatically. Do not use
the old release pin in `PRIME_AS_IS_RESTART.md` as though it includes this work.
That guide remains the operational capture/backup/migration reference.

## Preserve the existing checkout and prepare an isolated candidate

Read local `AGENTS.md` and the canonical owner-actions bus first. Inventory the
existing checkout, worktrees, running engine executable/source/data root, listener
ports, saved asset selection, and current Main NQ settings. Keep private captures
and tokens on the PC. Do not reset, clean, automatically stash, or pull into the
working checkout.

The following PowerShell preparation leaves that checkout's files and running
process intact. Record the resulting SHA and verify it against the PR head and
its test evidence before proceeding.

```powershell
$Repo = 'C:\Users\tripl\Icarus-as-is'
$Branch = 'codex/icarus-cloud-readiness-20261026'
git -C $Repo status --short --branch
if ($LASTEXITCODE) { throw 'Cannot inspect checkout' }
git -C $Repo worktree list
if ($LASTEXITCODE) { throw 'Cannot inspect worktrees' }
git -C $Repo fetch origin "refs/heads/${Branch}:refs/remotes/origin/${Branch}"
if ($LASTEXITCODE) { throw 'Candidate fetch failed' }
$CandidateSha = git -C $Repo rev-parse --verify "refs/remotes/origin/${Branch}^{commit}"
if ($LASTEXITCODE -or $CandidateSha -notmatch '^[0-9a-f]{40}$') { throw 'Invalid candidate SHA' }
$Candidate = "C:\Users\tripl\Icarus-cloud-$($CandidateSha.Substring(0,12))"
if (Test-Path -LiteralPath $Candidate) { throw 'Inspect existing candidate before reusing it' }
git -C $Repo worktree add --detach $Candidate $CandidateSha
if ($LASTEXITCODE) { throw 'Candidate worktree creation failed' }
```

In Git Bash **inside the new candidate**, prepare its isolated Windows Python
environment using `bash scripts/start-as-is.sh --setup --help`. Use this
candidate's `.venv/Scripts/python.exe`; do not substitute a global installation
or the convenience `start-plant.ps1`/`start-yahoo.ps1` launchers for the complete
capture, backup, migration and verification procedure.

## Native Windows verification and restart gate

Run these contracts with the candidate interpreter and required test dependencies:

```powershell
$Py = Join-Path $Candidate '.venv\Scripts\python.exe'
& $Py -m pytest -q `
  tests_engine/test_windows_background.py::test_real_background_child_has_no_console_window `
  tests_engine/test_bridge_background.py::BridgeBackgroundTests::test_real_windows_tunnel_children_have_no_console `
  tests_engine/test_provider_corpus.py::test_windows_regular_file_and_final_reparse_point
if ($LASTEXITCODE) { throw 'Native Windows verification failed' }
```

Record passes and any explicit platform/privilege skip; a skipped contract is not
a pass. Native private `corpus_intake` intentionally requires POSIX descriptor
operations and is a separate Linux intake workflow.

Before stopping the existing engine, use the candidate restart utility's prepare
mode to capture actual current Main NQ configuration from it. Follow the capture
token procedure in the operational guide without printing the token. Inspect the
capture summary, prove the running source/private root and record the stopped-state
backup location. Preserve asset selections, journals, native economics and CC power.
Retain the ETHUSD/SOLUSD exceptions documented in the operational guide.

Only after all these gates and the owner's requested restart approval: stop the
owning launcher, back up the private root, apply and verify the captured defaults,
set a unique owner token and launch the verified candidate with explicit private
root/feed/assets. Verify sustained warm health and interact with every actual
PC panel. Keep phone pairing and any broker bridge as separate authorized steps.
Rollback must stop the candidate before restoring private state; retain the old
checkout, environment, and backup.

## Resume the broader work

Read `cloud-audit-20261026/tasks.json` and the 31 attached evidence reports.
Reproduce candidate findings before editing; some are static review leads, not
confirmed regressions. Complete the remaining 19 agent tasks directly if agent
quota remains unavailable. Prioritize temporal data integrity, depth event/reset
semantics, source-qualified consumers, historical branch recovery and automation
receipts. Never classify a link catalog as a downloaded corpus, historical data
as live data, or a provider client as a market-data entitlement.
