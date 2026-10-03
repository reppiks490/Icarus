"""Parse every shipped dashboard JavaScript surface with Node when available."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="node is not installed on this developer machine")
@pytest.mark.parametrize(
    "rel",
    [
        "icarus_engine/dashboard.html",
        "icarus_bridge/dashboard.html",
        "icarus_engine/research-ui.js",
        "icarus_engine/sources-ui.js",
        "icarus_engine/market-data-ui.js",
        "icarus_engine/brain-ui.js",
        "icarus_engine/evolution-ui.js",
        "icarus_engine/parallax-ui.js",
        "icarus_engine/possibility-ui.js",
        "icarus_engine/pantheon-ui.js",
        "icarus_engine/sibyl-ui.js",
        "icarus_engine/apex-ui.js",
        "icarus_engine/ascendancy-ui.js",
        "icarus_engine/learning-ui.js",
        "icarus_engine/chronofold-ui.js",
        "icarus_engine/commissioning-ui.js",
        "icarus_engine/integrity-ui.js",
        "icarus_engine/engine-control-ui.js",
        "icarus_engine/autopilot-ui.js",
        "icarus_engine/experience-ui.js",
    ],
)
def test_dashboard_javascript_parses(rel, tmp_path):
    src = (REPO / rel).read_text(encoding="utf-8")
    if rel.endswith(".html"):
        blocks = re.findall(r"<script\b[^>]*>([\s\S]*?)</script>", src, flags=re.IGNORECASE)
        assert blocks, f"{rel} has no inline JavaScript to validate"
        src = "\n".join(blocks)
    out = tmp_path / (Path(rel).name.replace(".html", "") + ".js")
    out.write_text(src, encoding="utf-8")
    result = subprocess.run([NODE, "--check", str(out)], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_engine_dashboard_has_no_expiry_contract_ui():
    src = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    assert "a.next_contract" not in src
    assert "a.contract?" not in src
    assert "continuous_symbol || a.provider_symbol || a.symbol" in src


def test_strategy_tester_timeframes_are_cache_aware():
    src = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    assert "available_from_cache" in src
    assert "cache unavailable" in src
    assert "cached_source_resolutions_minutes" in src
    assert "$('#btAsset').addEventListener('change'" in src
    assert "BT.res = null; BT.compare = null" in src


def test_asset_adder_uses_registry_and_timeframe_suggestions_and_single_flight_submit():
    src = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    assert 'list="addAssetOptions"' in src
    assert 'datalist id="addAssetOptions"' in src
    assert 'list="addTfOptions"' in src
    assert 'datalist id="addTfOptions"' in src
    assert "['1','2','3','5','10','15','20','30','45','60','120','180','240','D','W']" in src
    assert "REGISTRY.map" in src
    assert "b.disabled = true" in src
    assert "await admin('/admin/assets/add'" in src
    assert "j.detail||j.error||'request failed'" in src


def test_engine_dashboard_surfaces_repository_mcp_audit():
    src = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    assert 'id="repoHealth"' in src
    assert 'data-v="system">System</span>' in src
    assert "repositoryAuditCard(window.ICARUS_AUDIT" in src
    assert "fetch('/api/system/audit'" in src
    assert "setInterval(refreshAudit, 20000)" in src
    assert "System Intelligence" in src
    assert "Automation loops" in src
    assert "MCP activity" in src
    assert "a.loops || []" in src
    assert "a.events || []" in src
    assert "a.loop_sync || {}" in src
    assert "Loop auto-sync" in src
    assert "x.signals || {}" in src
    assert "run output" in src


def test_dashboard_surfaces_export_data_integrity_and_mcp_receipts():
    dashboard = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    ui = (REPO / "icarus_engine/integrity-ui.js").read_text(encoding="utf-8")
    server = (REPO / "icarus_engine/server.py").read_text(encoding="utf-8")
    assert '/integrity-ui.js' in dashboard
    assert 'data-v="integrity">Data Integrity</span>' in dashboard
    assert "wireIntegrity()" in dashboard
    assert "/api/integrity" in ui
    assert "MCP change ledger" in ui
    assert "source_commit" in ui
    assert "execution" in ui.lower()
    assert 'p.path == "/api/integrity"' in server
    assert 'p.path == "/admin/integrity/event"' in server


def test_dashboard_surfaces_adaptive_brain_fabric():
    dashboard = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    ui = (REPO / "icarus_engine/brain-ui.js").read_text(encoding="utf-8")
    server = (REPO / "icarus_engine/server.py").read_text(encoding="utf-8")
    assert '/brain-ui.js' in dashboard
    assert 'data-v="brain">Adaptive Brain</span>' in dashboard
    assert "wireBrain()" in dashboard
    assert "/api/brain" in ui
    assert "5 custom agents" in ui
    assert "SHADOW_ONLY" in ui
    assert "Observed success rate" in ui
    assert "Closed-sample 100%" in ui
    assert "Hot-path p99" in ui
    assert "Evidence champion / challenger tournaments" in ui
    assert "Causal evidence graph" in ui
    assert "Independent corroboration" in ui
    assert "Source reliability memory" in ui
    assert "/api/source-reliability" in server
    assert "/admin/source-reliability/observation" in server
    assert "/api/performance-proof" in server
    assert "/api/latency" in server
    assert "Agent federation contract" in ui
    assert "agentContract.event_records" in ui
    assert "STRICT EVENT ENVELOPE" in ui
    assert "Peer lane packet" in ui
    assert "source ${sync.peer_source_commit_verified?'VERIFIED '+" in ui
    assert "Peer freshness" in ui
    assert "sync.peer_packet_fresh" in ui
    assert "agentContract.peer_packet_max_age_seconds" in ui
    assert "PERSISTED_WORKER_EVIDENCE" in ui
    assert "Peer substantive lanes" in ui
    assert "Peer lane provenance" in ui
    assert "Source proof" in ui
    assert "source_witness_status" in ui
    assert "Federated Icarus-engine lane state" in ui
    assert "DURABILITY_ONLY never counts as substantive research evidence" in ui
    assert "CSV Evidence Lab" in ui
    assert "CSV durability closure" in ui
    assert "finalization_pointer_matches_heartbeat" in ui
    assert "compatibility_pointer_lag" in ui
    assert "/api/evidence-lab" in server
    assert "sync.evidence_lab" in server
    assert "/admin/performance-proof/forecast" in server
    assert "/admin/performance-proof/outcome" in server
    assert "/admin/performance-proof/replay" in server
    assert 'p.path == "/api/brain"' in server
    assert 'p.path == "/admin/brain/event"' in server


def test_dashboard_surfaces_repository_native_mcp_evolution_panel():
    dashboard = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    ui = (REPO / "icarus_engine/evolution-ui.js").read_text(encoding="utf-8")
    server = (REPO / "icarus_engine/server.py").read_text(encoding="utf-8")
    sync = (REPO / "icarus_engine/evolution_sync.py").read_text(encoding="utf-8")
    assert '/evolution-ui.js' in dashboard
    assert 'data-v="evolution">MCP Evolution</span>' in dashboard
    assert "wireEvolution()" in dashboard
    assert "/api/evolution" in ui
    assert "Subsystem evolution state" in ui
    assert "Important MCP activity" in ui
    assert "Other receipt families" in ui
    assert "ignored_total" in ui
    assert "Foreign receipt schemas" in ui
    assert "execution_authorized=false" in ui
    assert 'p.path == "/api/evolution"' in server
    assert "EvolutionRemoteSync" in server
    assert "automation_intelligence/mcp_interface/events" in sync
    assert "execution_authorized must be false" in sync
    assert "production_decision_authorized must be false" in sync


def test_dashboard_surfaces_icarus_psi_without_replacing_oracle_or_parallax():
    dashboard = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    ui = (REPO / "icarus_engine/possibility-ui.js").read_text(encoding="utf-8")
    server = (REPO / "icarus_engine/server.py").read_text(encoding="utf-8")
    brain = (REPO / "icarus_engine/brain.py").read_text(encoding="utf-8")
    assert '/possibility-ui.js' in dashboard
    assert 'data-v="possibility">ICARUS Ψ</span>' in dashboard
    assert "wirePossibility()" in dashboard
    assert "/api/possibility" in ui
    assert 'p.path == "/api/possibility"' in server
    assert 'p.path == "/admin/possibility/evidence"' in server
    assert 'votes["psi"] = possibility.parallax_vote' not in server
    assert "Any Psi vote must be captured causally" in server
    assert '{"id": "oracle", "title": "ORACLE"' in brain
    assert '{"id": "psi", "title": "ICARUS Ψ"' in brain
    assert '{"id": "parallax", "title": "PARALLAX"' in brain
    assert "execution_authorized=false" in ui
    assert "Research evidence console" in ui
    assert "psiEvidenceSubmit" in ui
    assert "psiEvidenceSource" in ui
    assert "/admin/possibility/evidence" in ui
    assert "/api/possibility/evidence" in ui
    assert "gamma_pressure" in ui
    assert "basis_pressure" in ui
    assert "cta_pressure" in ui
    assert "liquidation_pressure" in ui
    assert "rebalance_pressure" in ui
    assert "Evidence ledger" in ui
    assert "Active evidence" in ui
    assert "Evidence history" in ui
    assert "History source" in ui
    assert "Chart cadence" in ui
    assert "Gap returns skipped" in ui
    assert "Leader alignment" in ui
    assert "POST-BAR CAUSAL WINDOW" in ui
    assert "Ledger integrity" in ui
    assert "possibilityQuickOverviewHtml" in ui
    assert "wirePossibilityQuickOverview" in ui
    assert "possibilityQuickAssetHtml" in ui
    assert "wirePossibilityQuickAsset" in ui
    assert "ICARUS Ψ · LIVE RESEARCH MONITOR" in ui
    assert "Open full Ψ console" in ui
    assert "possibilityQuickOverviewHtml(A)" in dashboard
    assert "possibilityQuickAssetHtml(a)" in dashboard
    assert "wirePossibilityQuickOverview(A)" in dashboard
    assert "wirePossibilityQuickAsset(viewAsset.symbol)" in dashboard
    assert '/api/possibility/evidence' in server


def test_dashboard_surfaces_authenticated_engine_control_panel():
    dashboard = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    ui = (REPO / "icarus_engine/engine-control-ui.js").read_text(encoding="utf-8")
    server = (REPO / "icarus_engine/server.py").read_text(encoding="utf-8")
    backend = (REPO / "icarus_engine/engine_control.py").read_text(encoding="utf-8")

    assert '<script src="/engine-control-ui.js"></script>' in dashboard
    assert 'data-v="engine-control">Engine Control</span>' in dashboard
    assert "view === 'engine-control'" in dashboard
    assert "wireEngineControl()" in dashboard
    assert 'p.path == "/engine-control-ui.js"' in server
    assert 'p.path == "/api/engine-control"' in server
    assert 'p.path == "/admin/engine-control"' in server
    assert "EngineControlPlane(" in server
    assert "ControlAction(" in server
    assert "arbitrary_shell" in backend
    assert "broker_arming" in backend
    assert "/api/engine-control" in ui
    assert "/admin/engine-control" in ui
    assert "MCP / audit mirror" in ui
    assert "Specialized control surfaces" in ui
    assert "asset.apply_config" in server
    assert "sync.stop_all" in server
    assert "FLATTEN ALL PAPER POSITIONS" in server
    assert "RESET ASSET CONFIG" in server
    assert "RESET AUTOPILOT" in server
    assert "STOP ALL INTELLIGENCE SYNCS" in server
    assert '"mcp_repository": lambda: mcp_control.status(200)' in server
    assert 'ControlAction("backtest.start"' in server
    assert 'ControlAction("research.start"' in server
    assert 'ControlAction("parallax.record_decision"' in server
    assert 'ControlAction("possibility.ingest_evidence"' in server
    assert "data-ec-template" in ui
    assert "ecEventTable" in ui


def test_dashboard_surfaces_tactical_autopilot_and_root_engine_control():
    dashboard = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    autopilot = (REPO / "icarus_engine/autopilot-ui.js").read_text(encoding="utf-8")
    control = (REPO / "icarus_engine/engine-control-ui.js").read_text(encoding="utf-8")
    server = (REPO / "icarus_engine/server.py").read_text(encoding="utf-8")
    assert '/autopilot-ui.js' in dashboard
    assert 'data-v="autopilot">Tactical Autopilot</span>' in dashboard
    assert "wireAutopilot()" in dashboard
    assert '/engine-control-ui.js' in dashboard
    assert 'data-v="engine-control">Engine Control</span>' in dashboard
    assert "wireEngineControl()" in dashboard
    assert "/api/autopilot" in autopilot
    assert "robustness_windows" in autopilot
    assert "Tactical learning map" in autopilot
    assert "/api/engine-control" in control
    assert "Tactical Autopilot" in control
    assert 'p.path == "/api/autopilot"' in server
    assert 'p.path == "/api/engine-control"' in server
    assert 'ControlAction("autopilot.configure"' in server
    assert '"autopilot": autopilot.status' in server


def test_engine_control_ui_supports_every_registered_target_and_generic_args():
    ui = (REPO / "icarus_engine/engine-control-ui.js").read_text(encoding="utf-8")
    server = (REPO / "icarus_engine/server.py").read_text(encoding="utf-8")
    for target in ("job", "candidate", "proposal", "source"):
        assert target + ":" in ui
    assert "action.args_example" in ui
    assert "JSON.stringify(action.args_example)" in ui
    assert 'ControlAction("research.export"' in server
    assert 'target="proposal"' in server
    assert 'ControlAction("research.collect"' in server
    assert 'target="source"' in server
    assert 'ControlAction("dreamstate.evaluate"' in server
    assert 'target="candidate"' in server


def test_dashboard_surfaces_authentic_market_data_console():
    dashboard = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    ui = (REPO / "icarus_engine/market-data-ui.js").read_text(encoding="utf-8")
    server = (REPO / "icarus_engine/server.py").read_text(encoding="utf-8")

    assert '<script src="/market-data-ui.js"></script>' in dashboard
    assert 'data-v="market-data">Market Data</span>' in dashboard
    assert "view === 'market-data'" in dashboard
    assert "wireMarketData()" in dashboard
    assert 'p.path == "/market-data-ui.js"' in server
    assert "/api/market-data/" in ui
    assert "/capabilities" in ui
    assert "/ticks?limit=300" in ui
    assert "/depth?schema=" in ui
    assert "/admin/market-data/mbo-snapshot" in ui
    assert "engine_market_data_capabilities" in ui
    assert "engine_recent_ticks" in ui
    assert "engine_order_book_events" in ui
    assert "engine_mbo_snapshot" in ui
    assert "continuous_symbol" in ui
    assert "resolved_raw_symbol" in ui
    assert "resolved_instrument_id" in ui
    assert "core_session_ok" in ui
    assert "depth_schema_health" in ui
    assert "live_error" in ui
    assert "ts_recv_ns" in ui
    assert "ts_event_ns" in ui
    assert "Sequence jumps in window" in ui
    assert "does not invent a buy/sell interpretation" in ui


def test_dashboard_surfaces_apex_omega_world_intelligence():
    dashboard = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    ui = (REPO / "icarus_engine/apex-ui.js").read_text(encoding="utf-8")
    server = (REPO / "icarus_engine/server.py").read_text(encoding="utf-8")

    assert '<script src="/apex-ui.js"></script>' in dashboard
    assert 'data-v="apex">APEX Ω</span>' in dashboard
    assert "view === 'apex'" in dashboard
    assert "wireApex()" in dashboard
    assert 'p.path == "/apex-ui.js"' in server
    assert "/api/apex" in ui
    assert "WORLD" in ui
    assert "PARTICIPANTS" in ui
    assert "CROWDHUNT" in ui
    assert "FORCES" in ui
    assert "LIQUIDITY" in ui
    assert "CASCADES" in ui
    assert "CAUSAL GRAPH" in ui
    assert "COUNTERFACTUAL WORLDS" in ui
    assert "UNKNOWN FORCE" in ui
    assert "EPISTEMIC HEALTH" in ui
    assert "MODEL HEALTH" in ui
    assert "CONSCIENCE" in ui
    assert "UNAVAILABLE" in ui
    assert "UNMEASURED" in ui
    assert "execution_authorized=false" in ui
    assert "production_decision_authorized=false" in ui
    assert "v == null" in ui or "v === null" in ui


def test_dashboard_surfaces_continuous_learning_fabric():
    dashboard = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    ui = (REPO / "icarus_engine/learning-ui.js").read_text(encoding="utf-8")
    server = (REPO / "icarus_engine/server.py").read_text(encoding="utf-8")
    assert '<script src="/learning-ui.js"></script>' in dashboard
    assert 'data-v="learning">Learning Fabric</span>' in dashboard
    assert "view === 'learning'" in dashboard
    assert "wireLearning()" in dashboard
    assert 'p.path == "/learning-ui.js"' in server
    assert "/api/learning" in ui
    assert "DATASET COVERAGE" in ui
    assert "EMPIRICAL SCORECARDS" in ui
    assert "NATIVE EMPIRICAL FEDERATION" in ui
    assert "NATIVE EMPIRICAL EVENTS" in ui
    assert "PARALLAX UTILITY Δ" in ui
    assert "PANTHEON FITNESS" in ui
    assert "probability coercion OFF" in ui
    assert "TRAINING REPLAY" in ui
    assert "LIVE MATURITY" in ui
    assert "REALIZED EXPERIENCE" in ui
    assert "PROFIT FACTOR" in ui
    assert "LEARNER HEALTH" in ui
    assert "BACKLOG" in ui
    assert "CONSECUTIVE FAILURES" in ui
    assert "STALE" in ui
    assert "/api/learning/health" in ui
    assert "runtime_live_sim" in ui
    assert "historical_trade_list" in ui
    assert "learningTick" in ui
    assert "/admin/learning/tick" in ui
    assert "AUTOMATIC PRODUCTION PROMOTION: OFF" in ui
    assert "UNAVAILABLE" in ui
    assert "UNMEASURED" in ui
    assert "v == null" in ui or "v === null" in ui


def test_learning_dashboard_exposes_configuration_scoped_trade_experience():
    ui = (REPO / "icarus_engine/learning-ui.js").read_text(encoding="utf-8")
    assert "STRATEGY CONFIGURATION EXPERIENCE" in ui
    assert "Strategy fingerprint" in ui
    assert "PAYOFF RATIO" in ui
    assert "MAX DRAWDOWN" in ui
    assert "by_configuration" in ui
    assert "unscoped_count" in ui
    assert "CLOSURE-TIME PROVENANCE" in ui


def test_learning_dashboard_surfaces_psi_scenario_calibration():
    ui = (REPO / "icarus_engine/learning-ui.js").read_text(encoding="utf-8")
    assert "Ψ SCENARIO CALIBRATION" in ui
    assert "RAW SHARES UNCALIBRATED" in ui
    assert "forecasts_imported" in ui
    assert "outcomes_imported" in ui
    assert "overlap_withheld" in ui
    assert "psi-scenario-v1" in ui


def test_learning_dashboard_surfaces_shadow_recalibration():
    ui = (REPO / "icarus_engine/learning-ui.js").read_text(encoding="utf-8")
    assert "SHADOW RECALIBRATION" in ui
    assert "VALIDATED MODELS" in ui
    assert "REJECTED MODELS" in ui
    assert "RAW VS CALIBRATED BRIER" in ui
    assert "Holdout raw Brier" in ui
    assert "Holdout calibrated Brier" in ui
    assert "shadow_calibration" in ui
    assert "calibrated_validation_brier" in ui
    assert "automatic probability rewrite: off" in ui.lower()


def test_every_advertised_dashboard_command_has_a_ui_dispatch_case():
    dashboard = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    server = (REPO / "icarus_engine/server.py").read_text(encoding="utf-8")
    command_block = re.search(r"COMMANDS\s*=\s*\[(.*?)\]\s*\n\s*def serve", server, flags=re.DOTALL)
    assert command_block, "server COMMANDS registry was not found"
    advertised = set(re.findall(r'"id": "([^"]+)"', command_block.group(1)))
    dispatcher = re.search(
        r"async function runCommand\(id, asset\)\s*\{(.*?)\n\}\n/\* palette \*/",
        dashboard,
        flags=re.DOTALL,
    )
    assert dispatcher, "dashboard runCommand dispatcher was not found"
    handled = set(re.findall(r"case '([^']+)'", dispatcher.group(1)))
    assert advertised <= handled, "dashboard has dead advertised commands: " + ", ".join(sorted(advertised - handled))


def test_dashboard_control_failures_are_visible_and_backtest_polling_is_navigation_safe():
    dashboard = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    assert "request failed: " in dashboard
    assert "async function copyText" in dashboard
    assert "copy failed: " in dashboard
    assert "inputs unavailable: " in dashboard
    assert "backtest start failed: " in dashboard
    assert "backtest status failed: " in dashboard
    assert "compare failed: " in dashboard
    assert "if (view === 'backtest' && $('#btOut')) renderBacktest();" in dashboard
    assert "case 'backtest': BT.asset = A || BT.asset; setView('backtest'); return;" in dashboard
    assert '<a class="sm" style="margin-left:auto" href="/api/backtest/' not in dashboard
    assert "trade history unavailable:" in dashboard
    assert "Go-live integrity unavailable:" in dashboard
    assert "Field Agent unavailable:" in dashboard
    assert "} catch (e) {}" not in dashboard


def test_command_scope_renderer_does_not_offer_all_assets_to_asset_only_actions():
    dashboard = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    assert "const scopeOptions = c => (String(c.scope||'').includes('all')" in dashboard
    assert "scopeOptions(c)" in dashboard
    assert 'const opts = `<option value="*">all assets</option>`' not in dashboard


def test_interactive_panels_preserve_latest_user_selection_during_refresh():
    dashboard = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    research = (REPO / "icarus_engine/research-ui.js").read_text(encoding="utf-8")
    market = (REPO / "icarus_engine/market-data-ui.js").read_text(encoding="utf-8")
    psi = (REPO / "icarus_engine/possibility-ui.js").read_text(encoding="utf-8")
    chronofold = (REPO / "icarus_engine/chronofold-ui.js").read_text(encoding="utf-8")
    commissioning = (REPO / "icarus_engine/commissioning-ui.js").read_text(encoding="utf-8")
    sibyl = (REPO / "icarus_engine/sibyl-ui.js").read_text(encoding="utf-8")
    apex = (REPO / "icarus_engine/apex-ui.js").read_text(encoding="utf-8")

    assert "inputsLoadSeq" in dashboard
    assert "seq !== inputsLoadSeq" in dashboard
    assert "researchPendingLoad" in research
    assert "marketDataPendingLoad" in market
    assert "requestAsset!==marketDataState.asset" in market
    assert "pendingLoad = true" in psi
    assert "requestAsset !== selected" in psi
    assert "pendingLoad=true" in chronofold
    assert "requestAsset!==selected" in chronofold
    assert "pendingLoad=true" in commissioning
    assert "requestAsset!==selected" in commissioning
    assert "loadSeq" in sibyl and "seq !== loadSeq" in sibyl
    assert "loadSeq" in apex and "seq !== loadSeq" in apex


def test_financial_data_refreshes_are_latest_request_wins():
    ui = (REPO / "icarus_engine/sources-ui.js").read_text(encoding="utf-8")
    assert "sourcesPendingLoad" in ui
    assert "sourceRecordsSeq" in ui
    assert "seq!==sourceRecordsSeq" in ui
    assert "$('#sourceFilterAsset').value!==asset" in ui


def test_stateful_controls_are_single_flight_and_refresh_after_actions():
    dashboard = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    control = (REPO / "icarus_engine/engine-control-ui.js").read_text(encoding="utf-8")
    autopilot = (REPO / "icarus_engine/autopilot-ui.js").read_text(encoding="utf-8")
    learning = (REPO / "icarus_engine/learning-ui.js").read_text(encoding="utf-8")
    market = (REPO / "icarus_engine/market-data-ui.js").read_text(encoding="utf-8")

    assert "async function withBusyButton" in dashboard
    assert "withBusyButton(b, () => runCommand" in dashboard
    assert "engineControlPendingLoad" in control
    assert "engineControlRunning=new Set()" in control
    assert "action already running" in control
    assert "autopilotPendingLoad" in autopilot
    assert "autopilotMutationBusy" in autopilot
    assert "runAutopilotMutation" in autopilot
    assert "Autopilot control already running" in autopilot
    assert "mutationBusy" in learning
    assert "Learning action already running" in learning
    assert "let loadSeq = 0;" in learning
    assert "seq !== loadSeq" in learning
    assert "const requestAsset=marketDataState.asset;" in market
    assert "requestAsset!==marketDataState.asset" in market


def test_command_palette_and_scheduler_mutations_are_single_flight():
    dashboard = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    research = (REPO / "icarus_engine/research-ui.js").read_text(encoding="utf-8")
    sources = (REPO / "icarus_engine/sources-ui.js").read_text(encoding="utf-8")

    assert "const commandInflight = new Set();" in dashboard
    assert "async function adminCommand" in dashboard
    assert "command already running:" in dashboard
    assert "researchOperation($('#rsCancel'),'cancel'" in research
    assert "researchOperation($('#rsAnalysisCancel'),'analysis/cancel'" in research
    assert "configure(JSON.parse($('#rsAdaptationConfig').value),$('#rsSaveAdaptation'))" in research
    assert "configure({enabled:true},$('#rsEnableAdaptation'))" in research
    assert "configure(JSON.parse($('#sourceWatchConfig').value),$('#sourceWatchSave'))" in sources
    assert "configure({enabled:true},$('#sourceWatchEnable'))" in sources


def test_dashboard_catalogs_recover_after_transient_startup_failures():
    dashboard = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    assert "async function refreshUiCatalogs()" in dashboard
    assert "Promise.allSettled([get('/api/presets'), get('/api/commands'), get('/api/assets')])" in dashboard
    assert "const CATALOG_READY = {presets:false, commands:false, registry:false};" in dashboard
    assert "CATALOG_READY.presets = true;" in dashboard
    assert "CATALOG_READY.commands = true;" in dashboard
    assert "CATALOG_READY.registry = true;" in dashboard
    assert "if (!CATALOG_READY.presets || !CATALOG_READY.commands || !CATALOG_READY.registry) refreshUiCatalogs();" in dashboard
    assert "catalogRefreshBusy" in dashboard


def test_autopilot_operator_actions_are_not_silent():
    ui = (REPO / "icarus_engine/autopilot-ui.js").read_text(encoding="utf-8")
    assert "admin('/admin/autopilot/step',{},true)" not in ui
    assert "admin('/admin/autopilot/config',{cadence_seconds:Number(e.target.value)},true)" not in ui
    assert "admin('/admin/autopilot/config',{robustness_windows:Number(e.target.value)},true)" not in ui
    assert "admin('/admin/autopilot/config',{assets:e.target.value?[e.target.value]:[]},true)" not in ui


def test_dashboard_surfaces_ascendancy_capability_orchestrator():
    dashboard = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    ui = (REPO / "icarus_engine/ascendancy-ui.js").read_text(encoding="utf-8")
    server = (REPO / "icarus_engine/server.py").read_text(encoding="utf-8")
    assert '<script src="/ascendancy-ui.js"></script>' in dashboard
    assert 'data-v="ascendancy">ASCENDANCY</span>' in dashboard
    assert "view === 'ascendancy'" in dashboard
    assert "wireAscendancy()" in dashboard
    assert 'p.path == "/ascendancy-ui.js"' in server
    assert "/api/ascendancy/capabilities" in ui
    assert "Capability Orchestrator" in ui
    assert "BLOCKED_SUBSCRIPTION" in ui
    assert "BLOCKED_NETWORK_POLICY" in ui
    assert "claims_allowed" in ui
    assert "claims_forbidden" in ui
    assert "execution_authorized=false" in ui
    assert "production_decision_authorized=false" in ui


def test_learning_dashboard_surfaces_manifest_linked_historical_artifact_experience():
    ui = (REPO / "icarus_engine/learning-ui.js").read_text(encoding="utf-8")
    assert "HISTORICAL ARTIFACT CONFIGURATION EXPERIENCE" in ui
    assert "Manifest-linked artifact fingerprint" in ui
    assert "Strategy report" in ui
    assert "artifactExperienceRows" in ui
    assert "by_artifact_configuration" in ui
    assert "artifact_scoped_count" in ui
    assert "MANIFEST-LINKED" in ui


def test_learning_dashboard_exposes_label_and_revision_scoped_credibility():
    ui = (REPO / "icarus_engine/learning-ui.js").read_text(encoding="utf-8")
    assert "LABEL-SCOPED" in ui
    assert "REVISION-SCOPED" in ui
    assert "Prediction label" in ui
    assert "Source revision" in ui
    assert "r.prediction_label" in ui
    assert "r.source_commit" in ui
    assert "producer × asset × regime × horizon × label × revision" in ui


def test_learning_dashboard_exposes_overlap_aware_scorecard_counts():
    ui = (REPO / "icarus_engine/learning-ui.js").read_text(encoding="utf-8")
    assert "Effective settled" in ui
    assert "Raw settled" in ui
    assert "Overlap purged" in ui
    assert "r.raw_settled" in ui
    assert "r.overlap_purged" in ui
    assert "effective non-overlapping outcomes" in ui



def test_learning_ui_names_runtime_and_historical_provenance_classes():
    source = (REPO / "icarus_engine" / "learning-ui.js").read_text(encoding="utf-8")
    assert "RUNTIME_CLOSURE_CONFIG" in source
    assert "HISTORICAL_ARTIFACT_CONFIG" in source



def test_learning_ui_exposes_historical_artifact_session_provenance():
    source = (REPO / "icarus_engine" / "learning-ui.js").read_text(encoding="utf-8")
    assert "r.session_mode" in source
    assert "Historical session" in source


def test_learning_ui_exposes_proper_score_calibration_diagnostics():
    source = (REPO / "icarus_engine" / "learning-ui.js").read_text(encoding="utf-8")
    assert "expected_calibration_error" in source
    assert "maximum_calibration_error" in source
    assert "mean_log_loss" in source
    assert "brier_skill_score" in source


def test_learning_ui_exposes_semantic_trade_twin_proof():
    source = (REPO / "icarus_engine" / "learning-ui.js").read_text(encoding="utf-8")
    assert "semantic_trade_signature_sha256" in source
    assert "Semantic trade proof" in source
    assert "SEMANTIC_TRADE_SIGNATURE_V1" in source



def test_adaptive_brain_surfaces_historical_engine_context():
    ui = (REPO / "icarus_engine/brain-ui.js").read_text(encoding="utf-8")

    assert "historical_context_sources" in ui
    assert "Historical peer research context" in ui
    assert "HISTORICAL_RESEARCH_EVIDENCE" in ui
    assert "HISTORICAL_COLLECTION_EVIDENCE" in ui
    assert "candidate evidence=false" in ui.lower()
    assert "Foundry + Evaluator required" in ui
    assert "historical_context_ingested_total" in ui
    assert "historical_candidate_evidence_count" in ui
    assert "historical_context_status" in ui
    assert "Historical packet provenance" in ui
    assert "PACKET SOURCE VERIFIED" in ui
    assert "Packet-bound source proof" in ui
    assert "historical_packet_witness_status" in ui


def test_rebased_ascendancy_dashboard_uses_canonical_federation_and_full_research_stack():
    ui = (REPO / "icarus_engine/ascendancy-ui.js").read_text(encoding="utf-8")
    server = (REPO / "icarus_engine/server.py").read_text(encoding="utf-8")

    for route in (
        "/api/ascendancy/capabilities",
        "/api/ascendancy/genomes",
        "/api/ascendancy/candidates",
        "/api/ascendancy/unknowns",
        "/api/ascendancy/mechanisms",
        "/api/ascendancy/inventions",
        "/api/ascendancy/contributions",
        "/api/ascendancy/evaluator",
    ):
        assert route in ui
        assert route in server

    assert "fetchJson('/api/brain', token)" in ui
    assert "/api/ascendancy/peers" not in ui
    assert "/api/ascendancy/peers" not in server
    assert "FEDERATED ICARUS-ENGINE CONTEXT" in ui
    assert "HISTORICAL RESEARCH CONTEXT" in ui
    assert "candidate evidence=false" in ui.lower()
    assert "historical_context_never_bypasses_foundry" in ui
    assert "historical_context_never_bypasses_evaluator" in ui
    assert "ASCENDANCY EVALUATOR" in ui
    assert "INFORMATION CONTRIBUTION MATRIX" in ui
    assert "MECHANISM LABORATORY" in ui
    assert "INVENTION ENGINE" in ui
    assert "UNKNOWN-UNKNOWN" in ui


def test_ascendancy_dashboard_surfaces_autonomous_evolution_governor():
    ui = (REPO / "icarus_engine/ascendancy-ui.js").read_text(encoding="utf-8")
    server = (REPO / "icarus_engine/server.py").read_text(encoding="utf-8")

    assert "/api/ascendancy/governor" in ui
    assert "AUTONOMOUS EVOLUTION GOVERNOR" in ui
    assert "EXPLORATION" in ui
    assert "EXPLOITATION" in ui
    assert "ESTIMATED COST" in ui
    assert "scheduler_heuristic_not_edge_score" in ui
    assert "can_mint_evaluator_receipts=false" in ui
    assert "can_mint_qualification=false" in ui
    assert 'p.path == "/api/ascendancy/governor"' in server
    assert 'p.path == "/admin/ascendancy/governor-plan"' in server


def test_ascendancy_dashboard_surfaces_safe_internal_executor():
    ui = (REPO / "icarus_engine/ascendancy-ui.js").read_text(encoding="utf-8")
    server = (REPO / "icarus_engine/server.py").read_text(encoding="utf-8")

    assert "/api/ascendancy/executor" in ui
    assert "SAFE INTERNAL EXECUTOR" in ui
    assert "APPLIED INTERNAL" in ui
    assert "AWAITING EXTERNAL" in ui
    assert "NOT SCIENTIFIC EVIDENCE" in ui
    assert "evidence-producing actions are never auto-applied" in ui.lower()
    assert 'p.path == "/api/ascendancy/executor"' in server
    assert 'p.path == "/admin/ascendancy/governor-execute-safe"' in server


def test_ascendancy_dashboard_surfaces_bounded_autopilot():
    ui = (REPO / "icarus_engine/ascendancy-ui.js").read_text(encoding="utf-8")
    server = (REPO / "icarus_engine/server.py").read_text(encoding="utf-8")

    assert "/api/ascendancy/autopilot" in ui
    assert "BOUNDED AUTONOMOUS LOOP" in ui
    assert "STOP REASON" in ui
    assert "NEW INTERNAL TRANSITIONS" in ui
    assert "EXTERNAL EVIDENCE STOPS LOOP" in ui
    assert 'p.path == "/api/ascendancy/autopilot"' in server
    assert 'p.path == "/admin/ascendancy/autopilot-cycle"' in server
    assert "ascendancy_autopilot.start()" in server
    assert "ascendancy_autopilot.close()" in server
