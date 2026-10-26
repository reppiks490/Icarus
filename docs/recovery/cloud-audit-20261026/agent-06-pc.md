# Task 06 — Windows takeover readiness

**Verdict: preparation possible; candidate restart not ready to hand over.** Read-only source audit; no network, application execution, source edits, or PC observation. Original `/workspace/Icarus` and `/workspace/Icarus-engine` remain untouched.

## Missing concrete handoff

- `/workspace/publish/Icarus` still has staged, unstaged and untracked changes on `codex/icarus-cloud-readiness-20261026`. There is no immutable published candidate SHA covering these bytes. Engine PR260 and owner-actions PR71 do not publish the main application candidate.
- `docs/recovery/PRIME_AS_IS_RESTART.md:12` explicitly leaves candidate validation pending; its commands still fetch **main only** and pin `a21507b8b9bb46ec418a0a9b89fae448fb3eae96`. Running them will not install the cloud fixes. Publish the main candidate, provide exact SHA/PR/check receipts, then update the pinned runbook coherently.
- Missing native Windows results: `test_windows_background.py::test_real_background_child_has_no_console_window`, `test_bridge_background.py::BridgeBackgroundTests::test_real_windows_tunnel_children_have_no_console`, `test_provider_corpus.py::test_windows_regular_file_and_final_reparse_point`. Record any symlink-permission skip explicitly. POSIX launcher tests skip Windows entirely.
- Missing owner-PC inventory/readback: checkout HEAD/status/worktrees, running executable/source/root/port, intended saved asset selection, NQ preparation JSON, stopped-state backup path, apply/verify receipts, sustained warm health and actual rendered PC pages. Cloud screenshots are not that evidence. Keep tokens/private captures local.
- Publication manifest still describes both repositories as unpublished; central START_HERE still says full restart HELD. Reconcile the durable handoff with current publication/check status before telling local Codex to restart.

## Actual Windows boundaries

The supported as-is setup/capture path is **Git Bash + Windows Python**: `bash scripts/start-as-is.sh --setup --help`, then that worktree's `.venv/Scripts/python.exe -m icarus_engine.restart_defaults --prepare`. There is no equivalent complete PowerShell restart workflow. Do not paste the Bash block into PowerShell.

`start-plant.ps1` installs into global selected Python, runs setup and starts NQ/offline. `start-yahoo.ps1` accepts any importable existing installation without verifying source, defaults to sixteen assets, and supplies no explicit private root. Neither performs NQ capture, isolated environment setup, or defaults migration. `start-engine-background.ps1` likewise uses PATH Python and checks HTTP 200 rather than warm/asset identity. These are unsuitable substitutes for this takeover. `scripts/restart-command-centers.ps1` is a separate workspace operation, not the full restart.

`icarus_engine/corpus_intake.py:199` intentionally refuses native Windows without POSIX descriptor-relative no-follow opens. Private corpus intake therefore remains a Linux workflow; this does not mean the separate Windows provider-context reader is unsupported.

## Safe local Codex sequence

First read the local AGENTS/cooperation bus and inventory `C:\Users\tripl\Icarus-as-is` with `git status --short --branch`, `git rev-parse HEAD`, and `git worktree list`. Preserve local edits, ignored private files and running process. Do not reset, clean, stash automatically, pull into, or detach the existing checkout.

After publication, the following PowerShell preparation preserves its working tree. Replace the SHA placeholder from the published handoff; stop on any nonzero Git exit:

```powershell
$Repo = 'C:\Users\tripl\Icarus-as-is'
$Branch = 'codex/icarus-cloud-readiness-20261026'
$Expected = '<published exact 40-character candidate SHA>'
git -C $Repo fetch origin "refs/heads/${Branch}:refs/remotes/origin/${Branch}"
if ($LASTEXITCODE) { throw 'Fetch failed; preserve local state' }
$Actual = git -C $Repo rev-parse "refs/remotes/origin/$Branch"
if ($LASTEXITCODE -or $Actual -ne $Expected) { throw 'Candidate SHA mismatch' }
$Candidate = "C:\Users\tripl\Icarus-cloud-$($Expected.Substring(0,12))"
if (Test-Path -LiteralPath $Candidate) { throw 'Inspect existing candidate; do not overwrite' }
git -C $Repo worktree add --detach $Candidate $Expected
if ($LASTEXITCODE) { throw 'Worktree creation failed' }
```

Use Git Bash **inside this candidate**, prepare its own environment, and capture Main NQ while the current engine stays running. Validate the summary before shutdown. Only after the separately authorized restart step: Ctrl+C the owning launcher, back up `C:\Users\tripl\Icarus`, apply/verify captured defaults, set a unique owner token, and launch the candidate with explicit private root/feed/assets. Adapt every hard-coded health/verifier interpreter path to the actual candidate worktree. Do not launch a second engine or start mobile/broker bridges. Rollback requires stopping the candidate before restoring private state; retain the old checkout/environment and backup.
