"""MCP control-surface contract tests. No daemon or network required."""
from __future__ import annotations

import icarus_bridge.mcp_server as mcp_server


def test_mcp_server_imports_and_registers_engine_surface():
    assert mcp_server.mcp is not None
    for name in (
        "engine_status",
        "engine_repository_audit",
        "record_engine_repository_audit",
        "record_engine_system_event",
        "record_engine_loop_status",
        "engine_configuration",
        "set_engine_chart_config",
        "start_engine_backtest",
        "engine_backtest_status",
        "engine_market_data_capabilities",
        "engine_recent_ticks",
        "engine_order_book_events",
        "engine_mbo_snapshot",
        "engine_integrity_state",
        "record_engine_integrity_event",
        "engine_brain_state",
        "record_engine_brain_event",
        "engine_performance_proof",
        "record_engine_performance_forecast",
        "record_engine_performance_outcome",
        "record_engine_replay_proof",
        "engine_latency_telemetry",
        "engine_possibility_state",
        "record_engine_possibility_evidence",
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


def test_mcp_system_intelligence_event_and_loop_routes(monkeypatch):
    seen = []

    def post(path, body):
        seen.append((path, body))
        return {"ok": True}

    monkeypatch.setattr(mcp_server, "_engine_post", post)

    assert mcp_server.record_engine_system_event(
        kind="repair",
        title="Alpha repaired",
        detail="Durability chain restored",
        severity="success",
        repository="reppiks490/Icarus-engine",
        ref="abc123",
    ) == {"ok": True}
    assert mcp_server.record_engine_loop_status(
        loop_id="alpha-synthesis",
        title="Alpha Synthesis Evolution",
        status="RUN_PERSISTED",
        run_id="alpha-synthesis-20261001T012500Z",
        scheduler_id="sched-alpha",
        schedule=":25 hourly",
        repository="reppiks490/Icarus-engine",
        finalization_commit_sha="abc123",
        finalization_state_blob_sha="def456",
        detail="verified",
    ) == {"ok": True}

    assert seen[0][0] == "/admin/system/event"
    assert seen[0][1]["event"]["kind"] == "repair"
    assert seen[1][0] == "/admin/system/loop"
    assert seen[1][1]["loop"]["id"] == "alpha-synthesis"


def test_mcp_integrity_receipt_uses_same_engine_plane_and_exact_provenance(monkeypatch):
    seen = []

    def get(path):
        seen.append(("get", path))
        return {"execution_authorized": False}

    def post(path, body):
        seen.append(("post", path, body))
        return {"ok": True, "execution_authorized": False, "idempotent": False}

    monkeypatch.setattr(mcp_server, "_engine_get", get)
    monkeypatch.setattr(mcp_server, "_engine_post", post)

    assert mcp_server.engine_integrity_state()["execution_authorized"] is False
    result = mcp_server.record_engine_integrity_event(
        "repair",
        "ingestion",
        "Reject backward timestamps.",
        "reppiks490/divine-providence",
        "main",
        "4a27b4776a56bd63bedd3243696316440c5a8ef8",
        "Regression checked.",
        "Blocker shown as repaired.",
        status="repaired",
        severity="high",
        evidence_json='["pytest"]',
        details_json='{"ci":"green"}',
    )
    assert result["execution_authorized"] is False
    assert seen == [
        ("get", "/api/integrity"),
        ("post", "/admin/integrity/event", {
            "kind": "repair",
            "area": "ingestion",
            "summary": "Reject backward timestamps.",
            "status": "repaired",
            "severity": "high",
            "source_repo": "reppiks490/divine-providence",
            "source_branch": "main",
            "source_commit": "4a27b4776a56bd63bedd3243696316440c5a8ef8",
            "verification": "Regression checked.",
            "interface_effect": "Blocker shown as repaired.",
            "evidence": ["pytest"],
            "details": {"ci": "green"},
        }),
    ]


def test_mcp_adaptive_brain_routes(monkeypatch):
    seen = []

    def get(path):
        seen.append(("get", path))
        return {"authority": {"execution_authorized": False}}

    def post(path, body):
        seen.append(("post", path, body))
        return {
            "ok": True,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    monkeypatch.setattr(mcp_server, "_engine_get", get)
    monkeypatch.setattr(mcp_server, "_engine_post", post)

    assert mcp_server.engine_brain_state()["authority"]["execution_authorized"] is False
    result = mcp_server.record_engine_brain_event(
        kind="candidate",
        subject="nq-strong-v1",
        summary="qualified regime specialist",
        status="qualified",
        evidence_json='["walk-forward","independent oracle"]',
        candidate_id="nq-strong-v1",
        stage="qualified_shadow",
        regimes_json='["STRONG"]',
        metrics_json='{"validation_score":0.84}',
        validation_json='{"causal_time":true,"provenance":true,"oos":true,"protected_holdout":true,"multiple_testing":true,"costs_slippage_latency":true,"ablation":true,"calibration":true,"ood_drift":true,"deterministic_replay":true,"independent_verification":true}',
        source_repo="reppiks490/Icarus",
        source_commit="a" * 40,
    )
    assert result["execution_authorized"] is False
    assert result["production_decision_authorized"] is False
    assert seen[0] == ("get", "/api/brain")
    assert seen[1][0] == "post"
    assert seen[1][1] == "/admin/brain/event"
    body = seen[1][2]
    assert body["candidate_id"] == "nq-strong-v1"
    assert body["stage"] == "qualified_shadow"
    assert body["regimes"] == ["STRONG"]
    assert body["validation"]["independent_verification"] is True
    assert body["source_commit"] == "a" * 40


def test_mcp_icarus_psi_routes_are_research_only(monkeypatch):
    seen = []

    def get(path):
        seen.append(("get", path))
        return {"authority": {"execution_authorized": False}}

    def post(path, body):
        seen.append(("post", path, body))
        return {"ok": True, "execution_authorized": False, "production_decision_authorized": False}

    monkeypatch.setattr(mcp_server, "_engine_get", get)
    monkeypatch.setattr(mcp_server, "_engine_post", post)

    state = mcp_server.engine_possibility_state("nq")
    assert state["authority"]["execution_authorized"] is False
    result = mcp_server.record_engine_possibility_evidence(
        "nq",
        "unit-test",
        '{"gamma_pressure":{"value":0.4,"confidence":0.7}}',
        observed_at="2026-10-01T05:00:00Z",
        ttl_seconds=120,
    )
    assert result["execution_authorized"] is False
    assert result["production_decision_authorized"] is False
    assert seen[0] == ("get", "/api/possibility?asset=NQ")
    assert seen[1] == ("post", "/admin/possibility/evidence", {
        "asset": "NQ",
        "source": "unit-test",
        "values": {"gamma_pressure": {"value": 0.4, "confidence": 0.7}},
        "ttl_seconds": 120.0,
        "observed_at": "2026-10-01T05:00:00Z",
    })


def test_mcp_icarus_psi_rejects_non_object_evidence_json():
    assert "error" in mcp_server.record_engine_possibility_evidence("NQ", "fixture", "[]")
    assert "error" in mcp_server.record_engine_possibility_evidence("NQ", "fixture", "{bad")

def test_mcp_performance_proof_and_latency_routes(monkeypatch):
    seen = []

    def get(path):
        seen.append(("get", path))
        return {"ok": True}

    def post(path, body):
        seen.append(("post", path, body))
        return {"ok": True, "execution_authorized": False, "production_decision_authorized": False}

    monkeypatch.setattr(mcp_server, "_engine_get", get)
    monkeypatch.setattr(mcp_server, "_engine_post", post)

    assert mcp_server.engine_performance_proof() == {"ok": True}
    assert mcp_server.engine_latency_telemetry() == {"ok": True}

    forecast = mcp_server.record_engine_performance_forecast(
        candidate_id="nq-trend-v1",
        asset="nq",
        regime="STRONG",
        decision_at="2026-10-01T12:00:00Z",
        matures_at="2026-10-01T12:05:00Z",
        probability_success=0.8,
        success_definition="positive net outcome after configured costs",
        source_repo="reppiks490/Icarus",
        source_commit="a" * 40,
        dataset_hash="b" * 64,
        evidence_hash="c" * 64,
    )
    assert forecast["execution_authorized"] is False

    outcome = mcp_server.record_engine_performance_outcome(
        forecast_id="d" * 64,
        observed_at="2026-10-01T12:05:01Z",
        success=True,
        realized_value=1.25,
        outcome_hash="e" * 64,
        source="unit-test",
    )
    assert outcome["production_decision_authorized"] is False

    replay = mcp_server.record_engine_replay_proof(
        subject="nq-trend-v1",
        source_commit="a" * 40,
        input_hash="f" * 64,
        first_output_hash="1" * 64,
        second_output_hash="1" * 64,
        observed_at="2026-10-01T12:06:00Z",
    )
    assert replay["execution_authorized"] is False

    assert seen[0] == ("get", "/api/performance-proof")
    assert seen[1] == ("get", "/api/latency")
    assert seen[2][0:2] == ("post", "/admin/performance-proof/forecast")
    assert seen[3][0:2] == ("post", "/admin/performance-proof/outcome")
    assert seen[4][0:2] == ("post", "/admin/performance-proof/replay")
