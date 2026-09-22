# Grok (xAI) — 2026-09-22.
from icarus_engine.events.calendar import event_features, load_event_csv, seed_events
from icarus_engine.events.candidate import annotate_bar

def test_fomc_seed_hits_sept_2026():
    ev = seed_events()
    assert any(e["kind"] == "fomc" for e in ev)
    # 2026-09-16 18:00 UTC
    ts = 1758045600
    feat = event_features(ts, ev, "NQ")
    assert feat["fomc"] == 1 and feat["any_macro"] == 1

def test_quiet_day_has_no_fomc():
    ev = seed_events()
    feat = event_features(1700000000, ev, "NQ")
    assert feat["fomc"] == 0 and feat["event_n"] == 0

def test_owner_csv(tmp_path):
    p = tmp_path / "macro.csv"
    p.write_text("ts_or_date,name,kind,scope,surprise\n2026-10-15,CPI,cpi,equity,0.2\n")
    rows = load_event_csv(p)
    assert rows[0]["kind"] == "cpi" and rows[0]["surprise"] == 0.2

def test_annotate_bar_keeps_ohlc():
    ev = seed_events()
    bar = {"ts": 1758045600, "open": 1, "high": 2, "low": 1, "close": 1.5, "tide_long": 1, "tide_short": 0}
    out = annotate_bar(bar, ev, asset="NQ")
    assert out["close"] == 1.5 and out["events"]["fomc"] == 1 and out["micro"]["tide"] == 1
