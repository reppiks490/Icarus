"""Acceptance checks against real paper runners with an offline feed."""
import json
import sqlite3
import threading
import time
import urllib.error
import urllib.request

from icarus_engine import paper_workspaces
from icarus_engine.assets import REGISTRY
from icarus_engine.pine.timeframe import Bar
from icarus_engine.runtime import Journal, Portfolio
from icarus_engine.server import serve


class _OfflineFeed:
    def candles(self, *_args, **_kwargs):
        return []

    def ticker(self, _symbol):
        return 100.0


def _open_test_position(runner, direction):
    runner.em.process_bar(Bar(0, 100, 100, 100, 100, 1), 0)
    runner.em.entry("Acceptance", direction, 1)
    runner.em.process_bar(Bar(60, 100, 100, 100, 100, 1), 1)
    runner.last_price = 105.0 if direction > 0 else 95.0


def test_real_paper_workspaces_isolate_ledgers_positions_and_aggregate_open_pnl(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("ICARUS_FEED", "file")
    monkeypatch.setattr(
        paper_workspaces,
        "_PROFILE_DEFAULTS",
        tuple({**profile, "assets": ["NQ"]} for profile in paper_workspaces._PROFILE_DEFAULTS),
    )
    monkeypatch.setattr(paper_workspaces, "REGISTRY", {"NQ": REGISTRY["NQ"]})
    feed = _OfflineFeed()
    parent = Portfolio(
        Journal(":memory:"), str(tmp_path), profile="nq", pts_ref_symbol="NQ",
        feeds={"yahoo": feed, "coinbase": feed},
    )
    manager = paper_workspaces.PaperWorkspaceManager(parent)
    manager.start()
    journals = [portfolio.journal for portfolio in manager.portfolios.values()]
    try:
        deadline = time.monotonic() + 5
        while not all(
            portfolio.runner_list()[0].warm
            for portfolio in manager.portfolios.values()
        ) and time.monotonic() < deadline:
            time.sleep(0.01)

        assert all(portfolio.runner_list()[0].warm for portfolio in manager.portfolios.values())
        assert len({p.journal.path for p in manager.portfolios.values()}) == 4

        _open_test_position(manager.portfolios["cc1"].runner_list()[0], 1)
        _open_test_position(manager.portfolios["cc2"].runner_list()[0], -1)

        snapshot = manager.snapshot()
        profiles = {row["id"]: row for row in snapshot["profiles"]}
        assert snapshot["mode"] == "concurrent_paper"
        assert len(profiles) == 4
        assert profiles["cc1"]["status"]["net"] > 0
        assert profiles["cc2"]["status"]["net"] > 0
        assert profiles["cc3"]["status"]["net"] == 0
        assert profiles["cc4"]["status"]["net"] == 0
        assert sum(row["status"]["net"] for row in profiles.values()) == (
            profiles["cc1"]["status"]["net"] + profiles["cc2"]["status"]["net"]
        )
        assert all(not row["execution_authorized"] for row in profiles.values())

        manager.flatten("cc1")
        assert manager.portfolios["cc1"].runner_list()[0].em.position_size == 0
        assert manager.portfolios["cc2"].runner_list()[0].em.position_size == -1
        assert manager.portfolios["cc3"].runner_list()[0].em.position_size == 0
        assert manager.portfolios["cc4"].runner_list()[0].em.position_size == 0
    finally:
        manager.stop()
    for journal in journals:
        try:
            journal.con.execute("SELECT 1")
        except sqlite3.ProgrammingError:
            pass
        else:
            raise AssertionError("paper workspace journal stayed open after manager shutdown")


def test_command_center_api_reports_isolated_pnl_and_requires_confirmed_paper_flatten(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("ICARUS_FEED", "file")
    monkeypatch.setattr(
        paper_workspaces,
        "_PROFILE_DEFAULTS",
        tuple({**profile, "assets": ["NQ"]} for profile in paper_workspaces._PROFILE_DEFAULTS),
    )
    monkeypatch.setattr(paper_workspaces, "REGISTRY", {"NQ": REGISTRY["NQ"]})
    feed = _OfflineFeed()
    parent = Portfolio(
        Journal(":memory:"), str(tmp_path), profile="nq", pts_ref_symbol="NQ",
        feeds={"yahoo": feed, "coinbase": feed},
    )
    server = serve(parent, 0, token="test-token", start=False)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    server.command_centers.start()
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not all(
            portfolio.runner_list()[0].warm
            for portfolio in server.command_centers.portfolios.values()
        ) and time.monotonic() < deadline:
            time.sleep(0.01)

        _open_test_position(server.command_centers.portfolios["cc1"].runner_list()[0], 1)
        _open_test_position(server.command_centers.portfolios["cc2"].runner_list()[0], -1)
        base = f"http://127.0.0.1:{server.server_port}"

        with urllib.request.urlopen(base + "/api/command-centers", timeout=5) as reply:
            data = json.load(reply)
        profiles = {row["id"]: row for row in data["profiles"]}
        assert data["mode"] == "concurrent_paper"
        assert len(profiles) == 4
        assert all(row["paper_only"] and not row["execution_authorized"] for row in profiles.values())
        assert profiles["cc1"]["status"]["net"] > 0
        assert profiles["cc2"]["status"]["net"] > 0
        assert profiles["cc3"]["status"]["net"] == 0
        assert profiles["cc4"]["status"]["net"] == 0

        def post(path, payload, token):
            request = urllib.request.Request(
                base + path,
                data=json.dumps(payload).encode(),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(request, timeout=5) as reply:
                    return reply.status, json.load(reply)
            except urllib.error.HTTPError as error:
                return error.code, json.loads(error.read())

        cc1 = server.command_centers.portfolios["cc1"].runner_list()[0]
        cc2 = server.command_centers.portfolios["cc2"].runner_list()[0]
        assert post("/admin/command-centers/cc1/pause", {"paused": "false"}, "test-token")[0] == 400
        assert not cc1.paused
        assert post("/admin/command-centers/cc1/pause", {"paused": True}, "test-token")[0] == 200
        assert cc1.paused and not cc2.paused
        assert post("/admin/command-centers/cc1/pause", {"paused": False}, "test-token")[0] == 200
        assert not cc1.paused and not cc2.paused
        assert post("/admin/command-centers/cc1/flatten", {"confirm": True}, "bad-token")[0] == 401
        assert post("/admin/command-centers/cc1/flatten", {}, "test-token")[0] == 400
        assert cc1.em.position_size == 1 and cc2.em.position_size == -1

        status, response = post(
            "/admin/command-centers/cc1/flatten", {"confirm": True}, "test-token"
        )
        assert status == 200 and response["paper_only"] and response["paused"]
        assert cc1.em.position_size == 0
        assert cc2.em.position_size == -1
        assert server.command_centers.portfolios["cc3"].runner_list()[0].em.position_size == 0
        assert server.command_centers.portfolios["cc4"].runner_list()[0].em.position_size == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
        parent.journal.con.close()
