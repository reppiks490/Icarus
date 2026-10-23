# Current ICARUS as-is restart — 23 October 2026

This is the authoritative operator restart guide. It replaces older restart commands, including [the pre-installer-repair guide](archive/2026-10-23/pre-installer-repair-PRIME_AS_IS_RESTART.md). [Earlier notes remain archived](archive/2026-10-23/INDEX.md); use this procedure by itself.

**Install exactly `7aa3900282213c4e690436098702300a0447cb8d`**, branch `prime/as-is-restart-20261022`, [PR #471](https://github.com/reppiks490/Icarus/pull/471). Runtime code remains on that branch; a documentation update on main does not install it. The final verification receipt below must identify this exact revision.

This update repairs Windows setup, expands Main to the canonical 35 paper assets, distinguishes reported errors from historical counts, and adds independent CC1–CC4 paper worker switches. This is an observable as-is paper build. **Full-system readiness remains NO_GO; `execution_authorized=false`.** This cloud session cannot access or restart the owner's PC, and the cause of its reported feed/runtime fault remains unverified.

## 1. Stop and preserve your installation

Privately record any open paper positions first: restoration of every open in-memory position is not certified. In the terminal that owns the current engine, press **Ctrl+C** and wait for normal shutdown. Do not flatten positions merely to restart, kill unrelated Python processes, delete PID files or erase databases.

The previously observed PC uses **C:/Users/tripl/Icarus** for private state and **C:/Users/tripl/Icarus-as-is** for updated source. If the old launcher printed a different state root, use that actual root throughout. After shutdown, make a private backup in Git Bash:

```bash
export ICARUS_STATE='C:/Users/tripl/Icarus'
export ICARUS_HOME="$ICARUS_STATE"
test -d "$ICARUS_STATE" &&
export ICARUS_BACKUP="${ICARUS_STATE}.backup-$(date -u +%Y%m%dT%H%M%SZ)" &&
test ! -e "$ICARUS_BACKUP" &&
cp -a "$ICARUS_STATE" "$ICARUS_BACKUP"
```

Wait for the copy to finish successfully before updating. It may be large and contains private journals, saved configuration, history and credentials; keep it local. Copying stopped state preserves SQLite journals and sidecars together.

## 2. Fetch and verify the exact source before switching

Use the existing source checkout. Record the current `git rev-parse HEAD` privately for rollback and preserve local modifications. Do not force checkout, hard-reset or clean.

Run in **Git Bash on the PC**, after the backup:

```bash
cd "$HOME/Icarus-as-is" &&
git status --short &&
git rev-parse HEAD &&
git fetch origin prime/as-is-restart-20261022 &&
test "$(git rev-parse FETCH_HEAD)" = '7aa3900282213c4e690436098702300a0447cb8d' &&
git switch --detach 7aa3900282213c4e690436098702300a0447cb8d &&
test "$(git rev-parse HEAD)" = '7aa3900282213c4e690436098702300a0447cb8d'
```

Continue only after the block succeeds. If the fetched branch has a different SHA, stop and check the current delivery receipt; do not substitute an unverified head. Git refuses conflicting changes; preserve them instead of forcing a switch.

If this source folder is absent, locate your existing Icarus checkout first. From it, fetch and verify the same revision, then create the separate source checkout only when the destination does not exist:

```bash
git fetch origin prime/as-is-restart-20261022 &&
test "$(git rev-parse FETCH_HEAD)" = '7aa3900282213c4e690436098702300a0447cb8d' &&
test ! -e "$HOME/Icarus-as-is" &&
git worktree add --detach "$HOME/Icarus-as-is" 7aa3900282213c4e690436098702300a0447cb8d
```

Do not create a fresh private state root. Return to `$HOME/Icarus-as-is` for installation.

## 3. Install and launch with the expanded Main assets

```bash
export ICARUS_STATE='C:/Users/tripl/Icarus'
export ICARUS_HOME="$ICARUS_STATE"
export ICARUS_MAIN_ASSETS='NQ,BTC,MNQ,MES,ES,YM,MYM,RTY,M2K,GC,MGC,SI,SIL,PL,PA,MBT,ETH,SOL,CL,NG,HG,6E,6J,6B,6A,ZN,ZB,BTCF,MHG,MCL,MNG,M6E,MJY,M6B,M6A'
bash scripts/start-as-is.sh --setup --root "$ICARUS_STATE" --feed yahoo --assets "$ICARUS_MAIN_ASSETS"
```

This uses all **35 symbols in `dashboard_assets()` for Main only**. Saved CC1–CC4 asset selections, custom Inputs and journals remain independent. CC1, CC2 and CC4 retain the three customized workspaces; CC3 remains the spare. Do not use an old expansion/reset helper to overwrite them.

Windows Python **3.10+** is supported; install 64-bit Python 3.11 or 3.12 if Python is missing. Setup uses the source checkout's separate `.venv`, upgrades pip/setuptools/wheel, then installs the declared extras with `--no-build-isolation`. The launcher scopes `SETUPTOOLS_USE_DISTUTILS=stdlib` to setup commands on Python below 3.12 and uses `local` on 3.12+. This addresses the pip/setuptools distutils collision on the owner's Python 3.10; do not set this variable globally or replace the launcher with the old bare editable-install command.

The launcher prints its source revision, Python and private state root, refuses empty Main assets or an occupied port, and does not kill another process. Preserve an existing custom `ICARUS_TOKEN` locally; never publish its value. Use the browser's Token control if prompted.

**Keep the launcher window open and the PC awake.** Yahoo futures data is delayed paper/research data. A listed asset, a price or an ON worker does not establish provider entitlement or connect a futures/prop-firm account. The 35-symbol catalog is not verified fresh feed coverage. Existing locally configured auxiliary providers remain separate; the Yahoo argument alone does not prove every paid capability is inactive. No order bridge is launched. Existing local history remains preserved; missing history stays missing.

For later starts at the verified source, repeat the exports and launcher command **without `--setup`**. Inspect any old `~/icarus-start.sh` before using it: its source path, six-asset list or feed choice may be stale. The local engine does not require an active ChatGPT subscription; external provider/model services retain their own availability and account requirements.

## 4. Open the views and control each CC independently

Refresh existing tabs once with Ctrl+Shift+R after updating.

| View | URL |
| --- | --- |
| Main | http://127.0.0.1:8791/ |
| CC1 | http://127.0.0.1:8791/dashboards/cc1 |
| CC2 | http://127.0.0.1:8791/dashboards/cc2 |
| CC3 | http://127.0.0.1:8791/dashboards/cc3 |
| CC4 | http://127.0.0.1:8791/dashboards/cc4 |
| Connections | http://127.0.0.1:8791/dashboards/connections |

**Paper workspace on/off** in Main has four independent switches. Each CC page has its own switch. These are authenticated owner actions that start/stop that CC's paper workers; they also stop its selected-page runtime polling while it is off. Main remains available for monitoring and for switching the CC back on.

| State | Meaning |
| --- | --- |
| STARTING | Startup was accepted; worker confirmation is pending. Cancel start requests OFF if preparation is stuck. |
| ON | The selected CC's paper workers are running. Inspect its data and warmup separately. |
| STOPPING | Shutdown was accepted; workers or in-flight I/O have not fully finished. |
| OFF | The selected CC's paper workers have stopped. |
| ERROR | A transition or saved control state failed; inspect the reason. Retry stop finishes failed cleanup before ON is allowed. |

The checked switch reflects confirmed **ON**, not merely requested startup. New installations default all four CCs to enabled; later desired settings persist privately at `ROOT/command_centers/runtime-power.json` and survive a normal restart. Inputs, asset selections and paper journals are retained when switching off or on.

OFF is refused when that CC has open positions, pending entries/closes in either its primary or shadow emulator, or busy work/configuration/activation. Wait for work to finish and review positions normally; the switch never flattens positions or cancels orders to make shutdown succeed. A long in-flight provider call can leave it **STOPPING** until that call returns. Do not interpret STOPPING as OFF or repeatedly force a retry.

The switches isolate CC worker lifecycle and selected polling. The application still shares its parent process and provider transports, so an outage or failure of shared infrastructure can affect more than one workspace. These switches are not a guarantee of complete process/provider fault isolation.

## 5. Verify actual state and diagnose problems

Check the launcher printed `7aa3900282213c4e690436098702300a0447cb8d` (its first 12 characters) and the existing private state root. Check each URL's workspace badge, saved Inputs and selected Performance journal. On Main, inspect the expanded asset list; on every running CC inspect actual prices, warmup and freshness.

Asset cards distinguish a **reported error** from **past errors** counted since launch and show **bar age**. A past-error count alone does not prove a current fault; no reported error alone does not establish fresh prices or a healthy feed. The owner-PC cause must be established from its current status/logs after launch.

A blank view or repeated “Selected runtime observation expired” after **30 seconds**, while that workspace is ON, needs diagnostics. An OFF/STARTING/STOPPING CC deliberately suppresses its ordinary runtime observation polls. Warmup depends on available history/feed and may remain incomplete.

In a second Git Bash window:

```bash
curl --noproxy 127.0.0.1 --max-time 10 -sS -w '\nHealth HTTP %{http_code}\n' http://127.0.0.1:8791/healthz
curl --noproxy 127.0.0.1 --max-time 15 -sS -o /dev/null -H "Authorization: Bearer ${ICARUS_TOKEN:-icarus}" -w 'Status HTTP %{http_code}; response %{time_total}s\n' http://127.0.0.1:8791/status/public
tail -n 80 'C:/Users/tripl/Icarus/logs/engine.log'
```

Set your custom token locally in this second window if applicable. Use the actual state root for logs. The native status route is **`/status/public`**; **`/api/status` is not this engine's route**. HTTP 200 alone is insufficient: inspect nonempty assets, price/bar age, warmup and rendered views. Keep logs private and redact tokens/account details before sharing. A browser connection-aborted message alone does not establish that the process died.

Shared Access refreshes when opened, on Refresh or after an access action. Connections inventory does not prove an account is connected. Native read-only research panels can honestly report zero or unavailable private evidence; unavailable adapters remain visible. UI paper strategy states such as LIVE/ARMED are not broker authorization.

## Verification and limits

Runtime `7aa3900282213c4e690436098702300a0447cb8d`, tree `d6020c33e6a7c7d72946a2faaae52ca8189bae40`, is byte/tree-equivalent to the frozen local tested build. Independent final review is CLEAR.

- Full local suite: **4,083 passed, 89 skipped, 111 subtests passed**, exit 0 in 403.30 seconds, including the 17 new disconnect regressions. Earlier legacy browser fixture failures were reproduced and repaired. Command: `ICARUS_SETUP_TEST_PYTHON=/workspace/scratch/prime-setup-python310/bin/python PYTHONPATH=$PWD /workspace/Icarus/.venv/bin/python -m pytest tests_engine tests/test_provider_corpus_intake.py -q -o addopts='' --durations=3 -rs`. Source files stayed frozen throughout.
- Real Chromium power controls: **16 passed**. Broader UI/Node suite: **71 passed, 1 skipped**; its skipped performance assertions separately passed using system Chromium. Four additional real-browser API/settings/page-lifecycle checks passed. Optional browser imports and three Windows-only cases explain the local full-suite skips; these are not invented passes.
- Hosted checks of the preceding `0560627e7522e85eb97a5f906800e376508a4cd6` found three Windows test-fixture encoding failures and a world-view pointer fixture below/behind navigation. The intermediate `0bc3a110d7e4c8dd26e079501698bdda2a297377` changes only those two test files: explicit UTF-8 decoding, a visible real pointer target, and restored scroll setup. All original world assertions remain; actual WebGL depth, shadow, cinema and world checks passed with no browser errors or writes. These earlier execution failures remain in the delivery receipt. Runtime source was unchanged by that test-only follow-up.
- The final runtime repair also handles expected client resets while reading initial requests, partial headers (including Expect: 100-continue), or idle keepalive requests. It closes only that client connection; unrelated input I/O failures and upstream application errors remain visible. The initial regression had nine failures; independent review exposed three additional header-side-effect failures. All 17 new cases then passed, including a real TCP reset, and the full API file passed 137 checks with four optional browser cases exercised separately.
- Packaging regression passed using actual Python **3.10.22** and **3.12** metadata builds. The original pip/setuptools collision was reproduced before repair. Owner-PC Windows setup still requires the local command's readback.
- Actual Bash launcher and same-root second launch restored three enabled workspaces and retained saved-OFF CC4, preserved configuration bytes, warmed synthetic NQ and exited cleanly. A separate **35-symbol synthetic file-data** launcher rehearsal warmed all 35 Main symbols and exited cleanly. These are synthetic engineering checks, not current exchange data or profitability evidence.
- Strict rehearsal result remains **NOT_FULLY_READY**: containment denied 11 external research/subprocess attempts per NQ launch and 13 for the 35-symbol launch. No paid requests were allowed. This limitation was preserved rather than turned into a successful federation-health claim.
- Exact-head hosted checks were automatically triggered and are tracked on [PR #471](https://github.com/reppiks490/Icarus/pull/471). Their final outcomes belong to the immutable [delivery receipt](https://github.com/reppiks490/icarus-owner-actions/blob/main/coordination/handoffs/prime-installer-expanded-restart-20261023.json); older-head CI results are not evidence for this revision.

Earlier 4,009/177 test counts and eight hosted-run receipts describe the archived build.

The current Engine health record also contains authentication, licensing and workflow blockers; these cloud records do not diagnose the PC's current asset errors. Provider-specific failures must remain visible rather than be relabelled as connected.

The candidate retains status recovery, expected browser-disconnect handling, selected-workspace status, shared owner-gated Access, layout repairs, native selected-private read-only diagnostic readers, empty-Main startup refusal and bounded pinned Brain inventory repair. Existing selected action adapters keep their authorization boundaries.

Cloud/synthetic and hosted checks cannot certify the owner's PC network, feed entitlement, imported history, journals, all open-position reconstruction or sustained uptime. Accuracy recovery, strategy value, all mutation adapters, real broker/prop operation and full-system readiness remain uncertified. New readers do not start training, collectors or autonomous activation; selected-private Learning shared-history admission remains unavailable. Protected holdouts, raw-data rights, point-in-time identities and research promotion gates remain in force.

Windows private vault/archive intake still refuses without safe descriptor-relative no-follow file operations. Ordinary local CSV/file/Yahoo startup uses a separate path; do not bypass the vault safeguard.

## Rollback and stopping point

Stop the owning launcher with Ctrl+C, preserve the current private state again, and switch the source checkout to the privately recorded previous commit without force. Use that version's corresponding launcher and the confirmed state/feed/assets. Do not casually restore an older backup over current state: that can discard newer journal entries. Keep backups for deliberate recovery.

No automatic main code merge, deployment, release, paid feed selection, new spend, scheduler change or PC reboot is part of this handoff. Live execution stays disabled. The recurring federation loop remains cancelled; after this bounded update, Prime waits for the owner's PC command output and continues restart diagnosis in this session. [Delivery handoff](https://github.com/reppiks490/icarus-owner-actions/blob/main/coordination/handoffs/prime-installer-expanded-restart-20261023.json).

