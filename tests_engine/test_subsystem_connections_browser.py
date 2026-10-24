"""Chromium acceptance of the real page-owned transport and subsystem component.

Only the diagnostic HTTP frames are synthetic. The served dashboard, immutable
IcarusClient, selected routing, DOM, request cancellation and timers are real.
"""
import json
import time
from pathlib import Path

import pytest

from tests_engine.test_workspace_api import workspace_http  # noqa: F401


SOURCE = Path(__file__).resolve().parents[1] / "icarus_engine/subsystem-connections-ui.js"


def common_page(*args, **kwargs):
    # The existing required CI module imports these acceptance functions too.
    # Resolve its shared fixture lazily so either file can be collected first.
    from tests_engine.test_workspace_dashboard_browser import common_page as hosted_page
    return hosted_page(*args, **kwargs)


def _frame(scope, **changes):
    now = time.time_ns()
    data = {
        "schema_version": "icarus-nexus-aion-v1", "workspace_id": scope,
        "config_revision": 0, "state": "OBSERVING", "observed_at_ns": now,
        "capture_age_seconds": 0.2, "warnings": [], "source_revision": "27ae69c593ede3019957100cd401625bd2424f43",
        "execution_authorized": False, "production_decision_authorized": False,
        "assets": [{"symbol": "NQ", "provider": "published cache", "provider_symbol": "NQ",
                    "kind": "paper", "captured_at_ns": now, "capture_age_seconds": 0.2,
                    "cache_state": "CURRENT", "bar_index": 7, "last_bar_ts": now / 1e9 - 2,
                    "poll_age_seconds": 1, "bar_age_seconds": 2, "price_age_seconds": 1,
                    "active_error": False, "warm": True, "rewarming": False,
                    "paused": False, "state": "OBSERVING"}],
        "nexus": {"state": "UNKNOWN_SLO", "plane_hash": "native-plane-123", "stream_count": 1,
                  "unknown_slo_streams": 1},
        "aion": {"state": "VERIFIED", "event_count": 4, "chain_verified": True,
                 "last_persisted_ns": now, "recovered_event_count": 2},
    }
    data.update(changes)
    return data


def _serve(page, base, scope, state):
    path = "/api/subsystem-connections" if scope == "main" else f"/api/command-centers/{scope}/panels/subsystem-connections"
    state.setdefault("requests", [])
    page.on("request", lambda req: state["requests"].append(req) if req.url == base + path else None)

    def reply(route):
        frame = _frame(scope, **state.get("changes", {}))
        if state.get("error"):
            return route.fulfill(status=503, content_type="application/json", body=json.dumps({
                "workspace_id": scope, "detail": "diagnostic storage unavailable"}))
        return route.fulfill(content_type="application/json", body=json.dumps(frame))

    page.route(base + path, reply)
    return path


def _mount(page):
    page.add_script_tag(path=str(SOURCE))
    page.evaluate("""() => {
      document.querySelector('#subsystem-browser-mount')?.remove();
      const container=document.createElement('div');container.id='subsystem-browser-mount';
      document.body.append(container);window.subsystemContainer=container;
      window.subsystemView=IcarusSubsystemConnections.mount(container,IcarusClient);
    }""")
    page.wait_for_function("() => document.querySelector('#subsystem-state')?.textContent.includes('OBSERVING')")


@pytest.mark.parametrize("scope,width", [("main", 1440), ("cc2", 390)])
def test_subsystems_show_native_receipts_unknown_slos_and_safe_selected_identity(workspace_http, scope, width):
    """Catches wrong selected routes, provider-health inference and HTML injection."""
    with common_page(workspace_http, scope, viewport={"width": width, "height": 950}, pause_periodic=True) as (page, base):
        state = {"changes": {"warnings": ["<img src=x onerror=window.subsystemXss=1>"],
                             "assets": [_frame(scope)["assets"][0] | {"symbol": "<svg onload=window.subsystemXss=1>"}]}}
        path = _serve(page, base, scope, state)
        _mount(page)
        assert page.evaluate("Object.isFrozen(IcarusClient) && Object.isFrozen(IcarusClient.context)")
        assert page.locator("#subsystem-title").inner_text().startswith(scope.upper())
        assert "native-plane-123" in page.locator("#subsystem-nexus").inner_text()
        assert "4" in page.locator("#subsystem-aion").inner_text()
        assert "2" in page.locator("#subsystem-aion").inner_text()
        assert "unknown" in page.locator("#subsystem-slo").inner_text().lower()
        assert "adapter-local" in page.locator("#subsystem-slo").inner_text().lower()
        assert "verified" in page.locator("#subsystem-chain").inner_text().lower()
        assert "27ae69c" in page.locator("#subsystem-source").inner_text()
        assert "2.0s" in page.locator("#subsystem-assets").inner_text()
        assert page.locator("#subsystem-connections img, #subsystem-connections svg").count() == 0
        assert not page.evaluate("window.subsystemXss")
        assert all(req.url == base + path for req in state["requests"])
        assert all(req.headers.get("x-icarus-workspace") == scope for req in state["requests"])
        assert page.locator("#subsystem-connections").evaluate("el => el.scrollWidth <= el.clientWidth")
        assert not page.icarus_errors


def test_subsystems_latest_failure_is_unavailable_and_recovers_automatically(workspace_http):
    """Catches cached success being relabelled current and a stopped retry loop."""
    with common_page(workspace_http, "cc1", pause_periodic=True) as (page, base):
        state = {}
        _serve(page, base, "cc1", state)
        _mount(page)
        button = page.get_by_role("button", name="Refresh subsystem status", exact=True)
        button.focus()
        page.evaluate("window.subsystemFocusedButton=document.activeElement")
        state["error"] = True
        button.click()
        page.wait_for_function("() => document.querySelector('#subsystem-state').textContent.includes('UNAVAILABLE')")
        assert "unavailable" in page.locator("#subsystem-nexus").inner_text().lower()
        assert "unavailable" in page.locator("#subsystem-aion").inner_text().lower()
        assert "native-plane-123" not in page.locator("#subsystem-connections").inner_text()
        assert page.evaluate("document.activeElement===subsystemFocusedButton && subsystemFocusedButton.isConnected")
        state["error"] = False
        state["changes"] = {"state": "DEGRADED", "capture_age_seconds": None,
                            "warnings": ["runner cache unavailable"],
                            "nexus": {"state": "UNAVAILABLE", "plane_hash": None,
                                      "stream_count": 0, "unknown_slo_streams": 0},
                            "aion": {"state": "UNAVAILABLE", "event_count": None,
                                     "chain_verified": None, "last_persisted_ns": None,
                                     "recovered_event_count": None}}
        page.wait_for_function("() => document.querySelector('#subsystem-state').textContent.includes('DEGRADED')", timeout=7000)
        assert "unknown" in page.locator("#subsystem-chain").inner_text().lower()
        assert "unknown" in page.locator("#subsystem-observed").inner_text().lower()
        state["changes"] = {}
        page.wait_for_function("() => document.querySelector('#subsystem-state').textContent.includes('OBSERVING')", timeout=7000)
        assert "native-plane-123" in page.locator("#subsystem-nexus").inner_text()
        assert page.evaluate("document.activeElement===subsystemFocusedButton")
        assert not page.icarus_errors


@pytest.mark.parametrize("changes", [
    {"workspace_id": "cc3"}, {"execution_authorized": True},
    {"production_decision_authorized": True}, {"observed_at_ns": 1},
    {"nexus": {}, "aion": {"chain_verified": True}},
])
def test_subsystems_reject_foreign_authorized_or_stale_frames(workspace_http, changes):
    """Catches rendering an old, foreign or authority-escalated diagnostic as current."""
    with common_page(workspace_http, "cc2", pause_periodic=True) as (page, base):
        state = {}
        _serve(page, base, "cc2", state)
        _mount(page)
        state["changes"] = changes
        page.get_by_role("button", name="Refresh subsystem status", exact=True).click()
        page.wait_for_function("() => /UNAVAILABLE|STALE/.test(document.querySelector('#subsystem-state').textContent)")
        assert "OBSERVING" not in page.locator("#subsystem-state").inner_text()
        assert not page.icarus_errors


@pytest.mark.parametrize("native_state", ["STARTING", "UNAVAILABLE", "STOPPED"])
def test_subsystems_keep_explicit_service_states_without_observations(workspace_http, native_state):
    """Catches an absent first observation overwriting real lifecycle/error states."""
    with common_page(workspace_http, "main", pause_periodic=True) as (page, base):
        state = {}
        _serve(page, base, "main", state)
        _mount(page)
        state["changes"] = {"state": native_state, "observed_at_ns": None,
                            "capture_age_seconds": None, "assets": []}
        page.get_by_role("button", name="Refresh subsystem status", exact=True).click()
        page.wait_for_function("expected => document.querySelector('#subsystem-state').textContent.startsWith(expected)", arg=native_state)
        assert "unknown" in page.locator("#subsystem-observed").inner_text().lower()
        assert not page.icarus_errors


def test_subsystems_pause_hidden_and_off_keep_focus_and_dispose_pending_requests(workspace_http):
    """Catches duplicate mounts/polls, hidden/OFF work and late detached writes."""
    with common_page(workspace_http, "cc1", pause_periodic=True) as (page, base):
        state = {}
        path = _serve(page, base, "cc1", state)
        _mount(page)
        assert page.evaluate("subsystemView===IcarusSubsystemConnections.mount(subsystemContainer,IcarusClient)")
        start = len(state["requests"])
        page.evaluate("subsystemContainer.hidden=true")
        page.wait_for_timeout(5300)
        assert len(state["requests"]) == start
        page.evaluate("subsystemContainer.hidden=false")
        page.wait_for_function("() => !document.querySelector('#subsystem-connections').hasAttribute('aria-busy')")
        page.wait_for_timeout(150)
        assert len(state["requests"]) == start + 1
        button = page.get_by_role("button", name="Refresh subsystem status", exact=True)
        button.focus()
        page.evaluate("window.subsystemFocusedButton=document.activeElement")
        page.wait_for_timeout(5200)
        assert len(state["requests"]) == start + 2
        assert page.evaluate("document.activeElement===subsystemFocusedButton")
        page.evaluate("""() => {
          window.subsystemTestHidden=true;
          Object.defineProperty(document,'hidden',{configurable:true,get:()=>subsystemTestHidden});
          document.dispatchEvent(new Event('visibilitychange'));
        }""")
        visible_reads = len(state["requests"])
        page.wait_for_timeout(5200)
        assert len(state["requests"]) == visible_reads
        page.evaluate("subsystemTestHidden=false;document.dispatchEvent(new Event('visibilitychange'))")
        page.wait_for_timeout(150)
        assert len(state["requests"]) == visible_reads + 1
        page.get_by_role("switch", name="CC1 paper workers", exact=True).click()
        page.wait_for_function("() => IcarusWorkspacePower.isOff('cc1')")
        page.wait_for_timeout(150)
        off_reads = len(state["requests"])
        page.wait_for_timeout(5200)
        assert len(state["requests"]) == off_reads
        assert "STOPPED" in page.locator("#subsystem-state").inner_text()
        page.get_by_role("switch", name="CC1 paper workers", exact=True).click()
        page.wait_for_function("() => !IcarusWorkspacePower.isOff('cc1')", timeout=15000)
        page.wait_for_function("() => document.querySelector('#subsystem-state').textContent.includes('OBSERVING')")
        held, failed = [], []
        page.on("requestfailed", lambda req: failed.append(req) if req.url == base + path else None)
        page.route(base + path, lambda route: held.append(route))
        page.evaluate("document.querySelector('#subsystem-refresh').click();document.querySelector('#subsystem-refresh').click();document.querySelector('#subsystem-refresh').click()")
        page.wait_for_timeout(150)
        assert len(held) == 1
        with page.expect_event("requestfailed", predicate=lambda req: req.url == base + path):
            page.evaluate("subsystemView.dispose();window.subsystemDisposedText=subsystemContainer.textContent")
        assert len(failed) == 1 and "ABORTED" in failed[0].failure
        for route in held:
            try:
                route.fulfill(content_type="application/json", body=json.dumps(_frame("cc1", state="DEGRADED")))
            except Exception:
                pass  # Chromium may discard an aborted interception immediately.
        disposed_reads = len(state["requests"])
        page.wait_for_timeout(5200)
        assert len(state["requests"]) == disposed_reads
        assert page.evaluate("subsystemContainer.textContent===subsystemDisposedText")
        assert not page.icarus_errors
