"""Real Chromium controls for independent, revisioned paper worker power."""
import copy
import threading

import pytest

from icarus_engine import paper_workspaces
from tests_engine.test_workspace_api import _open_live, workspace_http  # noqa: F401
from tests_engine.test_workspace_dashboard_browser import common_page


def _runtime(request):
    code, data, _ = request("/api/workspace-runtime")
    assert code == 200, data
    assert data["schema_version"] == "icarus.workspace-power.v1"
    assert data["paper_only"] is True and data["execution_authorized"] is False
    return {row["id"]: row for row in data["workspaces"]}


def _ready(page):
    page.wait_for_function("() => window.IcarusWorkspacePower !== undefined")
    page.evaluate("async () => { await IcarusWorkspacePower.ready; await IcarusWorkspacePower.refresh(); }")


def test_main_shows_four_independent_switches_without_starting_or_stopping(workspace_http):
    _, _, request = workspace_http
    before = _runtime(request)
    with common_page(workspace_http, "main") as (page, _):
        posts = []
        page.on("request", lambda req: posts.append(req.url) if req.method == "POST" else None)
        page.reload(wait_until="load")
        page.evaluate("async () => { await dashboardReady; }")
        _ready(page)
        switches = page.locator("#workspace-power input[role=switch]")
        assert switches.count() == 4
        for key in ("cc1", "cc2", "cc3", "cc4"):
            assert page.get_by_role("switch", name=key.upper() + " paper workers", exact=True).is_checked()
        assert "spare" in page.locator('[data-power-row="cc3"]').inner_text().lower()
        assert posts == []
        assert not page.icarus_errors
    assert _runtime(request) == before


@pytest.mark.parametrize("scope", ["cc1", "cc2", "cc3", "cc4"])
def test_selected_dashboard_only_exposes_its_immutable_power_scope(workspace_http, scope):
    with common_page(workspace_http, scope) as (page, _):
        _ready(page)
        page.evaluate("history.replaceState(null, '', '?workspace=cc4&profile=main'); localStorage.setItem('icarus-workspace','main')")
        assert page.locator("#workspace-power input[role=switch]").count() == 1
        assert page.get_by_role("switch", name=scope.upper() + " paper workers", exact=True).is_checked()
        assert page.evaluate("IcarusWorkspacePower.context.id") == scope
        assert not page.icarus_errors


@pytest.mark.parametrize("scope", ["cc1", "cc2", "cc4"])
def test_main_switch_stops_only_requested_workspace_and_preserves_profiles(workspace_http, scope):
    server, parent, request = workspace_http
    profiles = copy.deepcopy(server.command_centers.profiles)
    original = dict(server.command_centers.portfolios)
    before = _runtime(request)
    with common_page(workspace_http, "main") as (page, _):
        _ready(page)
        posts = []
        page.on("request", lambda req: posts.append((req.url, req.post_data_json))
                if req.method == "POST" and req.url.endswith("/runtime") else None)
        switch = page.get_by_role("switch", name=scope.upper() + " paper workers", exact=True)
        if scope == "cc2":
            switch.focus()
            switch.press("Space")
        else:
            switch.click()
        page.wait_for_function("id => document.querySelector('[data-power-state=' + id + ']').textContent === 'OFF'", arg=scope)
        switch = page.get_by_role("switch", name=scope.upper() + " paper workers", exact=True)
        assert not switch.is_checked() and switch.is_enabled()
        assert len(posts) == 1
        assert posts[0][0].endswith("/admin/command-centers/" + scope + "/runtime")
        assert posts[0][1] == {"enabled": False, "expected_revision": before[scope]["revision"]}
        assert not page.evaluate("IcarusWorkspacePower.isOff('main')")
        assert not page.icarus_errors
    after = _runtime(request)
    assert after[scope]["runtime_state"] == "OFF"
    assert after[scope]["desired_enabled"] is False
    assert server.command_centers.profiles == profiles
    assert parent.runners["NQ"].last_price == 900 and not parent.runners["NQ"].paused
    for sibling in set(before) - {scope}:
        assert after[sibling] == before[sibling]
        assert server.command_centers.portfolios[sibling] is original[sibling]


def test_viewer_runtime_refusal_displays_actual_403_and_keeps_worker_on(workspace_http):
    _, _, request = workspace_http
    viewer = request("/admin/access/add", body={"label": "power-viewer"})[1]["user"]["token"]
    before = _runtime(request)
    with common_page(workspace_http, "cc2", token=viewer) as (page, _):
        _ready(page)
        switch = page.get_by_role("switch", name="CC2 paper workers", exact=True)
        switch.click()
        page.wait_for_function("() => document.querySelector('[data-power-error=cc2]').textContent.includes('403')")
        assert switch.is_checked() and switch.is_enabled()
        assert page.locator('[data-power-state="cc2"]').inner_text() == "ON"
        assert page.evaluate("localStorage.getItem('icarus-engine-token')") == viewer
    assert _runtime(request) == before


def test_open_position_refusal_is_visible_and_never_flattens(workspace_http):
    server, _, request = workspace_http
    runner = server.command_centers.portfolios["cc1"].runners["NQ"]
    _open_live(runner)
    assert runner.em.position_size == 1
    before = _runtime(request)
    with common_page(workspace_http, "cc1") as (page, _):
        _ready(page)
        switch = page.get_by_role("switch", name="CC1 paper workers", exact=True)
        switch.click()
        page.wait_for_function("() => document.querySelector('[data-power-error=cc1]').textContent.includes('409')")
        reason = page.locator('[data-power-error="cc1"]').inner_text().lower()
        assert "position" in reason or "flat" in reason
        assert switch.is_checked() and switch.is_enabled()
    assert runner.em.position_size == 1
    assert _runtime(request) == before


def test_starting_and_stopping_wait_for_real_http_readback(workspace_http, monkeypatch):
    server, parent, request = workspace_http
    profiles = copy.deepcopy(server.command_centers.profiles)
    start_entered, start_release = threading.Event(), threading.Event()
    stop_entered, stop_release = threading.Event(), threading.Event()
    created = []
    original_stop = paper_workspaces.WorkspacePortfolio.stop

    def start_local_workers(portfolio):
        # Replace only provider-facing worker startup. Control, persistence,
        # publication, HTTP and browser state remain the production path.
        created.append(portfolio)
        start_entered.set()
        assert start_release.wait(10)
        worker = threading.Thread(target=portfolio._stop.wait, daemon=True)
        worker.start()
        portfolio._threads["NQ"] = worker
        sampler = threading.Thread(target=portfolio._stop.wait, daemon=True)
        sampler.start()
        portfolio._sampler_thread = sampler

    def hold_stop(portfolio):
        if portfolio in created:
            stop_entered.set()
            assert stop_release.wait(10)
        return original_stop(portfolio)

    monkeypatch.setattr(paper_workspaces.WorkspacePortfolio, "start", start_local_workers)
    monkeypatch.setattr(paper_workspaces.WorkspacePortfolio, "stop", hold_stop)
    try:
        with common_page(workspace_http, "main") as (page, _):
            _ready(page)
            switch = page.get_by_role("switch", name="CC1 paper workers", exact=True)
            switch.click()
            page.wait_for_function("() => document.querySelector('[data-power-state=cc1]').textContent === 'OFF' && !document.querySelector('#workspace-power-cc1').disabled")
            switch.click()
            page.wait_for_function("() => document.querySelector('[data-power-state=cc1]').textContent === 'STARTING'")
            assert start_entered.is_set() and switch.is_disabled()
            assert not switch.is_checked() and page.evaluate("IcarusWorkspacePower.isOff('cc1')")
            assert page.get_by_role("switch", name="CC2 paper workers", exact=True).is_enabled()
            start_release.set()
            page.wait_for_function("() => document.querySelector('[data-power-state=cc1]').textContent === 'ON'")
            assert switch.is_checked() and switch.is_enabled()
            assert created[0]._threads["NQ"].is_alive()
            switch.click()
            page.wait_for_function("() => document.querySelector('[data-power-state=cc1]').textContent === 'STOPPING'")
            assert stop_entered.is_set() and switch.is_disabled()
            assert page.evaluate("IcarusWorkspacePower.isOff('cc1')")
            stop_release.set()
            page.wait_for_function("() => document.querySelector('[data-power-state=cc1]').textContent === 'OFF'")
            assert not switch.is_checked() and switch.is_enabled()
            assert not created[0]._threads["NQ"].is_alive()
            assert not page.icarus_errors
    finally:
        start_release.set()
        stop_release.set()
    assert server.command_centers.profiles == profiles
    assert parent.runners["NQ"].last_price == 900 and not parent._stop.is_set()
    assert _runtime(request)["cc1"]["runtime_state"] == "OFF"


def test_owner_can_cancel_blocked_start_and_wait_for_stopped_readback(workspace_http, monkeypatch):
    server, parent, request = workspace_http
    entered, release = threading.Event(), threading.Event()

    def blocked_start(portfolio):
        # Hold the provider-facing boundary; the real control worker must
        # consume its cancellation before publishing this portfolio.
        entered.set()
        assert release.wait(15)

    monkeypatch.setattr(paper_workspaces.WorkspacePortfolio, "start", blocked_start)
    try:
        with common_page(workspace_http, "cc1") as (page, _):
            _ready(page)
            switch = page.get_by_role("switch", name="CC1 paper workers", exact=True)
            switch.click()
            page.wait_for_function("() => document.querySelector('[data-power-state=cc1]').textContent === 'OFF' && !document.querySelector('#workspace-power-cc1').disabled")
            switch.click()
            page.wait_for_function("() => document.querySelector('[data-power-state=cc1]').textContent === 'STARTING'")
            assert entered.is_set() and switch.is_disabled() and not switch.is_checked()
            cancel = page.get_by_role("button", name="Cancel CC1 start", exact=True)
            assert cancel.count() == 1, "STARTING must offer an explicit owner OFF action"
            page.wait_for_function("() => !document.querySelector('[aria-label=\"Cancel CC1 start\"]').disabled")
            assert cancel.is_enabled()
            before_cancel = _runtime(request)["cc1"]
            posts = []
            page.on("request", lambda req: posts.append(req.post_data_json)
                    if req.method == "POST" and req.url.endswith("/cc1/runtime") else None)
            cancel.click()
            page.wait_for_function("() => document.querySelector('[data-power-state=cc1]').textContent === 'STOPPING'")
            assert switch.is_disabled() and not switch.is_checked()
            assert not cancel.is_visible() or cancel.is_disabled()
            assert posts == [{"enabled": False, "expected_revision": before_cancel["revision"]}]
            assert page.evaluate("IcarusWorkspacePower.isOff('cc1')")
            release.set()
            page.wait_for_function("() => document.querySelector('[data-power-state=cc1]').textContent === 'OFF'")
            assert not switch.is_checked() and switch.is_enabled()
            assert not cancel.is_visible()
            assert not page.icarus_errors
    finally:
        release.set()
    assert _runtime(request)["cc1"]["desired_enabled"] is False
    assert "cc1" not in server.command_centers.portfolios
    assert parent.runners["NQ"].last_price == 900 and not parent._stop.is_set()


def test_owner_can_retry_failed_stop_without_reenabling_old_workers(workspace_http, monkeypatch):
    server, parent, request = workspace_http
    old = server.command_centers.portfolios["cc1"]
    original_start = threading.Thread.start
    original_stop = paper_workspaces.WorkspacePortfolio.stop
    stop_release = threading.Event()
    failed = []

    def fail_first_drain_start(worker):
        if worker.name == "workspace-power-cc1" and not failed:
            failed.append(worker)
            raise RuntimeError("test lifecycle thread admission failure")
        return original_start(worker)

    def hold_retry_stop(portfolio):
        if portfolio is old:
            assert stop_release.wait(15)
        return original_stop(portfolio)

    monkeypatch.setattr(threading.Thread, "start", fail_first_drain_start)
    monkeypatch.setattr(paper_workspaces.WorkspacePortfolio, "stop", hold_retry_stop)
    try:
        with common_page(workspace_http, "cc1") as (page, _):
            _ready(page)
            switch = page.get_by_role("switch", name="CC1 paper workers", exact=True)
            switch.click()
            page.wait_for_function("() => document.querySelector('[data-power-state=cc1]').textContent === 'ERROR'")
            error = _runtime(request)["cc1"]
            assert error["desired_enabled"] is False and failed
            assert server.command_centers.portfolios["cc1"] is old
            retry = page.get_by_role("button", name="Retry CC1 stop", exact=True)
            assert retry.count() == 1, "Failed OFF must offer a retry of the saved OFF operation"
            page.wait_for_function("() => !document.querySelector('[aria-label=\"Retry CC1 stop\"]').disabled")
            posts = []
            page.on("request", lambda req: posts.append(req.post_data_json)
                    if req.method == "POST" and req.url.endswith("/cc1/runtime") else None)
            retry.click()
            page.wait_for_function("() => document.querySelector('[data-power-state=cc1]').textContent === 'STOPPING'")
            assert posts == [{"enabled": False, "expected_revision": error["revision"]}]
            assert switch.is_disabled() and not switch.is_checked()
            stop_release.set()
            page.wait_for_function("() => document.querySelector('[data-power-state=cc1]').textContent === 'OFF'")
            assert switch.is_enabled() and not switch.is_checked()
            assert not page.icarus_errors
    finally:
        stop_release.set()
    assert "cc1" not in server.command_centers.portfolios
    assert _runtime(request)["cc1"]["desired_enabled"] is False
    assert parent.runners["NQ"].last_price == 900 and not parent._stop.is_set()


def test_connections_links_to_main_without_power_actions(workspace_http):
    with common_page(workspace_http, "main") as (page, base):
        page.goto(base + "/connections", wait_until="load")
        link = page.get_by_role("link", name="Paper worker on/off controls in Main")
        assert page.locator("#workspace-power input[role=switch]").count() == 0
        link.click()
        page.wait_for_load_state("load")
        page.evaluate("async () => { await dashboardReady; }")
        _ready(page)
        assert page.evaluate("view") == "overview"
        assert page.evaluate("IcarusClient.context.id") == "main"
        assert page.locator("#workspace-power input[role=switch]").count() == 4


def test_power_controls_wrap_at_390px_and_keep_light_theme_text_readable(workspace_http):
    with common_page(workspace_http, "main", viewport={"width": 390, "height": 900}) as (page, _):
        _ready(page)
        page.evaluate("document.documentElement.dataset.theme='light'")
        geometry = page.locator("#workspace-power").evaluate("""el => ({
          width: el.clientWidth, scroll: el.scrollWidth,
          foreground: getComputedStyle(el).color, background: getComputedStyle(el).backgroundColor,
          right: el.getBoundingClientRect().right,
          rows: [...el.querySelectorAll('[data-power-row]')].map(row => ({width:row.clientWidth,scroll:row.scrollWidth}))
        })""")
        assert geometry["scroll"] <= geometry["width"] and geometry["right"] <= 390
        assert all(row["scroll"] <= row["width"] for row in geometry["rows"])
        assert geometry["foreground"] != geometry["background"]
        switch = page.get_by_role("switch", name="CC1 paper workers", exact=True)
        switch.focus()
        assert switch.evaluate("el => el === document.activeElement")


def test_failed_runtime_metadata_does_not_disable_main_dashboard(workspace_http):
    with common_page(workspace_http, "main") as (page, base):
        _ready(page)
        page.route(base + "/api/workspace-runtime", lambda route: route.abort())
        page.evaluate("async () => { await IcarusWorkspacePower.refresh(); await refresh(); }")
        assert "unavailable" in page.locator("#workspace-power-status").inner_text().lower()
        assert page.evaluate("last.assets.find(a => a.symbol === 'NQ').price") == 900
        assert not page.evaluate("IcarusWorkspacePower.isOff('main')")
