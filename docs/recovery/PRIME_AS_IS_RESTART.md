# Icarus Prime as-is restart — current operator procedure

**Purpose.** Restore the current Icarus paper runtime on the owner's Windows PC, keep its existing private state, and make the dashboards observable. This procedure never enables live trading or starts a broker bridge.

**Release gate.** Do not execute the new-source restart until the PR linked below has green Linux, Windows, and browser checks on its latest commit. Then use that exact commit. Cloud tests cannot run commands on the owner's PC or certify PC uptime.

- Integrated restart candidate: [PR #471](https://github.com/reppiks490/Icarus/pull/471)
- Dashboard scroll and restart-gate fixes: [PR #474](https://github.com/reppiks490/Icarus/pull/474)
- Source commit to use after the PR #474 exact-head checks are green: `41f5c8a8b0d9a62a1e15b69bca91f16a2885d34c`.
- Owner machine: `C:\Users\tripl\Icarus-as-is` (Git Bash: `~/Icarus-as-is`)
- Private state: `C:\Users\tripl\Icarus` (Git Bash: `~/Icarus`)
- Paper-only; `execution_authorized=false`.
- Dashboard/read/write adapter boundaries: [adapter status matrix](ICARUS_ADAPTER_STATUS.md).

## Defaults that this restart applies

The baseline is the actual current Main NQ settings: all declared strategy inputs, chart type, fill source, security source, timeframe, and session. Preparation captures live Main NQ when the local engine is reachable; otherwise it resolves the saved NQ configuration and its named preset. Missing, invalid, or changed source files stop the procedure. There is no stock-input fallback.

Every registered Main asset and every saved selected CC asset receives that NQ baseline. **ETH / COINBASE:ETHUSD alone** receives quantity input `25`, timeframe `30` minutes, and `use_session=false` (24/7 crypto session). SOL and every other asset retain the NQ values. Native contract economics remain instrument-specific. Saved asset selection, journals, and workspace on/off state are retained. Explicit later per-asset edits keep their usual precedence.

Main currently declares 35 symbols: `NQ,BTC,MNQ,MES,ES,YM,MYM,RTY,M2K,GC,MGC,SI,SIL,PL,PA,MBT,ETH,SOL,CL,NG,HG,6E,6J,6B,6A,ZN,ZB,BTCF,MHG,MCL,MNG,M6E,MJY,M6B,M6A`. The migration applies defaults across that inventory and saved selected CC assets. The last owner-PC health snapshot showed six active Main assets (`NQ,ES,YM,GC,SI,BTC`), so the launch below preserves that known active set instead of expanding runtime load; change it only if the intended saved Main selection has since changed.

## Git Bash commands

Run in Git Bash on the owner's PC. Leave any currently running Icarus launcher open until the capture succeeds, so preparation can read current Main NQ inputs. If the server is already stopped, preparation uses the verified saved NQ records instead.

```bash
set -euo pipefail
export ICARUS_HOME="$HOME/Icarus"
export ICARUS_TOKEN="${ICARUS_TOKEN:-icarus}"
RELEASE_COMMIT="41f5c8a8b0d9a62a1e15b69bca91f16a2885d34c"
cd "$HOME/Icarus-as-is"

# Fetch the final, CI-green commit recorded in this guide's release pin.
git fetch origin pull/474/head
git status --short --branch
git cat-file -e "${RELEASE_COMMIT}^{commit}"
git merge-base --is-ancestor "$RELEASE_COMMIT" FETCH_HEAD

# Use the pinned restart utility without changing the active checkout.
CANDIDATE="$HOME/Icarus-as-is-restart-candidate"
if [[ -e "$CANDIDATE" ]]; then
  test "$(git -C "$CANDIDATE" rev-parse HEAD)" = "$RELEASE_COMMIT"
  test -z "$(git -C "$CANDIDATE" status --porcelain)"
else
  git worktree add --detach "$CANDIDATE" "$RELEASE_COMMIT"
fi

# Capture before changing the active checkout or stopping its server.
PY="$PWD/.venv/Scripts/python.exe"
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

## Prior notes and evidence boundary

This file replaces the former generic restart pointer. Previous restart instructions are archived in Git history and must not be mixed with this procedure. The restart defaults, Windows path/port checks, canceled-request handling, and scroll-churn regression have automated evidence; their latest exact-head hosted checks must be green before use. A successful cloud check is not proof of owner-PC restart, sustained uptime, provider freshness, phone pairing, or zero future runtime errors. This release is paper-only and excludes live trading, broker adaptation, and order execution.
