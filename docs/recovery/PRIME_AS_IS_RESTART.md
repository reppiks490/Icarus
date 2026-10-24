# Current ICARUS as-is restart — 24 October 2026

**Current source: `c8bd8d49d9fc759067c75ee76157b812ce287775`**, tree `98533b4e053d6cc13447c4decd62f5b327385f3c`, branch `prime/as-is-restart-20261022`, [PR #471](https://github.com/reppiks490/Icarus/pull/471). Runtime code remains on that branch. Updating documentation on main does not install it.

This guide replaces the [previous guide, archived with its original bytes](archive/2026-10-24/pre-main-flow-fix-PRIME_AS_IS_RESTART.md). [Earlier instructions remain archived](archive/2026-10-23/INDEX.md); use the current procedure by itself.

The latest update fixes a continuous dashboard decoration render loop, retains asset/chart nodes during status updates and prevents overlapping chart batches. Main uses a bounded four-worker chart pool; CC readers stay serial for their exclusive configuration lock. Actual request deadlines and observation expiry remain unchanged. Normal status recovery after an actual request deadline is tested; unavailable data is not displayed as fresh.

The build retains Windows setup repair, all 35 canonical Main assets, independent CC1–CC4 worker switches, selected-private readers, saved Inputs and paper journals. It remains an as-is paper build with `execution_authorized=false`. Owner-PC performance and sustained runtime remain to be verified after applying the update.

## Already running the previous verified build: update the UI without stopping Python

Use this route only when the existing owning launcher's output identifies startup revision `7aa390028221` and Source `C:/Users/tripl/Icarus-as-is`, and that checkout is still exactly clean at the full base revision in the command. Git HEAD alone cannot identify the active Python process. If that precondition is unknown, or the engine is stopped, use the full restart below.

Close the ICARUS browser tabs, keep the owning launcher open, and run this in a **second Git Bash window**. No other terminal should edit the source during the update. The guards verify the exact base, fetched source/tree, clean source and an allowlist of the two served UI files plus their tests. Any unexpected change stops the block.

```bash
(
set +x
set -euo pipefail
trap 'printf "%s\n" "Update stopped. Do not force Git or alter private state; follow the failure note below." >&2' ERR
NEW_COMMIT='c8bd8d49d9fc759067c75ee76157b812ce287775'; NEW_TREE='98533b4e053d6cc13447c4decd62f5b327385f3c'
BASE='7aa3900282213c4e690436098702300a0447cb8d'
[[ "$NEW_COMMIT" =~ ^[0-9a-f]{40}$ && "$NEW_TREE" =~ ^[0-9a-f]{40}$ ]]
cd /c/Users/tripl/Icarus-as-is
[[ -z "$(git rev-parse --show-prefix)" && "$(git rev-parse HEAD)" == "$BASE" && "$(git rev-parse 'HEAD^{tree}')" == 'd6020c33e6a7c7d72946a2faaae52ca8189bae40' ]]
dirty=$(git status --porcelain=v1 --untracked-files=all)
[[ -z "$dirty" ]]
git fetch --quiet origin prime/as-is-restart-20261022 >/dev/null 2>&1
[[ "$(git rev-parse 'FETCH_HEAD^{commit}')" == "$NEW_COMMIT" && "$(git rev-parse "${NEW_COMMIT}^{tree}")" == "$NEW_TREE" ]]
git diff --quiet "$BASE" "$NEW_COMMIT" -- . \
  ':(exclude)icarus_engine/dashboard.html' \
  ':(exclude)icarus_engine/world-immersion.js' \
  ':(exclude)tests_engine/test_workspace_dashboard_browser.py' \
  ':(exclude)tests_engine/test_world_immersion.py'
for ui in icarus_engine/dashboard.html icarus_engine/world-immersion.js; do [[ "$(git ls-tree "$NEW_COMMIT" -- "$ui")" == 100644\ blob\ * ]]; done
dirty=$(git status --porcelain=v1 --untracked-files=all)
[[ -z "$dirty" ]]
git switch --quiet --no-overwrite-ignore --detach "$NEW_COMMIT" >/dev/null 2>&1
[[ "$(git rev-parse HEAD)" == "$NEW_COMMIT" && "$(git rev-parse 'HEAD^{tree}')" == "$NEW_TREE" ]]
printf 'UI source verified: %s\nTree: %s\nNo Python stop/start requested.\n' "$NEW_COMMIT" "$NEW_TREE"
)
```

Then verify that the running server serves the updated script:

```bash
(
set +x
set -euo pipefail
cd /c/Users/tripl/Icarus-as-is
expected=$(git hash-object --no-filters icarus_engine/world-immersion.js)
served=$(curl --disable --noproxy 127.0.0.1 --max-time 15 --fail --silent --show-error http://127.0.0.1:8791/world-immersion.js | git hash-object --stdin)
[[ "$served" == "$expected" ]]
curl --disable --noproxy 127.0.0.1 --max-time 10 --fail --silent --show-error --output /dev/null http://127.0.0.1:8791/healthz
printf '%s\n' 'Served script matches this checkout; health endpoint responds.'
)
```

The hash compares raw served and working-tree bytes, including Windows line endings. The responding health route alone does not prove fresh market data. Reopen [Main](http://127.0.0.1:8791/) and the required CC views. Use **Ctrl+Shift+R** for an existing tab.

This is a UI update: the Python process remains the one launched at `7aa3900`, and its served UI source is `c8bd8d49d9fc759067c75ee76157b812ce287775`. It does not request setup, worker shutdown, state copying or a process restart. If a guard fails, preserve local changes; do not force checkout, reset, clean or delete state. The full procedure below handles an actual restart. A failure after switching may leave Git at the new revision; inspect `git rev-parse HEAD` before repeating a base-only command.

## Full controlled restart or next normal start

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
test -z "$(git status --porcelain=v1 --untracked-files=all)" &&
git rev-parse HEAD &&
git fetch --quiet origin prime/as-is-restart-20261022 &&
test "$(git rev-parse FETCH_HEAD)" = 'c8bd8d49d9fc759067c75ee76157b812ce287775' &&
git switch --no-overwrite-ignore --detach c8bd8d49d9fc759067c75ee76157b812ce287775 &&
test "$(git rev-parse HEAD)" = 'c8bd8d49d9fc759067c75ee76157b812ce287775'
```

Continue only after the block succeeds. If the fetched branch has a different SHA, stop and check the current delivery receipt; do not substitute an unverified head. Git refuses conflicting changes; preserve them instead of forcing a switch.

If this source folder is absent, locate your existing Icarus checkout first. From it, fetch and verify the same revision, then create the separate source checkout only when the destination does not exist:

```bash
git fetch origin prime/as-is-restart-20261022 &&
test "$(git rev-parse FETCH_HEAD)" = 'c8bd8d49d9fc759067c75ee76157b812ce287775' &&
test ! -e "$HOME/Icarus-as-is" &&
git worktree add --detach "$HOME/Icarus-as-is" c8bd8d49d9fc759067c75ee76157b812ce287775
```

Do not create a fresh private state root. Return to `$HOME/Icarus-as-is` for installation.

## 3. Install and launch with the expanded Main assets

```bash
export ICARUS_STATE='C:/Users/tripl/Icarus'
export ICARUS_HOME="$ICARUS_STATE"
export ICARUS_MAIN_ASSETS='NQ,BTC,MNQ,MES,ES,YM,MYM,RTY,M2K,GC,MGC,SI,SIL,PL,PA,MBT,ETH,SOL,CL,NG,HG,6E,6J,6B,6A,ZN,ZB,BTCF,MHG,MCL,MNG,M6E,MJY,M6B,M6A'
bash scripts/start-as-is.sh --root "$ICARUS_STATE" --feed yahoo --assets "$ICARUS_MAIN_ASSETS"
```

This uses all **35 symbols in `dashboard_assets()` for Main only**. Saved CC1–CC4 asset selections, custom Inputs and journals remain independent. CC1, CC2 and CC4 retain the three customized workspaces; CC3 remains the spare. Do not use an old expansion/reset helper to overwrite them.

A working installation already prepared at the previous verified `7aa3900` needs no dependency reinstall for this UI-only update. If this source checkout has never completed setup, add `--setup` to the launcher command above.

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

Check the launcher printed `c8bd8d49d9fc759067c75ee76157b812ce287775` (its first 12 characters) and the existing private state root. Check each URL's workspace badge, saved Inputs and selected Performance journal. On Main, inspect the expanded asset list; on every running CC inspect actual prices, warmup and freshness.

Asset cards distinguish a **reported error** from **past errors** counted since launch and show **bar age**. A past-error count alone does not prove a current fault; no reported error alone does not establish fresh prices or a healthy feed. The owner-PC cause must be established from its current status/logs after launch.

A blank view or repeated “Selected runtime observation expired” after **30 seconds**, while that workspace is ON, needs diagnostics. An OFF/STARTING/STOPPING CC deliberately suppresses its ordinary runtime observation polls. Warmup depends on available history/feed and may remain incomplete.

In a second Git Bash window:

```bash
curl --noproxy 127.0.0.1 --max-time 10 -sS -w '\nHealth HTTP %{http_code}\n' http://127.0.0.1:8791/healthz
curl --noproxy 127.0.0.1 --max-time 15 -sS -o /dev/null -H "Authorization: Bearer ${ICARUS_TOKEN:-icarus}" -w 'Status HTTP %{http_code}; response %{time_total}s\n' http://127.0.0.1:8791/status/public
tail -n 80 'C:/Users/tripl/Icarus/logs/engine.log'
```

Set your custom token locally in this second window if applicable. Use the actual state root for logs. The native status route is **`/status/public`**; **`/api/status` is not this engine's route**. HTTP 200 alone is insufficient: inspect nonempty assets, price/bar age, warmup and rendered views. Keep logs private and redact tokens/account details before sharing. A browser connection-aborted message alone does not establish that the process died.

**HTTP 000 with connection refusal means the client did not reach a listener at the sampled address and port.** Run the foreground launcher from step 3 and read its new source-revision/startup output. `logs/engine.log` appends historical entries, so a traceback in its tail may predate the current launch. A per-request disconnect traceback alone does not prove it terminated the engine. Preserve your custom token locally; do not post process command lines or unredacted startup logs.

Shared Access refreshes when opened, on Refresh or after an access action. Connections inventory does not prove an account is connected. Native read-only research panels can honestly report zero or unavailable private evidence; unavailable adapters remain visible. UI paper strategy states such as LIVE/ARMED are not broker authorization.


## Verification and limits

Exact published source: `c8bd8d49d9fc759067c75ee76157b812ce287775`; tree `98533b4e053d6cc13447c4decd62f5b327385f3c`, identical to the frozen local commit `564ec213df31f26e64915638ee24372ece3cc789`. The Main flow update changes only `dashboard.html`, `world-immersion.js` and two test files relative to the previous verified `7aa3900`; all Python runtime/dependency/launcher blobs are unchanged.

- **10 focused real-Chromium checks passed in 57.05 seconds.** These cover 35-asset card/SVG retention, changed values and membership, shared bounded chart reads, progress despite one held chart, serial selected reads, a real status deadline with automatic poll recovery, and automatic status continuity while a chart reaches its real deadline. That chart then recovers after an explicit refresh.
- **114 presentation/client checks passed in 8.69 seconds**, including the real-browser decoration regression. Before the fix, five idle frames rewrote 175 panel labels; afterward idle refreshes/mutations are zero, and two actual changes coalesce to one refresh.
- In an isolated synthetic 35-asset browser fixture, five unchanged status updates dropped from **3,332 ms and 175 removed SVGs** to **about 270 ms and zero removed SVGs**. Live value updates retain all 35 cards/charts. These measurements are cloud engineering evidence, not an owner-PC benchmark.
- The full API/accounting suite before the final decoration-only repair passed **4,083 tests and 111 subtests**, with 97 explicit skips, in 454.12 seconds. The wider real-Chromium run passed **93 checks in 327.19 seconds** at the identical production UI. The final test-only fixture correction then passed **3 focused checks in 35.77 seconds**. New exact-head hosted results are pending; previous-source totals are not relabelled as final-source results.
- The operator UI-update command also passed a synthetic local Git rehearsal: a clean exact source updates; tracked changes, untracked changes, a wrong fetched pin and an unexpected runtime-file change are refused before checkout. A separate private-state sentinel remained unchanged. This does not execute or certify the owner's PC. All seven Bash blocks parse.
- The previous `7aa3900` passed all ten automatic hosted workflows, including both Windows/Linux test runs and visual contracts. Its [hosted receipt](https://github.com/reppiks490/icarus-owner-actions/blob/main/coordination/events/2026/10/23/icarus2-20261020-federation-integration/054-hosted-verified-pc-launch.json) and [original delivery receipt](https://github.com/reppiks490/icarus-owner-actions/blob/main/coordination/handoffs/prime-installer-expanded-restart-20261023.json) remain historical evidence.

Failed pre-fix tests and intermediate attempts remain recorded: duplicate chart reads, a chunk barrier behind one chart, parallel selected-reader lock contention, and persistent slow-chart failures before the decoration loop was found. The request and observation deadlines were not widened to conceal those failures. An environment restart interrupted one wider browser run after 37 passing cases; it is not a completed pass. The first hosted visual run failed its recovery fixture: a hold-all route could strand a second poll, and generic screen expiry did not prove the first request's deadline had elapsed. The final test holds exactly one scheduled request, observes its actual deadline and cleared caches, then verifies normal poll recovery using the original six-second recovery budget. Production code is unchanged by this follow-up.

Full-system readiness remains **NO_GO**. These cloud checks do not certify the owner's PC, provider entitlement/freshness, imported history, all open-position reconstruction, sustained uptime or trading accuracy. A listed symbol is not verified fresh feed coverage. Provider, licensing and workflow blockers remain explicit; no training, collectors, live broker arming, paid feed selection, new spend or scheduler changes are introduced by this update.

## Rollback and stopping point

For an actual process restart or rollback, use Ctrl+C in the owning launcher, preserve the current private state, and switch to the privately recorded previous source without force. Use that source's matching launcher and confirmed state/feed/assets. Do not restore an older backup over newer journal entries casually.

No automatic main runtime merge, deployment, release or PC reboot is included. The federation mega-loop remains cancelled. Prime waits for the owner's PC readback after this bounded update and continues diagnosis if the recurring symptom remains.
