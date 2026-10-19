"""Native source intervals must survive polling without invented finer bars."""
import copy
import gzip
import hashlib
import json
import os
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
        self.quote = 101.0

    def mintick(self, symbol):
        return 0.25

    def ticker(self, symbol):
        return 101.0

    def daily_volume(self, symbol, days=5):
        return 21.0

    def recent_ex(self, symbol, granularity, since_ts=None):
        self.requests.append(granularity)
        return self.rows, self.clock, self.quote


def _runner(tmp_path, feed, chart="5", symbol="NQ"):
    journal = Journal(":memory:")
    portfolio = Portfolio(journal, str(tmp_path), pts_ref_symbol=symbol,
                          feeds={"yahoo": feed, "coinbase": feed})
    spec = apply_chart_config(copy.deepcopy(REGISTRY[symbol]), {"timeframe": chart}, pin=True)
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


def test_workspace_shared_transport_retains_native_five_minute_interval(tmp_path):
    from icarus_engine.paper_workspaces import SharedFeed
    feed = NativeFeed()
    runner, journal = _runner(tmp_path, SharedFeed(feed))
    try:
        runner.poll()
        assert feed.requests == [300]
        assert len(runner.subbars) == 2
        assert all(minutes == 5 for _, minutes in runner.subbars)
    finally:
        journal.close()


def test_unclosed_native_rows_never_supply_a_fallback_mark(tmp_path):
    feed = NativeFeed(clock=START + 240)
    feed.quote = None
    runner, journal = _runner(tmp_path, feed)
    try:
        runner.poll()
        assert runner.last_price is None
        assert runner.last_price_ts == 0
    finally:
        journal.close()


def _corpus(tmp_path, contracts):
    if os.name != "posix":
        pytest.skip("private corpus intake requires POSIX no-follow directory opens")
    from icarus_engine.corpus_intake import CorpusFeed, load_vault_bars
    filename = "databento_mnq_5m.csv.gz"
    rows = ["ts_open,open,high,low,close,volume,instrument_id"]
    for i, contract in enumerate(contracts):
        stamp = datetime.fromtimestamp(START + i * 300, timezone.utc).isoformat()
        rows.append(f"{stamp},100,101,99,100,10,{contract if contract is not None else ''}")
    raw = gzip.compress(("\n".join(rows) + "\n").encode())
    (tmp_path / filename).write_bytes(raw)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"caches": {"bars_primary": {filename: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}}}}))
    clock = (START + len(contracts) * 300 + 1) * 10**9
    return CorpusFeed(load_vault_bars(tmp_path, manifest, "bars_primary", filename,
        source_repo="reppiks490/Icarus-engine", source_commit="a" * 40,
        available_at_ns=clock, asof_ns=clock))


@pytest.mark.parametrize("contracts", [(111, 111, 222, 222), (None, None, None, None)])
def test_native_corpus_cannot_bypass_contract_identity_by_chart_aggregation(tmp_path, contracts):
    feed = _corpus(tmp_path, contracts)
    runner, journal = _runner(tmp_path, feed, "20", "MNQ")
    try:
        runner.poll()
        assert not runner.subbars and not runner.bars
        assert runner.feed_error
    finally:
        journal.close()


def test_single_contract_corpus_still_supplies_strategy_native_bars(tmp_path):
    feed = _corpus(tmp_path, (111, 111, 111, 111))
    runner, journal = _runner(tmp_path, feed, "20", "MNQ")
    try:
        runner.poll()
        assert len(runner.subbars) == 4
        assert not runner.feed_error
    finally:
        journal.close()
