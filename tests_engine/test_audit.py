# Grok (xAI) — 2026-09-22.
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
    ex = _bars()
    cand = _bars()
    r = score_pair(ex, cand, seed_events(), "AAPL", "NQ")
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
