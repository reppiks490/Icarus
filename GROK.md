# Grok (xAI) — ownership map

For **Claude, Astra, and any later agent**. Grep the tree for `Grok (xAI)`.

Astra wrote the original engine, Pine port, emulator, bridge, and tests
(`312ff25`, 2026-09-20). Grok filled the unpaid gaps (PR #1 / `df89e8b`),
signed every file (PR #2), added FOMC 2027 + bridge tests (PR #3), and
built the local paper-trading **plant** (this PR).

Do **not** undo these constraints without the owner asking:

- Do not scrape TradingView.
- Do not invent ticks, queue, or spread.
- A TradingView CME pack is **display**. It does not feed this Python process.
- Do not add Databento without keys.
- Alpaca `NQ1! → QQQ` is a percent-mapped equity proxy, not an NQ fill.
- Do not Docker the engine as the primary deploy: it binds `127.0.0.1` against DNS rebinding.

## Files Grok added (whole file)

| File | What |
|---|---|
| `icarus_engine/feeds/bars.py` | TV/generic OHLCV parse, `FileFeed` (mtime reload), `HistoryHub`, `merge_bars()`, `file_feed_mode()` |
| `icarus_engine/doctor.py` | Offline engine doctor |
| `icarus_plant/__init__.py` | Local plant package |
| `icarus_plant/layout.py` | `ICARUS_HOME` dirs: history/drop, run, logs |
| `icarus_plant/drop.py` | `history/drop/*.csv` → `history/{SYM}_{N}m.csv` (merge by ts) |
| `icarus_plant/supervisor.py` | stdlib process supervisor; `/healthz` on loopback |
| `icarus_plant/cli.py` | `icarus-plant init\|start\|stop\|status\|ingest-drop\|doctor` |
| `icarus_plant/guide.py` | Dummy checklist, `NEXT.txt`, open-drop, preflight |
| `start-plant.ps1` | Windows one-shot: pip, setup --open, start --offline |
| `start-plant.bat` | Double-click wrapper for the ps1 |
| `start-plant.sh` | Unix twin |
| `SETUP.md` | Numbered dummy list (clone → bat → CSV → dashboard) |
| `deploy/icarus-plant.service` | Optional local systemd unit (loopback only) |
| `tests_engine/test_bars.py` | Ingest / FileFeed / holiday coverage / CSV warmup / HistoryHub |
| `tests_engine/test_doctor.py` | Doctor CLI |
| `tests_engine/test_alert_template.py` | `pine/ALERT_TEMPLATE.json` ↔ bridge parser |
| `tests_engine/test_plant.py` | Drop ingest, supervisor spawn/stop, FileFeed-offline Portfolio |
| `DATA.md` | Two-brain data: free vs paid |
| `PARITY.md` | Pine departures A1–A9 / roll / fills |
| `README.md` | Repo entry (this repo had none) |
| `pyproject.toml` | Package + pytest paths + `icarus-engine` / `icarus-bridge` / `icarus-plant` |
| `.gitignore` | Stop tracking `__pycache__`, `.bak`, `.env`, `history/*.csv`, `run/`, `logs/` |
| `.github/workflows/test.yml` | pytest CI |
| `history/.gitkeep` | Chart-export drop dir |
| `history/drop/.gitkeep` | Plant inbox |
| `history/drop/done/.gitkeep` | Ingested originals |
| `icarus_bridge/.env.example` | Bridge env, QQQ warning |
| `pine/ALERT_TEMPLATE.json` | TV webhook JSON |
| `pine/README.md` | How to paste it |
| `presets/NQ-20m-ultracoded.json` | Reconstructed from tests (not a TV export) |
| `presets/NQ-10m-original.json` | Same |
| `presets/NQ-20m-ultracoded-0914.json` | CLI default alias |
| `presets/.gitkeep` | |
| `start-engine-background.ps1` | Windows launcher; only live `/healthz` counts as running |
| `start-engine-background.sh` | Unix twin of the launcher |
| `tests_engine/test_bridge.py` | Bridge mapping / planner / alert parser (no Alpaca) |
| `tests_engine/test_fomc.py` | FOMC 2027 decision days vs Fed press release |
| `GROK.md` | This map |

## Blocks Grok added inside Astra files

| File | Block |
|---|---|
| `icarus_engine/calendar.py` | `holiday_coverage()` |
| `icarus_engine/cli.py` | `ingest-bars` (merge by default, `--replace` wipes), `doctor`, `_base_dir`/`_journal_path` honor `ICARUS_HOME`, `--feed file` |
| `icarus_engine/runtime.py` | Warm-up prefers `history/{SYM}_1m.csv` then chart-TF under `RunnerConfig.base_dir`; `_warmup_from_csv` uses `parse_ohlcv_csv`; `ICARUS_FEED=file` → `HistoryHub`; `roll=none` in file mode |
| `icarus_engine/feeds/__init__.py` | `bars` / FileFeed / HistoryHub note in the module docstring |
| `icarus_engine/strategy/inputs.py` | FOMC 2027 (+ first 2028) *decision* days from federalreserve.gov |
| `icarus_engine/strategy/pine_inputs_meta.json` | matching `fomc_dates` default |
| `icarus_engine/doctor.py` | `fomc_coverage()` + plant drop / `ICARUS_FEED` checks |
| `icarus_bridge/cli.py` | Doctor warning: `NQ1! → QQQ` is not CME |

## Still unpaid / not Grok's to fake

Live undisplayed NQ tape, CME non-display, futures-broker fills.
