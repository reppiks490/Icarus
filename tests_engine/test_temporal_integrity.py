# Claude (Opus 5.5) — 2026-09-27. TIME invariants (docs/empirical_qualification/TEST_PLAN.md): no label reads a
# price from the next slice, a row's features never read a later bar, and the candidate audit only counts
# candidate bars that had closed when the execution decision was made.
import random

from icarus_engine.audit.run import score_pair
from icarus_engine.events.calendar import seed_events
from icarus_engine.trainers.dataset import attach_labels, walk_slices

T0 = 1_700_000_000


def _bars(closes, t0=T0, step=60):
    out = []
    for i, c in enumerate(closes):
        o = closes[i - 1] if i else c
        out.append({"ts": t0 + i * step, "open": o, "high": max(o, c) + 0.1, "low": min(o, c) - 0.1,
                    "close": c, "tide_long": 0.0, "tide_short": 0.0})
    return out


def _walk(n=400, seed=1):
    rng = random.Random(seed)
    px, closes = 100.0, []
    for _ in range(n):
        px += rng.choice((1.0, -1.0, 0.5, -0.5))
        closes.append(px)
    return _bars(closes)


# ---- trainer rows ----------------------------------------------------------------------------------

def test_label_is_the_next_bar():
    bars = _walk(50)
    rows = attach_labels(bars, "clock_minutes")
    at = {b["ts"]: i for i, b in enumerate(bars)}
    assert rows and all(r["label_ts"] == bars[at[r["ts"]] + 1]["ts"] for r in rows)


def test_train_label_crossing_validation_start_is_purged():
    rows = attach_labels(_walk(), "clock_minutes")
    tr, va, _ = walk_slices(len(rows))
    assert max(r["label_ts"] for r in rows[tr[0]:tr[1]]) < rows[va[0]]["ts"]


def test_validation_label_crossing_holdout_start_is_purged():
    rows = attach_labels(_walk(), "clock_minutes")
    _, va, ho = walk_slices(len(rows))
    assert max(r["label_ts"] for r in rows[va[0]:va[1]]) < rows[ho[0]]["ts"]


def test_features_never_read_a_later_bar():
    bars = _walk(120)
    k = 70
    shaken = bars[:k + 1] + [dict(b, close=b["close"] + 50, high=b["high"] + 50) for b in bars[k + 1:]]
    before = {r["ts"]: r["x"] for r in attach_labels(bars, "clock_minutes")}
    after = {r["ts"]: r["x"] for r in attach_labels(shaken, "clock_minutes")}
    kept = [ts for ts in before if ts <= bars[k]["ts"]]
    assert len(kept) > 50 and all(before[ts] == after[ts] for ts in kept)


# ---- candidate audit -------------------------------------------------------------------------------

def test_completed_before_uses_only_closed_candidate_bars():
    from icarus_engine.audit.lead import completed_before
    cand = [{"ts": 0}, {"ts": 3600}, {"ts": 7200}]
    assert completed_before(cand, 3599) is None       # bar 0 closes when bar 1 opens
    assert completed_before(cand, 3600) == 0
    assert completed_before(cand, 7199) == 0
    assert completed_before(cand, 7200) == 1
    assert completed_before(cand, 10 ** 9) == 1       # the last bar has no close we can see


def test_same_interval_agreement_is_not_predictive():
    ex = _bars([100.0 + (i % 2) for i in range(300)])     # up, down, up, down
    r = score_pair(ex, ex, seed_events(), "AAPL", "NQ", cand_floored=False)     # declared 1m candles
    assert r["lead"] == "strict" and r["overlap"] >= 200
    assert r["sign_agree"] == 0.0                          # the same series never predicts its own reversal


def test_a_candidate_that_moved_first_can_lead():
    rng = random.Random(3)
    moves = [rng.choice((1.0, -1.0)) for _ in range(300)]
    cand, ex = [100.0], [100.0, 100.0]
    for m in moves[1:]:
        cand.append(cand[-1] + m)      # candidate bar k moves by m
        ex.append(ex[-1] + m)          # execution bar k+1 moves by the same m, one bar later
    r = score_pair(_bars(ex), _bars(cand), seed_events(), "AAPL", "NQ", cand_floored=False)   # declared 1m candles
    assert r["overlap"] >= 200 and r["sign_agree"] == 1.0


def test_a_candidate_bar_still_open_at_the_decision_is_never_read():
    ex = _bars([100.0 + i for i in range(300)])                     # decisions at minutes 1..299
    closes = [200.0, 190.0, 195.0, 185.0, 180.0, 170.0]
    hourly = _bars(closes, step=3600)
    moved = _bars(closes[:4] + [999.0] + closes[5:], step=3600)     # hour 4 only closes at minute 300
    a = score_pair(ex, hourly, seed_events(), "AAPL", "NQ")
    b = score_pair(ex, moved, seed_events(), "AAPL", "NQ")
    assert a["overlap"] > 0
    assert (a["overlap"], a["sign_agree"]) == (b["overlap"], b["sign_agree"])


def test_macro_agreement_counts_only_released_events():
    ex = _bars([100.0 + i for i in range(300)])
    future = [{"ts": ex[-1]["ts"] + 3600, "name": "FOMC", "kind": "fomc", "scope": "all",
               "source": "test", "surprise": None}]
    r = score_pair(ex, ex, future, "AAPL", "NQ")
    assert r["macro_overlap"] == 0
    past = [dict(future[0], ts=ex[100]["ts"])]
    assert score_pair(ex, ex, past, "AAPL", "NQ")["macro_overlap"] > 0
