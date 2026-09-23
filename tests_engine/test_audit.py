# Grok (xAI) — 2026-09-22.
import hashlib
import json

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

def test_score_pair_reports_alignment_as_diagnostic_only():
    r = score_pair(_bars(), _bars(), seed_events(), "AAPL", "NQ")
    assert r["overlap"] >= 200 and r["status"] == "diagnostic"
    assert r["candidate_qualified"] is False
    assert r["execution_authorized"] is False

def test_score_pair_does_not_qualify_short_overlap():
    r = score_pair(_bars(30), _bars(30), seed_events(), "AAPL", "NQ")
    assert r["status"] == "diagnostic" and r["candidate_qualified"] is False

def test_score_pair_ignores_eth_execution():
    r = score_pair(_bars(), _bars(), seed_events(), "AAPL", "ETHUSD")
    assert r["status"] == "ignored"

def test_score_pair_blocks_without_xgb(tmp_path):
    r = score_pair(_bars(), _bars(), seed_events(), "AAPL", "NQ", require_xgb=True,
                   xgb_path=tmp_path / "missing.json")
    assert r["status"] == "blocked"


def test_xgb_gate_requires_native_model_and_exact_source(tmp_path):
    from icarus_engine.trainers.run import training_signature
    from icarus_engine.trainers.xgb import fit_models, validate_artifact

    source = tmp_path / "NQ.csv"
    source.write_text("time,open,high,low,close\n1,1,2,1,2\n", encoding="utf-8")
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    events = seed_events()
    rows = [{"row_index": i, "label_index": i + 1,
             "ts": 1_700_000_000 + i * 60, "label_ts": 1_700_000_060 + i * 60,
             "asset": "NQ", "family": "clock_minutes",
             "y": 1 if i % 5 < 3 else -1,
             "x": {"ret_1": (i % 7 - 3) / 10, "body": (i % 5 - 2) / 10,
                   "vol_20": (i % 11 + 1) / 10}}
            for i in range(360)]
    artifact = fit_models(rows, asset="NQ", family="clock_minutes",
                          num_boost_round=8, early_stopping_rounds=3)
    artifact.update(dataset_sha256=source_sha, training_signature=training_signature(),
                    chart_type="minutes", event_sha256=hashlib.sha256(
                        json.dumps(events, sort_keys=True).encode()).hexdigest(),
                    provenance={"sha256": source_sha, "asset": "NQ",
                                "family": "clock_minutes", "chart_type": "minutes", "interval": "1"})
    assert validate_artifact(artifact, asset="NQ", family="clock_minutes")
    model = tmp_path / "NQ_clock_minutes_xgb.json"
    model.write_text(json.dumps(artifact), encoding="utf-8")
    params = dict(require_xgb=True, xgb_path=model, execution_source=source)
    accepted = score_pair(_bars(), _bars(), events, "AAPL", "NQ", **params)
    assert accepted["status"] == "diagnostic"
    assert accepted["xgb_evidence"]["source_sha256"] == source_sha
    assert accepted["candidate_qualified"] is False

    source.write_text(source.read_text(encoding="utf-8") + "2,2,3,2,3\n", encoding="utf-8")
    assert score_pair(_bars(), _bars(), events, "AAPL", "NQ", **params)["status"] == "blocked"
    source.write_text("time,open,high,low,close\n1,1,2,1,2\n", encoding="utf-8")
    artifact["primary"]["booster_json"] = "{}"
    model.write_text(json.dumps(artifact), encoding="utf-8")
    assert score_pair(_bars(), _bars(), events, "AAPL", "NQ", **params)["status"] == "blocked"

def test_losers_skip_missing_db(tmp_path):
    assert losers_from_journal(tmp_path / "no.db")["status"] == "skipped"

def test_losers_from_csv(tmp_path):
    p = tmp_path / "paper-trades.csv"
    p.write_text("symbol,pnl,exit_ts,side\nNQ,-12.5,1700000000,long\nNQ,8,1700000060,short\n")
    r = losers_from_journal(p)
    assert r["n_losers"] == 1 and r["losers"][0]["pnl"] == -12.5

def test_losers_any_sqlite_table(tmp_path):
    import sqlite3
    dbp = tmp_path / "j.db"
    db = sqlite3.connect(dbp)
    db.execute("CREATE TABLE fills (sym TEXT, realized REAL, ts_close INT)")
    db.execute("INSERT INTO fills VALUES ('NQ', -3.0, 1700000000)")
    db.commit(); db.close()
    r = losers_from_journal(dbp)
    assert r["table"] == "fills" and r["n_losers"] == 1
