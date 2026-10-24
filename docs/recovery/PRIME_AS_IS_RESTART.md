# Current ICARUS full restart — 24 October 2026

**HIGHLY IMPORTANT: [required NQ, ETHUSD and SOLUSD settings](HIGHLY_IMPORTANT_RESTART_INFO.md).**

**Verified runtime: `3122d349524fbce803970dc34ab6fc74dad87467` · tree `9ad37de97e160aead6602351b54c43608086a006`** · branch `prime/as-is-restart-20261022` · [PR #471](https://github.com/reppiks490/Icarus/pull/471). Main contains documentation only; fetch the exact runtime below.

This replaces the [previous instructions, archived byte-for-byte](archive/2026-10-24/pre-nexus-aion-PRIME_AS_IS_RESTART.md). [Older notes remain historical](archive/2026-10-24/INDEX.md). This build changes Python runtime code and requires a full restart.

Every Main and CC asset receives actual Main NQ strategy/chart defaults, with these exceptions:

| Asset | Timeframe | RTH gate | Quantity input |
| --- | --- | --- | --- |
| Every other asset | Same as current NQ | Same as current NQ | Same as current NQ |
| ETH / COINBASE:ETHUSD | 30 minutes | Disabled; 24/7 crypto calendar | 25 |
| SOL / COINBASE:SOLUSD | 30 minutes | Disabled; 24/7 crypto calendar | 25 |

This intentionally resets existing strategy/chart overrides as requested. Asset selections, journals and CC power settings are preserved. Future assets inherit the template; later explicit per-asset edits keep their normal precedence. Native instrument economics and existing runtime point/tick scaling remain asset-specific.

The build includes NEXUS source-health observations and AION durable monitoring history. It repairs the reproduced timeout causes: synchronous authentication activity writes, runner recomputation and journal aggregation on status requests. Authentication stays authoritative and immediately revocable; audit writes run separately. Published runtime snapshots preserve source timestamps. Missing or dirty accounting stays explicitly unknown while assets remain visible. Main/CC/activation views update after configuration commits. Request deadlines and freshness limits are not widened.

## 1. Prepare the actual NQ template

Use **Git Bash on the PC**. The known source is `C:/Users/tripl/Icarus-as-is`; existing private state is `C:/Users/tripl/Icarus`. Use the actual state root if the previous launcher printed another one.

Paste this complete block. It fetches verified Git objects and reads their preparation helper without switching the running source. If Icarus is running, preparation authenticates and captures current NQ. If it is already stopped, it verifies the saved NQ and preset records. Missing settings or authentication failures stop the operation; stock defaults are not silently substituted.

```bash
(
set +x
set -euo pipefail
trap 'printf "\nNQ preparation stopped. Keep the error above; no defaults were applied.\n" >&2' ERR
cd /c/Users/tripl/Icarus-as-is
ICARUS_RESTART_REV='3122d349524fbce803970dc34ab6fc74dad87467'
ICARUS_RESTART_TREE='9ad37de97e160aead6602351b54c43608086a006'
ICARUS_STATE='C:/Users/tripl/Icarus'
ICARUS_PREPARE_PY="$PWD/.venv/Scripts/python.exe"
test -d "$ICARUS_STATE"
test -x "$ICARUS_PREPARE_PY"
test -z "$(git status --porcelain=v1 --untracked-files=all)"
git fetch --quiet origin prime/as-is-restart-20261022
test "$(git rev-parse 'FETCH_HEAD^{commit}')" = "$ICARUS_RESTART_REV"
test "$(git rev-parse "${ICARUS_RESTART_REV}^{tree}")" = "$ICARUS_RESTART_TREE"
git show "${ICARUS_RESTART_REV}:icarus_engine/restart_defaults.py" |
  PYTHONUTF8=1 "$ICARUS_PREPARE_PY" -c 'import sys; from pathlib import Path; import icarus_engine; assert Path(icarus_engine.__file__).resolve().parent.parent == Path.cwd().resolve(), "Wrong installed source"; source=sys.stdin.read(); sys.argv=["verified-restart-defaults","--root",sys.argv[1],"--prepare"]; exec(compile(source,"verified-restart-defaults","exec"),{"__name__":"__main__","__package__":"icarus_engine"})' "$ICARUS_STATE"
printf '\nNQ snapshot prepared. If the old launcher is running, press Ctrl+C there before the full restart block.\n'
)
```

The result must say `PREPARED` and show the actual NQ overview plus both crypto exceptions. The snapshot remains private at `ROOT/current-nq-restart-capture.json`. Keep existing custom `ICARUS_TOKEN` configured locally; never send its value. Do not edit Inputs between preparation and restart.

If the old engine cannot answer preparation because it is already timing out, stop its owning launcher normally and rerun preparation against saved settings. The output labels that saved-resolution basis explicitly.

## 2. Stop, back up, apply and launch

Privately record open paper positions first; complete reconstruction of in-memory positions is not certified. Close Icarus browser tabs. In the terminal owning the old engine, press **Ctrl+C** and wait for shutdown. Do not flatten positions merely to restart. If it is already stopped, proceed.

Paste the complete block below. It verifies recorded PIDs and port 8791, copies the stopped private state, records the prior source revision, verifies the new source/tree, applies and verifies NQ defaults, and launches all 35 canonical Main symbols. It does not kill another process or force Git.

```bash
(
set +x
set -euo pipefail
trap 'printf "\nRestart stopped. Keep the error above; do not force Git or delete PID files.\n" >&2' ERR

cd /c/Users/tripl/Icarus-as-is
export ICARUS_STATE='C:/Users/tripl/Icarus'
export ICARUS_HOME="$ICARUS_STATE"
ICARUS_RESTART_REV='3122d349524fbce803970dc34ab6fc74dad87467'
ICARUS_RESTART_TREE='9ad37de97e160aead6602351b54c43608086a006'
ICARUS_RESTART_PY="$PWD/.venv/Scripts/python.exe"
test -d "$ICARUS_STATE"
test -x "$ICARUS_RESTART_PY"
test -f "$ICARUS_STATE/current-nq-restart-capture.json"

if test -n "$(git status --porcelain=v1 --untracked-files=all)"; then
  printf '%s\n' 'STOP: this source checkout has local changes. Preserve them before updating.' >&2
  exit 1
fi

"$ICARUS_RESTART_PY" - "$ICARUS_STATE" <<'PY'
import socket, sys
from pathlib import Path
from icarus_engine.process_identity import identity
root = Path(sys.argv[1])
for name in ("plant", "engine", "bridge"):
    path = root / "run" / (name + ".pid")
    if path.exists():
        try:
            pid = int(path.read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            raise SystemExit("STOP: cannot verify " + str(path))
        if identity(pid) is not False:
            raise SystemExit(f"STOP: {name} PID {pid} is still running or unverified. Stop its owning launcher with Ctrl+C before retrying.")
with socket.socket() as probe:
    try:
        probe.bind(("127.0.0.1", 8791))
    except OSError:
        raise SystemExit("STOP: port 8791 is still occupied. Stop its owning launcher with Ctrl+C before retrying.")
print("Old plant/engine stopped; port 8791 is available.", flush=True)
PY

ICARUS_RESTART_PREVIOUS="$(git rev-parse HEAD)"
ICARUS_RESTART_BACKUP="${ICARUS_STATE}.backup-$(date -u +%Y%m%dT%H%M%SZ)"
test ! -e "$ICARUS_RESTART_BACKUP"
test ! -e "${ICARUS_RESTART_BACKUP}.source-revision.txt"
printf "Backing up private state to %s — wait for the copy to finish.\n" "$ICARUS_RESTART_BACKUP"
cp -a "$ICARUS_STATE" "$ICARUS_RESTART_BACKUP"
printf "%s\n" "$ICARUS_RESTART_PREVIOUS" > "${ICARUS_RESTART_BACKUP}.source-revision.txt"

if ! git fetch --quiet origin prime/as-is-restart-20261022 >/dev/null 2>&1; then
  printf '%s\n' 'STOP: Git fetch failed. Source was not switched.' >&2
  exit 1
fi
test "$(git rev-parse 'FETCH_HEAD^{commit}')" = "$ICARUS_RESTART_REV"
test "$(git rev-parse "${ICARUS_RESTART_REV}^{tree}")" = "$ICARUS_RESTART_TREE"
test -z "$(git status --porcelain=v1 --untracked-files=all)"
git switch --no-overwrite-ignore --detach "$ICARUS_RESTART_REV"
test "$(git rev-parse HEAD)" = "$ICARUS_RESTART_REV"
test "$(git rev-parse 'HEAD^{tree}')" = "$ICARUS_RESTART_TREE"

"$ICARUS_RESTART_PY" -m icarus_engine.restart_defaults --root "$ICARUS_STATE" --capture-file "$ICARUS_STATE/current-nq-restart-capture.json" --apply
"$ICARUS_RESTART_PY" -m icarus_engine.restart_defaults --root "$ICARUS_STATE" --capture-file "$ICARUS_STATE/current-nq-restart-capture.json" --verify
printf '%s\n' 'Verified NQ defaults for all assets; ETHUSD and SOLUSD: 30-minute, RTH disabled, 25 contracts.'

export ICARUS_MAIN_ASSETS='NQ,BTC,MNQ,MES,ES,YM,MYM,RTY,M2K,GC,MGC,SI,SIL,PL,PA,MBT,ETH,SOL,CL,NG,HG,6E,6J,6B,6A,ZN,ZB,BTCF,MHG,MCL,MNG,M6E,MJY,M6B,M6A'
printf "Verified source: %s\nPrivate state: %s\nBackup: %s\nLaunching — keep this window open.\n" "$ICARUS_RESTART_REV" "$ICARUS_STATE" "$ICARUS_RESTART_BACKUP"
trap - ERR
ICARUS_PYTHON="$ICARUS_RESTART_PY" bash scripts/start-as-is.sh --root "$ICARUS_STATE" --feed yahoo --assets "$ICARUS_MAIN_ASSETS"
)
```

Wait for the backup to finish. It may be large and contains private configuration, journals, history and credentials; keep it local. The adjacent `.source-revision.txt` records the prior source. The migration also records a private configuration backup and receipt under `ROOT/audit/restart-defaults/`.

The working existing `.venv` needs no dependency reinstall: these changes add no runtime dependency. If setup never completed, use this pinned source's `scripts/start-as-is.sh` with `--setup`; do not repeat the old bare editable-install command. The launcher retains the scoped Python 3.10 distutils repair. Do not set `SETUPTOOLS_USE_DISTUTILS` globally.

**Keep the launcher window open and the PC awake.** A guard failure stops the block; preserve the error instead of forcing checkout, cleaning files or deleting PID records.

## 3. Observe the restarted system

Open [Main](http://127.0.0.1:8791/) first. Use **Ctrl+Shift+R** for an existing tab, then open **Subsystems** in navigation.

| View | URL |
| --- | --- |
| Main | http://127.0.0.1:8791/ |
| CC1 | http://127.0.0.1:8791/dashboards/cc1 |
| CC2 | http://127.0.0.1:8791/dashboards/cc2 |
| CC3 | http://127.0.0.1:8791/dashboards/cc3 |
| CC4 | http://127.0.0.1:8791/dashboards/cc4 |
| Connections | http://127.0.0.1:8791/dashboards/connections |

Existing independent CC switches retain their saved desired states. OFF stops that CC's paper workers, native monitoring worker and ordinary selected-page polling. Main stays available. STOPPING means work is still draining; open positions or pending operations can block OFF. The switch does not flatten positions or promise isolation from shared infrastructure.

Confirm the launcher printed the pinned source (first 12 characters), the existing private root and the verified defaults message. Inspect Main NQ Inputs and compare other assets. ETHUSD and SOLUSD must show 30-minute charts, session filtering disabled and quantity 25. Check saved journals, CC selections and normal Main scrolling/clicking.

In a second Git Bash window, use your existing token locally if customized:

```bash
curl --disable --noproxy 127.0.0.1 --max-time 10 --fail --silent --show-error \
  -w '\nHealth HTTP %{http_code}\n' http://127.0.0.1:8791/healthz
curl --disable --noproxy 127.0.0.1 --max-time 15 --fail --silent --show-error \
  -o /dev/null -H "Authorization: Bearer ${ICARUS_TOKEN:-icarus}" \
  -w 'Status HTTP %{http_code}; response %{time_total}s\n' http://127.0.0.1:8791/status/public
```

`/status/public` is the native route; `/api/status` is not. HTTP 200 only proves a responding route. Empty assets or `warm:false` do not prove readiness. Warmup depends on actual available history and feeds. A blank ON dashboard or repeated deadline/expiry after 30 seconds needs the preceding startup/runtime log, not indefinite waiting: `tail -n 80 'C:/Users/tripl/Icarus/logs/engine.log'`.

Subsystems should show actual observations, a NEXUS plane hash and AION receipts with chain verification at observation. Unknown provider SLOs are expected. These are local monitoring receipts, not recovered market bars, reconstructed open positions or provider qualification. Both native cores are pinned to Divine Providence `27ae69c593ede3019957100cd401625bd2424f43` with exact source provenance.

The 35-symbol catalog is not verified fresh feed coverage. Yahoo is delayed paper/research data; configured auxiliary providers retain their own access requirements. A past error count differs from an active reported source error. Inspect current ages and errors. No order bridge or live broker arming is requested.

## Verification and next step

Fresh local verification at this exact runtime tree: **4152 passed, 128 skipped, 111 subtests passed (468.28s)**. Optional browser checks ran separately: **107 real Chromium checks passed (437.29s)**. Actual Python 3.10 preparation/application and authenticated NQ capture are included in 18 settings checks. Auth/scope integration passed 96 checks; final publication-writer audit passed 69 checks. Main/CC configuration coverage passed 239 checks with 4 skips. Independent review reproduced and verified accounting-clock coherence. The Python3.10 wheel contains seven byte-exact final runtime modules and all four pinned native cores (wheel SHA256 `f084e5357081f05304bfc3520596759a067f407722a699a42f5f627ae9b4beb2`).

**Hosted checks for this exact head are still running, including Windows. No final Windows pass is claimed yet.** See [this head's checks](https://github.com/reppiks490/Icarus/commit/3122d349524fbce803970dc34ab6fc74dad87467/checks). The preceding native build `211592f2515d`'s ten hosted workflows passed; those are historical proof, not this head's Windows results.

Intermediate failed integration tests and deliberately interrupted runs remain recorded in the coordination handoff. They are not final passes. The final full and browser suites ran against the frozen tree named above.

The owner PC, real provider freshness/entitlement and sustained uptime still require observation. No software test promises zero future outages. Full-system readiness remains NO_GO; execution and production-decision authority remain false. No paid data, collectors, training, scheduler changes or runtime merge into main are added.

After the owner confirms this PC restart is working, reconnect the phone using its existing access setup. Phone/network access is not changed during this restart delivery.

For rollback, Ctrl+C the owning launcher, preserve the newest private state, and switch without force to the source recorded beside the backup. Do not casually overwrite newer journals with an older backup. `icarus_plant stop` is not a graceful Windows substitute: its implementation force-kills a process tree.
