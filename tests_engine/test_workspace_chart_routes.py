"""Workspace chart pages retain the selected paper runner's observed history."""
import copy
import json
import threading
from collections import deque
from http.client import HTTPConnection

import pytest

from icarus_engine.assets import REGISTRY
from icarus_engine.paper_workspaces import WorkspacePortfolio
from icarus_engine.pine.timeframe import Bar
from icarus_engine.runtime import Journal, Portfolio
from icarus_engine.server import serve


class _OfflineFeed:
    def candles(self, *_args, **_kwargs):
        raise AssertionError("chart reads must not fetch provider history")

    def ticker(self, *_args, **_kwargs):
        raise AssertionError("chart reads must not fetch provider quotes")


def _history(runner, *, count=60, price=100):
    runner.bars = deque(
        (Bar(index * 60, price, price + 1, price - 1, price, 1)
         for index in range(count)), maxlen=count,
    )
    runner.overlays = deque(
        ({"ts": index * 60, "marker": index} for index in range(count)),
        maxlen=count,
    )
    runner.recent_fills = deque(
        ({"ts": index * 60, "id": f"{price}:{index}"} for index in range(count)),
        maxlen=count,
    )


@pytest.fixture
def charts(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_FEED", "file")
    feed = _OfflineFeed()
    parent = Portfolio(Journal(":memory:"), str(tmp_path),
                       feeds={"yahoo": feed, "coinbase": feed})
    parent.pts_ref_price = 100
    for symbol in ("NQ", "ES"):
        _history(parent.add_asset(copy.deepcopy(REGISTRY[symbol]), start=False), price=900)
    server = serve(parent, 0, token="offline-chart-test", start=False)
    journals = []
    for index, profile_id in enumerate(("cc1", "cc2", "cc3", "cc4"), 1):
        journal = Journal(":memory:")
        journals.append(journal)
        workspace = WorkspacePortfolio(
            journal, str(tmp_path),
            workspace=copy.deepcopy(server.command_centers.profiles[profile_id]),
            feeds={"yahoo": feed, "coinbase": feed},
        )
        runner = workspace.add_asset(copy.deepcopy(REGISTRY["NQ"]), start=False)
        _history(runner, price=index * 100)
        server.command_centers.portfolios[profile_id] = workspace
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def get(path):
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        try:
            connection.request("GET", path)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    try:
        yield server, parent, get
    finally:
        server.shutdown()
        thread.join(5)
        server.server_close()
        for journal in journals:
            journal.close()
        parent.journal.close()


@pytest.mark.parametrize("profile_id,price", [("cc1", 100), ("cc2", 200), ("cc3", 300), ("cc4", 400)])
def test_workspace_chart_pages_keep_selected_bars_overlays_fills_and_metadata(charts, profile_id, price):
    _, _, get = charts
    path = f"/api/command-centers/{profile_id}/chart/NQ?n=20"
    code, latest = get(path)
    assert code == 200
    code, older = get(path + "&offset=20")
    assert code == 200
    assert [row[0] for row in latest["bars"]] == list(range(2400, 3600, 60))
    assert [row[0] for row in older["bars"]] == list(range(1200, 2400, 60))
    assert {row[4] for row in older["bars"]} == {price}
    assert [row["ts"] for row in older["overlays"]] == list(range(1200, 2400, 60))
    assert [row["id"] for row in older["fills"]] == [f"{price}:{index}" for index in range(20, 40)]
    assert older["history"] == {
        "available": 60, "offset": 20, "page_size": 20,
        "has_older": True, "has_newer": True,
    }
    assert latest["history"]["offset"] == 0
    assert latest["history"]["has_newer"] is False


@pytest.mark.parametrize("query,page_size,offset", [
    ("n=1&offset=-20", 20, 0),
    ("n=1400", 1400, 0),
    ("n=9000&offset=60000", 5000, 50000),
    ("n=bad&offset=bad", 240, 0),
    ("n=20&offset=60", 20, 60),
    ("", 240, 0),
])
def test_workspace_chart_query_bounds_match_main_chart(charts, query, page_size, offset):
    _, _, get = charts
    code, scoped = get("/api/command-centers/cc2/chart/NQ?" + query)
    assert code == 200
    code, main = get("/api/chart/NQ?" + query)
    assert code == 200
    assert scoped["history"] == main["history"]
    assert scoped["history"]["page_size"] == page_size
    assert scoped["history"]["offset"] == offset
    if offset >= 60:
        assert scoped["bars"] == scoped["overlays"] == scoped["fills"] == []
        assert scoped["history"]["has_older"] is False
        assert scoped["history"]["has_newer"] is True
    else:
        assert len(scoped["bars"]) == min(page_size, 60)
        assert {row[4] for row in scoped["bars"]} == {200}


def test_workspace_chart_can_return_the_full_main_chart_page_bound(charts):
    server, parent, get = charts
    _history(server.command_centers.portfolios["cc2"].runners["NQ"], count=5100, price=200)
    _history(parent.runners["NQ"], count=5100, price=900)
    code, scoped = get("/api/command-centers/cc2/chart/NQ?n=9000")
    assert code == 200
    code, main = get("/api/chart/NQ?n=9000")
    assert code == 200
    assert len(scoped["bars"]) == len(main["bars"]) == 5000
    assert scoped["bars"][0][0] == 6000
    assert scoped["bars"][-1][0] == 305940
    assert scoped["history"] == main["history"] == {
        "available": 5100, "offset": 0, "page_size": 5000,
        "has_older": True, "has_newer": False,
    }


def test_workspace_chart_missing_runtime_or_asset_never_falls_back_to_parent(charts):
    server, _, get = charts
    assert get("/api/chart/NQ")[0] == get("/api/chart/ES")[0] == 200
    assert get("/api/command-centers/cc2/chart/ES")[0] == 404
    assert get("/api/command-centers/cc5/chart/NQ")[0] == 404
    workspace = server.command_centers.portfolios.pop("cc3")
    try:
        assert get("/api/command-centers/cc3/chart/NQ")[0] == 503
        code, sibling = get("/api/command-centers/cc4/chart/NQ?n=20")
        assert code == 200
        assert {row[4] for row in sibling["bars"]} == {400}
    finally:
        server.command_centers.portfolios["cc3"] = workspace
