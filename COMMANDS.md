# Commands — dummy list (Grok / xAI 2026-09-20)

You are away from the PC. This is every command that was given. Do them **on the Windows PC**, in **PowerShell**. Not on the phone. Not in this Grok chat.

Folder: `C:\Users\tripl\Icarus`

---

## Right now (Brain B is already running)

If the black PowerShell window is still open: **leave it**. Closing it kills the dashboard.

On the **PC** browser (not the phone):

```
http://127.0.0.1:8791/
```

Token: `icarus`

Phone `127.0.0.1` is the phone. It will fail.

Sunday night: **outside RTH**. No live paper trades until **Monday 9:30 AM ET**. Yahoo `NQ=F`, ~10 min late. Not NQ1!. Not CME. Not Alpaca.

---

## If the plant died — bring it back (Yahoo, free)

```powershell
cd C:\Users\tripl\Icarus
git pull
py -3 -m icarus_plant stop
py -3 -m icarus_plant start --assets NQ
```

No `--offline`. Leave that window open.

Same thing, double-click: `start-yahoo.bat`

If `py` is not recognized, use `python` instead of `py -3`.

---

## Paper book CSV (local emulator — not a broker)

**New** PowerShell. Do **not** close the plant window.

```powershell
cd C:\Users\tripl\Icarus
git pull
py -3 -m icarus_engine.cli paper-export
```

File: `C:\Users\tripl\Icarus\paper-trades.csv`

`live=0` = warmup replay (the +$214k). `live=1` = since go-live. Not a broker statement.

Live-only:

```powershell
py -3 -m icarus_engine.cli paper-export --live-only
```

---

## Stop / status

```powershell
cd C:\Users\tripl\Icarus
py -3 -m icarus_plant status
py -3 -m icarus_plant stop
```

---

## Do **not** run these by accident

| Command | Why |
|---|---|
| `icarus-plant start --assets NQ --offline` | FileFeed. Empty unless you have a Plus CSV |
| `icarus-plant` from `C:\Users\tripl` (home) | Not installed there. Must `cd Icarus` first |
| `git clone` Icarus-engine | Wrong repo. Real one is `reppiks490/Icarus` |
| Phone browser → `127.0.0.1` | Wrong machine |
| `ALPACA_PAPER=false` | Live money. Not tonight |

---

## When you have money — Alpaca paper (QQQ, not NQ)

Second PowerShell. Plant stays up.

```powershell
cd C:\Users\tripl\Icarus
py -3 -m pip install -e ".[bridge]"
py -3 -m pip install alpaca-py
copy icarus_bridge\.env.example .env
notepad .env
```

In `.env`: paper keys, `ALPACA_PAPER=true`, real `WEBHOOK_SECRET` and `ADMIN_TOKEN` (not `replace-me`).

```powershell
py -3 -m icarus_bridge doctor
py -3 -m icarus_bridge serve --tunnel ngrok
```

TV alert webhook = the printed `https://…/webhook`  
Body = `pine\ALERT_TEMPLATE.json` with your secret.

Dashboard A: `http://127.0.0.1:8787/` (Alpaca QQQ)  
Dashboard B: `http://127.0.0.1:8791/` (Yahoo NQ engine)

---

## When you have Plus — Supercharts CSV

Essential **cannot** export.

TradingView: `CME_MINI:NQ1!` → **1 minute** → scroll left → Download chart data  
File: `CME_MINI_NQ1!, 1.csv` → `C:\Users\tripl\Icarus\history\drop` or leave in Downloads.

Then optional:

```powershell
py -3 -m icarus_plant stop
py -3 -m icarus_plant start --assets NQ --offline
```

---

## When you have a futures broker — TradersPost or PickMyTrade

Not Icarus commands. Cloud webhook → Tradovate/Rithmic. Actual NQ/MNQ.  
Do **not** point the same TV alert at Icarus-bridge **and** them.  
Full steps: [PAID_NEXT.md](PAID_NEXT.md)

---

## First-time clone (already done on this PC)

```powershell
cd $HOME
git clone https://github.com/reppiks490/Icarus.git
cd Icarus
.\start-plant.bat
```

Wrong: `Icarus-engine`. Right: `Icarus`.

---

Grok (xAI) — 2026-09-20.
