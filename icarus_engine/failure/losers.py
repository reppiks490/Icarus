# Grok (xAI) — 2026-09-22. Whole file.
from __future__ import annotations
import csv, json, sqlite3
from pathlib import Path

_PNL = ("pnl", "profit", "net_pnl", "realized", "realized_pnl", "pl")
_SYM = ("symbol", "asset", "sym", "ticker")
_SIDE = ("type", "side", "entry_id", "dir")
_ENTRY = ("entry_ts", "entry", "open_ts", "ts_open")
_EXIT = ("exit_ts", "exit", "close_ts", "ts_close", "ts")

def _pick(row, names):
    lower = {str(k).lower(): k for k in row}
    for n in names:
        if n in lower:
            return row[lower[n]]
    return None

def _row_pnl(row):
    v = _pick(row, _PNL)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

def _as_loser(row, events=None):
    pnl = _row_pnl(row)
    if pnl is None or pnl >= 0:
        return None
    ts = _pick(row, _EXIT) or _pick(row, _ENTRY) or 0
    rec = {
        "symbol": _pick(row, _SYM),
        "pnl": pnl,
        "entry_ts": _pick(row, _ENTRY),
        "exit_ts": _pick(row, _EXIT),
        "side": _pick(row, _SIDE),
        "source_keys": sorted(str(k) for k in row.keys()),
    }
    if events and ts:
        from icarus_engine.events.calendar import event_features
        try:
            rec["events"] = event_features(float(ts), events, rec["symbol"] or "")
        except (TypeError, ValueError):
            pass
    return rec

def _from_csv(path: Path, events=None):
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    losers = [r for r in (_as_loser(row, events) for row in rows) if r]
    return rows, losers

def losers_from_journal(db_path, events=None):
    path = Path(db_path)
    if path.suffix.lower() == ".csv" and path.is_file():
        rows, losers = _from_csv(path, events)
        return {"status": "ok", "n_rows": len(rows), "n_losers": len(losers),
                "losers": losers[:500], "table": path.name, "execution_authorized": False}
    if not path.is_file():
        csv_sib = path.with_name("paper-trades.csv")
        if csv_sib.is_file():
            rows, losers = _from_csv(csv_sib, events)
            return {"status": "ok", "n_rows": len(rows), "n_losers": len(losers),
                    "losers": losers[:500], "table": "paper-trades.csv", "execution_authorized": False}
        return {"status": "skipped", "reason": f"no journal at {path}", "losers": []}
    db = sqlite3.connect(str(path))
    db.row_factory = sqlite3.Row
    try:
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        chosen = rows = None
        for name in tables:
            sample = [dict(r) for r in db.execute(f'SELECT * FROM "{name}" LIMIT 5')]
            if sample and any(_row_pnl(r) is not None for r in sample):
                chosen = name
                rows = [dict(r) for r in db.execute(f'SELECT * FROM "{name}"')]
                break
        if chosen is None:
            return {"status": "ok", "n_rows": 0, "n_losers": 0, "losers": [],
                    "tables": tables, "reason": "no table with a pnl column", "execution_authorized": False}
    finally:
        db.close()
    losers = [r for r in (_as_loser(row, events) for row in rows) if r]
    return {"status": "ok", "n_rows": len(rows), "n_losers": len(losers),
            "losers": losers[:500], "table": chosen, "execution_authorized": False}

def write_losers(report, dest):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, allow_nan=False))
    return dest
