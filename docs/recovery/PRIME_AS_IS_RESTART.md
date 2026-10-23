# Current ICARUS as-is restart — 23 October 2026

This is the authoritative operator restart guide. It replaces older restart instructions. Those notes are preserved in [the historical archive](archive/2026-10-23/INDEX.md); do not combine their commands with this procedure. Immutable older commits still contain historical documents.

**Install exactly `402722b4b708fc0ea6e2b2ede62252e75ccdd4a0`**, reviewed in [PR #471](https://github.com/reppiks490/Icarus/pull/471), branch `prime/as-is-restart-20261022`. Tested Git tree: `7df29ad8829d123eb6ad52e4599fe464c8295db3`. Runtime code has not been merged into main. The main documentation update does not install it.

The owner requested a stopping point: finish the original Prime's current recovery work, deliver this updated observable paper application, then standby. This is an as-is paper restart; full-system readiness remains NO_GO and `execution_authorized=false`. This cloud session has not restarted or observed the owner's PC.

## 1. Stop and preserve your installation

In the terminal that owns the current engine, press **Ctrl+C** and wait for normal shutdown. Privately record any open paper positions first: restoration of every open in-memory position is not certified. Do not flatten positions merely to restart, kill unrelated Python processes, delete PID files or erase databases.

The previously observed PC uses **C:/Users/tripl/Icarus** for private state and **C:/Users/tripl/Icarus-as-is** for updated source. These are separate purposes. This launcher is in the Icarus repository; other federation repositories retain their own responsibilities.

After shutdown, in Git Bash, preserve the private state before updating:

```bash
export ICARUS_STATE='C:/Users/tripl/Icarus'
export ICARUS_HOME="$ICARUS_STATE"
test -d "$ICARUS_STATE" &&
export ICARUS_BACKUP="${ICARUS_STATE}.backup-$(date -u +%Y%m%dT%H%M%SZ)" &&
test ! -e "$ICARUS_BACKUP" &&
cp -a "$ICARUS_STATE" "$ICARUS_BACKUP"
```

Wait for the copy to finish successfully. It may be large and contains private journals, history and credentials; keep it local. If the old launcher printed a different state root, use that actual root throughout instead.

## 2. Update and launch the reviewed build

Use the existing source checkout. Preserve any local modifications; Git refuses conflicting changes. Do not force checkout, hard-reset or clean. Record its current `git rev-parse HEAD` privately for rollback.

Run this block in **Git Bash on your PC**, after the backup:

```bash
cd "$HOME/Icarus-as-is" &&
git fetch origin prime/as-is-restart-20261022 &&
git switch --detach 402722b4b708fc0ea6e2b2ede62252e75ccdd4a0 &&
test "$(git rev-parse HEAD)" = '402722b4b708fc0ea6e2b2ede62252e75ccdd4a0' &&
export ICARUS_STATE='C:/Users/tripl/Icarus' &&
export ICARUS_HOME="$ICARUS_STATE" &&
export ICARUS_MAIN_ASSETS='NQ,ES,YM,GC,SI,BTC' &&
bash scripts/start-as-is.sh --setup --root "$ICARUS_STATE" --feed yahoo --assets "$ICARUS_MAIN_ASSETS"
```

This preserves the six main symbols last observed on the owner's PC; saved CC1–CC4 selections remain independent. It does not expand every workspace to a different asset universe. Preserve an existing custom `ICARUS_TOKEN` in your local environment; never publish its value. Use the browser's Token control if prompted.

If the source folder does not exist, stop and locate the actual checkout. Do not make a fresh private state root. From an existing Icarus checkout, `git fetch origin prime/as-is-restart-20261022` followed by `git worktree add --detach "$HOME/Icarus-as-is" 402722b4b708fc0ea6e2b2ede62252e75ccdd4a0` creates the separate source checkout only when that destination is absent.

Setup installs the declared runtime dependencies into the source checkout's separate venv and prints source/Python/state identities. If Python is missing, install 64-bit Python 3.11 or 3.12. The launcher refuses empty main assets and an occupied port; it does not kill another process.

**Leave the launcher window open and the PC awake.** Yahoo futures quotes are delayed paper/research data; this choice does not connect a futures or prop-firm account. No order bridge is launched. Existing local history remains preserved; missing history remains missing.

For later starts at the installed source, use the same exports and launcher command **without `--setup`**. An old `~/icarus-start.sh` may point to an older checkout or asset/feed choice; use this explicit command until you have inspected or updated that private shortcut.

## 3. Observe the restarted system

Open these in the PC browser, then refresh existing tabs once with Ctrl+Shift+R:

| View | URL |
| --- | --- |
| Main | http://127.0.0.1:8791/ |
| CC1 | http://127.0.0.1:8791/dashboards/cc1 |
| CC2 | http://127.0.0.1:8791/dashboards/cc2 |
| CC3 | http://127.0.0.1:8791/dashboards/cc3 |
| CC4 | http://127.0.0.1:8791/dashboards/cc4 |
| Connections | http://127.0.0.1:8791/dashboards/connections |

Check the launcher's source revision is `402722b4b708`, the state root is your existing root, every URL shows the correct workspace badge, saved Inputs remain, Performance reads the selected persisted ledger, and prices/status display their actual freshness. Shared Access refreshes on opening, its Refresh button or an access action; ordinary status polls preserve an in-progress viewer label.

A blank view or repeated “Selected runtime observation expired” after **30 seconds** needs diagnostics; do not wait indefinitely or assume the restart succeeded. Warmup depends on available history/feed and can remain incomplete. In a second Git Bash window:

```bash
curl --noproxy 127.0.0.1 --max-time 10 -sS -w '\nHealth HTTP %{http_code}\n' http://127.0.0.1:8791/healthz
curl --noproxy 127.0.0.1 --max-time 15 -sS -o /dev/null -H "Authorization: Bearer ${ICARUS_TOKEN:-icarus}" -w 'Status HTTP %{http_code}; response %{time_total}s\n' http://127.0.0.1:8791/status/public
tail -n 80 'C:/Users/tripl/Icarus/logs/engine.log'
```

The native status route is **/status/public**, not /api/status. HTTP 200 alone is insufficient: an empty asset list or `warm:false` does not establish a useful running engine. Keep logs private and redact tokens/account details before sharing. Local connection-aborted tracebacks alone do not prove the whole process died; the repaired build handles expected browser disconnects without attempting another error response.

## What is included and verified

- Status refresh admission/recovery, browser disconnect handling, the selected-workspace status path, shared owner-gated Access controls, stable viewer-label editing, readout batching, narrow Connections layout and settings anchoring.
- Native selected-private read-only Research/Brain/Learning/Autopilot/ASCENDANCY, research-engine and Go-live diagnostic readers. Existing Possibility, Chronofold, Commissioning and Engine Control actions keep their established selected authorization boundaries.
- Empty-main-assets startup refusal and bounded pinned Brain inventory repair.
- Independent source review: CLEAR. Final full suite: **4,009 passed, 73 skipped, 111 subtests**. Separate status/API/actual Chromium selection: **177 passed**. The first aggregate's two stale test expectations and their fixes remain recorded in the immutable handoff.
- All **8** hosted workflow runs at the newest head succeeded, including Windows/Linux runtime tests, visual/browser, portfolio, configuration, intelligence and federation contracts: [runtime run 39901834113](https://github.com/reppiks490/Icarus/actions/runs/39901834113), [visual run 39901834144](https://github.com/reppiks490/Icarus/actions/runs/39901834144). The preceding reviewed commit also passed all 10 hosted runs. The newest commit changes only the browser DOM-churn regression: it reacquires current panel geometry before sampling. All runtime blobs are identical; this revision drift was explicitly reviewed and revalidated through the newest hosted checks.
- Actual contained Bash launcher starts and same-root restart served main/all four selected statuses, warmed synthetic NQ history, preserved all four saved configuration byte hashes, and shut down owned Plant/engine processes cleanly. The final rehearsal used the preceding reviewed tree `cdf3bee0e2e8efb8d5ff945595bac3ef4e3785f4`; the newest commit changes only the browser test, with identical runtime blobs. The local full/API results above were run on that preceding tree.

## Remaining limits and rollback

These are cloud/synthetic and hosted checks, **not owner-PC feed/account/history/uptime certification**. The strict contained rehearsal remains NOT_FULLY_READY because existing main background GitHub/public-source network and subprocess attempts were denied (11 per launch, 33 cumulative). No external provider collection was permitted by that rehearsal. Shared-history admission in the new selected-private Learning reader remains explicitly unavailable. New readers do not start training, collectors or autonomous activation. Zero private evidence is shown honestly.

Protected holdouts, raw-data rights, point-in-time identities and research promotion gates remain unchanged. Measured strategy value, accuracy recovery, sustained provider freshness, every mutation adapter, all open-position reconstruction and real broker/prop operation remain uncertified. Windows private vault intake still refuses without safe descriptor-relative no-follow file operations; ordinary CSV/file/Yahoo startup is separate.

To roll back, stop the owning launcher, preserve the current private state again, and switch the source checkout to the privately recorded previous commit without force. Use that version's corresponding launcher with the same confirmed state/feed/assets. Do not overwrite the state with a backup casually: doing so can discard newer journal entries. Backups are retained for deliberate recovery, not an automatic reset.

No automatic main code merge, deployment, release, paid feed selection, new spend, scheduler change or PC reboot is authorized here. Current Prime has reached the stopping point and is **on standby until the owner calls again**. [Durable final handoff](https://github.com/reppiks490/icarus-owner-actions/blob/main/coordination/handoffs/prime-as-is-restart-20261023.json).
