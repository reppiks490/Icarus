"""Native source intervals must survive polling without invented finer bars."""
import copy
from datetime import datetime, timezone

import pytest

from icarus_engine.assets import REGISTRY, apply_chart_config
from icarus_engine.pine.timeframe import Bar
from icarus_engine.runtime import Journal, Portfolio


START = int(datetime(2026, 10, 12, 13, 30, tzinfo=timezone.utc).timestamp())


class NativeFeed:
    def __init__(self, interval=300, *, clock=None):
        self.native_interval_seconds = interval
        self.requests = []
        self.rows = [Bar(START, 100, 101, 99, 100, 10),
                     Bar(START + 300, 100, 102, 99, 101, 11)]
        self.clock = START + 600 if clock is None else clock

    def mintick(self, symbol):
        return 0.25

    def ticker(self, symbol):
        return 101.0

    def daily_volume(self, symbol, days=5):
        return 21.0

    def recent_ex(self, symbol, granularity, since_ts=None):
        self.requests.append(granularity)
        return self.rows, self.clock, 101.0


def _runner(tmp_path, feed, chart="5"):
    journal = Journal(":memory:")
    portfolio = Portfolio(journal, str(tmp_path), pts_ref_symbol="NQ",
                          feeds={"yahoo": feed, "coinbase": feed})
    spec = apply_chart_config(copy.deepcopy(REGISTRY["NQ"]), {"timeframe": chart}, pin=True)
    runner = portfolio.make_runner(spec)
    assert runner.chart_minutes == int(chart)
    return runner, journal


def test_five_minute_source_is_requested_and_processed_as_five_minutes(tmp_path, monkeypatch):
    feed = NativeFeed()
    runner, journal = _runner(tmp_path, feed)
    seen = []
    original = runner.on_sub_bar
    def capture(bar, sub_minutes, live, **kwargs):
        seen.append((bar.ts, sub_minutes, live))
        return original(bar, sub_minutes, live, **kwargs)
    monkeypatch.setattr(runner, "on_sub_bar", capture)
    try:
        runner.poll()
        assert feed.requests == [300]
        assert seen == [(START, 5, True), (START + 300, 5, True)]
        assert all(minutes == 5 for _, minutes in runner.subbars)
    finally:
        journal.close()


def test_native_bar_is_not_closed_after_just_one_minute(tmp_path):
    feed = NativeFeed(clock=START + 240)
    runner, journal = _runner(tmp_path, feed)
    try:
        runner.poll()
        assert runner.last_sub_ts is None
        assert list(runner.subbars) == []
    finally:
        journal.close()


@pytest.mark.parametrize("interval,chart", [(300, "1"), (300, "2"), (True, "5"), ("300", "5"), (90, "5")])
def test_unusable_native_interval_never_requests_or_fabricates_bars(tmp_path, interval, chart):
    feed = NativeFeed(interval)
    runner, journal = _runner(tmp_path, feed, chart)
    try:
        runner.poll()
        assert feed.requests == []
        assert runner.feed_error
        assert not runner.subbars
    finally:
        journal.close()


def test_unadvertised_feed_preserves_the_existing_one_minute_contract(tmp_path):
    feed = NativeFeed()
    del feed.native_interval_seconds
    runner, journal = _runner(tmp_path, feed)
    try:
        runner.poll()
        assert feed.requests == [60]
        assert all(minutes == 1 for _, minutes in runner.subbars)
    finally:
        journal.close()


def test_retired_runner_rejects_direct_sub_bar_and_poll_mutations(tmp_path):
    feed = NativeFeed()
    runner, journal = _runner(tmp_path, feed)
    runner._removed = True
    try:
        runner.on_sub_bar(feed.rows[0], 5, live=True)
        runner.poll()
        assert runner.last_sub_ts is None
        assert not runner.subbars and not feed.requests
        assert runner.last_poll_ok == 0
    finally:
        journal.close()
