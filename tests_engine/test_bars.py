# Grok (xAI) — 2026-09-20. Whole file. Covers ingest-bars / FileFeed / holiday_coverage / CSV warmup.
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
    HistoryHub,
    _hub_symbol,
    detect_granularity,
    file_feed_mode,
    find_history,
    merge_bars,
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


def test_filefeed_reloads_on_mtime(tmp_path):
    p = tmp_path / "NQ_1m.csv"
    write_canonical(str(p), [Bar(ET_0930, 1, 2, 0.5, 1.5, 1)])
    feed = FileFeed.from_csv(str(p))
    assert feed.ticker("NQ") == 1.5
    write_canonical(str(p), [
        Bar(ET_0930, 1, 2, 0.5, 1.5, 1),
        Bar(ET_0930 + 60, 2, 3, 1.5, 2.5, 1),
    ])
    os.utime(str(p), (os.path.getatime(p), os.path.getmtime(p) + 1))
    assert feed.ticker("NQ") == 2.5
    assert len(feed.candles("NQ", 60, 0, 2**31 - 1)) == 2


def test_filefeed_does_not_invent_1m_from_20m():
    twenties = [Bar(ET_0930 + 1200 * k, 1, 2, 0.5, 1.5, 1.0 + k) for k in range(4)]
    feed = FileFeed(twenties, mintick=0.25)
    assert feed._granularity == 1200
    assert feed.candles("NQ", 60, 0, 2**31 - 1) == []
    bars, ft, px = feed.recent_ex("NQ", 60)
    assert bars == [] and px == 1.5 and ft == twenties[-1].ts + 1200


def test_hub_symbol_maps_yahoo_and_cme_tickers():
    assert _hub_symbol("NQ=F") == "NQ"
    assert _hub_symbol("NQU26.CME") == "NQ"
    assert _hub_symbol("CME_MINI:NQ1!") == "NQ"
    assert _hub_symbol("NQ") == "NQ"
    assert _hub_symbol("ES=F") == "ES"
    assert _hub_symbol("BTC-USD") == "BTC"


def test_historyhub_reads_nq_equals_f(tmp_path):
    hist = tmp_path / "history"
    hist.mkdir()
    ones = [Bar(ET_0930 + 60 * k, 10 + k, 11 + k, 9 + k, 10.5 + k, 1) for k in range(5)]
    write_canonical(str(hist / "NQ_1m.csv"), ones)
    hub = HistoryHub(str(tmp_path))
    assert hub.ticker("NQ=F") == ones[-1].c
    assert hub.ticker("NQU26.CME") == ones[-1].c
    five = hub.candles("NQ=F", 300, ET_0930, ET_0930 + 600)
    assert len(five) == 1 and five[0].v == 5


def test_find_history_falls_back_to_finest_other_tf(tmp_path):
    hist = tmp_path / "history"
    hist.mkdir()
    (hist / "NQ_5m.csv").write_text("ts,open,high,low,close,volume\n1,1,1,1,1,1\n")
    path, minutes = find_history(str(tmp_path), "NQ", 20)
    assert minutes == 5 and path.endswith("NQ_5m.csv")


def test_warmup_uses_base_dir_not_cwd(tmp_path, monkeypatch):
    hist = tmp_path / "history"
    hist.mkdir()
    rows = ["ts,open,high,low,close,volume"]
    t0 = _from_ny(2026, 9, 14, 9, 30)
    for k in range(20):
        px = 24700.0 + k * 0.25
        rows.append(f"{t0 + 60 * k},{px},{px + 1},{px - 1},{px + 0.25},10")
    (hist / "NQ_1m.csv").write_text("\n".join(rows) + "\n")
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    spec = parse_spec("NQ")
    spec.roll = "none"
    r = AssetRunner(
        RunnerConfig(spec=spec, inputs=Inputs(use_tide=False, use_eod_flat=False), warmup_bars=2, base_dir=str(tmp_path)),
        Journal(":memory:"),
        feeds={"yahoo": _Quiet()},
    )
    r.warmup(now_ts=_from_ny(2026, 9, 14, 10, 0))
    assert r.warm and r.bar_index >= 0
    assert r.bars[0].ts == t0


def test_cli_base_dir_and_journal_honor_icarus_home(tmp_path, monkeypatch):
    from argparse import Namespace
    from icarus_engine.cli import _base_dir, _journal_path
    monkeypatch.setenv("ICARUS_HOME", str(tmp_path))
    assert os.path.samefile(_base_dir(), tmp_path)
    path = _journal_path(Namespace(db=None, cmd="run"))
    assert path == os.path.join(str(tmp_path), "icarus_engine.db")
    assert _journal_path(Namespace(db=None, cmd="backtest")) == ":memory:"
    assert _journal_path(Namespace(db="/tmp/x.db", cmd="run")) == "/tmp/x.db"


def test_file_feed_mode_env(monkeypatch):
    monkeypatch.delenv("ICARUS_FEED", raising=False)
    assert file_feed_mode() is False
    monkeypatch.setenv("ICARUS_FEED", "file")
    assert file_feed_mode() is True
    monkeypatch.setenv("ICARUS_FEED", "offline")
    assert file_feed_mode() is True


def test_merge_bars_unions_by_ts_incoming_wins():
    a = [Bar(ET_0930, 1, 2, 0.5, 1.5, 1), Bar(ET_0930 + 60, 2, 3, 1, 2.5, 1)]
    b = [Bar(ET_0930 + 60, 9, 9, 9, 9, 9), Bar(ET_0930 + 120, 3, 4, 2, 3.5, 1)]
    m = merge_bars(a, b)
    assert [x.ts for x in m] == [ET_0930, ET_0930 + 60, ET_0930 + 120]
    assert m[1].c == 9
    assert merge_bars([], a) == a


def test_ingest_bars_merges_second_dump(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    first = tmp_path / "a.csv"
    first.write_text(
        "time,open,high,low,close,Volume\n"
        "2026-09-14T13:30:00Z,24700,24701,24699,24700.5,4\n",
        encoding="utf-8",
    )
    assert engine_main(["ingest-bars", str(first), "--symbol", "NQ"]) == 0
    second = tmp_path / "b.csv"
    second.write_text(
        "time,open,high,low,close,Volume\n"
        "2026-09-14T13:30:00Z,1,1,1,1,1\n"
        "2026-09-14T13:31:00Z,24700.5,24702,24700,24701,5\n",
        encoding="utf-8",
    )
    assert engine_main(["ingest-bars", str(second), "--symbol", "NQ"]) == 0
    dest = tmp_path / "history" / "NQ_1m.csv"
    bars = parse_ohlcv_csv(dest.read_text())
    assert len(bars) == 2
    assert bars[0].c == 1.0
    assert bars[1].c == 24701
    out = capsys.readouterr().out
    assert "merged" in out

