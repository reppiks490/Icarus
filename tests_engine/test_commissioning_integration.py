from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_commissioning_server_dashboard_and_control_wiring():
    server = (ROOT / "icarus_engine" / "server.py").read_text(encoding="utf-8")
    dashboard = (ROOT / "icarus_engine" / "dashboard.html").read_text(encoding="utf-8")
    ui = (ROOT / "icarus_engine" / "commissioning-ui.js").read_text(encoding="utf-8")

    assert "from .commissioning import CommissioningEngine" in server
    assert "commissioning = CommissioningEngine(port.base_dir, port, chronofold)" in server
    assert '"/api/commissioning"' in server
    assert '"/commissioning-ui.js"' in server
    assert '"commissioning": commissioning.status' in server
    assert 'ControlAction("commissioning.capture"' in server
    assert 'ControlAction("commissioning.settle_all"' in server
    assert 'ControlAction("commissioning.tick"' in server
    assert "commissioning.start_background()" in server
    assert "commissioning.close()" in server

    assert '<script src="/commissioning-ui.js"></script>' in dashboard
    assert "view==='commissioning'" in dashboard
    assert "view === 'commissioning'" in dashboard
    assert "wireCommissioning()" in dashboard

    assert "window.commissioningHtml=commissioningHtml" in ui
    assert "fetch('/api/commissioning'" in ui
    assert "commissioning.capture" in ui
    assert "commissioning.settle_asset" in ui
    assert "commissioning.settle_all" in ui
    assert "commissioning.tick" in ui


def test_commissioning_ui_preserves_shadow_only_authority_language():
    ui = (ROOT / "icarus_engine" / "commissioning-ui.js").read_text(encoding="utf-8")
    for required in (
        "append-only",
        "shadow-only",
        "cannot arm execution",
        "execution_authorized=false",
        "production_decision_authorized=false",
        "broker_authority=false",
    ):
        assert required in ui
