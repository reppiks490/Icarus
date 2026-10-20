"""Real HTTP workspace reads and controls cannot select the parent portfolio."""
import copy
import json
import threading
import time
from collections import deque
from http.client import HTTPConnection

import pytest

from icarus_engine import paper_workspaces
from icarus_engine.assets import REGISTRY
from icarus_engine.pine.timeframe import Bar
from icarus_engine.runtime import Journal, Portfolio
from icarus_engine.server import serve


class _NoNetwork:
    def ticker(self, *_args, **_kwargs):
        raise AssertionError("workspace HTTP tests must not fetch quotes")

    def candles(self, *_args, **_kwargs):
        raise AssertionError("workspace HTTP tests must not fetch history")


def _seed(runner, price, label):
    runner._init_strategy(price)
    runner.warm = True
    runner.last_price = price
    runner.last_price_ts = time.time()
    runner.bars = deque([Bar(i * 60, price, price, price, price, 1) for i in range(60)], maxlen=60)
    runner.em.process_bar(Bar(60, price, price, price, price, 1), 0)
    runner.em.entry(label, 1, 1)
    runner.em.process_bar(Bar(120, price, price, price, price, 1), 1)
    runner.em.close(label)
    runner.em.process_bar(Bar(180, price + 10, price + 10, price + 10, price + 10, 1), 2)
    runner.live_from_ts = 0
    runner.live_closed_start = 0


@pytest.fixture
def workspace_http(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_FEED", "file")
    monkeypatch.setattr(paper_workspaces, "_PROFILE_DEFAULTS", tuple(
        {**p, "assets": ["NQ"]} for p in paper_workspaces._PROFILE_DEFAULTS))
    feed = _NoNetwork()
    parent = Portfolio(Journal(":memory:"), str(tmp_path), feeds={"yahoo": feed, "coinbase": feed})
    parent.pts_ref_price = 100
    for symbol in ("NQ", "ES"):
        _seed(parent.add_asset(copy.deepcopy(REGISTRY[symbol]), start=False), 900, "main-entry")
    server = serve(parent, 0, token="api-owner", start=False)
    journals = []
    for index, profile_id in enumerate(("cc1", "cc2", "cc3", "cc4"), 1):
        profile = server.command_centers.profiles[profile_id]
        profile["inputs"] = {"tp1_pts": index * 10}
        server.command_centers._save(profile)
        journal = Journal(":memory:")
        journals.append(journal)
        portfolio = paper_workspaces.WorkspacePortfolio(journal, str(tmp_path), workspace=profile,
                                                       feeds={"yahoo": feed, "coinbase": feed})
        portfolio.pts_ref_price = 100
        _seed(portfolio.add_asset(copy.deepcopy(REGISTRY["NQ"]), start=False), index * 100, profile_id + "-entry")
        server.command_centers.portfolios[profile_id] = portfolio
    (tmp_path / "inputs.NQ.json").write_text('{"tp1_pts":999}')
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request(path, *, body=None, token="api-owner", raw=False):
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        try:
            connection.request("GET" if body is None else "POST", path,
                               body=None if body is None else json.dumps(body), headers=headers)
            response = connection.getresponse()
            payload = response.read()
            return response.status, (payload.decode() if raw else json.loads(payload)), dict(response.getheaders())
        finally:
            connection.close()

    try:
        yield server, parent, request
    finally:
        server.shutdown()
        thread.join(5)
        server.server_close()
        for journal in journals:
            journal.close()
        parent.journal.close()


@pytest.mark.parametrize("profile_id,price,tp1", [("cc1", 100, 10), ("cc2", 200, 20), ("cc3", 300, 30), ("cc4", 400, 40)])
def test_scoped_status_and_inputs_are_real_selected_runtime(workspace_http, profile_id, price, tp1):
    _, _, request = workspace_http
    code, status, _ = request(f"/api/command-centers/{profile_id}/status")
    assert code == 200
    assert status["workspace_id"] == profile_id and status["config_revision"] == 0
    assert status["assets"][0]["price"] == price
    assert status["paper_only"] is True and status["execution_authorized"] is False
    code, inputs, _ = request(f"/api/command-centers/{profile_id}/inputs/NQ")
    assert code == 200
    assert inputs["workspace_id"] == profile_id and inputs["config_revision"] == 0
    assert inputs["base"]["tp1_pts"] == tp1
    assert inputs["effective"]["tp1_pts"] == tp1
    assert inputs["overrides"] == {}
    assert not any("inputs.NQ.json" in source for source in inputs["sources"])


@pytest.mark.parametrize("profile_id", ["cc1", "cc2", "cc3", "cc4"])
def test_scoped_trade_rows_and_csv_use_selected_runner_only(workspace_http, profile_id):
    _, _, request = workspace_http
    code, payload, _ = request(f"/api/command-centers/{profile_id}/trades/NQ?limit=10")
    assert code == 200
    assert payload["workspace_id"] == profile_id and payload["config_revision"] == 0
    assert len(payload["trades"]) == 1
    assert profile_id + "-entry" in json.dumps(payload["trades"])
    assert "main-entry" not in json.dumps(payload)
    code, csv, headers = request(f"/api/command-centers/{profile_id}/export/NQ.csv", raw=True)
    assert code == 200 and profile_id + "-entry" in csv and "main-entry" not in csv
    assert headers["X-Icarus-Workspace"] == profile_id
    assert headers["X-Icarus-Config-Revision"] == "0"
    assert profile_id + "_NQ" in headers["Content-Disposition"]


def test_assets_and_chart_keep_selected_identity_and_running_selection(workspace_http):
    _, _, request = workspace_http
    code, payload, _ = request("/api/command-centers/cc2/assets")
    assert code == 200 and payload["workspace_id"] == "cc2"
    assert payload["running"] == ["NQ"]
    assert payload["registry_scope"] == "shared"
    code, payload, _ = request("/api/command-centers/cc2/chart/NQ?n=20&offset=20")
    assert code == 200
    assert payload["workspace_id"] == "cc2" and payload["config_revision"] == 0
    assert {r[4] for r in payload["bars"]} == {200}
    assert payload["history"]["offset"] == 20


@pytest.mark.parametrize("resource", ["status", "assets", "inputs/NQ", "trades/NQ", "export/NQ.csv"])
def test_missing_runtime_does_not_fall_back_to_healthy_parent(workspace_http, resource):
    server, _, request = workspace_http
    absent = server.command_centers.portfolios.pop("cc4")
    try:
        code, payload, _ = request("/api/command-centers/cc4/" + resource)
        assert code == 503
        assert payload["workspace_id"] == "cc4"
        assert payload["execution_authorized"] is False
    finally:
        server.command_centers.portfolios["cc4"] = absent


@pytest.mark.parametrize("resource", ["inputs/ES", "trades/ES", "export/ES.csv", "inputs/nq", "inputs/NQ%2FES", "inputs//NQ", "status/extra"])
def test_missing_asset_and_malformed_path_never_select_parent(workspace_http, resource):
    _, _, request = workspace_http
    assert request("/api/command-centers/cc1/" + resource)[0] == 404


def test_scoped_status_matches_main_read_auth_and_rejects_foreign_selector(workspace_http):
    _, _, request = workspace_http
    assert request("/api/command-centers/cc1/status", token=None)[0] == 401
    assert request("/api/command-centers/cc1/status?workspace=cc2")[0] == 400
    assert request("/api/command-centers/cc1/chart/NQ?workspace=cc2")[0] == 400


def test_scoped_performance_identifies_configuration_revision(workspace_http):
    _, _, request = workspace_http
    code, payload, _ = request("/api/command-centers/cc3/performance")
    assert code == 200
    assert payload["workspace_id"] == "cc3" and payload.get("config_revision") == 0


@pytest.mark.parametrize("resource", ["status", "chart/NQ"])
def test_initially_busy_status_returns_structured_unavailable(workspace_http, resource):
    from http.client import RemoteDisconnected
    server, _, request = workspace_http
    runner = server.command_centers.portfolios["cc1"].runners["NQ"]
    runner._public_views = None
    entered, release = threading.Event(), threading.Event()

    def hold():
        with runner.lock:
            entered.set()
            release.wait(5)

    worker = threading.Thread(target=hold)
    worker.start()
    assert entered.wait(3)
    try:
        try:
            code, payload, _ = request("/api/command-centers/cc1/" + resource)
        except RemoteDisconnected:
            code, payload = 0, {}
        assert code == 503, "busy initial status must return JSON unavailable, not disconnect"
        assert payload["workspace_id"] == "cc1" and payload["execution_authorized"] is False
    finally:
        release.set()
        worker.join(5)


def test_busy_sibling_does_not_make_selected_healthy_workspace_unavailable(workspace_http):
    server, _, request = workspace_http
    busy = server.command_centers.portfolios["cc4"].runners["NQ"]
    busy._public_views = None
    entered, release = threading.Event(), threading.Event()

    def hold():
        with busy.lock:
            entered.set()
            release.wait(5)

    worker = threading.Thread(target=hold)
    worker.start()
    assert entered.wait(3)
    try:
        code, selected, _ = request("/api/command-centers/cc1/status")
        assert code == 200
        assert selected["workspace_id"] == "cc1" and selected["assets"][0]["price"] == 100
        code, unavailable, _ = request("/api/command-centers/cc4/status")
        assert code == 503 and unavailable["workspace_id"] == "cc4"
    finally:
        release.set()
        worker.join(5)


def test_trade_read_waits_for_complete_runner_cutover_state(workspace_http):
    from concurrent.futures import ThreadPoolExecutor
    server, _, request = workspace_http
    runner = server.command_centers.portfolios["cc1"].runners["NQ"]
    entered, release, reader_started, reader_done = (threading.Event() for _ in range(4))

    def change_cutover():
        with runner.lock:
            runner.live_from_ts = None
            entered.set()
            assert release.wait(5)
            runner.live_from_ts = 0

    def read_trades():
        reader_started.set()
        result = request("/api/command-centers/cc1/trades/NQ")
        reader_done.set()
        return result

    with ThreadPoolExecutor(max_workers=2) as executor:
        writer = executor.submit(change_cutover)
        assert entered.wait(3)
        reader = executor.submit(read_trades)
        assert reader_started.wait(3)
        try:
            assert not reader_done.wait(.2), "trade read escaped an unfinished runner cutover"
        finally:
            release.set()
        writer.result(timeout=5)
        code, payload, _ = reader.result(timeout=5)
    assert code == 200 and payload["trades"][0]["live"] is True
