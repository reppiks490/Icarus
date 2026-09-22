# Grok (xAI) — 2026-09-22.
from pathlib import Path

from icarus_engine.audit.run import score_pair
from icarus_engine.events.calendar import seed_events
from icarus_engine.failure.losers import losers_from_journal

def _bars(n=250, start=1_700_000_000, step=60, drift=0.1):
    out = []
    px = 100.0
    for i in range(n):
        px += drift
        out.append({"ts": start + i * step, "open": px, "high": px + 0.2, "low": px - 0.2,
                    "close": px, "tide_long": 1.0, "tide_short": 0.0})
    return out

def test_score_pair_eligible_on_aligned_drift():
    r = score_pair(_bars(), _bars(), seed_events(), "AAPL", "NQ")
    assert r["overlap"] >= 200
    assert r["status"] == "eligible"
    assert r["sign_agree"] == 1.0
    assert r["execution_authorized"] is False

def test_score_pair_rejects_short_overlap():
    r = score_pair(_bars(30), _bars(30), seed_events(), "AAPL", "NQ")
    assert r["status"] in ("reject", "eligible_macro_exceeds")
    assert r["overlap"] < 200

def test_losers_skip_missing_db(tmp_path):
    r = losers_from_journal(tmp_path / "no.db")
    assert r["status"] == "skipped"

def test_losers_from_csv(tmp_path):
    p = tmp_path / "paper-trades.csv"
    p.write_text("symbol,pnl,exit_ts,side\nNQ,-12.5,1700000000,long\nNQ,8,1700000060,short\n")
    r = losers_from_journal(p)
    assert r["status"] == "ok" and r["n_losers"] == 1 and r["losers"][0]["pnl"] == -12.5

def test_losers_any_sqlite_table(tmp_path):
    import sqlite3
    dbp = tmp_path / "j.db"
    db = sqlite3.connect(dbp)
    db.execute("CREATE TABLE fills (sym TEXT, realized REAL, ts_close INT)")
    db.execute("INSERT INTO fills VALUES ('NQ', -3.0, 1700000000)")
    db.execute("INSERT INTO fills VALUES ('NQ', 4.0, 1700000060)")
    db.commit(); db.close()
    r = losers_from_journal(dbp)
    assert r["status"] == "ok" and r["table"] == "fills" and r["n_losers"] == 1
