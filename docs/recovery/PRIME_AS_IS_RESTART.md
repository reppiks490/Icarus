# Icarus Prime as-is restart — current operator procedure

**Purpose.** Restore the current Icarus paper runtime on the owner's Windows PC, keep its existing private state, and make the dashboards observable. This procedure never enables live trading or starts a broker bridge.

**Release status.** Paper restart source `2fd305598cdbaf1937c3c4214a6f5a72ef13e15a` was integrated by [PR #462](https://github.com/reppiks490/Icarus/pull/462), merged to `main` at `8c1dbf0d989894683d9daaefe6f1a4b6bcf4cc25` on 2026-10-25. The exact PR head `9a44dc1c6d20088bac1df013e6ec09e80446d30e` passed its Linux and Windows engine suites, contracts, browser, configuration, PyTorch contract, and federation checks. One conditional canonical-artifact job was skipped by its workflow guard. The merge-triggered `main` checks must also finish green before installation. Locally, the complete engine suite, 42 workspace client/UI tests, 19 disconnect-regression tests, the real-browser control retry regression, and dashboard/performance/runtime/Connections Chromium suite passed; the optional Node/Playwright-only performance subtest skipped because that Node package is unavailable here. This release contains restart/defaults work, selected-workspace Intuition Ω, the optional research-only GRU challenger, provider-origin/query-bound discovery evidence, bounded discovery receipts, and retry handling for a selected-workspace control rejected before execution because a reader briefly held its lock. Cloud checks cannot run commands on the owner's PC, certify `warm:true`, or establish sustained uptime.

- Integrated restart: [PR #462](https://github.com/reppiks490/Icarus/pull/462) (merged)
- Integrated `main` revision: `8c1dbf0d989894683d9daaefe6f1a4b6bcf4cc25`; its provider receipts and observe-only federation acceptance do not establish present provider availability.
- Latest restart source and owner-default changes: [PR #471](https://github.com/reppiks490/Icarus/pull/471) (merged into this candidate branch)
- Provider-context consumption and ETH-only defaults began at `5160a55368fc5c7e5a61dcf53c85193c028042ab` and received a Windows byte-stability fix at `1283551fbec56113da656d998ff4c04866c1624e`; both are ancestors of the current runtime source candidate. PR #457's validated historical-statistics reader is present; it does not claim live provider freshness.
- Dashboard scroll and restart-gate fixes: [PR #474](https://github.com/reppiks490/Icarus/pull/474), merged into #471.
- The Learning page's Intuition Ω bridge reads each selected workspace independently and offers an owner-triggered import of receipt-verified settled Learning pairs into that workspace's private research ledger. Status refresh is manual; no 5-second polling is used. The feature is included in merged `main`; wait for merge-triggered checks before installation.
- Restart code source: `2fd305598cdbaf1937c3c4214a6f5a72ef13e15a` (included in merged `main`; merge-triggered checks must finish green before install).
- Selected-workspace Intuition Ω adapter source: `cde6d0cca771ec8a401092a231449646306c026c`, included in the current release source candidate.
- Owner machine: `C:\Users\tripl\Icarus-as-is` (Git Bash: `~/Icarus-as-is`)
- Private state: `C:\Users\tripl\Icarus` (Git Bash: `~/Icarus`)
- Paper-only; `execution_authorized=false`.
- Dashboard/read/write adapter boundaries: [adapter status matrix](ICARUS_ADAPTER_STATUS.md).

Selected-workspace pause, resume, and flatten controls retry only the exact server response emitted before a busy workspace admits the operation. Other errors are returned immediately; successful or partial operations are never replayed.

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
RELEASE_COMMIT="2fd305598cdbaf1937c3c4214a6f5a72ef13e15a"
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

Launch the local **paper** engine with the last owner-observed feed and active assets. The last documented owner-PC startup used Yahoo and reached `warm:true`; if the intended source has since changed, select the owner's intended non-live feed explicitly rather than guessing:

```bash
bash scripts/start-as-is.sh --root "$ICARUS_HOME" \
  --feed yahoo \
  --assets NQ,ES,YM,GC,SI,BTC
```

Keep this launcher window open. The launcher prints its source path, Python interpreter, private-state path, saved workspace/journal counts and URLs.

## Verify local observation

In a second Git Bash window:

```bash
set -euo pipefail
HEALTH_PY="$HOME/Icarus-as-is/.venv/Scripts/python.exe"
test -x "$HEALTH_PY"
export ICARUS_EXPECTED_ASSETS="${ICARUS_ASSETS:-NQ,ES,YM,GC,SI,BTC}"
read -r -s -p 'Dashboard token used by the launcher (hidden): ' ICARUS_VERIFY_TOKEN </dev/tty
printf '\n'
test -n "$ICARUS_VERIFY_TOKEN"

check_http() {
  local label="$1" url="$2" code
  code="$(curl --noproxy 127.0.0.1 --max-time 10 -sS -o /dev/null -w '%{http_code}' \
    -H "Authorization: Bearer $ICARUS_VERIFY_TOKEN" "$url")"
  printf '%s HTTP %s\n' "$label" "$code"
  [[ "$code" == 200 ]]
}
ready=false
health_json=''
warm_deadline=$((SECONDS + 300))
while (( SECONDS < warm_deadline )); do
  health_json="$(curl --noproxy 127.0.0.1 --max-time 3 -fsS http://127.0.0.1:8791/healthz 2>/dev/null || true)"
  if [[ -n "$health_json" ]] && printf '%s' "$health_json" | "$HEALTH_PY" -c '
import json, os, sys
try:
    health = json.load(sys.stdin)
    expected = sorted(os.environ["ICARUS_EXPECTED_ASSETS"].split(","))
    actual = sorted(health.get("assets", []))
except (ValueError, TypeError, KeyError):
    raise SystemExit(1)
raise SystemExit(0 if health.get("ok") is True and health.get("warm") is True and actual == expected else 1)
'; then
    ready=true
    break
  fi
  sleep 1
done
if [[ "$ready" != true ]]; then
  printf 'Engine did not report warm:true with the expected assets within five minutes. Last /healthz response: %s\n' "${health_json:-<no response>}" >&2
  echo 'Keep the launcher open and inspect Icarus/logs/engine.log; do not start a second engine.' >&2
  exit 1
fi
printf 'Warm engine health: %s\n' "$health_json"
check_http Main http://127.0.0.1:8791/
check_http 'Public status' http://127.0.0.1:8791/status/public
for panel in cc1 cc2 cc3 cc4 connections; do
  check_http "$panel" "http://127.0.0.1:8791/dashboards/$panel"
done
```

The second window prompts for the same dashboard token used by the launcher without echoing it; the public-status check is authenticated because `/status/public` requires a bearer token. The verification waits up to five minutes for `/healthz` to report `warm:true` and the expected active asset set before checking HTTP 200 for Main, public status, and each dashboard. If it does not warm in that window, keep the launcher open and inspect its log instead of refreshing repeatedly or starting a second engine. The public status route is `/status/public` (`/api/status` is not the route). Open Main and each CC/Connections URL in the PC browser; check that each page renders and that CC toggles affect only the selected paper workspace. Keep one dashboard tab open during the initial lag check.

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

The Learning page also shows the selected workspace's Intuition Ω source and private-ledger status. Press **Refresh status** for a fresh observation. Press **Import verified Learning pairs** only when you want to start a bounded, asynchronous research import; the source database remains read-only and the result cannot alter trading inputs or promote a model. A completed import with zero qualified pairs is a truthful empty result, not a runtime failure. The card does not poll automatically.

## Additional non-live research connections

The **Financial & data** page now includes a read-only **Capability discovery registry** card backed by `/api/discovery-registry`. It displays bounded summaries for the three pinned public catalog receipts, including source revision, retrieval time, import counts, review backlog, rejected entries, and parse failures. It does not run catalog refreshes, open the private registry database, probe discovered services, or provide market data. The receipts currently describe catalog metadata only; credentials and current provider availability are separate and may be unavailable.

The candidate also contains the optional GRU research challenger from PR #453. It is manually invoked through the research CLI and is not a startup worker or dashboard poll. The ordinary restart install command intentionally omits the optional `deep` extra, so it does not install PyTorch or make the desktop engine heavier. Research runs require a separate owner choice to install `.[deep]`; artifacts remain challenger-only, frozen training slots stay unchanged, and automatic model promotion, production decisions, and execution authority remain false.

## Prior notes and evidence boundary

The old per-panel restart instructions are physically archived at [archive/restarts/2026-10-25/pre-final/ICARUS_PANEL_RESTARTS.md](archive/restarts/2026-10-25/pre-final/ICARUS_PANEL_RESTARTS.md); use this single procedure. Restart defaults, Windows path/port checks, canceled-request handling, and scroll-churn have automated evidence. PR #462's exact-head required checks passed; wait for merged-main checks to finish before installation. This is paper-only and excludes live trading, broker adaptation, and order execution. A successful cloud check is not proof of owner-PC restart, sustained uptime, provider freshness, phone pairing, or zero future runtime errors.
