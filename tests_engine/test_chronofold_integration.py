from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_chronofold_server_and_dashboard_are_wired():
    server = (ROOT / "icarus_engine" / "server.py").read_text(encoding="utf-8")
    dashboard = (ROOT / "icarus_engine" / "dashboard.html").read_text(encoding="utf-8")
    ui = (ROOT / "icarus_engine" / "chronofold-ui.js").read_text(encoding="utf-8")

    assert "from .chronofold import ChronofoldEngine" in server
    assert "chronofold = ChronofoldEngine(port, possibility=possibility)" in server
    assert '"/api/chronofold"' in server
    assert '"/chronofold-ui.js"' in server
    assert '"chronofold": chronofold.status' in server

    assert '<script src="/chronofold-ui.js"></script>' in dashboard
    assert "view==='chronofold'" in dashboard
    assert "view === 'chronofold'" in dashboard
    assert "wireChronofold()" in dashboard

    assert "window.chronofoldHtml=chronofoldHtml" in ui
    assert "fetch('/api/chronofold'" in ui
    assert "assetsCache" in ui


def test_chronofold_truth_contract_is_visible_in_operator_ui():
    ui = (ROOT / "icarus_engine" / "chronofold-ui.js").read_text(encoding="utf-8")
    for required in (
        "no future leakage",
        "no execution authority",
        "no quantum-market claim",
        "not calibrated probabilities",
    ):
        assert required in ui
