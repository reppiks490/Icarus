# Grok (xAI) — 2026-09-22. Whole file.
from __future__ import annotations
import json, sqlite3
from pathlib import Path

def losers_from_journal(db_path, events=None):
    path = Path(db_path)
    if not path.is_file():
        return {"status": "skipped", "reason": f"no journal at {path}", "losers": []}
    db = sqlite3.connect(str(path))
    db.row_factory = sqlite3.Row
    try:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        rows = []
        for name in ("trades", "paper"):
            if name in tables:
                rows = [dict(r) for r in db.execute(f"SELECT * FROM {name}")]
                break
    finally:
        db.close()
    losers = []
    for row in rows:
        pnl = row.get("pnl", row.get("profit"))
        try:
            pnl = float(pnl)
        except (TypeError, ValueError):
            continue
        if pnl >= 0:
            continue
        ts = row.get("exit_ts") or row.get("entry_ts") or 0
        rec = {"symbol": row.get("symbol") or row.get("asset"), "pnl": pnl,
               "entry_ts": row.get("entry_ts"), "exit_ts": row.get("exit_ts"),
               "side": row.get("type") or row.get("entry_id") or row.get("side")}
        if events and ts:
            from icarus_engine.events.calendar import event_features
            rec["events"] = event_features(float(ts), events, rec["symbol"] or "")
        losers.append(rec)
    return {"status": "ok", "n_rows": len(rows), "n_losers": len(losers),
            "losers": losers[:500], "execution_authorized": False}

def write_losers(report, dest):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, allow_nan=False))
    return dest
