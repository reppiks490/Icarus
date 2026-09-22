# Grok (xAI) — 2026-09-22. First trainer tests. Does not touch Pulse.
from pathlib import Path
import tempfile

from icarus_engine.trainers.families import family_for
from icarus_engine.trainers.dataset import attach_labels, load_ohlc
from icarus_engine.trainers.run import train_file


def _csv(rows):
    p = Path(tempfile.mkdtemp()) / "s.csv"
    p.write_text("time,open,high,low,close\n" + "\n".join(rows) + "\n")
    return p


def test_family_map_clock_and_renko():
    assert family_for("minutes") == "clock_minutes"
    assert family_for("renko") == "renko"
    assert family_for("range") == "range"
    assert family_for("tick") == "tick"


def test_close_only_has_no_family():
    try:
        family_for("minutes", "close_only")
    except ValueError:
        return
    raise AssertionError("close_only must raise")


def test_labels_are_next_bar_on_same_index():
    rows = []
    px, ts = 100.0, 1_700_000_000
    for i in range(12):
        nxt = px + 1
        rows.append(f"{ts+i},{px},{nxt},{px},{nxt}")
        px = nxt
    bars = load_ohlc(_csv(rows))
    lab = attach_labels(bars, "renko")
    assert lab[0]["ts"] == bars[0]["ts"]
    assert lab[0]["y"] == 1


def test_train_file_skips_under_min_rows():
    rows = [f"{1_700_000_000+i},1,1,1,1" for i in range(12)]
    r = train_file(_csv(rows), "renko", "ohlc", "NQ")
    assert r["status"] == "skipped"
    assert r.get("execution_authorized") is not True


def test_train_file_fits_synthetic_walkforward():
    rows = []
    px, ts = 100.0, 1_700_000_000
    for i in range(500):
        step = 1 if (i // 8) % 2 == 0 else -1
        nxt = px + step
        hi, lo = max(px, nxt), min(px, nxt)
        rows.append(f"{ts+i},{px},{hi},{lo},{nxt}")
        px = nxt
    r = train_file(_csv(rows), "renko", "ohlc", "NQ")
    assert r["status"] == "fitted"
    assert r["family"] == "renko"
    assert r["execution_authorized"] is False
    assert r["accuracy_guaranteed"] is False
    assert r["holdout_rows"] >= 10
