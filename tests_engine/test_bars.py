"""Local OHLCV ingest / FileFeed — no network."""
from __future__ import annotations

import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

from icarus_engine.assets import parse_spec
from icarus_engine.calendar import _from_ny, holiday_coverage
from icarus_engine.cli import main as engine_main
from icarus_engine.feeds.bars import (
    FileFeed,
    detect_granularity,
    find_history,
    parse_ohlcv_csv,
    parse_timestamp,
    write_canonical,
)
from icarus_engine.pine.timeframe import Bar
from icarus_engine.runtime import AssetRunner, Journal, RunnerConfig
from icarus_engine.strategy.inputs import Inputs

NY = ZoneInfo("America/New_York")
ET_0930 = int(datetime(2026, 9, 14, 9, 30, tzinfo=NY).timestamp())


def test_parse_unix_iso_naive_and_millis():
    assert parse_timestamp("1757842200", NY) == 1757842200
    assert parse_timestamp("1757842200000", NY) == 1757842200
    iso = parse_timestamp("2026-09-14T13:30:00Z", NY)
    naive = parse_timestamp("2026-09-14 09:30", NY)
    assert iso == naive == ET_0930
    assert parse_timestamp("09/14/2026 09:30", NY) == ET_0930


def test_parse_tv_export_volume_capital_and_semicolon():
    tv = (
        "time,open,high,low,close,Volume\n"
        "2026-09-14T13:30:00Z,24700.00,24702.50,24699.75,24701.25,12\n"
        "2026-09-14T13:31:00Z,24701.25,24703.00,24700.50,24702.00,8\n"
    )
    bars = parse_ohlcv_csv(tv)
    assert len(bars) == 2
    assert bars[0].ts == ET_0930 and bars[0].o == 24700.00 and bars[0].v == 12
    eu = (
        "time;open;high;low;close;volume\n"
        "2026-09-14 09:30;24700;24702.5;24699.75;24701.25;12\n"
    )
    one = parse_ohlcv_csv(eu)
    assert len(one) == 1 and one[0].ts == ET_0930


def test_zero_volume_kept_and_bad_rows_dropped():
    raw = (
        "ts,open,high,low,close,volume\n"
        f"{ET_0930},1,2,0.5,1.5,0\n"
        "not-a-time,1,2,0.5,1.5,1\n"
        f"{ET_0930 + 60},1,2,0.5,1.5,3\n"
    )
    bars = parse_ohlcv_csv(raw)
    assert [b.v for b in bars] == [0.0, 3.0]


def test_detect_granularity_and_canonical_roundtrip(tmp_path):
    ones = [Bar(ET_0930 + 60 * k, 1, 2, 0.5, 1.5, 1) for k in range(5)]
    assert detect_granularity(ones) == 60
    twenties = [Bar(ET_0930 + 1200 * k, 1, 2, 0.5, 1.5, 1) for k in range(4)]
    assert detect_granularity(twenties) == 1200
    dest = tmp_path / "NQ_1m.csv"
    n = write_canonical(str(dest), ones)
    assert n == 5
    again = parse_ohlcv_csv(dest.read_text())
    assert [b.ts for b in again] == [b.ts for b in ones]


def test_find_history_prefers_1m(tmp_path):
    hist = tmp_path / "history"
    hist.mkdir()
    (hist / "NQ_20m.csv").write_text("ts,open,high,low,close,volume\n1,1,1,1,1,1\n")
    path, minutes = find_history(str(tmp_path), "NQ", 20)
    assert minutes == 20 and path.endswith("NQ_20m.csv")
    (hist / "NQ_1m.csv").write_text("ts,open,high,low,close,volume\n1,1,1,1,1,1\n")
    path, minutes = find_history(str(tmp_path), "NQ", 20)
    assert minutes == 1 and path.endswith("NQ_1m.csv")


def test_filefeed_aggregates_1m_to_5m():
    ones = [Bar(ET_0930 + 60 * k, 10 + k, 11 + k, 9 + k, 10.5 + k, 1) for k in range(5)]
    feed = FileFeed(ones, mintick=0.25)
    five = feed.candles("NQ", 300, ET_0930, ET_0930 + 600)
    assert len(five) == 1
    assert five[0].ts == ET_0930 and five[0].o == 10 and five[0].c == 14.5
    assert five[0].v == 5 and five[0].h == 15 and five[0].l == 9


def test_holiday_coverage_dates():
    assert holiday_coverage("equity") == date(2027, 12, 24)
    assert holiday_coverage("metals") == date(2027, 12, 24)
    assert holiday_coverage("crypto") is None
    assert holiday_coverage("nope") is None


class _Quiet:
    def ticker(self, s):
        return 24700.0

    def candles(self, *a, **k):
        return []

    def daily_volume(self, *a, **k):
        return []


def test_warmup_prefers_1m_history(tmp_path, monkeypatch):
    hist = tmp_path / "history"
    hist.mkdir()
    rows = ["ts,open,high,low,close,volume"]
    t0 = _from_ny(2026, 9, 14, 9, 30)
    for k in range(20):  # one RTH 20m bar
        px = 24700.0 + k * 0.25
        rows.append(f"{t0 + 60 * k},{px},{px + 1},{px - 1},{px + 0.25},10")
    (hist / "NQ_1m.csv").write_text("\n".join(rows) + "\n")
    monkeypatch.chdir(tmp_path)
    spec = parse_spec("NQ")
    spec.roll = "none"
    r = AssetRunner(
        RunnerConfig(spec=spec, inputs=Inputs(use_tide=False, use_eod_flat=False), warmup_bars=2),
        Journal(":memory:"),
        feeds={"yahoo": _Quiet()},
    )
    r.warmup(now_ts=_from_ny(2026, 9, 14, 10, 0))
    assert r.warm
    assert r.bar_index >= 0
    assert r.bars[0].ts == t0


def test_ingest_bars_cli(tmp_path, monkeypatch, capsys):
    src = tmp_path / "tv.csv"
    src.write_text(
        "time,open,high,low,close,Volume\n"
        "2026-09-14T13:30:00Z,24700,24701,24699,24700.5,4\n"
        "2026-09-14T13:31:00Z,24700.5,24702,24700,24701,5\n"
    )
    monkeypatch.chdir(tmp_path)
    rc = engine_main(["ingest-bars", str(src), "--symbol", "NQ1!"])
    assert rc == 0
    dest = tmp_path / "history" / "NQ_1m.csv"
    assert dest.is_file()
    bars = parse_ohlcv_csv(dest.read_text())
    assert len(bars) == 2 and bars[0].ts == ET_0930
    out = capsys.readouterr().out
    assert "NQ" in out and "2 bars" in out
    assert os.path.samefile(dest, tmp_path / "history" / "NQ_1m.csv")
