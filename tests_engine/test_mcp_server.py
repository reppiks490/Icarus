"""MCP control-surface contract tests. No daemon or network required."""
from __future__ import annotations

import icarus_bridge.mcp_server as mcp_server


def test_mcp_server_imports_and_registers_engine_surface():
    assert mcp_server.mcp is not None
    for name in (
        "engine_status",
        "engine_repository_audit",
        "record_engine_repository_audit",
        "engine_system_evolution",
        "record_engine_system_evolution",
        "engine_configuration",
        "set_engine_chart_config",
        "start_engine_backtest",
        "engine_backtest_status",
        "engine_market_data_capabilities",
        "engine_recent_ticks",
        "engine_order_book_events",
        "engine_mbo_snapshot",
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


def test_mcp_databento_market_data_routes(monkeypatch):
    seen = []

    def get(path):
        seen.append(("get", path))
        return {"ok": True}

    def post(path, body):
        seen.append(("post", path, body))
        return {"ok": True}

    monkeypatch.setattr(mcp_server, "_engine_get", get)
    monkeypatch.setattr(mcp_server, "_engine_post", post)

    assert mcp_server.engine_market_data_capabilities("nq") == {"ok": True}
    assert mcp_server.engine_recent_ticks("nq", limit=25, since_ts=123) == {"ok": True}
    assert mcp_server.engine_order_book_events("nq", schema="mbp-10", limit=50) == {"ok": True}
    assert mcp_server.engine_mbo_snapshot("nq", timeout=2.5) == {"ok": True}
    assert seen == [
        ("get", "/api/market-data/NQ/capabilities"),
        ("get", "/api/market-data/NQ/ticks?limit=25&since_ts=123"),
        ("get", "/api/market-data/NQ/depth?schema=mbp-10&limit=50"),
        ("post", "/admin/market-data/mbo-snapshot", {"asset": "NQ", "timeout": 2.5}),
    ]


def test_mcp_repository_audit_routes(monkeypatch):
    seen = []

    def get(path):
        seen.append(("get", path))
        return {"status": "green"}

    def post(path, body):
        seen.append(("post", path, body))
        return {"ok": True}

    monkeypatch.setattr(mcp_server, "_engine_get", get)
    monkeypatch.setattr(mcp_server, "_engine_post", post)

    assert mcp_server.engine_repository_audit() == {"status": "green"}
    assert mcp_server.record_engine_repository_audit('{"status":"green","repository":"reppiks490/Icarus"}') == {"ok": True}
    assert seen == [
        ("get", "/api/system/audit"),
        ("post", "/admin/system/audit", {"audit": {"status": "green", "repository": "reppiks490/Icarus"}}),
    ]


def test_mcp_repository_audit_rejects_non_object_json():
    assert "error" in mcp_server.record_engine_repository_audit("[]")
    assert "error" in mcp_server.record_engine_repository_audit("{bad")


def test_mcp_system_evolution_routes(monkeypatch):
    seen = []

    def get(path):
        seen.append(("get", path))
        return {"mirror_ok": True}

    def post(path, body):
        seen.append(("post", path, body))
        return {"ok": True}

    monkeypatch.setattr(mcp_server, "_engine_get", get)
    monkeypatch.setattr(mcp_server, "_engine_post", post)

    assert mcp_server.engine_system_evolution() == {"mirror_ok": True}
    payload = '{"items":[{"id":"x","subsystem":"ATHENA","kind":"repair","status":"verified","severity":"notice","important":true,"summary":"x","interface_surface":"System"}]}'
    assert mcp_server.record_engine_system_evolution(payload) == {"ok": True}
    assert seen == [
        ("get", "/api/system/evolution"),
        ("post", "/admin/system/evolution", {"evolution": {
            "items": [{
                "id": "x", "subsystem": "ATHENA", "kind": "repair", "status": "verified",
                "severity": "notice", "important": True, "summary": "x", "interface_surface": "System",
            }]
        }}),
    ]


def test_mcp_system_evolution_rejects_non_object_json():
    assert "error" in mcp_server.record_engine_system_evolution("[]")
    assert "error" in mcp_server.record_engine_system_evolution("{bad")
