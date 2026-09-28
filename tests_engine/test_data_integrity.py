# Claude (Opus 5.5) — 2026-09-27. DATA gate (docs/empirical_qualification): canonical timestamps, exact
# timeframe identity, duplicate and OHLC integrity, and a manifest that travels with every trainer artifact.
import pytest

from icarus_engine.feeds.bars import detect_granularity
from icarus_engine.pine.timeframe import Bar
from icarus_engine.trainers.dataset import load_ohlc
from icarus_engine.trainers.families import family_for
from icarus_engine.trainers.run import file_hash, train_file, train_xgb_file

T0 = 1_700_000_000


def _csv(tmp_path, lines, name="s.csv"):
    p = tmp_path / name
    p.write_text("time,open,high,low,close\n" + "\n".join(lines) + "\n")
    return p


def _rows(n=20, t0=T0, step=60):
    return [f"{t0 + i * step},{100 + i},{101 + i},{99 + i},{100.5 + i}" for i in range(n)]


# ---- timestamps --------------------------------------------------------------------------------------

def test_iso_timestamps_with_an_offset_are_read_not_dropped(tmp_path):
    lines = [f"2023-11-14T{22 + i // 60:02d}:{i % 60:02d}:20Z,100,101,99,100.5" for i in range(20)]
    bars = load_ohlc(_csv(tmp_path, lines))
    assert len(bars) == 19 and bars[0]["ts"] == 1699999220          # the last row may still be forming


def test_a_naive_timestamp_is_not_guessed(tmp_path):
    from icarus_engine.trainers.integrity import inspect_ohlc
    bars, m = inspect_ohlc(_csv(tmp_path, _rows() + ["2023-11-14 22:13:20,100,101,99,100.5"]))
    assert m["unparseable_time"] == 1 and m["rows_used"] == 19 and m["status"] == "issues"


# ---- duplicates and OHLC -------------------------------------------------------------------------------

def test_exact_duplicates_are_collapsed(tmp_path):
    from icarus_engine.trainers.integrity import inspect_ohlc
    lines = _rows()
    bars, m = inspect_ohlc(_csv(tmp_path, lines + [lines[5]]))
    assert len(bars) == 19 and m["duplicate_exact"] == 1 and m["status"] == "issues"
    assert len({b["ts"] for b in bars}) == len(bars)


def test_conflicting_duplicates_block_the_file(tmp_path):
    from icarus_engine.trainers.integrity import inspect_ohlc
    lines = _rows()
    p = _csv(tmp_path, lines + [f"{T0 + 5 * 60},105,106,104,104.5"])
    assert inspect_ohlc(p)[1]["status"] == "blocked" and inspect_ohlc(p)[1]["duplicate_conflict"] == 1
    with pytest.raises(ValueError, match="conflict"):
        load_ohlc(p)


def test_impossible_ohlc_blocks_the_file(tmp_path):
    from icarus_engine.trainers.integrity import inspect_ohlc
    p = _csv(tmp_path, _rows() + [f"{T0 + 30 * 60},100,98,99,100"])       # high below low
    m = inspect_ohlc(p)[1]
    assert m["status"] == "blocked" and m["invalid_ohlc"] == 1
    with pytest.raises(ValueError, match="OHLC"):
        load_ohlc(p)


# ---- manifest --------------------------------------------------------------------------------------------

def test_manifest_identifies_the_file_and_its_rows(tmp_path):
    from icarus_engine.trainers.integrity import inspect_ohlc
    lines = _rows()
    a = _csv(tmp_path, lines, "a.csv")
    b = _csv(tmp_path, lines[::-1], "b.csv")                                 # same rows, reversed order
    ma, mb = inspect_ohlc(a)[1], inspect_ohlc(b)[1]
    assert ma["raw_sha256"] == file_hash(a) and ma["raw_sha256"] != mb["raw_sha256"]
    assert ma["canonical_rows_sha256"] == mb["canonical_rows_sha256"]
    assert ma["status"] == "clean" and mb["out_of_order"] == 19 and ma["out_of_order"] == 0
    assert (ma["rows_total"], ma["rows_used"], ma["first_ts"], ma["last_ts"], ma["median_step"]) == \
        (20, 19, T0, T0 + 18 * 60, 60)


def test_trainers_report_a_blocked_file_instead_of_crashing(tmp_path):
    lines = _rows(500)
    p = _csv(tmp_path, lines + [f"{T0 + 5 * 60},105,106,104,104.5"])
    for r in (train_file(p, "minutes", "ohlc", "NQ"),
              train_xgb_file(p, "minutes", "ohlc", "NQ", out=tmp_path / "x.json", ledger=tmp_path / "l.sqlite3")):
        assert r["status"] == "blocked" and r["execution_authorized"] is False
        assert r["dataset_manifest"]["duplicate_conflict"] == 1
    assert not (tmp_path / "x.json").exists()


def test_fitted_artifacts_carry_the_dataset_manifest(tmp_path):
    lines, px = [], 100.0
    for i in range(700):
        step = 1 if (i // 8) % 2 == 0 else -1
        lines.append(f"{T0 + i * 60},{px},{max(px, px + step)},{min(px, px + step)},{px + step}")
        px += step
    p = _csv(tmp_path, lines)
    r = train_xgb_file(p, "minutes", "ohlc", "NQ", out=tmp_path / "x.json", ledger=tmp_path / "l.sqlite3")
    assert r["status"] == "fitted" and r["dataset_manifest"]["raw_sha256"] == file_hash(p)
    assert r["dataset_manifest"]["status"] == "clean"
    assert train_file(p, "minutes", "ohlc", "NQ")["dataset_manifest"]["rows_used"] == 699


# ---- timeframe identity -------------------------------------------------------------------------------

def test_monthly_is_not_minutes():
    assert family_for("1m") == "clock_minutes"
    for monthly in ("1M", "M", "3M", "12M"):
        with pytest.raises(ValueError, match="monthly"):
            family_for(monthly)


def _series(step, n=40):
    return [Bar(T0 + i * step, 1, 1, 1, 1, 1) for i in range(n)]


def test_granularity_keeps_an_exact_uncommon_interval():
    assert detect_granularity(_series(3600)) == 3600
    assert detect_granularity(_series(3660)) == 3660            # 61 minutes is not 60 minutes
    assert detect_granularity(_series(604800)) == 604800        # weekly is not daily
    assert detect_granularity(_series(3601)) == 3600            # clock jitter still snaps


def test_audit_cli_refuses_a_blocked_file(tmp_path, capsys):
    import json
    from icarus_engine.audit.__main__ import main
    good = _csv(tmp_path, _rows(300), "good.csv")
    bad = _csv(tmp_path, _rows(300) + [f"{T0 + 5 * 60},105,106,104,104.5"], "bad.csv")
    assert main(["--exec", str(bad), "--cand", str(good), "--future", "NQ", "--asset", "AAPL"]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "blocked" and "conflict" in out["reason"] and out["execution_authorized"] is False
