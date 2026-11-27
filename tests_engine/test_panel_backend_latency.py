"""Display reads must not wait for warmup or a scheduler's research work."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import ExitStack
import sqlite3
import threading

import pytest

from tests_engine.test_workspace_api import workspace_http  # noqa: F401


@pytest.mark.parametrize("path", ["/api/brain", "/api/research"])
def test_main_intelligence_reads_published_views_during_runner_work(workspace_http, path):
    _, parent, request = workspace_http
    held, release = threading.Event(), threading.Event()

    def warmup():
        with ExitStack() as stack:
            for runner in parent.runner_list():
                stack.enter_context(runner.lock)
            held.set()
            release.wait(10)

    worker = threading.Thread(target=warmup)
    worker.start()
    assert held.wait(2)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(request, path)
        try:
            result = future.result(timeout=2)
        except TimeoutError:
            pytest.fail("intelligence display waited for runner work instead of its published view")
        finally:
            release.set()
            worker.join(3)
        code, data, _ = result
    assert code == 200, data
    if path == "/api/research":
        assert {row["asset"] for row in data["assets"]} == {"NQ", "ES"}
        assert all(row["view_stale"] and row["view_captured_at"] for row in data["assets"])
        assert data["execution_authorized"] is False
    else:
        assert {row["asset"] for row in data["market"]["regimes"]} == {"NQ", "ES"}
        assert data["market_view"]["view_stale"] is True
        assert data["authority"]["execution_authorized"] is False


@pytest.mark.parametrize("path", ["/api/brain", "/api/research", "/api/research/adaptation"])
@pytest.mark.parametrize("busy", ["mutex", "writer"])
def test_intelligence_reads_committed_scheduler_state_during_research_work(workspace_http, path, busy):
    server, _, request = workspace_http
    scheduler = server.research.adaptation
    scheduler.configure({"assets": ["NQ"], "cadence_seconds": 120})
    held, release = threading.Event(), threading.Event()

    def research_work():
        with ExitStack() as stack:
            if busy == "mutex":
                stack.enter_context(scheduler._mutex)
            else:
                con = stack.enter_context(sqlite3.connect(scheduler.lock_path))
                con.execute("BEGIN IMMEDIATE")
            held.set()
            release.wait(10)

    worker = threading.Thread(target=research_work)
    worker.start()
    assert held.wait(2)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(request, path)
        try:
            code, data, _ = future.result(timeout=2)
        except TimeoutError:
            pytest.fail("intelligence display waited for a scheduler writer reservation")
        finally:
            release.set()
            worker.join(3)
    assert code == 200, data
    if path == "/api/brain":
        assert data["authority"]["execution_authorized"] is False
        state = data["research_view"]["adaptation"]
    else:
        state = data["adaptation"] if path == "/api/research" else data
        assert state["config"]["assets"] == ["NQ"]
        assert state["config"]["cadence_seconds"] == 120
    if busy == "mutex":
        assert state["view_stale"] is True
    assert state["view_captured_at"] > 0
    assert "cross-process work is not observed" in state["view_freshness"]


@pytest.mark.parametrize("path", ["/api/brain", "/api/research"])
def test_missing_published_market_view_reports_unavailable(workspace_http, path):
    _, parent, request = workspace_http
    for runner in parent.runner_list():
        runner._public_views = None
    code, data, _ = request(path)
    assert code == 503, data
    assert "not ready" in data["detail"]
    assert data["execution_authorized"] is False


@pytest.mark.parametrize("service_name", ["ledger", "analysis", "activation"])
def test_research_panel_reads_service_state_during_writer_reservation(workspace_http, service_name):
    server, _, request = workspace_http
    if service_name == "ledger":
        service = server.research.ledger
        database = service.path
    elif service_name == "analysis":
        service = server.research.analysis.journal
        database = service.path
    else:
        service = server.research.activation
        database = service.path
    writer = sqlite3.connect(str(database), timeout=1)
    writer.execute("BEGIN IMMEDIATE")
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(request, "/api/research")
            try:
                code, data, _ = future.result(timeout=2)
            except TimeoutError:
                pytest.fail(f"research panel waited for a {service_name} writer reservation")
    finally:
        writer.rollback()
        writer.close()
    assert code == 200, data
    assert data["execution_authorized"] is False


def test_research_panel_returns_during_learning_snapshot_lock(workspace_http):
    server, _, request = workspace_http
    learning = server.research.learning
    held, release = threading.Event(), threading.Event()

    def hold_snapshot_lock():
        with learning._lock:
            held.set()
            release.wait(10)

    worker = threading.Thread(target=hold_snapshot_lock)
    worker.start()
    assert held.wait(2)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(request, "/api/research")
        try:
            code, data, _ = future.result(timeout=2)
        except TimeoutError:
            pytest.fail("research panel waited for learning snapshot work")
        finally:
            release.set()
            worker.join(3)
    assert code == 200, data
    assert data["learning"]["execution_authorized"] is False
