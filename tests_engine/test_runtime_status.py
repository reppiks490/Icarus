"""Request-facing runtime reads must never wait for workers or SQLite."""
from copy import deepcopy
import threading
import time
from types import SimpleNamespace

import pytest

from icarus_engine.assets import REGISTRY
from icarus_engine.runtime import Journal, Portfolio
from tests_engine.test_workspace_api import workspace_http  # noqa: F401


@pytest.fixture
def status_portfolio(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_FEED", "file")
    feed = SimpleNamespace(ticker=lambda _symbol: 100.0)
    journal = Journal(":memory:")
    portfolio = Portfolio(journal, str(tmp_path), feeds={"yahoo": feed, "coinbase": feed})
    portfolio.pts_ref_price = 100.0
    runner = portfolio.add_asset(deepcopy(REGISTRY["NQ"]), start=False)
    runner.last_price = 100.0
    runner.last_price_ts = time.time() - 2
    with runner.lock:
        runner.publish_read_views()
    yield portfolio
    journal.close()


def test_nonblocking_summary_only_reads_published_metadata_and_ages_it(status_portfolio, monkeypatch):
    runner = status_portfolio.runners["NQ"]
    published = runner._public_views[0]
    monkeypatch.setattr(runner, "_summary", lambda: pytest.fail("HTTP recomputed worker summary"))
    row = runner.summary(nonblocking=True)
    assert row["price"] == 100.0
    assert row["view_captured_at"] == published[1]
    assert row["price_age"] >= published[0]["price_age"]


def _read_while_journal_busy(journal, read):
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    values, errors = [], []
    def hold():
        with journal._lock:
            entered.set()
            release.wait(5)
    holder = threading.Thread(target=hold)
    holder.start()
    assert entered.wait(1)
    def capture():
        try:
            values.append(read())
        except BaseException as error:
            errors.append(error)
        finally:
            finished.set()
    reader = threading.Thread(target=capture)
    reader.start()
    try:
        assert finished.wait(.7), "request-facing status waited for the journal writer"
    finally:
        release.set()
        holder.join(2)
        reader.join(2)
    assert not errors, errors
    return values[0]


def test_nonblocking_portfolio_status_does_not_wait_for_journal(status_portfolio):
    row = _read_while_journal_busy(status_portfolio.journal,
                                 lambda: status_portfolio.status(nonblocking=True))
    assert row["assets"][0]["symbol"] == "NQ"


@pytest.mark.parametrize("scope", ["main", "cc1"])
def test_runtime_http_status_returns_while_its_journal_writer_is_busy(workspace_http, scope):
    server, parent, request = workspace_http
    portfolio = parent if scope == "main" else server.command_centers.portfolios[scope]
    for runner in portfolio.runner_list():
        with runner.lock:
            runner.publish_read_views()
    path = "/status/public" if scope == "main" else "/api/command-centers/cc1/status"
    code, data, _ = _read_while_journal_busy(portfolio.journal, lambda: request(path))
    assert code == 200, data
    assert data["assets"]


def _trade():
    now = int(time.time())
    return SimpleNamespace(entry_id="cache-regression", direction=1, qty=1,
                           entry_price=100.0, entry_ts=now-60, exit_price=110.0,
                           exit_ts=now-1, exit_comment="closed", profit=10.0)


def test_dirty_journal_marks_valuation_unknown_then_publisher_restores_it(workspace_http):
    server, _, request = workspace_http
    journal = server.command_centers.portfolios["cc1"].journal
    journal.add_trade("NQ", _trade(), True)
    code, row, _ = request("/api/command-centers/cc1/status")
    assert code == 200 and row["assets"], row
    assert row["accounting"]["realized_pnl"] is None
    assert "REALIZED_PNL_INVALID" in row["accounting"]["reasons"]
    journal.publish_dashboard_views()
    code, recovered, _ = request("/api/command-centers/cc1/status")
    assert code == 200
    assert recovered["accounting"]["realized_pnl"] == 10.0


def test_journal_expiry_and_clock_reversal_preserve_capture_time_and_unknown(status_portfolio):
    journal = status_portfolio.journal
    captured = journal._dashboard_views["captured_at"]
    stale = journal.closed_paper_profit(nonblocking=True, as_of_ts=captured+91)
    future = journal.closed_paper_profit(nonblocking=True, as_of_ts=captured-1)
    for row in (stale, future):
        assert row["realized_pnl"] is None and row["view_stale"] is True
        assert row["view_captured_at"] == captured
    assert stale["reason"] == "JOURNAL_VIEW_STALE"
    assert future["reason"] == "JOURNAL_VIEW_IN_FUTURE"


def test_display_publisher_is_idempotent_updates_dirty_journal_and_drains_on_close(tmp_path):
    journal = Journal(str(tmp_path / "book.sqlite3"))
    journal.start_display_publisher()
    thread = journal._display_thread
    journal.start_display_publisher()
    assert journal._display_thread is thread
    journal.add_trade("NQ", _trade(), True)
    deadline = time.monotonic()+2
    while time.monotonic() < deadline:
        if journal.closed_paper_profit(nonblocking=True)["realized_pnl"] == 10.0:
            break
        time.sleep(.01)
    assert journal.closed_paper_profit(nonblocking=True)["realized_pnl"] == 10.0
    journal.close()
    assert not thread.is_alive()
    assert journal.closed_paper_profit(nonblocking=True)["reason"] == "JOURNAL_CLOSED"
    journal.start_display_publisher()
    assert journal._display_thread is thread and not thread.is_alive()


def test_failed_startup_reset_keeps_explicit_error_state_observable(status_portfolio):
    runner = status_portfolio.runners["NQ"]
    runner.errors = 1
    runner.last_error = "source unavailable; retrying"
    runner.reset_failed_startup_warmup()
    row = runner.summary(nonblocking=True)
    assert row["warm"] is False and row["price"] is None
    assert row["last_error"] == runner.last_error and row["errors"] == 1


def test_each_worker_poll_publishes_new_market_state_outside_http(status_portfolio, monkeypatch):
    from icarus_engine import activation_runtime
    runner = status_portfolio.runners["NQ"]
    monkeypatch.setattr(status_portfolio, "_warmup_with_retry", lambda _runner: True)
    monkeypatch.setattr(activation_runtime, "load_startup_overlay", lambda *_args: None)
    def poll():
        runner.last_price = 105.0
        runner.last_price_ts = time.time()
        status_portfolio._stop.set()
    monkeypatch.setattr(runner, "poll", poll)
    status_portfolio._run(runner)
    assert runner.summary(nonblocking=True)["price"] == 105.0


def test_unchanged_journal_image_does_not_rescan_ledger_and_external_changes_do(tmp_path, monkeypatch):
    import sqlite3
    journal = Journal(str(tmp_path / "book.sqlite3"))
    original, calls = journal.closed_paper_profit, []
    def observed(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)
    monkeypatch.setattr(journal, "closed_paper_profit", observed)
    try:
        for _ in range(10):
            journal.publish_dashboard_views()
        assert not calls
        journal.add_trade("NQ", _trade(), True)
        journal.publish_dashboard_views()
        assert len(calls) == 1
        assert original(nonblocking=True)["realized_pnl"] == 10.0
        with sqlite3.connect(journal.path) as other:
            other.execute("UPDATE trades SET profit=NULL")
        journal.publish_dashboard_views()
        assert len(calls) == 2
        assert original(nonblocking=True)["realized_pnl"] is None
        assert original(nonblocking=True)["reason"] == "INVALID_PERSISTED_TRADE"
    finally:
        journal.close()


def test_fresh_open_mark_can_follow_unchanged_realized_receipt_without_future_mark_error(workspace_http):
    from icarus_engine.pine.timeframe import Bar
    server, _, request = workspace_http
    portfolio = server.command_centers.portfolios["cc1"]
    runner, journal = portfolio.runners["NQ"], portfolio.journal
    captured = int(time.time())-3
    journal._dashboard_views = {**journal._dashboard_views, "captured_at": captured}
    with runner.lock:
        runner.em.entry("fresh-mark", 1, 1)
        runner.em.process_bar(Bar(240, 100, 100, 100, 100, 1), 3)
        runner.last_price, runner.last_price_ts = 105.0, time.time()-1
        runner.publish_read_views()
    code, row, _ = request("/api/command-centers/cc1/status")
    assert code == 200, row
    assert row["accounting"]["accounting_complete"] is True, row["accounting"]
    assert row["realized_snapshot_ts"] == captured
    assert row["realized_view_stale"] is False


def test_selected_configuration_commit_publishes_new_chart_metadata_before_return(workspace_http):
    server, _, request = workspace_http
    path = "/api/command-centers/cc1/status"
    code, before, _ = request(path)
    assert code == 200 and before["assets"][0]["chart_type"] == "heikin_ashi"
    server.command_centers.update_asset("cc1", "NQ", {
        "expected_revision": 0, "chart": {"chart_type": "real"},
    })
    code, after, _ = request(path)
    assert code == 200 and after["config_revision"] == 1, after
    assert after["assets"][0]["chart_type"] == "real"
    assert after["assets"][0]["view_captured_at"] > before["assets"][0]["view_captured_at"]
