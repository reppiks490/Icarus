"""Dedicated views use the selected real workspace and never the main ledger."""
import json
import sys
import threading
import types
from http.client import HTTPConnection
from unittest.mock import Mock

import pytest

from icarus_engine import paper_workspaces
from icarus_engine.assets import REGISTRY
from icarus_engine.runtime import Journal, Portfolio
from icarus_engine.server import serve


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_FEED", "file")
    journal = Journal(":memory:")
    parent = Portfolio(journal, str(tmp_path), feeds={})
    srv = serve(parent, 0, token="owner-test", start=False)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()

    def request(path, *, method="GET", body=None, token=None, host=None):
        connection = HTTPConnection("127.0.0.1", srv.server_port, timeout=5)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        if host:
            headers["Host"] = host
        connection.request(method, path, json.dumps(body) if body is not None else None, headers)
        response = connection.getresponse()
        raw = response.read()
        status, kind = response.status, response.getheader("Content-Type")
        connection.close()
        return status, json.loads(raw) if kind.startswith("application/json") else raw.decode()

    yield srv, request
    srv.shutdown()
    thread.join(timeout=5)
    srv.command_centers.portfolios.clear()
    srv.server_close()
    journal.close()


@pytest.mark.parametrize("profile_id", ["cc1", "cc2", "cc3", "cc4"])
def test_dedicated_page_and_profile_filter(engine, profile_id):
    srv, request = engine
    code, page = request("/dashboards/" + profile_id)
    assert code == 200
    assert 'id="combined-accounting"' in page
    assert page.index('id="combined-accounting"') < page.index('id="workspace-panel"')
    assert '/workspace-dashboard.js' in page
    code, payload = request("/api/command-centers/" + profile_id + "?profile=cc4")
    assert code == 200
    assert payload["profile"]["id"] == profile_id
    assert "profiles" not in payload
    assert payload["aggregate"]["workspace_count"] == 4
    assert payload["accounting"]["reconciled_broker_pnl"] is None
    assert payload["accounting"]["fees_verified"] is False
    assert payload["accounting"]["complete"] is False
    assert payload["aggregate"]["realized_pnl"] is None
    assert payload["profile"]["pnl"]["realized_pnl"] is None
    assert payload["execution_authorized"] is False


@pytest.mark.parametrize("path", ["/dashboards/cc5", "/dashboards/cc1/extra", "/api/command-centers/CC1", "/api/command-centers/cc1/extra", "/api/command-centers/cc1%2Fcc2"])
def test_unknown_profile_routes_fail_closed(engine, path):
    assert engine[1](path)[0] == 404


def test_corpus_safe_reader_has_no_user_selected_path(engine, monkeypatch):
    called = Mock(return_value={"status": "HISTORICAL_CONSUMPTION_VERIFIED", "corpora": [], "execution_authorized": False})
    monkeypatch.setitem(sys.modules, "icarus_engine.corpus_evidence", types.SimpleNamespace(snapshot=called))
    status, result = engine[1]("/api/corpus-consumption?path=/etc/passwd&now_ns=1")
    assert status == 200
    assert result["status"] == "HISTORICAL_CONSUMPTION_VERIFIED"
    called.assert_called_once_with()


def test_chart_is_scoped_to_workspace_and_auth_controls_preserved(engine):
    srv, request = engine
    workspace_runner = Mock()
    workspace_runner.chart.return_value = {"asset": "NQ", "bars": [{"c": 121}]}
    workspace = Mock()
    workspace.runners = {"NQ": workspace_runner}
    srv.command_centers.portfolios["cc2"] = workspace
    code, result = request("/api/command-centers/cc2/chart/NQ?n=40")
    assert code == 200 and result["bars"][0]["c"] == 121
    workspace_runner.chart.assert_called_once_with(40, nonblocking=True)
    assert request("/api/command-centers/cc1/chart/NQ")[0] == 503
    assert request("/api/command-centers/cc2/chart/ES")[0] == 404
    assert request("/admin/command-centers/cc2/pause", method="POST", body={"paused": True})[0] == 401
    assert request("/dashboards/cc2", host="attacker.example")[0] == 403
    srv.command_centers.portfolios.clear()


def test_complete_paper_accounting_reuses_manager_totals(engine, monkeypatch):
    srv, request = engine
    snapshot = srv.command_centers.snapshot()
    for i, profile in enumerate(snapshot["profiles"], 1):
        profile["pnl"].update(realized_pnl=10 * i, open_pnl=i)
    snapshot["aggregate"].update(realized_pnl=100, open_pnl=10)
    monkeypatch.setattr(srv.command_centers, "snapshot", lambda: snapshot)
    srv.command_centers.portfolios = {key: object() for key in ("cc1", "cc2", "cc3", "cc4")}
    status, result = request("/api/command-centers/cc3")
    assert status == 200
    assert result["accounting"]["complete"] is True
    assert result["aggregate"]["realized_pnl"] == 100
    assert result["aggregate"]["open_pnl"] == 10
    assert result["profile"]["pnl"]["realized_pnl"] == 30
    srv.command_centers.portfolios.clear()


def test_old_ui_links_all_four_separate_views(engine):
    status, script = engine[1]("/command-centers-ui.js")
    assert status == 200
    assert '/dashboards/' in script
    assert '/dashboards/connections' in script


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), True, "12.50"])
def test_invalid_accounting_values_never_produce_complete_aggregate(engine, monkeypatch, bad_value):
    srv, request = engine
    snapshot = srv.command_centers.snapshot()
    snapshot["profiles"][0]["pnl"]["open_pnl"] = bad_value
    monkeypatch.setattr(srv.command_centers, "snapshot", lambda: snapshot)
    srv.command_centers.portfolios = {key: object() for key in ("cc1", "cc2", "cc3", "cc4")}
    status, result = request("/api/command-centers/cc1")
    assert status == 200
    assert result["accounting"]["complete"] is False
    assert result["aggregate"]["realized_pnl"] is None


def test_connections_routes_authenticate_before_any_account_read(engine):
    srv, request = engine
    assert request("/connections")[0] == 200
    assert request("/api/account-connections")[0] == 401
    assert request("/admin/account-connections", method="POST", body={})[0] == 401
    assert request("/admin/account-connections/arbitrary/connect", method="POST", body={})[0] == 401


def test_corrupt_duplicate_workspace_accounting_is_unavailable(engine, monkeypatch):
    srv, request = engine
    snapshot = srv.command_centers.snapshot()
    snapshot["profiles"][3]["id"] = "cc1"
    monkeypatch.setattr(srv.command_centers, "snapshot", lambda: snapshot)
    srv.command_centers.portfolios = {key: object() for key in ("cc1", "cc2", "cc3", "cc4")}
    result = request("/api/command-centers/cc1")[1]
    assert result["accounting"]["complete"] is False
    assert result["aggregate"]["open_pnl"] is None


def test_connections_hooks_use_authenticated_manager_and_owner_controls(monkeypatch, request):
    manager = Mock()
    manager.snapshot.return_value = {"connections": [], "execution_authorized": False}
    manager.upsert.return_value = {"id": "paper-one", "status": "CONFIGURED", "execution_authorized": False}
    manager.connect.return_value = {"id": "paper-one", "status": "UNSUPPORTED", "execution_authorized": False}
    constructor = Mock(return_value=manager)
    monkeypatch.setitem(sys.modules, "icarus_engine.account_connections", types.SimpleNamespace(ConnectionManager=constructor))
    srv, http = request.getfixturevalue("engine")
    assert http("/api/account-connections", token="owner-test")[0] == 200
    manager.snapshot.assert_called_once_with()
    assert http("/admin/account-connections", method="POST", body={"id": "paper-one"}, token="owner-test")[0] == 200
    manager.upsert.assert_called_once_with({"id": "paper-one"})
    assert http("/admin/account-connections/paper-one/connect", method="POST", body={}, token="owner-test")[0] == 200
    manager.connect.assert_called_once_with("paper-one")
    assert http("/admin/account-connections/paper-one/connect/extra", method="POST", body={}, token="owner-test")[0] == 404


def test_missing_marks_with_numeric_fallback_never_appear_as_verified_pnl(engine, monkeypatch):
    srv, request = engine
    snapshot = srv.command_centers.snapshot()
    snapshot["aggregate"]["accounting_complete"] = False
    snapshot["profiles"][0]["valuation_complete"] = False
    snapshot["profiles"][0]["pnl"]["open_pnl"] = 0.0
    monkeypatch.setattr(srv.command_centers, "snapshot", lambda: snapshot)
    srv.command_centers.portfolios = {key: object() for key in ("cc1", "cc2", "cc3", "cc4")}
    result = request("/api/command-centers/cc1")[1]
    assert result["accounting"]["complete"] is False
    assert result["aggregate"]["open_pnl"] is None
    assert result["profile"]["pnl"]["open_pnl"] is None
