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
        "engine_latency_telemetry",
        "record_engine_replay_proof",
        "record_engine_performance_outcome",
        "record_engine_performance_forecast",
        "engine_source_reliability",
        "record_engine_source_reliability_observation",
        "engine_performance_proof",
        "engine_possibility_state",
        "engine_possibility_evidence",
        "record_engine_possibility_evidence",
        "engine_pantheon_state",
        "record_engine_pantheon_observation",
        "record_engine_aether_claim",
        "engine_sibyl_state",
        "record_engine_sibyl_evidence",
        "record_engine_sibyl_forecast",
        "record_engine_sibyl_outcome",
        "record_engine_sibyl_scenario",
        "refresh_engine_dreamstate",
        "record_engine_parallax_outcome",
        "record_current_parallax_decision_with_psi",
        "retire_engine_dreamstate_candidate",
        "evaluate_engine_dreamstate_candidate",
        "record_historical_parallax_decision",
        "engine_dreamstate_state",
        "engine_parallax_state",
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
    ledger = mcp_server.engine_possibility_evidence(
        "nq",
        limit=25,
        include_expired=True,
        as_of="2026-10-01T05:01:00Z",
    )
    assert ledger["authority"]["execution_authorized"] is False
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
    assert seen[1] == ("get", "/api/possibility/evidence?asset=NQ&limit=25&include_expired=true&as_of=2026-10-01T05%3A01%3A00Z")
    assert seen[2] == ("post", "/admin/possibility/evidence", {
        "asset": "NQ",
        "source": "unit-test",
        "values": {"gamma_pressure": {"value": 0.4, "confidence": 0.7}},
        "ttl_seconds": 120.0,
        "observed_at": "2026-10-01T05:00:00Z",
    })


def test_mcp_icarus_psi_rejects_non_object_evidence_json():
    assert "error" in mcp_server.record_engine_possibility_evidence("NQ", "fixture", "[]")
    assert "error" in mcp_server.record_engine_possibility_evidence("NQ", "fixture", "{bad")


def test_mcp_parallax_dreamstate_research_routes(monkeypatch):
    seen = []

    def get(path):
        seen.append(("get", path))
        return {"authority": {"execution_authorized": False}}

    def post(path, body):
        seen.append(("post", path, body))
        return {"execution_authorized": False, "production_decision_authorized": False}

    monkeypatch.setattr(mcp_server, "_engine_get", get)
    monkeypatch.setattr(mcp_server, "_engine_post", post)

    assert mcp_server.engine_parallax_state()["authority"]["execution_authorized"] is False
    assert mcp_server.engine_dreamstate_state()["authority"]["execution_authorized"] is False

    decision = mcp_server.record_current_parallax_decision_with_psi(
        "nq",
        "long",
        regime="strong",
        context_json='{"setup":"fixture"}',
        subsystem_votes_json='{"argus":{"state":"aligned"}}',
        branches_json='[{"kind":"actual","label":"actual","params":{}}]',
        decision_id="fixture-decision",
        source_commit="a" * 40,
    )
    assert decision["execution_authorized"] is False

    outcome = mcp_server.record_engine_parallax_outcome(
        "fixture-decision",
        "actual",
        1.25,
        metrics_json='{"pnl":125}',
        evidence_json='["observed replay"]',
        observed_at="2026-10-01T06:30:00Z",
    )
    assert outcome["production_decision_authorized"] is False

    refreshed = mcp_server.refresh_engine_dreamstate(7)
    assert refreshed["execution_authorized"] is False

    assert seen[0] == ("get", "/api/parallax")
    assert seen[1] == ("get", "/api/dreamstate")
    assert seen[2] == ("post", "/admin/parallax/decision/current", {
        "asset": "NQ",
        "action": "long",
        "regime": "strong",
        "context": {"setup": "fixture"},
        "subsystem_votes": {"argus": {"state": "aligned"}},
        "branches": [{"kind": "actual", "label": "actual", "params": {}}],
        "decision_id": "fixture-decision",
        "source_commit": "a" * 40,
    })
    assert seen[3] == ("post", "/admin/parallax/outcome", {
        "decision_id": "fixture-decision",
        "label": "actual",
        "utility": 1.25,
        "metrics": {"pnl": 125},
        "evidence": ["observed replay"],
        "observed_at": "2026-10-01T06:30:00Z",
    })
    assert seen[4] == ("post", "/admin/dreamstate/refresh", {"min_samples": 7})


def test_mcp_current_parallax_capture_rejects_caller_supplied_psi_vote():
    result = mcp_server.record_current_parallax_decision_with_psi(
        "NQ",
        "long",
        subsystem_votes_json='{"psi":{"state":"forged"}}',
    )
    assert "error" in result
    assert "captured atomically" in result["error"]



def test_mcp_historical_parallax_and_dreamstate_candidate_routes(monkeypatch):
    seen = []

    def post(path, body):
        seen.append((path, body))
        return {"execution_authorized": False, "production_decision_authorized": False}

    monkeypatch.setattr(mcp_server, "_engine_post", post)

    historical = mcp_server.record_historical_parallax_decision(
        "nq",
        "long",
        "2026-10-01T12:00:00Z",
        "b" * 40,
        regime="trend",
        context_json='{"fixture":true}',
        subsystem_votes_json='{"psi":{"state":"NO_EDGE"}}',
        branches_json='[{"kind":"actual","label":"actual","params":{}}]',
        decision_id="hist-1",
    )
    assert historical["execution_authorized"] is False

    evaluated = mcp_server.evaluate_engine_dreamstate_candidate(
        "ds-fixture",
        '{"causal_time":true,"provenance":true}',
        '["fixture evidence"]',
    )
    assert evaluated["production_decision_authorized"] is False

    retired = mcp_server.retire_engine_dreamstate_candidate(
        "ds-fixture",
        "negative holdout evidence",
    )
    assert retired["execution_authorized"] is False

    assert seen[0] == ("/admin/parallax/decision", {
        "asset": "NQ",
        "action": "long",
        "regime": "trend",
        "observed_at": "2026-10-01T12:00:00Z",
        "source_commit": "b" * 40,
        "context": {"fixture": True},
        "subsystem_votes": {"psi": {"state": "NO_EDGE"}},
        "branches": [{"kind": "actual", "label": "actual", "params": {}}],
        "decision_id": "hist-1",
    })
    assert seen[1] == ("/admin/dreamstate/evaluate", {
        "candidate_id": "ds-fixture",
        "validation": {"causal_time": True, "provenance": True},
        "evidence": ["fixture evidence"],
    })
    assert seen[2] == ("/admin/dreamstate/retire", {
        "candidate_id": "ds-fixture",
        "reason": "negative holdout evidence",
    })


def test_mcp_historical_parallax_requires_explicit_time_and_exact_sha():
    missing_time = mcp_server.record_historical_parallax_decision(
        "NQ", "long", "", "a" * 40,
    )
    assert "observed_at is required" in missing_time["error"]

    bad_sha = mcp_server.record_historical_parallax_decision(
        "NQ", "long", "2026-10-01T12:00:00Z", "not-a-sha",
    )
    assert "40-character hexadecimal" in bad_sha["error"]


def test_mcp_dreamstate_candidate_tools_require_identity_and_reason():
    empty_candidate = mcp_server.evaluate_engine_dreamstate_candidate(
        "", '{"causal_time":true}',
    )
    assert "candidate_id is required" in empty_candidate["error"]

    missing_reason = mcp_server.retire_engine_dreamstate_candidate("ds-1", "")
    assert "reason is required" in missing_reason["error"]

def test_mcp_pantheon_routes_are_shadow_only(monkeypatch):
    seen = []

    def get(path):
        seen.append(("get", path))
        return {"authority": {"execution_authorized": False, "production_decision_authorized": False}}

    def post(path, body):
        seen.append(("post", path, body))
        return {"analysis": {"authority": {"execution_authorized": False, "production_decision_authorized": False}}}

    monkeypatch.setattr(mcp_server, "_engine_get", get)
    monkeypatch.setattr(mcp_server, "_engine_post", post)

    state = mcp_server.engine_pantheon_state()
    assert state["authority"]["execution_authorized"] is False
    result = mcp_server.record_engine_pantheon_observation(
        "nq",
        "2026-10-01T06:05:00Z",
        '{"data_quality":0.9,"risk":0.2}',
        horizon_ms=15000,
        evidence_json='["fixture"]',
        subsystem_outputs_json='{"custom":{"value":1}}',
        source_commit="a" * 40,
        observation_id="pan-mcp-fixture",
    )
    assert result["analysis"]["authority"]["execution_authorized"] is False
    assert seen[0] == ("get", "/api/pantheon")
    assert seen[1] == ("post", "/admin/pantheon/observe", {
        "asset": "NQ",
        "observed_at": "2026-10-01T06:05:00Z",
        "horizon_ms": 15000,
        "signals": {"data_quality": 0.9, "risk": 0.2},
        "evidence": ["fixture"],
        "subsystem_outputs": {"custom": {"value": 1}},
        "source_commit": "a" * 40,
        "observation_id": "pan-mcp-fixture",
    })

def test_mcp_pantheon_rejects_bad_json_shapes():
    assert "error" in mcp_server.record_engine_pantheon_observation("NQ", "2026-10-01T06:05:00Z", "[]")
    assert "error" in mcp_server.record_engine_pantheon_observation("NQ", "2026-10-01T06:05:00Z", "{}", evidence_json="{}")
    assert "error" in mcp_server.record_engine_pantheon_observation("NQ", "2026-10-01T06:05:00Z", "{}", subsystem_outputs_json="[]")

def test_mcp_aether_claim_route_is_blind_and_shadow_only(monkeypatch):
    seen = {}

    def post(path, body):
        seen["path"] = path
        seen["body"] = body
        return {"deliberation": {"execution_authorized": False, "consensus_forced": False}}

    monkeypatch.setattr(mcp_server, "_engine_post", post)
    out = mcp_server.record_engine_aether_claim(
        "pan-1",
        "aeth-1",
        "independent thesis",
        direction="short",
        confidence=0.65,
        falsifier="opposite queue behavior",
        evidence_json='["partition:risk"]',
    )
    assert out["deliberation"]["execution_authorized"] is False
    assert seen["path"] == "/admin/pantheon/claim"
    assert seen["body"] == {
        "observation_id": "pan-1",
        "agent_id": "aeth-1",
        "peer_context_used": False,
        "claim": {
            "thesis": "independent thesis",
            "direction": "short",
            "confidence": 0.65,
            "falsifier": "opposite queue behavior",
            "evidence": ["partition:risk"],
        },
    }

def test_mcp_aether_claim_rejects_non_list_evidence():
    assert "error" in mcp_server.record_engine_aether_claim(
        "pan-1", "aeth-1", "thesis", evidence_json="{}"
    )

def test_mcp_sibyl_routes_are_research_only(monkeypatch):
    seen = []

    def get(path, **params):
        seen.append(("get", path, params))
        return {
            "asset": "NQ",
            "authority": {
                "execution_authorized": False,
                "production_decision_authorized": False,
            },
        }

    def post(path, body):
        seen.append(("post", path, body))
        return {
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    monkeypatch.setattr(mcp_server, "_engine_get", get)
    monkeypatch.setattr(mcp_server, "_engine_post", post)

    state = mcp_server.engine_sibyl_state("nq")
    assert state["authority"]["execution_authorized"] is False

    evidence = mcp_server.record_engine_sibyl_evidence(
        "nq",
        "fixture-source",
        "macro",
        "2026-10-01T06:00:00Z",
        0.5,
        0.8,
        300,
        magnitude=1.2,
        source_commit="a" * 40,
        target_price=25050.0,
        invalidation_price=24950.0,
        payload_json='{"fixture":true}',
    )
    assert evidence["execution_authorized"] is False

    forecast = mcp_server.record_engine_sibyl_forecast(
        "nq",
        horizons_json="[60,300]",
        observed_at="2026-10-01T06:00:00Z",
        current_price=25000.0,
        source_commit="b" * 40,
    )
    assert forecast["production_decision_authorized"] is False

    outcome = mcp_server.record_engine_sibyl_outcome(
        "fc-1",
        300,
        "2026-10-01T06:05:00Z",
        25025.0,
        evidence_json='["fixture"]',
    )
    assert outcome["execution_authorized"] is False

    scenario = mcp_server.record_engine_sibyl_scenario(
        "nq",
        '[{"domain":"macro","direction":-0.5}]',
        horizons_json="[300]",
        as_of="2026-10-01T06:00:00Z",
        current_price=25000.0,
    )
    assert scenario["production_decision_authorized"] is False

    assert seen[0] == ("get", "/api/sibyl", {"asset": "NQ"})
    assert seen[1][0:2] == ("post", "/admin/sibyl/evidence")
    assert seen[1][2]["source"] == "fixture-source"
    assert seen[1][2]["payload"] == {"fixture": True}
    assert seen[2][0:2] == ("post", "/admin/sibyl/forecast")
    assert seen[2][2]["observed_at"] == "2026-10-01T06:00:00Z"
    assert seen[2][2]["current_price"] == 25000.0
    assert seen[3][0:2] == ("post", "/admin/sibyl/outcome")
    assert seen[4][0:2] == ("post", "/admin/sibyl/scenario")
    assert seen[4][2]["as_of"] == "2026-10-01T06:00:00Z"


def test_mcp_sibyl_rejects_bad_shapes_and_reserved_pantheon_identity():
    assert "error" in mcp_server.record_engine_sibyl_evidence(
        "NQ", "fixture", "macro", "2026-10-01T06:00:00Z", 0.2, 0.8, 300,
        payload_json="[]",
    )
    reserved = mcp_server.record_engine_sibyl_evidence(
        "NQ", "pantheon-ananke", "structural_constraints",
        "2026-10-01T06:00:00Z", 0.2, 0.8, 300,
    )
    assert "reserved" in reserved["error"]
    assert "error" in mcp_server.record_engine_sibyl_forecast(
        "NQ", horizons_json="{}",
    )
    assert "error" in mcp_server.record_engine_sibyl_outcome(
        "fc-1", 300, "2026-10-01T06:05:00Z", 25000.0, evidence_json="{}",
    )
    assert "error" in mcp_server.record_engine_sibyl_scenario(
        "NQ", interventions_json="{}",
    )



def test_mcp_source_reliability_routes(monkeypatch):
    seen = []

    def get(path):
        seen.append(("get", path))
        return {"observation_count": 0, "execution_authorized": False}

    def post(path, body):
        seen.append(("post", path, body))
        return {"ok": True, "execution_authorized": False, "production_decision_authorized": False}

    monkeypatch.setattr(mcp_server, "_engine_get", get)
    monkeypatch.setattr(mcp_server, "_engine_post", post)

    assert mcp_server.engine_source_reliability()["execution_authorized"] is False
    out = mcp_server.record_engine_source_reliability_observation(
        source_id="provider-a",
        stream="NQ-trades",
        observed_at="2026-10-01T12:00:02Z",
        event_time="2026-10-01T12:00:00Z",
        retrieval_time="2026-10-01T12:00:01Z",
        expected_freshness_seconds=2.0,
        complete=True,
        evidence_hash="a" * 64,
        revision=False,
        agreement_bps=1.0,
        agreement_tolerance_bps=2.0,
    )
    assert out["production_decision_authorized"] is False
    assert seen[0] == ("get", "/api/source-reliability")
    assert seen[1][0:2] == ("post", "/admin/source-reliability/observation")
    assert seen[1][2]["source_id"] == "provider-a"
    assert seen[1][2]["complete"] is True
