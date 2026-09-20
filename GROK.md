# Grok (xAI) — ownership map

For **Claude, Astra, and any later agent**. Grep the tree for `Grok (xAI)`.

Astra wrote the original engine, Pine port, emulator, bridge, and tests
(`312ff25`, 2026-09-20). Grok filled the unpaid gaps (PR #1 / `df89e8b`)
and signed every file or block listed here.

Do **not** undo these constraints without the owner asking:

- Do not scrape TradingView.
- Do not invent ticks, queue, or spread.
- A TradingView CME pack is **display**. It does not feed this Python process.
- Do not add Databento without keys.
- Alpaca `NQ1! → QQQ` is a percent-mapped equity proxy, not an NQ fill.

## Files Grok added (whole file)

| File | What |
|---|---|
| `icarus_engine/feeds/bars.py` | TV/generic OHLCV parse, `FileFeed`, `history/` lookup |
| `icarus_engine/doctor.py` | Offline engine doctor |
| `tests_engine/test_bars.py` | Ingest / FileFeed / holiday coverage / CSV warmup |
| `tests_engine/test_doctor.py` | Doctor CLI |
| `tests_engine/test_alert_template.py` | `pine/ALERT_TEMPLATE.json` ↔ bridge parser |
| `DATA.md` | Two-brain data: free vs paid |
| `PARITY.md` | Pine departures A1–A9 / roll / fills |
| `README.md` | Repo entry (this repo had none) |
| `pyproject.toml` | Package + pytest paths + console scripts |
| `.gitignore` | Stop tracking `__pycache__`, `.bak`, `.env`, `history/*.csv` |
| `.github/workflows/test.yml` | pytest CI |
| `history/.gitkeep` | Chart-export drop dir |
| `icarus_bridge/.env.example` | Bridge env, QQQ warning |
| `pine/ALERT_TEMPLATE.json` | TV webhook JSON |
| `pine/README.md` | How to paste it |
| `presets/NQ-20m-ultracoded.json` | Reconstructed from tests (not a TV export) |
| `presets/NQ-10m-original.json` | Same |
| `presets/NQ-20m-ultracoded-0914.json` | CLI default alias |
| `presets/.gitkeep` | |
| `start-engine-background.ps1` | Windows launcher; only live `/healthz` counts as running |
| `GROK.md` | This map |

## Blocks Grok added inside Astra files

| File | Block |
|---|---|
| `icarus_engine/calendar.py` | `holiday_coverage()` |
| `icarus_engine/cli.py` | `ingest-bars`, `doctor` |
| `icarus_engine/runtime.py` | Warm-up prefers `history/{SYM}_1m.csv` then chart-TF; `_warmup_from_csv` uses `parse_ohlcv_csv` |
| `icarus_engine/feeds/__init__.py` | `bars` / FileFeed note in the module docstring |
| `icarus_bridge/cli.py` | Doctor warning: `NQ1! → QQQ` is not CME |

## Still unpaid / not Grok's to fake

Live undisplayed NQ tape, CME non-display, futures-broker fills.
