"""Real HTTP delivery and request identity for background configuration replay."""
import json
import socket
import threading
import time
import urllib.error
import urllib.request

import pytest

from icarus_engine.assets import AssetSpec
from icarus_engine.runtime import AssetRunner, Journal, Portfolio, RunnerConfig
from icarus_engine.server import serve
from icarus_engine.strategy.inputs import Inputs


@pytest.fixture
def config_server(tmp_path):
    servers = []
    releases = []

    def start(*, dynamic_port=False, blocked=False):
        port = Portfolio(Journal(":memory:"), str(tmp_path))
        spec = AssetSpec("TEST", "TEST", "yahoo", "TEST", "crypto", 1, 1,
                         chart_tf="1", commission=0, roll="none")
        runner = AssetRunner(RunnerConfig(spec, Inputs(use_tide=False, use_eod_flat=False)), port.journal)
        runner._init_strategy(100)
        runner.last_price = 100
        runner.warm = True
        port.runners["TEST"] = runner
        port.order = ["TEST"]
        entered, release = threading.Event(), threading.Event()
        releases.append(release)
        if blocked:
            original = runner.rewarm if blocked == "engine" else port.rewarm_asset

            def slow_rewarm(*args, **kwargs):
                entered.set()
                assert release.wait(5), "test replay was not released"
                return original(*args, **kwargs)

            if blocked == "engine":
                runner.rewarm = slow_rewarm
            else:
                port.rewarm_asset = slow_rewarm
        http_port = 0
        if not dynamic_port:
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0))
                http_port = reservation.getsockname()[1]
        srv = serve(port, http_port, token="test-token", start=False)
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        servers.append((srv, thread))
        base = f"http://127.0.0.1:{srv.server_address[1]}"

        def request(path, body=None, token="test-token"):
            req = urllib.request.Request(base + path,
                data=None if body is None else json.dumps(body).encode(),
                headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=3) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as ex:
                return ex.code, json.load(ex)

        request.portfolio = port
        return runner, request, entered, release

    yield start
    for release in releases:
        release.set()
    for srv, thread in servers:
        srv.shutdown()
        srv.server_close()
        thread.join(5)


def finished(request, job):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        code, row = request("/api/config-jobs/" + job)
        assert code == 200
        if row["status"] in ("done", "error"):
            return row
        time.sleep(.01)
    pytest.fail("configuration job did not finish")


def test_async_replay_delivers_to_actual_bound_port(config_server):
    runner, request, _, _ = config_server(dynamic_port=True)
    code, accepted = request("/admin/inputs/async", {"asset": "TEST", "values": {"tp1_pts": 80}})
    assert code == 202
    row = finished(request, accepted["job"])
    assert row["status"] == "done", row
    assert runner.inputs_base.tp1_pts == 80


@pytest.mark.parametrize("second_path,second_body", [
    ("/admin/inputs/async", {"asset": "TEST", "values": {"tp1_pts": 90}}),
    ("/admin/inputs/reset/async", {"asset": "TEST"}),
    ("/admin/inputs/async", {"asset": "*", "values": {"tp1_pts": 80}}),
])
def test_different_overlapping_request_is_rejected_without_false_acceptance(config_server, second_path, second_body):
    runner, request, entered, release = config_server(blocked=True)
    code, first = request("/admin/inputs/async", {"asset": "TEST", "values": {"tp1_pts": 80}})
    assert code == 202 and entered.wait(3)
    code, conflict = request(second_path, second_body)
    assert code == 409, conflict
    assert conflict["job"] == first["job"]
    release.set()
    assert finished(request, first["job"])["status"] == "done"
    assert runner.inputs_base.tp1_pts == 80


def test_identical_retry_reuses_one_job_while_health_remains_responsive(config_server):
    runner, request, entered, release = config_server(blocked=True)
    payload = {"asset": "TEST", "values": {"tp1_pts": 80, "tp2_pts": 100}}
    code, first = request("/admin/inputs/async", payload)
    assert code == 202 and entered.wait(3)
    code, second = request("/admin/inputs/async", {"values": {"tp2_pts": 100, "tp1_pts": 80}, "asset": "TEST"})
    assert code == 202 and second["job"] == first["job"]
    code, health = request("/healthz")
    assert code == 200 and health["ok"] is True
    release.set()
    assert finished(request, first["job"])["status"] == "done"
    assert runner.inputs_base.tp1_pts == 80 and runner.inputs_base.tp2_pts == 100


def test_async_replay_preserves_synchronous_validation_failure(config_server):
    runner, request, _, _ = config_server()
    before = runner.inputs_base.to_dict()
    code, accepted = request("/admin/inputs/async", {"asset": "TEST", "values": []})
    assert code == 202
    row = finished(request, accepted["job"])
    assert row["status"] == "error" and "values must be an object" in row["error"]
    assert runner.inputs_base.to_dict() == before


def test_async_replay_requires_admin_auth_before_enqueue(config_server):
    runner, request, entered, _ = config_server(blocked=True)
    before = runner.inputs_base.to_dict()
    code, _ = request("/admin/inputs/async", {"asset": "TEST", "values": {"tp1_pts": 80}}, token="wrong")
    assert code == 401 and not entered.is_set()
    assert runner.inputs_base.to_dict() == before


def test_wildcard_whitespace_has_same_selection_for_retry_and_execution(config_server):
    runner, request, entered, release = config_server(blocked=True)
    payload = {"asset": "*", "values": {"tp1_pts": 80}}
    code, first = request("/admin/inputs/async", payload)
    assert code == 202 and entered.wait(3)
    code, retry = request("/admin/inputs/async", {**payload, "asset": " * "})
    assert code == 202 and retry["job"] == first["job"]
    release.set()
    assert finished(request, first["job"])["status"] == "done"
    code, direct = request("/admin/inputs", {"asset": " * ", "values": {"tp1_pts": 90}})
    assert code == 200, direct
    assert runner.inputs_base.tp1_pts == 90


@pytest.mark.parametrize("path", ["/status/public", "/api/chart/TEST?n=20"])
def test_public_views_respond_with_labeled_snapshot_during_locked_replay(config_server, path):
    runner, request, entered, release = config_server(blocked=True)
    before = runner.summary()
    code, accepted = request("/admin/inputs/async", {"asset": "TEST", "values": {"tp1_pts": 80}})
    assert code == 202 and entered.wait(3)
    started = time.monotonic()
    code, view = request(path)
    assert code == 200 and time.monotonic() - started < 1
    row = view["assets"][0] if path == "/status/public" else view
    assert row["view_stale"] is True
    assert row["view_captured_at"] > 0
    if path == "/status/public":
        assert row["position"] == before["position"]
        assert row["equity"] == before["equity"]
    release.set()
    assert finished(request, accepted["job"])["status"] == "done"
    code, current = request(path)
    assert code == 200
    current_row = current["assets"][0] if path == "/status/public" else current
    assert not current_row.get("view_stale", False)
    assert runner.inputs_base.tp1_pts == 80


def test_replay_snapshot_uses_committed_capital_and_epoch_until_metadata_commits(config_server, tmp_path):
    presets = tmp_path / "presets"
    presets.mkdir()
    (presets / "changed.json").write_text(json.dumps({"tp1_pts": 80, "_meta": {"capital": 12345}}))
    runner, request, entered, release = config_server(blocked="engine")
    code, before = request("/status/public")
    assert code == 200
    code, accepted = request("/admin/preset/async", {"asset": "TEST", "preset": "changed"})
    assert code == 202 and entered.wait(3)
    assert runner.spec.capital == 12345  # Metadata is staged inside the locked transaction.
    code, pending = request("/status/public")
    assert code == 200 and pending["view_stale"] is True
    assert pending["capital"] == pending["assets"][0]["capital"] == before["capital"]
    assert pending["net"] == before["net"]
    assert pending["equity_epoch"] == before["equity_epoch"]
    internal_finished = threading.Event()
    internal = {}
    def internal_read():
        internal.update(request.portfolio.status())
        internal_finished.set()
    thread = threading.Thread(target=internal_read, daemon=True)
    thread.start()
    assert not internal_finished.wait(.1), "internal status must wait for committed engine state"
    release.set()
    assert finished(request, accepted["job"])["status"] == "done"
    assert internal_finished.wait(3)
    thread.join(3)
    assert internal["capital"] == 12345 and not internal["view_stale"]
    code, after = request("/status/public")
    assert code == 200 and not after["view_stale"]
    assert after["capital"] == after["assets"][0]["capital"] == 12345
    assert after["equity_epoch"] > before["equity_epoch"]


def test_wildcard_replay_snapshot_keeps_epoch_and_history_when_later_asset_rolls_back(config_server):
    runner, request, _, _ = config_server()
    port = request.portfolio
    spec = AssetSpec("ZZZ", "ZZZ", "yahoo", "ZZZ", "crypto", 1, 1,
                     chart_tf="1", commission=0, roll="none")
    second = AssetRunner(RunnerConfig(spec, Inputs(use_tide=False, use_eod_flat=False)), port.journal)
    second._init_strategy(100)
    second.warm = True
    port.runners["ZZZ"] = second
    port.order.append("ZZZ")
    port.journal.add_equity(port.equity())
    code, before = request("/status/public")
    assert code == 200 and before["equity_series"]
    entered, release = threading.Event(), threading.Event()
    def fail_second(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        raise ValueError("test replay failure")
    second.rewarm = fail_second
    original_inputs = runner.inputs_base.to_dict()
    code, accepted = request("/admin/inputs/async", {"asset": "*", "values": {"tp1_pts": 80}})
    assert code == 202 and entered.wait(3)
    try:
        assert port.equity_epoch > before["equity_epoch"]  # First asset staged a new epoch.
        code, pending = request("/status/public")
        assert code == 200 and all(x["view_stale"] for x in pending["assets"])
        assert pending["equity_epoch"] == before["equity_epoch"]
        assert pending["equity_series"] == before["equity_series"]
    finally:
        release.set()
    assert finished(request, accepted["job"])["status"] == "error"
    code, after = request("/status/public")
    assert code == 200 and not after["view_stale"]
    assert after["equity_epoch"] == before["equity_epoch"]
    assert runner.inputs_base.to_dict() == original_inputs
