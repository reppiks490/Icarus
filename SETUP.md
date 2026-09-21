# Setup (dummy list)

<!-- Grok (xAI) — 2026-09-20. Whole file. Do this on your PC, not in Grok. -->

You are setting up **Brain B** (the Python engine). The CSV is its market.
Pine alerts / Alpaca QQQ are **Brain A** — skip that tonight.

**Essential is enough** for the Supercharts CSV. You do not need Plus, Premium, or a CME pack to download the file.

## Windows (this is you)

1. Install [Git](https://git-scm.com/download/win) and [Python 3.10+](https://www.python.org/downloads/). Check **Add python.exe to PATH**.
2. Open **PowerShell**:

```powershell
cd $HOME
git clone https://github.com/reppiks490/Icarus.git
cd Icarus
```

Log in as `reppiks490` if GitHub asks (repo is private).

3. Double-click **`start-plant.bat`**  (or in that folder: `.\start-plant.ps1`).

   It installs Icarus, creates `history\drop\`, **opens Explorer** on that folder, and waits.

4. TradingView Supercharts:
   - Symbol `CME_MINI:NQ1!`
   - Timeframe **1 minute**
   - Scroll **left**
   - Top toolbar dropdown → **Download chart data…**
   - Leave the file in **Downloads**, or copy it into the Explorer window (`Icarus\history\drop\`)

The plant **also scans Downloads/Desktop** for chart CSVs (NQ, ES, … only). You do not have to copy if the filename looks like an NQ export.

5. Back in the script window: press Enter.
6. On **that same PC**, browser: `http://127.0.0.1:8791/`  token `icarus`.
7. Leave the script window open. Closing it stops the plant.

New exports: drop another CSV in `history\drop\` while it runs. Bars **merge** (older history is kept).

## If you hate double-click

Same folder, PowerShell:

```powershell
py -3 -m pip install -e .
icarus-plant setup --open
icarus-plant start --assets NQ --offline
```

## Not this

| Place | No |
|---|---|
| This Grok chat | cannot run the plant |
| TradingView Pine / alerts | Brain A, not this tape |
| GitHub website | files live there; the process runs on your PC |
| CME ~$10 pack | display only; does not stream into Python |

## Sanity

```powershell
icarus-plant doctor
icarus-plant status
```
