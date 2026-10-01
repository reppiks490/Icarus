# Claude (Opus 5.5) — 2026-09-27. SPEC.md: "Events: ts_event <= ts_bar only." Trainer rows must never
# see an event (or its surprise) that prints after the bar they describe.
import random

from icarus_engine.events.calendar import event_features, seed_events
from icarus_engine.trainers.dataset import attach_labels

FOMC_2026_09_16 = 1789581600  # 2026-09-16 18:00 UTC, in the seed calendar
HOUR = 3600


def _bars(t0, n, step=20 * 60):
    out, px = [], 100.0
    for i in range(n):
        px += 1.0 if i % 3 else -0.5
        out.append({"ts": t0 + i * step, "open": px - 0.2, "high": px + 0.3,
                    "low": px - 0.3, "close": px, "tide_long": 0.0, "tide_short": 0.0})
    return out


def _event(ts, kind="fomc", surprise=None):
    return {"ts": ts, "name": kind, "kind": kind, "scope": "all", "source": "test", "surprise": surprise}


def test_trainer_rows_before_the_fomc_print_are_not_flagged():
    bars = _bars(FOMC_2026_09_16 - 5 * HOUR, 12)  # 13:00 to 16:40 UTC, all before the 18:00 print
    rows = attach_labels(bars, "clock_minutes")
    assert rows
    assert all(r["ts"] < FOMC_2026_09_16 for r in rows)
    assert [r["x"]["fomc"] for r in rows] == [0.0] * len(rows)
    assert [r["x"]["any_macro"] for r in rows] == [0.0] * len(rows)


def test_trainer_rows_after_the_fomc_print_are_flagged():
    rows = attach_labels(_bars(FOMC_2026_09_16 + 20 * 60, 6), "clock_minutes")
    assert rows and all(r["x"]["fomc"] == 1.0 and r["x"]["any_macro"] == 1.0 for r in rows)


def test_future_events_cannot_change_any_training_row():
    bars = _bars(1_700_000_000, 60)
    base = [_event(1_700_000_000 - 2 * HOUR)]
    rows = attach_labels(bars, "clock_minutes", events=base)
    for i, b in enumerate(bars[:-1]):
        future = base + [_event(b["ts"] + 60, "cpi", 3.0), _event(b["ts"] + 5 * HOUR, "fomc")]
        after = attach_labels(bars, "clock_minutes", events=future)
        k = next(j for j, r in enumerate(rows) if r["ts"] == b["ts"])
        assert after[k] == rows[k], f"bar {i} changed when events after it were added"


def test_asof_features_match_released_events_only():
    from icarus_engine.events.calendar import event_features_asof
    rng = random.Random(7)
    t0 = 1_700_000_000
    kinds = ("fomc", "cpi", "nfp", "pce", "earnings", "geopol", "ppi")
    events = sorted((_event(t0 + rng.randint(-30, 400) * 600, rng.choice(kinds),
                            rng.choice((None, rng.uniform(-2, 2)))) for _ in range(40)),
                    key=lambda e: e["ts"])
    for ts in range(t0, t0 + 400 * 600, 1800):
        feat = event_features_asof(ts, events)
        released = [e for e in events if ts - 6 * HOUR <= e["ts"] <= ts]
        kinds_seen = {e["kind"] for e in released}
        assert feat["event_n"] == len(released)
        assert feat["fomc"] == int("fomc" in kinds_seen)
        assert feat["any_macro"] == int(bool(kinds_seen & {"fomc", "cpi", "ppi", "nfp", "pce", "gdp", "ism"}))
        assert feat["surprise_abs"] == max((abs(e["surprise"]) for e in released
                                            if e["surprise"] is not None), default=0.0)


def test_asof_never_reads_a_future_surprise():
    from icarus_engine.events.calendar import event_features_asof
    ts = 1_700_000_000
    assert event_features_asof(ts, [_event(ts + 1, "cpi", 9.9)])["surprise_abs"] == 0.0
    assert event_features_asof(ts, [_event(ts, "cpi", 9.9)])["surprise_abs"] == 9.9


def test_asof_includes_an_event_stamped_on_the_bar():
    from icarus_engine.events.calendar import event_features_asof
    assert event_features_asof(FOMC_2026_09_16, seed_events())["fomc"] == 1
    assert event_features_asof(FOMC_2026_09_16 - 1, seed_events())["fomc"] == 0


def test_posthoc_window_is_unchanged():
    # Candidate audit keeps the broad window (6h back, 20h ahead). It is post-hoc, never a trainer input.
    assert event_features(FOMC_2026_09_16 - 19 * HOUR, seed_events())["fomc"] == 1
