# Icarus Prime as-is restart — current operator procedure

**Purpose.** Restore the current Icarus paper runtime on the owner's Windows PC, keep its existing private state, and make the dashboards observable. This procedure never enables live trading or starts a broker bridge.

**Current release (2026-10-25).** The current paper runtime is pinned to Icarus `main` revision `a21507b8b9bb46ec418a0a9b89fae448fb3eae96`. It includes PR #479's all-asset restart defaults, PR #476's dashboard scroll/layout fix, and PR #481's native mobile observer and isolated gateway, which permits explicit rate-limited backtest requests but no trade-state mutations. PR #481's merge-triggered Linux/Windows/mobile run [40224524803](https://github.com/reppiks490/Icarus/actions/runs/40224524803) and deep-learning contract [40224524804](https://github.com/reppiks490/Icarus/actions/runs/40224524804) passed. PR #482's exact-head Linux/Windows/mobile tests [40224637484](https://github.com/reppiks490/Icarus/actions/runs/40224637484) and bilateral PR gate [40224637590](https://github.com/reppiks490/Icarus/actions/runs/40224637590) passed; #482 merged at `fb639c45b1c1afb3b1eb6dd0979784b7e4f4f6c3`. The post-merge main gate [40227416952](https://github.com/reppiks490/Icarus/actions/runs/40227416952) passed; its checkpoint receipt recorded Icarus `fb639c45...` and Engine `f49d93d9...`. Engine main can advance independently. Read the [canonical receipt](../../automation_intelligence/federation/icarus_engine_acceptance.json) and compare its peer SHA with current Engine `main` before treating the pair as current. This observe-only federation receipt establishes no substantive peer lane, keeps `execution_authorized=false`, and does not guarantee provider freshness. These hosted results do not observe the owner's PC or phone.

- Release commit: `a21507b8b9bb46ec418a0a9b89fae448fb3eae96`; verify it remains an ancestor of `origin/main` before using it.
- Defaults: PR #479, merged at `7ebbc0fe6ca76059f909d658ab79f5e37345951b`; 35 Main symbols and saved selected CC assets receive captured NQ settings, except ETH and SOL (30 minutes, session off, quantity 25).
- Dashboard performance: PR #476, merged at `c0cac098ac71dc0aa3acccf5a7c29b7c6742a3a5`; scroll feedback no longer performs repeated layout reads.
- Mobile integration: PR #481, merged at the release commit. The observation app and mobile gateway are integrated; explicit rate-limited backtest requests are supported, with no trade-state mutations; actual phone pairing and EAS/store signing remain pending owner-device/account setup.
- Last successful warm Main observation: six active assets (`NQ,ES,YM,GC,SI,BTC`). A later failed readiness probe returned `warm:false` and an empty asset list; that is not a healthy zero-asset selection. The launch preserves the saved six-asset set to avoid adding runtime load; the defaults migration covers the full 35-symbol registry and saved selected CC assets.
- Owner machine: `C:\Users\tripl\Icarus-as-is` (Git Bash: `~/Icarus-as-is`)
- Private state: `C:\Users\tripl\Icarus` (Git Bash: `~/Icarus`)
- Paper-only; `execution_authorized=false`.

## Defaults that this restart applies

The baseline is the actual current Main NQ settings: all declared strategy inputs, chart type, fill source, security source, timeframe, and session. Preparation captures live Main NQ when the local engine is reachable; otherwise it resolves the saved NQ configuration and its named preset. Missing, invalid, or changed source files stop the procedure. There is no stock-input fallback.

Every registered Main asset and every saved selected CC asset receives that NQ baseline. **ETH / COINBASE:ETHUSD and SOL / COINBASE:SOLUSD** each receive quantity input `25`, timeframe `30` minutes, and `use_session=false` (24/7 crypto session). Every other asset uses the current Main NQ defaults exactly. Native contract economics remain instrument-specific. Saved asset selection, journals, and workspace on/off state are retained. Explicit later per-asset edits keep their usual precedence.

Main currently declares 35 symbols: `NQ,BTC,MNQ,MES,ES,YM,MYM,RTY,M2K,GC,MGC,SI,SIL,PL,PA,MBT,ETH,SOL,CL,NG,HG,6E,6J,6B,6A,ZN,ZB,BTCF,MHG,MCL,MNG,M6E,MJY,M6B,M6A`. The migration applies defaults across that inventory and saved selected CC assets. The last owner-PC health snapshot showed six active Main assets (`NQ,ES,YM,GC,SI,BTC`), so the launch below preserves that known active set instead of expanding runtime load; change it only if the intended saved Main selection has since changed.

## Git Bash commands

Run in Git Bash on the owner's PC. Leave any currently running Icarus launcher open until the capture succeeds, so preparation can read current Main NQ inputs. If the server is already stopped, preparation uses the verified saved NQ records instead.

```bash
set -euo pipefail
export ICARUS_HOME="$HOME/Icarus"
if [[ -z "${ICARUS_TOKEN:-}" ]]; then
  read -r -s -p 'Dashboard token used by the running launcher (Enter if default is icarus or engine is stopped): ' ICARUS_TOKEN </dev/tty
  printf '\n'
  ICARUS_TOKEN="${ICARUS_TOKEN:-icarus}"
fi
export ICARUS_TOKEN
RELEASE_COMMIT="a21507b8b9bb46ec418a0a9b89fae448fb3eae96"
cd "$HOME/Icarus-as-is"

# Fetch main and prove the pinned release commit is still in its history.
git fetch origin refs/heads/main:refs/remotes/origin/main
git status --short --branch
if [[ -n "$(git status --porcelain)" ]]; then
  echo 'Checkout has local edits. Preserve or commit them before restarting.' >&2
  exit 2
fi
git cat-file -e "${RELEASE_COMMIT}^{commit}"
git merge-base --is-ancestor "$RELEASE_COMMIT" refs/remotes/origin/main

# Use the pinned restart utility without changing the active checkout.
CANDIDATE="$HOME/Icarus-as-is-restart-candidate-${RELEASE_COMMIT:0:12}"
if [[ -e "$CANDIDATE" ]]; then
  test "$(git -C "$CANDIDATE" rev-parse HEAD)" = "$RELEASE_COMMIT"
  test -z "$(git -C "$CANDIDATE" status --porcelain)"
else
  git worktree add --detach "$CANDIDATE" "$RELEASE_COMMIT"
fi

# Prepare and verify an isolated environment in the candidate worktree. This does
# not change the active checkout or its running engine.
cd "$CANDIDATE"
bash scripts/start-as-is.sh --setup --help
PY="$CANDIDATE/.venv/Scripts/python.exe"
test -x "$PY"
"$PY" -c "import sys; assert sys.version_info >= (3,10), sys.version"

# Capture before changing the active checkout or stopping its server.
"$PY" -m icarus_engine.restart_defaults \
  --root "$ICARUS_HOME" --prepare \
  --capture-output "$ICARUS_HOME/current-nq-restart-capture.json" \
  --port 8791
```

Read the JSON result. Stop if preparation fails or if the NQ chart/input/session summary is not the intended current Main NQ setup. The detached worktree receives its own environment through the same tested launcher setup path. This keeps the current checkout and running engine untouched while the NQ capture uses the exact pinned release. If Git reports a worktree conflict or the candidate interpreter command fails, do not reset the PC or improvise; preserve the output for diagnosis.

After a successful capture, press **Ctrl+C once** in the current launcher and wait for it to exit. Do not kill Python processes by name. Back up private state before applying settings or switching the checkout:

```bash
# Make a complete private-state backup while the engine is stopped.
BACKUP="$HOME/Icarus-backup-$(date -u +%Y%m%dT%H%M%SZ)"
test ! -e "$BACKUP"
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

Run the launcher's setup check from the pinned active checkout. It creates or refreshes that checkout's environment with the Python 3.10/3.11 distutils workaround; `--help` verifies the package source without starting the engine:

```bash
bash scripts/start-as-is.sh --setup --help
PY="$PWD/.venv/Scripts/python.exe"
test -x "$PY"
"$PY" -c "import sys; assert sys.version_info >= (3,10), sys.version"

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

The second window prompts for the same dashboard token used by the launcher without echoing it; the public-status check is authenticated because `/status/public` requires a bearer token. The verification waits up to five minutes for `/healthz` to report `warm:true` and the expected active asset set before checking HTTP 200 for Main, public status, and each dashboard. The current server catches broken-pipe, reset, and aborted-client errors while writing a response, and closes an aborted request-line read as a client disconnect; an ordinary browser close should not escape as the repeated Windows 10053 traceback. If it does not warm in that window, keep the launcher open and inspect its log instead of refreshing repeatedly or starting a second engine. The public status route is `/status/public` (`/api/status` is not the route). Open Main and each CC/Connections URL in the PC browser; check that each page renders and that CC toggles affect only the selected paper workspace. Keep one dashboard tab open during the initial lag check.

Re-run the defaults verifier from the first launcher window or another Git Bash window:

```bash
cd "$HOME/Icarus-as-is"
"$HOME/Icarus-as-is/.venv/Scripts/python.exe" -m icarus_engine.restart_defaults \
  --root "$HOME/Icarus" \
  --capture-file "$HOME/Icarus/current-nq-restart-capture.json" --verify
```

If an HTTP probe fails, the launcher exits, `warm` stays false, or the dashboard does not render, do not repeatedly refresh or start a second engine. Save the exact output and inspect `Icarus/logs/engine.log`; preserve the window and private-state backup for diagnosis. Disconnect handling prevents a dropped browser request from becoming an unhandled write exception; it cannot prevent genuine application, provider, or machine errors or promise zero future interruptions. Restore the backup only after stopping the failed engine.

## Mobile observation

The native mobile app and dedicated observation gateway are integrated at the pinned release, but no physical phone is paired from this workspace. The desktop restart does not start the mobile gateway. Pair only after desktop `/healthz` reports `warm:true`; follow [Windows gateway instructions](../icarus/MOBILE_WINDOWS.md) and [mobile app setup](../../mobile/README.md). Keep engine port 8791 private; expose only gateway port 8792 behind HTTPS or a private VPN. The phone receives device-scoped read credentials, never the engine admin token.

A distributable EAS build still requires the owner to link an Expo project (the committed app config currently has no EAS project ID) and supply Apple/Google signing credentials for store releases. The repository currently exports JavaScript bundles but does not run an EAS build workflow. If EAS automation is added, keep `EXPO_TOKEN` in a CI secret rather than a tracked file. The owner must install and pair the app using a reachable HTTPS/private-network hostname.

## Archived provider context

CC1–CC4 can display the pinned metadata-only provider statistics archive and record actual read receipts. This is historical context only: it does not poll providers, certify current freshness or entitlement, alter trading inputs, or enable execution. See the [adapter status matrix](ICARUS_ADAPTER_STATUS.md) for the exact boundary.

The Learning page also shows the selected workspace's Intuition Ω source and private-ledger status. Press **Refresh status** for a fresh observation. Press **Import verified Learning pairs** only when you want to start a bounded, asynchronous research import; the source database remains read-only and the result cannot alter trading inputs or promote a model. A completed import with zero qualified pairs is a truthful empty result, not a runtime failure. The card does not poll automatically.

## Additional non-live research connections

The **Financial & data** page now includes a read-only **Capability discovery registry** card backed by `/api/discovery-registry`. It displays bounded summaries for the three pinned public catalog receipts, including source revision, retrieval time, import counts, review backlog, rejected entries, and parse failures. It does not run catalog refreshes, open the private registry database, probe discovered services, or provide market data. The receipts currently describe catalog metadata only; credentials and current provider availability are separate and may be unavailable.

The candidate also contains the optional GRU research challenger from PR #453. It is manually invoked through the research CLI and is not a startup worker or dashboard poll. The ordinary restart install command intentionally omits the optional `deep` extra, so it does not install PyTorch or make the desktop engine heavier. Research runs require a separate owner choice to install `.[deep]`; artifacts remain challenger-only, frozen training slots stay unchanged, and automatic model promotion, production decisions, and execution authority remain false.

## Prior notes and evidence boundary

Superseded per-panel restart commands are preserved in the [restart archive](archive/restarts/2026-10-25/pre-final/INDEX.md); do not run them. This single guide is the current procedure. The scroll/layout fix, exact paper defaults, and mobile observation and bounded backtest code have automated evidence. PC restart, sustained warm health, provider freshness, and physical phone pairing require owner-side observation. This release excludes broker adaptation, live trading, and order execution; no automated suite can promise zero future runtime errors.