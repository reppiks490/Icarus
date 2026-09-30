"""MCP control-surface contract tests. No daemon or network required."""
from __future__ import annotations

import icarus_bridge.mcp_server as mcp_server


def test_mcp_server_imports_and_registers_engine_surface():
    assert mcp_server.mcp is not None
    for name in (
        "engine_status",
        "engine_configuration",
        "set_engine_chart_config",
        "start_engine_backtest",
        "engine_backtest_status",
    ):
        assert callable(getattr(mcp_server, name))


def test_mcp_chart_config_forwards_only_requested_settings(monkeypatch):
    seen = {}

    def post(path, body):
        seen["path"] = path
        seen["body"] = body
        return {"ok": True}

    monkeypatch.setattr(mcp_server, "_engine_post", post)
    result = mcp_server.set_engine_chart_config(
        asset="nq", timeframe="2m", chart_type="heikin_ashi",
        fill_on="real", security_source="chart", persist=False,
    )
    assert result == {"ok": True}
    assert seen == {
        "path": "/admin/inputs",
        "body": {
            "asset": "NQ",
            "values": {},
            "chart": {
                "timeframe": "2m",
                "chart_type": "heikin_ashi",
                "fill_on": "real",
                "security_source": "chart",
            },
            "persist": False,
        },
    }


def test_mcp_backtest_omits_unspecified_fill_mode_so_engine_can_inherit(monkeypatch):
    seen = {}

    def post(path, body):
        seen["path"] = path
        seen["body"] = body
        return {"ok": True, "job": "j1"}

    monkeypatch.setattr(mcp_server, "_engine_post", post)
    result = mcp_server.start_engine_backtest(asset="nq", timeframe="5")
    assert result["job"] == "j1"
    assert seen["path"] == "/admin/backtest"
    assert seen["body"] == {"asset": "NQ", "timeframe": "5"}


def test_mcp_endpoint_settings_load_plant_env_and_blank_token_fallbacks(tmp_path, monkeypatch):
    plant = tmp_path / "plant"
    plant.mkdir()
    (plant / ".env").write_text(
        "ADMIN_TOKEN=bridge-admin\n"
        "ICARUS_ADMIN_TOKEN=\n"
        "ICARUS_BRIDGE_URL=http://127.0.0.1:9876\n"
        "ICARUS_ENGINE_URL=http://127.0.0.1:9877\n"
        "ICARUS_ENGINE_TOKEN=\n",
        encoding="utf-8",
    )
    for key in (
        "ADMIN_TOKEN", "ICARUS_ADMIN_TOKEN", "ICARUS_BRIDGE_URL",
        "ICARUS_ENGINE_URL", "ICARUS_ENGINE_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ICARUS_HOME", str(plant))

    bridge_url, bridge_token, engine_url, engine_token = mcp_server._endpoint_settings()
    assert bridge_url == "http://127.0.0.1:9876"
    assert bridge_token == "bridge-admin"
    assert engine_url == "http://127.0.0.1:9877"
    assert engine_token == "bridge-admin"

    monkeypatch.setenv("ICARUS_ENGINE_TOKEN", "engine-explicit")
    assert mcp_server._endpoint_settings()[3] == "engine-explicit"
