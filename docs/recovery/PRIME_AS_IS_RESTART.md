# Icarus Prime as-is restart — current operator procedure

**Purpose.** Restore the current Icarus paper runtime on the owner's Windows PC, keep its existing private state, and make the dashboards observable. This procedure never enables live trading or starts a broker bridge.

**Release gate.** The restart code, provider-context consumer, ETH-only defaults, Windows byte-stable archive, and all current-main data receipts are in release tree `f4a4a2800069bcefc3661b38d0b4d134ae775326` for PR #462. Runtime source commit `1283551fbec56113da656d998ff4c04866c1624e` passed the full Linux suite and the selected full Windows suite twice: [40183899072](https://github.com/reppiks490/Icarus/actions/runs/40183899072) and [40183897492](https://github.com/reppiks490/Icarus/actions/runs/40183897492). Both Windows restart-persistence/private-intake steps passed. The portfolio, visual-browser, configuration, intelligence-feed, and federation consumer contracts also passed on that source. Local full suite `python -m pytest tests_engine tests/test_provider_corpus_intake.py -q` exited 0 with 4,331 cases collected. The current PR head includes only a current-main catalog receipt merge and these operator-document updates; verify all required checks on the current PR #462 head before installation. Cloud checks cannot run commands on the owner's PC, certify `warm:true`, or establish sustained uptime.

- Integrated restart candidate: [PR #462](https://github.com/reppiks490/Icarus/pull/462)
- Latest restart source and owner-default changes: [PR #471](https://github.com/reppiks490/Icarus/pull/471) (merged into this candidate branch)
- Historical provider-context consumer and ETH-only defaults: source commit `5160a55368fc5c7e5a61dcf53c85193c028042ab`, included in runtime source `1283551fbec56113da656d998ff4c04866c1624e`; PR #457 is consolidated into #462.
- Dashboard scroll and restart-gate fixes: [PR #474](https://github.com/reppiks490/Icarus/pull/474), merged into #471.
- Restart code source: `1283551fbec56113da656d998ff4c04866c1624e`; current-main receipt merge/release tree: `f4a4a2800069bcefc3661b38d0b4d134ae775326`.
- Owner machine: `C:\Users\tripl\Icarus-as-is` (Git Bash: `~/Icarus-as-is`)
- Private state: `C:\Users\tripl\Icarus` (Git Bash: `~/Icarus`)
- Paper-only; `execution_authorized=false`.
- Dashboard/read/write adapter boundaries: [adapter status matrix](ICARUS_ADAPTER_STATUS.md).

## Defaults that this restart applies

The baseline is the actual current Main NQ settings: all declared strategy inputs, chart type, fill source, security source, timeframe, and session. Preparation captures live Main NQ when the local engine is reachable; otherwise it resolves the saved NQ configuration and its named preset. Missing, invalid, or changed source files stop the procedure. There is no stock-input fallback.

Every registered Main asset and every saved selected CC asset receives that NQ baseline. **ETH / COINBASE:ETHUSD only** receives quantity input `25`, timeframe `30` minutes, and `use_session=false` (24/7 crypto session). SOLUSD follows the current Main NQ defaults exactly, as do all other assets. Native contract economics remain instrument-specific. Saved asset selection, journals, and workspace on/off state are retained. Explicit later per-asset edits keep their usual precedence.

Main currently declares 35 symbols: `NQ,BTC,MNQ,MES,ES,YM,MYM,RTY,M2K,GC,MGC,SI,SIL,PL,PA,MBT,ETH,SOL,CL,NG,HG,6E,6J,6B,6A,ZN,ZB,BTCF,MHG,MCL,MNG,M6E,MJY,M6B,M6A`. The migration applies defaults across that inventory and saved selected CC assets. The last owner-PC health snapshot showed six active Main assets (`NQ,ES,YM,GC,SI,BTC`), so the launch below preserves that known active set instead of expanding runtime load; change it only if the intended saved Main selection has since changed.

## Git Bash commands

Run in Git Bash on the owner's PC. Leave any currently running Icarus launcher open until the capture succeeds, so preparation can read current Main NQ inputs. If the server is already stopped, preparation uses the verified saved NQ records instead.

```bash
set -euo pipefail
export ICARUS_HOME="$HOME/Icarus"
export ICARUS_TOKEN="${ICARUS_TOKEN:-icarus}"
RELEASE_COMMIT="f4a4a2800069bcefc3661b38d0b4d134ae775326"
RELEASE_BRANCH="icarus1/restart-readiness-20261020"
cd "$HOME/Icarus-as-is"

# Fetch the exact candidate branch. Do not use a stale PR ref as the release gate.
git fetch origin "refs/heads/$RELEASE_BRANCH:refs/remotes/origin/$RELEASE_BRANCH"
git status --short --branch
git cat-file -e "${RELEASE_COMMIT}^{commit}"
git merge-base --is-ancestor "$RELEASE_COMMIT" "refs/remotes/origin/$RELEASE_BRANCH"

# Use the pinned restart utility without changing the active checkout.
CANDIDATE="$HOME/Icarus-as-is-restart-candidate-${RELEASE_COMMIT:0:12}"
if [[ -e "$CANDIDATE" ]]; then
  test "$(git -C "$CANDIDATE" rev-parse HEAD)" = "$RELEASE_COMMIT"
  test -z "$(git -C "$CANDIDATE" status --porcelain)"
else
  git worktree add --detach "$CANDIDATE" "$RELEASE_COMMIT"
fi

# Capture before changing the active checkout or stopping its server.
PY="$HOME/Icarus-as-is/.venv/Scripts/python.exe"
test -x "$PY"
cd "$CANDIDATE"
"$PY" -m icarus_engine.restart_defaults \
  --root "$ICARUS_HOME" --prepare \
  --capture-output "$ICARUS_HOME/current-nq-restart-capture.json" \
  --port 8791
```

Read the JSON result. Stop if preparation fails or if the NQ chart/input/session summary is not the intended current Main NQ setup. The utility runs from the detached, pinned worktree while the existing launcher and active checkout stay in place. If Git reports a worktree conflict or the candidate interpreter command fails, do not reset the PC or improvise; preserve the output for diagnosis.

After a successful capture, press **Ctrl+C once** in the current launcher and wait for it to exit. Do not kill Python processes by name. Back up private state before applying settings or switching the checkout:

```bash
# Make a complete private-state backup while the engine is stopped.
BACKUP="$HOME/Icarus-backup-$(date -u +%Y%m%dT%H%M%SZ)"
cp -a "$ICARUS_HOME" "$BACKUP"
printf 'Private-state backup: %s\n' "$BACKUP"

# Before checkout, stop and resolve any local edits rather than overwriting them.
cd "$HOME/Icarus-as-is"
if [[ -n "$(git status --porcelain)" ]]; then
  echo 'Checkout has local edits. Preserve or commit them before changing revisions.' >&2
  exit 2
fi
git checkout --detach "$RELEASE_COMMIT"
test "$(git rev-parse HEAD)" = "$RELEASE_COMMIT"
```

Reuse the checkout's existing `.venv` and update its editable install. The capture step above requires that environment; if it is missing, stop and prepare a verified environment without changing the active runtime. This install step does not start Icarus:

```bash
PY="$PWD/.venv/Scripts/python.exe"
DISTUTILS_MODE="$("$PY" -c 'import sys; print("stdlib" if sys.version_info < (3,12) else "local")')"
SETUPTOOLS_USE_DISTUTILS="$DISTUTILS_MODE" "$PY" -m pip install --upgrade pip 'setuptools>=68' wheel
SETUPTOOLS_USE_DISTUTILS="$DISTUTILS_MODE" "$PY" -m pip install --no-build-isolation -e '.[bridge,ml,databento]' 'cryptography>=44,<47'

# Apply the captured NQ template to Main and the selected CC assets, then verify.
"$PY" -m icarus_engine.restart_defaults \
  --root "$ICARUS_HOME" \
  --capture-file "$ICARUS_HOME/current-nq-restart-capture.json" --apply
"$PY" -m icarus_engine.restart_defaults \
  --root "$ICARUS_HOME" \
  --capture-file "$ICARUS_HOME/current-nq-restart-capture.json" --verify
```

The defaults utility makes its own hash-tracked backup of changed settings under `Icarus/audit/restart-defaults/`. The full backup above also preserves journals and other private state. Do not proceed if `--apply` or `--verify` fails.

Launch the local **paper** engine with the last observed feed and active assets. The known previous runtime used the local file feed; if its intended source has changed, replace `file` with the owner's intended non-live feed explicitly rather than guessing:

```bash
bash scripts/start-as-is.sh --root "$ICARUS_HOME" \
  --feed file \
  --assets NQ,ES,YM,GC,SI,BTC
```

Keep this launcher window open. The launcher prints its source path, Python interpreter, private-state path, saved workspace/journal counts and URLs.

## Verify local observation

In a second Git Bash window:

```bash
check_http() {
  local label="$1" url="$2" code
  code="$(curl --noproxy 127.0.0.1 --max-time 10 -sS -o /dev/null -w '%{http_code}' "$url")"
  printf '%s HTTP %s\n' "$label" "$code"
  [[ "$code" == 200 ]]
}
ready=false
for attempt in {1..30}; do
  if curl --noproxy 127.0.0.1 --max-time 3 -fsS http://127.0.0.1:8791/healthz; then ready=true; break; fi
  sleep 1
done
if [[ "$ready" != true ]]; then echo 'Engine health did not become ready; inspect the launcher and logs.' >&2; exit 1; fi
check_http Main http://127.0.0.1:8791/
check_http 'Public status' http://127.0.0.1:8791/status/public
for panel in cc1 cc2 cc3 cc4 connections; do
  check_http "$panel" "http://127.0.0.1:8791/dashboards/$panel"
done
```

Expected HTTP responses are 200 for health, Main, public status, and each dashboard. Confirm `/healthz` reports the intended active six assets and inspect `warm`; a 200 with `warm:false` means the server answered but its data is not warm, so it is not a fully observed/warmed restart. The public status route is `/status/public` (`/api/status` is not the route). Open Main and each CC/Connections URL in the PC browser; check that each page renders and that CC toggles affect only the selected paper workspace. Keep one dashboard tab open during the initial lag check.

Re-run the defaults verifier from the first launcher window or another Git Bash window:

```bash
cd "$HOME/Icarus-as-is"
"$HOME/Icarus-as-is/.venv/Scripts/python.exe" -m icarus_engine.restart_defaults \
  --root "$HOME/Icarus" \
  --capture-file "$HOME/Icarus/current-nq-restart-capture.json" --verify
```

If an HTTP probe fails, the launcher exits, `warm` stays false, or the dashboard does not render, do not repeatedly refresh or start a second engine. Save the exact output and inspect `Icarus/logs/engine.log`; preserve the window and private-state backup for diagnosis. Restore the backup only after stopping the failed engine.

## Mobile observation

The phone relay code is included in the candidate and retains its independent HTTP, authentication, and workspace-isolation checks. Physical pairing still has to be completed from the owner's PC and phone. Once the desktop runtime reports `warm:true`, use the [phone connection procedure](../PHONE_ACCESS.md) to create a read-only viewer token, start the loopback relay and temporary tunnel, and pair the hosted mobile page. This step does not restart the desktop engine. Keep the PC, relay, and tunnel awake; a new Quick Tunnel URL requires pairing again. The hosted page's private UI bundle and the actual phone session are not verifiable from this workspace.

## Archived provider context

CC1–CC4 can display the pinned metadata-only provider statistics archive and record actual read receipts. This is historical context only: it does not poll providers, certify current freshness or entitlement, alter trading inputs, or enable execution. See the [adapter status matrix](ICARUS_ADAPTER_STATUS.md) for the exact boundary.

## Prior notes and evidence boundary

The old per-panel restart instructions are physically archived at [archive/restarts/2026-10-25/pre-final/ICARUS_PANEL_RESTARTS.md](archive/restarts/2026-10-25/pre-final/ICARUS_PANEL_RESTARTS.md); use this single procedure. Restart defaults, Windows path/port checks, canceled-request handling, and scroll-churn have automated evidence. The exact integrated PR #462 head must pass all required hosted checks before installation. This is paper-only and excludes live trading, broker adaptation, and order execution. A successful cloud check is not proof of owner-PC restart, sustained uptime, provider freshness, phone pairing, or zero future runtime errors.
