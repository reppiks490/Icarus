"""Real HTTP workspace reads and controls cannot select the parent portfolio."""
import copy
import json
import re
import shutil
import subprocess
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


def _unaffected_state(server, parent):
    import hashlib
    journals = {"main": parent.journal, **{k: p.journal for k, p in server.command_centers.portfolios.items() if k != "cc1"}}
    result = {key: hashlib.sha256("\n".join(journal.con.iterdump()).encode()).hexdigest()
              for key, journal in journals.items()}
    result.update({key + "-settings": server.command_centers._path(key).read_bytes()
                   for key in ("cc2", "cc3", "cc4")})
    result["parent-inputs"] = (server.command_centers.root.parent / "inputs.NQ.json").read_bytes()
    return result


def _add_second_asset(server):
    manager = server.command_centers
    manager.update("cc1", {"expected_revision": 0, "assets": ["NQ", "ES"]})
    runner = manager.portfolios["cc1"].runners["ES"]
    _seed(runner, 500, "cc1-es-entry")
    return runner


def _open_live(runner):
    runner.em.entry("new-live-" + runner.symbol, 1, 1)
    runner.em.process_bar(Bar(240, 100, 100, 100, 100, 1), 3)
    runner.last_price = 110
    runner.last_price_ts = time.time()
    runner._closed_seen = len(runner.em.closed)
    runner._fills_seen = len(runner.em.fills)


def test_revisioned_asset_config_http_preserves_sibling_and_parent(workspace_http):
    server, parent, request = workspace_http
    es = _add_second_asset(server)
    before_es = es.inputs_base.to_dict()
    before = _unaffected_state(server, parent)
    path = "/admin/command-centers/cc1/assets/NQ/config"
    code, result, _ = request(path, body={"expected_revision": 1, "inputs": {"tp1_pts": 17}})
    assert code == 200 and result["workspace_id"] == "cc1" and result["asset"] == "NQ"
    assert result["config_revision"] == 2
    assert server.command_centers.portfolios["cc1"].runners["NQ"].inputs_base.tp1_pts == 17
    assert es.inputs_base.to_dict() == before_es
    assert _unaffected_state(server, parent) == before
    saved = server.command_centers._path("cc1").read_bytes()
    assert request(path, body={"expected_revision": 1, "inputs": {"tp1_pts": 19}})[0] == 409
    assert server.command_centers._path("cc1").read_bytes() == saved
    assert request(path, body={"inputs": {"tp1_pts": 19}})[0] == 400


@pytest.mark.parametrize("action,body", [("config", {"expected_revision": 0, "inputs": {"tp1_pts": 17}}),
                                          ("pause", {"paused": True}), ("flatten", {"confirm": True}),
                                          ("rewarm/async", {"expected_revision": 0})])
def test_workspace_mutations_require_owner_and_viewer_can_read(workspace_http, action, body):
    server, parent, request = workspace_http
    code, created, _ = request("/admin/access/add", body={"label": "test-viewer"})
    assert code == 201
    viewer = created["user"]["token"]
    before = _unaffected_state(server, parent)
    selected = server.command_centers._path("cc1").read_bytes()
    path = "/admin/command-centers/cc1/assets/NQ/" + action
    assert request(path, body=body, token=None)[0] == 401
    assert request(path, body=body, token=viewer)[0] == 403
    assert request("/api/command-centers/cc1/status", token=viewer)[0] == 200
    assert server.command_centers._path("cc1").read_bytes() == selected
    assert _unaffected_state(server, parent) == before
    assert not server.command_centers.portfolios["cc1"].runners["NQ"].paused


def test_asset_pause_resume_does_not_change_workspace_or_other_runners(workspace_http):
    server, parent, request = workspace_http
    es = _add_second_asset(server)
    portfolio = server.command_centers.portfolios["cc1"]
    before = _unaffected_state(server, parent)
    path = "/admin/command-centers/cc1/assets/NQ/pause"
    code, result, _ = request(path, body={"paused": True})
    assert code == 200 and result["asset"] == "NQ" and result["scope"] == "asset"
    assert portfolio.runners["NQ"].paused and not es.paused and not portfolio.paused
    assert request(path, body={"paused": False})[0] == 200
    assert not portfolio.runners["NQ"].paused
    assert _unaffected_state(server, parent) == before


@pytest.mark.parametrize("suffix,body", [
    ("pause", {"paused": True, "asset": "NQ"}),
    ("flatten", {"confirm": True, "asset": "NQ"}),
    ("pause", {"paused": True, "symbol": "NQ"}),
    ("pause", {"paused": True, "workspace": "cc2"}),
])
def test_whole_workspace_controls_reject_misleading_selectors(workspace_http, suffix, body):
    server, parent, request = workspace_http
    before = _unaffected_state(server, parent)
    assert request("/admin/command-centers/cc1/" + suffix, body=body)[0] == 400
    assert not server.command_centers.portfolios["cc1"].paused
    assert not server.command_centers.portfolios["cc1"].runners["NQ"].paused
    assert _unaffected_state(server, parent) == before


@pytest.mark.parametrize("suffix,body", [("pause", {"paused": True}), ("flatten", {"confirm": True}),
                                        ("assets/NQ/pause", {"paused": True})])
@pytest.mark.parametrize("query", ["asset=NQ", "symbol=NQ", "workspace=cc2", "profile=cc2"])
def test_workspace_controls_reject_query_scope_before_any_mutation(workspace_http, suffix, body, query):
    server, parent, request = workspace_http
    es = _add_second_asset(server)
    nq = server.command_centers.portfolios["cc1"].runners["NQ"]
    before = _unaffected_state(server, parent)
    assert request("/admin/command-centers/cc1/" + suffix + "?" + query, body=body)[0] == 400
    assert not nq.paused and not es.paused
    assert _unaffected_state(server, parent) == before


@pytest.mark.parametrize("resource", ["cc1//pause", "cc1/pause/", "cc1/assets/NQ//pause", "cc1/assets/NQ%2FES/pause", "cc1/assets/ES/pause"])
def test_malformed_or_unadmitted_control_routes_fail_without_parent_mutation(workspace_http, resource):
    server, parent, request = workspace_http
    before = _unaffected_state(server, parent)
    assert request("/admin/command-centers/" + resource, body={"paused": True})[0] == 404
    assert not server.command_centers.portfolios["cc1"].runners["NQ"].paused
    assert _unaffected_state(server, parent) == before


def test_asset_flatten_closes_only_selected_paper_position(workspace_http):
    server, parent, request = workspace_http
    es = _add_second_asset(server)
    nq = server.command_centers.portfolios["cc1"].runners["NQ"]
    _open_live(nq); _open_live(es)
    before = _unaffected_state(server, parent)
    code, result, _ = request("/admin/command-centers/cc1/assets/NQ/flatten", body={"confirm": True})
    assert code == 200 and result["flattened_positions"] == 1
    assert result["workspace_id"] == "cc1" and result["asset"] == "NQ"
    assert result["execution_authorized"] is False
    assert nq.em.position_size == 0 and es.em.position_size == 1
    assert nq.paused and not es.paused
    assert _unaffected_state(server, parent) == before


def test_asset_flatten_without_mark_reports_unavailable_without_touching_sibling(workspace_http):
    server, _, request = workspace_http
    es = _add_second_asset(server)
    nq = server.command_centers.portfolios["cc1"].runners["NQ"]
    _open_live(nq); _open_live(es)
    nq.last_price = None
    code, result, _ = request("/admin/command-centers/cc1/assets/NQ/flatten", body={"confirm": True})
    assert code == 409 and result["flattened_positions"] == 0
    assert result["partial"] is False and result["positions_remain_open"] is True
    assert nq.em.position_size == 1 and es.em.position_size == 1
    assert not es.paused


def test_asset_flatten_receipt_reports_actual_close_if_later_step_raises(workspace_http, monkeypatch):
    server, _, request = workspace_http
    nq = server.command_centers.portfolios["cc1"].runners["NQ"]
    _open_live(nq)
    flatten = nq.flatten

    def close_then_fail(*args, **kwargs):
        flatten(*args, **kwargs)
        raise OSError("injected post-close receipt failure")

    monkeypatch.setattr(nq, "flatten", close_then_fail)
    code, result, _ = request("/admin/command-centers/cc1/assets/NQ/flatten", body={"confirm": True})
    assert code == 409 and result["flattened_positions"] == 1
    assert result["partial"] is True and result["positions_remain_open"] is False
    assert nq.em.position_size == 0


def _finished_job(request, workspace, receipt):
    deadline = time.monotonic() + 4
    while True:
        code, row, _ = request(f"/api/command-centers/{workspace}/jobs/{receipt['job']}")
        assert code == 200, row
        if row["status"] != "running":
            assert row["status"] == "done", row
            return row
        assert time.monotonic() < deadline, row
        time.sleep(.01)


def _job_tape(server, workspace):
    runner = server.command_centers.portfolios[workspace].runners["NQ"]
    runner.spec.calendar = "crypto"
    runner.spec.session = "eth"
    runner.subbars = [(Bar(1_700_000_000 // 60 * 60 + k * 60,
                          runner.last_price + k, runner.last_price + k + 2,
                          runner.last_price + k - 1, runner.last_price + k + 1, 1), 1)
                      for k in range(30)]


@pytest.mark.parametrize("suffix,settings", [
    ("assets/NQ/config/async", {"inputs": {"tp1_pts": 17}}),
    ("config/async", {"inputs": {"tp1_pts": 17}}),
])
def test_workspace_config_jobs_commit_and_report_both_revisions(workspace_http, suffix, settings):
    server, parent, request = workspace_http
    before = _unaffected_state(server, parent)
    code, receipt, _ = request("/admin/command-centers/cc1/" + suffix,
                               body={"expected_revision": 0, **settings})
    assert code == 202, receipt
    assert receipt["workspace_id"] == "cc1" and receipt["config_revision"] == 0
    row = _finished_job(request, "cc1", receipt)
    assert row["kind"] == "config" and row["config_revision"] == 0
    assert row["result"]["config_revision"] == 1
    code, inputs, _ = request("/api/command-centers/cc1/inputs/NQ")
    assert code == 200 and inputs["config_revision"] == 1 and inputs["base"]["tp1_pts"] == 17
    assert _unaffected_state(server, parent) == before


@pytest.mark.parametrize("workspace", ["cc1", "cc2", "cc3", "cc4"])
def test_workspace_backtest_job_csv_and_compare_use_frozen_selected_source(workspace_http, workspace):
    server, parent, request = workspace_http
    _job_tape(server, workspace)
    before = _unaffected_state(server, parent)
    code, receipt, _ = request(f"/admin/command-centers/{workspace}/assets/NQ/backtest",
                               body={"expected_revision": 0})
    assert code == 202, receipt
    row = _finished_job(request, workspace, receipt)
    assert row["workspace_id"] == workspace and row["config_revision"] == 0
    result = row["result"]
    assert result["workspace_id"] == workspace and result["paper_only"] is True
    assert result["execution_authorized"] is False and result["bars"] > 0
    source = result["config"]["reproducibility"]["source_config"]["base_inputs"]
    assert source["tp1_pts"] == int(workspace[-1]) * 10
    job_path = f"/api/command-centers/{workspace}/jobs/{receipt['job']}"
    assert "result" not in request(job_path + "?full=0")[1]
    # Historical downloads retain the accepted revision after current settings change.
    server.command_centers.update_asset(workspace, "NQ", {"expected_revision": 0, "inputs": {"tp1_pts": 71}})
    code, csv_text, headers = request(job_path + "/trades.csv", raw=True)
    assert code == 200 and csv_text.startswith("Trade number,")
    assert headers["X-Icarus-Workspace"] == workspace and headers["X-Icarus-Config-Revision"] == "0"
    assert workspace in headers["Content-Disposition"] and receipt["job"] in headers["Content-Disposition"]
    code, comparison, _ = request(f"/admin/command-centers/{workspace}/jobs/{receipt['job']}/compare",
                                  body={"csv": csv_text, "tol": 1})
    assert code == 200 and comparison["workspace_id"] == workspace
    assert comparison["config_revision"] == 0 and "report" in comparison
    # The cc1 helper includes its selected file, so compare unrelated state only for cc1.
    if workspace == "cc1":
        assert _unaffected_state(server, parent) == before


def test_workspace_job_ownership_precedes_read_export_and_compare(workspace_http, monkeypatch):
    from icarus_engine import backtest
    server, _, request = workspace_http
    _job_tape(server, "cc1")
    code, receipt, _ = request("/admin/command-centers/cc1/assets/NQ/backtest", body={"expected_revision": 0})
    assert code == 202
    _finished_job(request, "cc1", receipt)
    monkeypatch.setitem(backtest.JOBS, "parent-forged", {"private": "must not read parent jobs"})
    for workspace, job in (("cc2", receipt["job"]), ("cc1", "parent-forged")):
        path = f"/api/command-centers/{workspace}/jobs/{job}"
        assert request(path)[0] == 404
        assert request(path + "/trades.csv")[0] == 404
        assert request(f"/admin/command-centers/{workspace}/jobs/{job}/compare", body={"csv": "invalid"})[0] == 404


def test_workspace_jobs_preserve_auth_and_reject_config_csv(workspace_http):
    server, _, request = workspace_http
    code, created, _ = request("/admin/access/add", body={"label": "job-reader"})
    assert code == 201
    viewer = created["user"]["token"]
    route = "/admin/command-centers/cc1/assets/NQ/config/async"
    body = {"expected_revision": 0, "inputs": {"tp1_pts": 17}}
    assert request(route, body=body, token=None)[0] == 401
    assert request(route, body=body, token=viewer)[0] == 403
    code, receipt, _ = request(route, body=body)
    assert code == 202
    _finished_job(request, "cc1", receipt)
    path = f"/api/command-centers/cc1/jobs/{receipt['job']}"
    assert request(path, token=None)[0] == 401
    assert request(path, token=viewer)[0] == 200
    assert request(path + "/trades.csv", token=None)[0] == 401
    assert request(path + "/trades.csv")[0] == 409
    assert request(f"/admin/command-centers/cc1/jobs/{receipt['job']}/compare", body={"csv": "invalid"})[0] == 409


@pytest.mark.parametrize("resource", ["config/async", "assets/NQ/config/async", "assets/NQ/backtest", "jobs/missing/compare", "rewarm/async", "assets/NQ/rewarm/async"])
def test_workspace_jobs_reject_query_scope_before_acceptance(workspace_http, resource):
    server, parent, request = workspace_http
    before = _unaffected_state(server, parent)
    body = {"expected_revision": 0, "inputs": {"tp1_pts": 17}}
    assert request("/admin/command-centers/cc1/" + resource + "?asset=", body=body)[0] == 400
    assert _unaffected_state(server, parent) == before


@pytest.mark.parametrize("body,status", [({}, 400), ({"expected_revision": 9}, 409),
                                        ({"expected_revision": 0, "asset": "ES"}, 400)])
def test_workspace_backtest_rejects_invalid_admission(workspace_http, body, status):
    server, parent, request = workspace_http
    before = _unaffected_state(server, parent)
    assert request("/admin/command-centers/cc1/assets/NQ/backtest", body=body)[0] == status
    assert _unaffected_state(server, parent) == before


@pytest.mark.parametrize("resource", ["config/async", "backtest", "rewarm/async"])
def test_workspace_job_admission_io_failure_is_sanitized_unavailable(workspace_http, monkeypatch, resource):
    server, parent, request = workspace_http
    manager = server.command_centers
    preset = manager.root.parent / "presets" / "unreadable.json"
    preset.parent.mkdir(exist_ok=True)
    preset.write_text("{}")
    body = {"expected_revision": 0, "preset": "unreadable"}
    if resource == "rewarm/async":
        manager.update_asset("cc1", "NQ", body)
        body = {"expected_revision": 1}
    saved = manager._path("cc1").read_bytes()
    before = _unaffected_state(server, parent)

    def inaccessible(*_args, **_kwargs):
        raise PermissionError("private-filesystem-path-must-not-leak")

    monkeypatch.setattr(paper_workspaces, "resolve_inputs", inaccessible)
    code, error, _ = request("/admin/command-centers/cc1/assets/NQ/" + resource,
                              body=body)
    assert code == 503 and error["workspace_id"] == "cc1"
    assert "private-filesystem-path" not in json.dumps(error)
    assert not server.workspace_jobs._jobs
    assert manager._path("cc1").read_bytes() == saved
    assert manager.profiles["cc1"]["config_revision"] == body["expected_revision"]
    assert _unaffected_state(server, parent) == before


def test_main_dashboard_bootstrap_precedes_every_ui_module_without_exposing_token(workspace_http):
    _, _, request = workspace_http
    code, html, _ = request("/", raw=True)
    assert code == 200
    bootstrap = re.search(r'<script id="icarus-workspace-bootstrap">([\s\S]*?)</script>', html)
    assert bootstrap, "main page must receive server-owned identity before UI scripts"
    assert html.index(bootstrap.group(0)) < html.index('src="/workspace-client.js"') < html.index('src="/research-ui.js"')
    assert html.index('window.IcarusClient') < html.index('src="/research-ui.js"')
    assert "api-owner" not in html
    if shutil.which("node"):
        script = "const vm=require('node:vm'),assert=require('node:assert/strict'),w={};w.window=w;vm.runInNewContext(" + json.dumps(bootstrap.group(1)) + ",w);assert.equal(w.IcarusWorkspace.id,'main');assert(Object.isFrozen(w.IcarusWorkspace));assert(Object.isFrozen(w.IcarusWorkspace.capabilities));assert.equal(Object.getOwnPropertyDescriptor(w,'IcarusWorkspace').writable,false);"
        result = subprocess.run([shutil.which("node"), "-e", script], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr


def test_client_static_route_and_dedicated_pages_remain_available_before_renderer_migration(workspace_http):
    _, _, request = workspace_http
    code, source, headers = request("/workspace-client.js", raw=True)
    assert code == 200 and "IcarusWorkspaceClient" in source and "javascript" in headers["Content-Type"]
    for profile in ("cc1", "cc2", "cc3", "cc4"):
        code, html, _ = request("/dashboards/" + profile, raw=True)
        assert code == 200 and 'src="/workspace-dashboard.js"' in html


def test_main_context_initializes_in_real_browser_before_status_reads(workspace_http):
    playwright = pytest.importorskip("playwright.sync_api")
    server, _, _ = workspace_http
    errors = []
    base = f"http://127.0.0.1:{server.server_port}"
    with playwright.sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(headless=True, executable_path=shutil.which("chromium"))
        except playwright.Error as error:
            pytest.skip("optional Chromium unavailable: " + str(error).splitlines()[0])
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.route("**/*", lambda route: route.continue_() if route.request.url.startswith(base + "/") else route.abort())
            page.add_init_script("localStorage.setItem('icarus-engine-token','api-owner')")
            page.goto(base + "/", wait_until="load")
            state = page.evaluate("""async () => ({
              id: window.IcarusClient.context.id,
              frozen: Object.isFrozen(window.IcarusWorkspace) && Object.isFrozen(window.IcarusClient),
              status: await window.IcarusClient.read('status'),
            })""")
            assert state["id"] == "main" and state["frozen"]
            assert next(a for a in state["status"]["assets"] if a["symbol"] == "NQ")["price"] == 900
            assert not errors, errors
        finally:
            browser.close()


@pytest.mark.parametrize("scope,expected", [("assets/NQ/rewarm/async", ["NQ"]), ("rewarm/async", ["NQ", "ES"])])
def test_explicit_workspace_rewarm_job_is_selected_and_revisioned(workspace_http, scope, expected):
    server, parent, request = workspace_http
    es = _add_second_asset(server)
    engines = {symbol: runner.em for symbol, runner in server.command_centers.portfolios["cc1"].runners.items()}
    before = _unaffected_state(server, parent)
    code, receipt, _ = request("/admin/command-centers/cc1/" + scope, body={"expected_revision": 1})
    assert code == 202 and receipt["config_revision"] == 1
    row = _finished_job(request, "cc1", receipt)
    assert row["kind"] == "config" and row["config_revision"] == 1
    assert row["result"]["config_revision"] == 2 and row["result"]["rewarmed_assets"] == expected
    for symbol, runner in server.command_centers.portfolios["cc1"].runners.items():
        assert (runner.em is not engines[symbol]) == (symbol in expected)
    assert _unaffected_state(server, parent) == before


@pytest.mark.parametrize("body,status", [({}, 400), ({"expected_revision": 1}, 409),
                                        ({"expected_revision": 0, "asset": "ES"}, 400)])
def test_workspace_rewarm_refuses_invalid_revision_or_body_scope(workspace_http, body, status):
    server, parent, request = workspace_http
    before = _unaffected_state(server, parent)
    assert request("/admin/command-centers/cc1/assets/NQ/rewarm/async", body=body)[0] == status
    assert not server.workspace_jobs._jobs and _unaffected_state(server, parent) == before


def test_settings_resize_uses_mobile_geometry_when_viewport_callbacks_are_delayed(workspace_http):
    playwright = pytest.importorskip("playwright.sync_api")
    server, _, _ = workspace_http
    with playwright.sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(headless=True, executable_path=shutil.which("chromium"))
        except playwright.Error as error:
            pytest.skip("optional Chromium unavailable: " + str(error).splitlines()[0])
        try:
            page = browser.new_page(viewport={"width": 800, "height": 600}, reduced_motion="reduce")
            base = f"http://127.0.0.1:{server.server_port}"
            page.route("**/*", lambda route: route.continue_() if route.request.url.startswith(base + "/") else route.abort())
            page.add_init_script("""localStorage.setItem('icarus-engine-token','api-owner');
              sessionStorage.setItem('icarus-intro-seen','1');window.holdPlacementEvents=false;
              const add=window.addEventListener.bind(window);
              window.addEventListener=(type,listener,options)=>add(type,
                ['resize','scroll'].includes(type)&&listener.name==='placeSettingsPanel'
                ? function(event){if(!window.holdPlacementEvents)listener.call(this,event);} : listener,options);
            """)
            page.goto(base + "/", wait_until="load")
            page.locator(".experience-settings summary").click()
            page.wait_for_function("""()=>{const s=document.querySelector('.experience-settings > div').style;
              return Boolean(s.left||s.getPropertyValue('--settings-left'));}""")
            page.evaluate("window.holdPlacementEvents=true")
            page.set_viewport_size({"width": 390, "height": 844})
            geometry = page.locator(".experience-settings > div").evaluate("""el=>{
              const r=el.getBoundingClientRect();return {x:r.x,right:r.right,y:r.y,bottom:r.bottom,
              left:el.style.left,top:el.style.top,maxHeight:el.style.maxHeight};}""")
            assert geometry["x"] >= 12 and geometry["right"] <= 390, geometry
            assert geometry["y"] >= 0 and geometry["bottom"] <= 844, geometry
            assert geometry["left"] == geometry["top"] == geometry["maxHeight"] == "", geometry
            page.evaluate("window.holdPlacementEvents=false;window.dispatchEvent(new Event('resize'))")
            assert page.locator(".experience-settings").evaluate("el=>el.open")
        finally:
            browser.close()
