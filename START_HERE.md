# START HERE — current ICARUS paper startup and all operator commands

**Use this page for the current recovery version.** The updated main and CC1–CC4 dashboards are on branch **`icarus1/restart-readiness-20261020`**, [PR #462](https://github.com/reppiks490/Icarus/pull/462). Pulling an older `main` does not install this work. This is a usable **as-is paper launch**, not certification that every subsystem, account or the reported accuracy regression is repaired. Live broker execution remains disabled.

The local Python engine and dashboards do not require an active ChatGPT subscription. Keep the PC awake and the launcher window open. External data services and optional model APIs retain their own availability, entitlement and credit requirements. Missing runtime adapters remain visibly unavailable.

## 1. Stop your existing instance and preserve its data

Before stopping, inspect and privately record any open paper positions in the existing dashboards. Closed-journal/configuration persistence is tested; restoration of every open in-memory position is not certified. Do not flatten positions merely to make a restart look successful.

On your PC, press **Ctrl+C in the Git Bash/terminal window that currently runs ICARUS**. Let it finish. Do not kill arbitrary Python processes, delete PID files, flatten positions, reset settings or erase databases to refresh a panel.

Open Git Bash **inside your existing Icarus checkout**. These commands retain its data root and make a private backup outside it. `ICARUS_HOME`, if already set, must point to the actual existing data directory. Verify the printed path before continuing.

```bash
cd "$(git rev-parse --show-toplevel)"
export ICARUS_OLD_SOURCE="$PWD"
export ICARUS_STATE="$(cygpath -am "${ICARUS_HOME:-$PWD}")"
export ICARUS_HOME="$ICARUS_STATE"
printf 'Existing private data: %s\n' "$ICARUS_STATE"
export ICARUS_BACKUP="${ICARUS_STATE}.backup-$(date +%Y%m%d-%H%M%S)"
cp -a "$ICARUS_STATE" "$ICARUS_BACKUP"
```

Wait for the copy to finish. It includes saved inputs, private settings, journals, history and credentials, so keep it local. Copy **after stopping** so SQLite journals and sidecars form a consistent backup. Large histories can make this copy large. On Linux/macOS replace the `cygpath` command with an absolute native data path.

## 2. Obtain the updated code without replacing the old checkout

```bash
git fetch origin
git worktree add --detach ../Icarus-as-is origin/icarus1/restart-readiness-20261020
cd ../Icarus-as-is
git rev-parse HEAD
```

If `Icarus-as-is` already exists, use its existing checkout; do not delete it or force the command. To update that checkout later, first stop its running launcher, then run:

```bash
cd ../Icarus-as-is
git status --short
git fetch origin
git switch --detach origin/icarus1/restart-readiness-20261020
```

Git refuses conflicting local edits; preserve them. Do not use `git reset --hard`, `git clean`, or overwrite saved data. The original source checkout and backup remain available for rollback.

## 3. Install once and open the current dashboard

Install 64-bit Python **3.11 or 3.12** if Python is missing. This launcher creates a separate `.venv` in the new source checkout, installs its declared runtime extras, verifies package origins and prints the actual Python, source revision and data directory. It refuses an occupied port before starting and never kills the other process.

Choose the **main** asset list explicitly. This example selects six paper assets; substitute your previous main list if it differed. Main startup arguments were not historically saved automatically. Existing CC1–CC4 selections and per-workspace settings load independently from the same private data root; this launcher does not expand them.

```bash
export ICARUS_MAIN_ASSETS='NQ,ES,YM,GC,SI,BTC'
bash scripts/start-as-is.sh --setup --root "$ICARUS_STATE" --feed yahoo --assets "$ICARUS_MAIN_ASSETS"
```

The browser opens when the engine answers. **Leave this Git Bash window open.** Subsequent starts use the same command **without `--setup`**. Press Ctrl+C for a normal owned shutdown, then start again with the same root/feed/asset list.

Feed choice is deliberate:

| Feed | Command change | What it means |
| --- | --- | --- |
| Yahoo/Coinbase paper | `--feed yahoo` | Existing public network routing; futures are delayed research/paper data. No futures account is connected by this choice. |
| Your existing local history | `--feed file` | File-fed paper operation. Missing history stays missing; old bars are not live ticks. |
| Configured Databento | `--feed databento --assets NQ,ES,YM,GC,SI` | Only with your already configured entitled account, SDK and appropriate contracts. Can acquire history/start subscriptions; never selected implicitly by this launcher. |

Do not call the file-fed option a connected live feed. A TradingView subscription does not automatically supply this Python engine. The paid-feed command is an optional operator choice, not a request to purchase access. The startup command omits the order bridge. Inputs and presets are editable in each dashboard; this guide does not retune your strategy or claim an accuracy improvement.

The default local dashboard token is `icarus`. If you previously chose a custom token, use that same value through your local `ICARUS_TOKEN` environment variable before launching; do not publish it. Use the browser's **Token** control to authenticate. Existing private provider configuration stays in the selected data root; do not copy credentials into GitHub.

## 4. Save a one-command start for the next 30 days

In the new checkout, after choosing and confirming your root and main assets, create a local shortcut. If `~/icarus-start.sh` already exists, choose another filename instead of overwriting it.

```bash
if [ ! -e "$HOME/icarus-start.sh" ]; then
  {
    printf '#!/usr/bin/env bash\n'
    printf 'export ICARUS_HOME=%q\n' "$ICARUS_STATE"
    printf 'exec bash %q --root %q --feed yahoo --assets %q\n' "$PWD/scripts/start-as-is.sh" "$ICARUS_STATE" "$ICARUS_MAIN_ASSETS"
  } > "$HOME/icarus-start.sh"
fi
```

Now your Git Bash start command, from any folder, is:

```bash
bash ~/icarus-start.sh
```

It runs local code and remembers the chosen root/assets/feed; it does not depend on this chat. Edit the shortcut's explicit feed if you selected file mode. Preserve your custom token environment if applicable. Reopen it after a PC reboot. Closing ChatGPT does not stop the engine; closing the launcher window, sleeping or shutting down the PC does.

## 5. Open and navigate all dashboards

| View | URL |
| --- | --- |
| Main trading dashboard | http://127.0.0.1:8791/ |
| CC1 | http://127.0.0.1:8791/dashboards/cc1 |
| CC2 | http://127.0.0.1:8791/dashboards/cc2 |
| CC3 | http://127.0.0.1:8791/dashboards/cc3 |
| CC4 | http://127.0.0.1:8791/dashboards/cc4 |
| Shared Connections inventory | http://127.0.0.1:8791/dashboards/connections |

All five trading views use the same renderer. Check the workspace badge before changing inputs or using controls. **Command Center** selects ledger links; **Inputs** configures that workspace; **Performance** reads its persisted journal; **Evidence & catalog** shows shared provenance and selected consumer receipts. The four-ledger P&L badge is separate from the current engine-epoch replay display. Partial or missing valuations stay unavailable rather than becoming zero.

Connections inventory does not mean a futures/prop-firm account is connected. Unavailable panels are unfinished adapters, not proof of running services. `LIVE`/`ARMED` in the emulator UI describes local paper strategy state, not broker authorization.

## 6. Status, exports, configuration and diagnostics

Open a **second Git Bash window** in `Icarus-as-is`. Set `ICARUS_STATE` to the exact directory printed by the launcher, then:

```bash
export ICARUS_STATE='C:/replace/with/the/exact/existing/data/root'
export ICARUS_HOME="$ICARUS_STATE"
PYTHON='.venv/Scripts/python.exe'
"$PYTHON" -m icarus_plant status --root "$ICARUS_STATE" --engine-port 8791 --json
"$PYTHON" -m icarus_engine.workspace_tools status --port 8791
"$PYTHON" -m icarus_engine.workspace_tools controls --port 8791
"$PYTHON" -m icarus_engine.cli assets
"$PYTHON" -m icarus_engine.cli inputs --asset NQ
"$PYTHON" -m icarus_engine.cli doctor --json
```

On Linux/macOS use `PYTHON='.venv/bin/python'`. The doctor inspects local configuration; its output is private diagnostics, not a restart certificate. A health response alone does not verify feeds, warmup, all panels or accounting. Keep token/credential values out of shared logs.

Export persisted paper records without changing positions:

```bash
"$PYTHON" -m icarus_engine.cli paper-export --db "$ICARUS_STATE/icarus_engine.db" --out "$ICARUS_STATE/main-paper-trades.csv"
"$PYTHON" -m icarus_engine.cli paper-export --db "$ICARUS_STATE/command_centers/cc1.sqlite3" --out "$ICARUS_STATE/cc1-paper-trades.csv"
```

Repeat the second command for `cc2`, `cc3`, `cc4`, or use each dashboard's scoped download. These are paper records, not broker statements. Only export a journal that exists at the verified root.

Existing-history comparison and import commands:

```bash
ICARUS_FEED=file "$PYTHON" -m icarus_engine.cli backtest --assets NQ --tf 20
ICARUS_FEED=file "$PYTHON" -m icarus_engine.cli parity --asset NQ --tf 20 --tv-csv 'C:/path/to/List of Trades.csv'
"$PYTHON" -m icarus_engine.cli ingest-bars 'C:/path/to/NQ1!.csv' --symbol NQ --tz America/New_York
```

Backtest/parity may use the selected feed if required history is missing; use `ICARUS_FEED=file` for file-only comparison. Ingestion deliberately changes local history. Do not import synthetic samples, substitute full-size series for missing micros, or compare accuracy across different inputs/configuration.

Full built-in syntax and additional commands:

```bash
"$PYTHON" -m icarus_plant --help
"$PYTHON" -m icarus_plant start --help
"$PYTHON" -m icarus_engine.cli --help
"$PYTHON" -m icarus_engine.cli run --help
"$PYTHON" -m icarus_engine.workspace_tools --help
"$PYTHON" -m icarus_agent --help
"$PYTHON" -m icarus_control --help
```

`workspace_tools expand` deliberately changes asset selections; its old `restart` helper forces file mode and a canonical main universe. Neither is the preserve-as-is command above. Earlier [COMMANDS.md](COMMANDS.md), [SETUP.md](SETUP.md) and launcher files remain historical references.

Optional engineering verification, after installing test dependencies (this is not required for ordinary startup):

```bash
"$PYTHON" -m pip install -e '.[dev,bridge,ml,databento]'
"$PYTHON" -m pytest tests_engine tests/test_provider_corpus_intake.py -q
```

## 7. Troubleshooting, rollback and continuity

- **Port occupied:** return to the existing owning window and Ctrl+C. If you want an independent instance, use a different port **and a different private data root**; never run two engines against the same journals.
- **Missing dependency/wrong package source:** rerun the launch command with `--setup`. The displayed source must be `Icarus-as-is`; the data root should remain the old private root.
- **Warming/missing prices:** inspect Market Data and logs at `ROOT/logs/engine.log`. File mode needs actual local history; Yahoo is delayed and markets can be closed. Empty history is not a healthy feed. Missing entitlement or missing micros cannot be repaired by restarting panels.
- **Wrong workspace data:** stop, verify the printed root and the badge/URL. Do not reset profiles. Expected files are `ROOT/command_centers/cc1.json` through `cc4.json` and their separate `.sqlite3` journals.
- **Stale input revision:** preserve/review your draft; **Discard edits** explicitly reloads current settings before making a new edit. It discards the local draft.
- **Rollback:** Ctrl+C in the new owning window. Keep the current state for investigation. Use the untouched original source with a **separate copy of the stopped-state backup**, following that version's launcher. Do not overwrite the current journals with older files while a process is running. Backups of legacy profiles also remain private; do not hand-edit schema versions.

Icarus 1's [recovery record](https://github.com/reppiks490/Icarus/blob/icarus1/restart-readiness-20261020/docs/recovery/ICARUS_RECOVERY_STATUS.md) and [coordination bus](https://github.com/reppiks490/icarus-owner-actions/blob/main/coordination/START_HERE.md) retain exact source/test receipts. Icarus 2's stable session is `icarus2-20261020-federation-integration`; its [restart verification and continuation handoff](https://github.com/reppiks490/icarus-owner-actions/blob/main/coordination/handoffs/icarus2-restart-verification-20261021.md) preserves independent work. It should continue from the final published recovery head, preserve private state, and prioritize missing operating adapters, Brain event coverage, freshness and the matched accuracy investigation. It must not overwrite this branch from an old PR or enable live orders.

**Full-system readiness remains NO_GO.** This runbook delivers an as-is paper startup path. Owner-PC execution, all provider consumers, real futures/prop-firm operation, accuracy recovery, long-running stability and every subsystem's operating connection remain unverified. The cloud session cannot execute commands on your PC; the commands above are the PC handoff.
