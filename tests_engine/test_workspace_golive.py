"""Go-live identity and P&L belong to selected cached paper state."""
import pytest

from tests_engine.test_workspace_api import workspace_http  # noqa: F401


@pytest.mark.parametrize("workspace,price", [("cc1", 100), ("cc2", 200), ("cc3", 300), ("cc4", 400)])
def test_golive_uses_selected_cached_identity_and_never_global_feed(workspace_http, monkeypatch, workspace, price):
    server, parent, request = workspace_http
    from tests_engine.test_workspace_market_data import owner
    feed = owner()
    def forbidden(*a, **k):
        pytest.fail("go-live report called a provider or parent runtime")
    monkeypatch.setattr(parent, "status", forbidden)
    feed.meta = feed.capabilities = feed.trades = feed.depth_events = forbidden
    server.command_centers.portfolios[workspace].runners["NQ"].feed = feed
    monkeypatch.setenv("ICARUS_FEED", "yahoo")
    monkeypatch.setenv("ALPACA_PAPER", "false")
    code, data, _ = request(f"/api/command-centers/{workspace}/panels/golive")
    assert code == 200, data
    assert data["workspace_id"] == workspace
    assert data["feed"] == "databento"
    assert "Yahoo" not in data["identity"]
    assert data["broker_armed"] is False and data["execution_authorized"] is False
    assert data["verdict"] == "PAPER_ONLY"
    assert data["nq_history"]["path"] is None
    assert data["selected_feeds"][0]["asset"] == "NQ"


def test_golive_does_not_read_parent_history(workspace_http):
    from pathlib import Path
    server, parent, request = workspace_http
    history = Path(parent.base_dir) / "history"
    history.mkdir()
    (history / "NQ_1m.csv").write_text("time,open,high,low,close\n1,999,999,999,999\n")
    code, data, _ = request("/api/command-centers/cc1/panels/golive")
    assert code == 200, data
    assert data["nq_history"] == {"path": None, "minutes": None}


def test_no_nq_cannot_substitute_another_assets_price_or_session(tmp_path):
    from types import SimpleNamespace
    from icarus_engine.workspace_golive import snapshot
    port = SimpleNamespace(base_dir=str(tmp_path), runner_list=lambda: [], status=lambda: {
        "assets": [{"symbol": "BTC", "price": 70000, "price_age": 1,
                    "market": {"describe": "open"}, "state": {"in_session": True}}],
        "net": 30, "live_profit": 20, "open_profit": 5})
    result = snapshot(port)
    assert result["verdict"] == "NQ_UNAVAILABLE"
    assert result["nq_context_available"] is False
    assert result["warmup_pnl"] == 5
    assert result["broker_armed"] is False
    gates = {row["id"]: row for row in result["gates"]}
    for name in ("tape", "session_rth", "feed_age", "fomc", "fill_model"):
        assert gates[name]["available"] is False and gates[name]["ok"] is False


@pytest.mark.parametrize("age", [None, -1, 300])
def test_unknown_or_stale_nq_age_does_not_pass_native_file_bypass(tmp_path, age):
    from types import SimpleNamespace
    from icarus_engine.workspace_golive import snapshot
    port = SimpleNamespace(base_dir=str(tmp_path), runner_list=lambda: [], status=lambda: {
        "assets": [{"symbol": "NQ", "price": 100, "price_age": age}]})
    result = snapshot(port)
    gate = next(row for row in result["gates"] if row["id"] == "feed_age")
    assert gate["ok"] is False


@pytest.mark.parametrize("seed_cached", [False, True])
def test_busy_golive_cached_reader_does_not_hold_selected_status_hostage(workspace_http, seed_cached):
    import threading
    import time
    server, _, request = workspace_http
    runner = server.command_centers.portfolios['cc1'].runners['NQ']
    if seed_cached:
        runner.summary(nonblocking=True)  # Publish a real cache before contention.
    entered, release = threading.Event(), threading.Event()
    def hold_runner():
        with runner.lock:
            entered.set()
            release.wait(4)
    thread=threading.Thread(target=hold_runner)
    thread.start()
    assert entered.wait(2)
    started=time.monotonic()
    try:
        code, data, _ = request('/api/command-centers/cc1/panels/golive')
        assert code == 503, data
        assert time.monotonic()-started < 1.5
        assert data['workspace_id']=='cc1'
    finally:
        release.set()
        thread.join(5)
    assert request('/api/command-centers/cc1/status')[0] == 200
