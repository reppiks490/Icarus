"""MCP (stdio) control surface for the running bridge.

Register with Claude Code:
  claude mcp add icarus-bridge -e ICARUS_BRIDGE_URL=http://127.0.0.1:8787 -e ICARUS_ADMIN_TOKEN=<token> -- <python> -m icarus_bridge.mcp_server

Every tool is a thin call to the bridge's admin API, so the daemon stays the
single source of truth and Claude can never race the webhook thread.
"""
from __future__ import annotations

import json
import os
from urllib.parse import quote
from typing import Any, Dict, Optional

import httpx
from mcp.server.mcpserver import MCPServer

from .config import _load_dotenv


def _endpoint_settings():
    """Load MCP endpoints/tokens from explicit env or the same persisted .env as the bridge."""
    _load_dotenv()
    e = os.environ.get
    bridge_url = (e("ICARUS_BRIDGE_URL") or "http://127.0.0.1:8787").rstrip("/")
    bridge_token = e("ICARUS_ADMIN_TOKEN") or e("ADMIN_TOKEN") or ""
    engine_url = (e("ICARUS_ENGINE_URL") or "http://127.0.0.1:8791").rstrip("/")
    engine_token = e("ICARUS_ENGINE_TOKEN") or bridge_token
    return bridge_url, bridge_token, engine_url, engine_token


BASE, TOKEN, ENGINE_BASE, ENGINE_TOKEN = _endpoint_settings()

mcp = MCPServer(
    "icarus-bridge",
    instructions=(
        "Control surface for the ICARUS Bridge: a local daemon that receives TradingView strategy "
        "webhooks and mirrors them onto an Alpaca PAPER account (NQ signals → QQQ proxy). Read tools are "
        "safe. The engine_* tools expose ICARUS strategy configuration, cached backtests and paper-engine "
        "results. After any material ICARUS repair, audit, evolution, integration, or loop durability "
        "change performed through MCP, publish the verified result with record_engine_system_event and "
        "record_engine_loop_status when applicable so the trader System Intelligence panel stays aligned. "
        "For export, corpus, data-quality, representation, replay-lineage, or provenance work, also publish "
        "the exact source repository/branch/40-character commit through record_engine_integrity_event so the "
        "Data Integrity panel stays aligned. For agent/subsystem learning, regime research, drift, training, "
        "evaluation, or rigorously-qualified candidate lifecycle updates, use record_engine_brain_event so the "
        "Adaptive Brain panel receives durable evidence. Use the performance-proof tools for immutable forecast/outcome/replay "
        "evidence and engine_latency_telemetry for measured timing. Brain publication is research/shadow-only and cannot "
        "grant production decision or broker authority. Those publication tools are diagnostic-only. "
        "pause_trading / resume_trading / flatten_all / "
        "simulate_alert change live paper state — confirm with the user before calling them unless they "
        "asked for exactly that action."
    ),
)


def _client() -> httpx.Client:
    return httpx.Client(base_url=BASE, timeout=20.0, headers={"Authorization": f"Bearer {TOKEN}"})


def _get(path: str, **params: Any) -> Any:
    with _client() as c:
        r = c.get(path, params={k: v for k, v in params.items() if v is not None})
        r.raise_for_status()
        return r.json()


def _post(path: str, body: Optional[Dict[str, Any]] = None, raw: Optional[str] = None) -> Any:
    with _client() as c:
        r = c.post(path, content=raw if raw is not None else json.dumps(body or {}),
                   headers={"Content-Type": "application/json"})
        if r.status_code >= 400:
            return {"error": r.status_code, "detail": r.text}
        return r.json()


def _engine_client() -> httpx.Client:
    return httpx.Client(base_url=ENGINE_BASE, timeout=60.0,
                        headers={"Authorization": f"Bearer {ENGINE_TOKEN}"})


def _engine_get(path: str, **params: Any) -> Any:
    with _engine_client() as c:
        r = c.get(path, params={k: v for k, v in params.items() if v is not None})
        r.raise_for_status()
        return r.json()


def _engine_post(path: str, body: Optional[Dict[str, Any]] = None) -> Any:
    with _engine_client() as c:
        r = c.post(path, content=json.dumps(body or {}), headers={"Content-Type": "application/json"})
        if r.status_code >= 400:
            return {"error": r.status_code, "detail": r.text}
        return r.json()


def _safe_engine(fn):
    try:
        return fn()
    except httpx.ConnectError:
        return {"error": f"ICARUS engine not reachable at {ENGINE_BASE} — start the paper engine/dashboard first"}
    except httpx.HTTPStatusError as ex:
        return {"error": ex.response.status_code, "detail": ex.response.text}
    except Exception as ex:  # noqa: BLE001
        return {"error": f"{type(ex).__name__}: {ex}"}


def _safe(fn):
    try:
        return fn()
    except httpx.ConnectError:
        return {"error": f"bridge not reachable at {BASE} — start it with: icarus-bridge serve"}
    except httpx.HTTPStatusError as ex:
        return {"error": ex.response.status_code, "detail": ex.response.text}
    except Exception as ex:  # noqa: BLE001
        return {"error": f"{type(ex).__name__}: {ex}"}


# ── read tools ──
@mcp.tool()
def bridge_status() -> dict:
    """Health + account + positions + resting orders + last alert age + pause state of the bridge."""
    return _safe(lambda: _get("/status"))


@mcp.tool()
def list_alerts(limit: int = 30) -> list:
    """Recent TradingView alerts as received (parsed fields, mapping, execution status, note)."""
    return _safe(lambda: _get("/admin/alerts", limit=limit))


@mcp.tool()
def list_orders(limit: int = 30) -> list:
    """Recent paper orders the bridge placed (kind, purpose, fill price, status)."""
    return _safe(lambda: _get("/admin/orders", limit=limit))


@mcp.tool()
def positions() -> dict:
    """Current paper positions and open orders straight from the broker."""
    def run():
        st = _get("/status")
        return {"positions": st.get("positions"), "open_orders": st.get("open_orders"),
                "symbol_state": st.get("symbol_state"), "market": st.get("market")}
    return _safe(run)


@mcp.tool()
def reality_gap_report(limit: int = 100) -> dict:
    """TV-vs-paper report: for each strategy fill, the paper fill(s) it produced, latency, and slippage.
    Use it to judge how honest the TradingView backtest fills are versus real paper execution."""
    def run():
        rows = _get("/admin/report", limit=limit)
        lat = [r["latency_sec"] for r in rows if r.get("latency_sec") is not None]
        summary = {"fills": len(rows), "with_paper_fill": sum(1 for r in rows if r.get("paper_fill_avg")),
                   "median_latency_sec": (sorted(lat)[len(lat) // 2] if lat else None),
                   "max_latency_sec": (max(lat) if lat else None)}
        return {"summary": summary, "rows": rows}
    return _safe(run)


@mcp.tool()
def recent_log(limit: int = 60) -> list:
    """Bridge log lines (INFO/WARN/ERROR), newest first."""
    return _safe(lambda: _get("/admin/log", limit=limit))


@mcp.tool()
def get_config() -> dict:
    """Effective bridge configuration (secrets masked): mode, symbol map, sizing, risk limits."""
    return _safe(lambda: _get("/admin/config"))


# ── ICARUS strategy/paper-engine tools ──
@mcp.tool()
def engine_status() -> dict:
    """Paper-engine status and per-asset calculations after the active chart/input configuration is replayed."""
    return _safe_engine(lambda: _engine_get("/status/public"))


@mcp.tool()
def engine_repository_audit() -> dict:
    """Latest local GitHub/MCP repository + CI audit snapshot shown in the ICARUS trader dashboard."""
    return _safe_engine(lambda: _engine_get("/api/system/audit"))


@mcp.tool()
def record_engine_repository_audit(audit_json: str) -> dict:
    """Persist a verified repository/CI audit so MCP and the trader dashboard surface the same state.

    This only updates local diagnostic state; it cannot pause, resume, place, cancel, or flatten trades.
    """
    try:
        audit = json.loads(audit_json)
    except json.JSONDecodeError as ex:
        return {"error": f"audit_json is invalid JSON: {ex}"}
    if not isinstance(audit, dict):
        return {"error": "audit_json must decode to an object"}
    return _safe_engine(lambda: _engine_post("/admin/system/audit", {"audit": audit}))


@mcp.tool()
def record_engine_system_event(kind: str, title: str, detail: str = "", severity: str = "info",
                               repository: str = "", ref: str = "") -> dict:
    """Publish an important verified MCP repair/audit/evolution/integration/finding to the trader UI.

    Diagnostic-only: this cannot alter strategy state, broker state, orders, positions, or execution authority.
    """
    event = {
        "kind": kind,
        "severity": severity,
        "title": title,
        "detail": detail,
        "repository": repository,
        "ref": ref,
    }
    return _safe_engine(lambda: _engine_post("/admin/system/event", {"event": event}))


@mcp.tool()
def record_engine_loop_status(loop_id: str, title: str, status: str, run_id: str = "",
                              scheduler_id: str = "", schedule: str = "", repository: str = "",
                              finalization_commit_sha: str = "", finalization_state_blob_sha: str = "",
                              detail: str = "") -> dict:
    """Publish one verified automation-loop durability receipt/status to the trader UI.

    Use after verifying the exact loop finalization + heartbeat binding. Diagnostic-only.
    """
    loop = {
        "id": loop_id,
        "title": title,
        "status": status,
        "run_id": run_id,
        "scheduler_id": scheduler_id,
        "schedule": schedule,
        "repository": repository,
        "finalization_commit_sha": finalization_commit_sha,
        "finalization_state_blob_sha": finalization_state_blob_sha,
        "detail": detail,
    }
    return _safe_engine(lambda: _engine_post("/admin/system/loop", {"loop": loop}))


@mcp.tool()
def engine_configuration(asset: str = "NQ") -> dict:
    """Effective strategy inputs plus chart timeframe/type/fill/source capabilities for one engine asset."""
    asset = asset.strip().upper()
    return _safe_engine(lambda: _engine_get(f"/api/inputs/{asset}"))


@mcp.tool()
def set_engine_chart_config(asset: str = "NQ", timeframe: Optional[str] = None,
                            chart_type: Optional[str] = None, fill_on: Optional[str] = None,
                            security_source: Optional[str] = None, persist: bool = True) -> dict:
    """Reconfigure and re-warm an engine asset from cached bars.

    Supported chart modes are standard OHLC (real) and Heikin Ashi (heikin_ashi).
    Real fills remain recommended even when the strategy calculates on Heikin Ashi.
    Databento now supplies genuine 1-second/tick/depth data, but chart-timeframe execution remains minute-based until the chart aggregator is upgraded for sub-minute/tick bars.
    """
    chart = {k: v for k, v in {
        "timeframe": timeframe, "chart_type": chart_type, "fill_on": fill_on,
        "security_source": security_source,
    }.items() if v not in (None, "")}
    if not chart:
        return {"error": "provide at least one chart setting"}
    body = {"asset": asset.strip().upper(), "values": {}, "chart": chart, "persist": bool(persist)}
    return _safe_engine(lambda: _engine_post("/admin/inputs", body))


@mcp.tool()
def start_engine_backtest(asset: str = "NQ", timeframe: Optional[str] = None,
                          chart_type: Optional[str] = None, fill_on: Optional[str] = None,
                          security_source: Optional[str] = None, preset: Optional[str] = None,
                          inputs_json: str = "") -> dict:
    """Start a cached ICARUS Strategy Tester replay using the requested timeframe/chart settings."""
    body: Dict[str, Any] = {"asset": asset.strip().upper()}
    for k, v in {"timeframe": timeframe, "chart_type": chart_type, "fill_on": fill_on,
                 "security_source": security_source, "preset": preset}.items():
        if v not in (None, ""):
            body[k] = v
    if inputs_json.strip():
        try:
            vals = json.loads(inputs_json)
        except json.JSONDecodeError as ex:
            return {"error": f"inputs_json is invalid JSON: {ex}"}
        if not isinstance(vals, dict):
            return {"error": "inputs_json must decode to an object"}
        body["inputs"] = vals
    return _safe_engine(lambda: _engine_post("/admin/backtest", body))


@mcp.tool()
def engine_backtest_status(job_id: str) -> dict:
    """Read a cached backtest job, including recalculated metrics/trades when it is complete."""
    return _safe_engine(lambda: _engine_get(f"/api/backtest/{job_id.strip()}"))


@mcp.tool()
def engine_market_data_capabilities(asset: str = "NQ") -> dict:
    """Active raw-feed capabilities. Databento exposes 1s OHLCV, ticks, MBP-10, and MBO."""
    asset = asset.strip().upper()
    return _safe_engine(lambda: _engine_get(f"/api/market-data/{asset}/capabilities"))


@mcp.tool()
def engine_recent_ticks(asset: str = "NQ", limit: int = 1000, since_ts: int = 0) -> dict:
    """Recent raw trade ticks from the active engine feed."""
    asset = asset.strip().upper()
    qs = f"?limit={max(1, min(10000, int(limit)))}"
    if int(since_ts) > 0:
        qs += f"&since_ts={int(since_ts)}"
    return _safe_engine(lambda: _engine_get(f"/api/market-data/{asset}/ticks{qs}"))


@mcp.tool()
def engine_order_book_events(asset: str = "NQ", schema: str = "mbp-10", limit: int = 1000) -> dict:
    """Recent Databento L2/L3 events. schema must be mbp-10 or mbo."""
    schema = schema.strip().lower()
    if schema not in ("mbp-10", "mbo"):
        return {"error": "schema must be mbp-10 or mbo"}
    asset = asset.strip().upper()
    return _safe_engine(lambda: _engine_get(
        f"/api/market-data/{asset}/depth?schema={schema}&limit={max(1, min(10000, int(limit)))}"
    ))


@mcp.tool()
def engine_mbo_snapshot(asset: str = "NQ", timeout: float = 5.0) -> dict:
    """Request a live Databento MBO snapshot for the continuous front contract."""
    body = {"asset": asset.strip().upper(), "timeout": max(0.1, min(30.0, float(timeout)))}
    return _safe_engine(lambda: _engine_post("/admin/market-data/mbo-snapshot", body))


@mcp.tool()
def engine_integrity_state() -> dict:
    """Read export/data integrity plus the MCP change ledger shown in the ICARUS trading interface."""
    return _safe_engine(lambda: _engine_get("/api/integrity"))


@mcp.tool()
def record_engine_integrity_event(
    kind: str,
    area: str,
    summary: str,
    source_repo: str,
    source_branch: str,
    source_commit: str,
    verification: str,
    interface_effect: str,
    status: str = "observed",
    severity: str = "important",
    evidence_json: str = "[]",
    details_json: str = "{}",
) -> dict:
    """Mirror one material data/provenance MCP change into the ICARUS Data Integrity panel.

    source_commit must be the exact 40-character source commit SHA. Writes are
    idempotent by semantic event identity. This tool cannot change strategy or
    broker state and always preserves execution_authorized=false.
    """
    try:
        evidence = json.loads(evidence_json or "[]")
        details = json.loads(details_json or "{}")
    except json.JSONDecodeError as ex:
        return {"error": f"invalid JSON metadata: {ex}"}
    if not isinstance(evidence, list):
        return {"error": "evidence_json must decode to a list"}
    if not isinstance(details, dict):
        return {"error": "details_json must decode to an object"}
    body = {
        "kind": kind,
        "area": area,
        "summary": summary,
        "status": status,
        "severity": severity,
        "source_repo": source_repo,
        "source_branch": source_branch,
        "source_commit": source_commit,
        "verification": verification,
        "interface_effect": interface_effect,
        "evidence": evidence,
        "details": details,
    }
    return _safe_engine(lambda: _engine_post("/admin/integrity/event", body))


@mcp.tool()
def engine_brain_state() -> dict:
    """Read the Adaptive Brain multi-agent/subsystem, learning, regime and shadow-candidate state."""
    return _safe_engine(lambda: _engine_get("/api/brain"))


@mcp.tool()
def record_engine_brain_event(
    kind: str,
    subject: str,
    summary: str,
    status: str = "observed",
    evidence_json: str = "[]",
    details_json: str = "{}",
    candidate_id: str = "",
    stage: str = "",
    regimes_json: str = "[]",
    metrics_json: str = "{}",
    validation_json: str = "{}",
    source_repo: str = "",
    source_commit: str = "",
) -> dict:
    """Publish one evidence-backed Adaptive Brain event.

    Candidate events require an exact source repository + 40-character Git SHA,
    explicit regime tags, metrics, and every validation gate. This endpoint is
    research/shadow-only and always preserves production_decision_authorized=false
    and execution_authorized=false.
    """
    try:
        evidence = json.loads(evidence_json or "[]")
        details = json.loads(details_json or "{}")
        regimes = json.loads(regimes_json or "[]")
        metrics = json.loads(metrics_json or "{}")
        validation = json.loads(validation_json or "{}")
    except json.JSONDecodeError as ex:
        return {"error": f"invalid JSON metadata: {ex}"}
    if not isinstance(evidence, list):
        return {"error": "evidence_json must decode to a list"}
    if not isinstance(details, dict):
        return {"error": "details_json must decode to an object"}
    if not isinstance(regimes, list):
        return {"error": "regimes_json must decode to a list"}
    if not isinstance(metrics, dict):
        return {"error": "metrics_json must decode to an object"}
    if not isinstance(validation, dict):
        return {"error": "validation_json must decode to an object"}

    body: Dict[str, Any] = {
        "kind": kind,
        "subject": subject,
        "summary": summary,
        "status": status,
        "evidence": evidence,
        "details": details,
    }
    if kind.strip().lower() == "candidate":
        body.update({
            "candidate_id": candidate_id,
            "stage": stage,
            "regimes": regimes,
            "metrics": metrics,
            "validation": validation,
            "source_repo": source_repo,
            "source_commit": source_commit,
        })
    return _safe_engine(lambda: _engine_post("/admin/brain/event", body))


@mcp.tool()
def engine_candidate_qualification_receipts() -> dict:
    """Read immutable exact-revision candidate qualification receipts and blockers."""
    return _safe_engine(lambda: _engine_get("/api/qualification-receipts"))


@mcp.tool()
def record_engine_candidate_qualification_receipt(
    candidate_id: str,
    candidate_source_repo: str,
    candidate_source_commit: str,
    gate: str,
    passed: bool,
    verifier_id: str,
    verifier_source_repo: str,
    verifier_source_commit: str,
    observed_at: str,
    evidence_hash: str,
) -> dict:
    """Record one exact-revision gate receipt and reconcile shadow eligibility."""
    body = {
        "candidate_id": candidate_id.strip(),
        "candidate_source_repo": candidate_source_repo.strip(),
        "candidate_source_commit": candidate_source_commit.strip().lower(),
        "gate": gate.strip(),
        "passed": bool(passed),
        "verifier_id": verifier_id.strip(),
        "verifier_source_repo": verifier_source_repo.strip(),
        "verifier_source_commit": verifier_source_commit.strip().lower(),
        "observed_at": observed_at.strip(),
        "evidence_hash": evidence_hash.strip().lower(),
    }
    return _safe_engine(lambda: _engine_post("/admin/qualification-receipts/record", body))


@mcp.tool()
def sync_engine_candidate_qualification(
    candidate_id: str,
    candidate_source_repo: str,
    candidate_source_commit: str,
) -> dict:
    """Reconcile one exact candidate revision with its current immutable gate receipts."""
    return _safe_engine(lambda: _engine_post("/admin/qualification-receipts/sync", {
        "candidate_id": candidate_id.strip(),
        "candidate_source_repo": candidate_source_repo.strip(),
        "candidate_source_commit": candidate_source_commit.strip().lower(),
    }))


@mcp.tool()
def engine_pantheon_state() -> dict:
    """Read PANTHEON faculties, AETHER swarm state, sentinel cells and durable shadow claims."""
    return _safe_engine(lambda: _engine_get("/api/pantheon"))

@mcp.tool()
def record_engine_pantheon_observation(
    asset: str,
    observed_at: str,
    signals_json: str,
    horizon_ms: int = 1000,
    evidence_json: str = "[]",
    subsystem_outputs_json: str = "{}",
    source_commit: str = "",
    observation_id: str = "",
) -> dict:
    """Submit one immutable PANTHEON shadow observation.

    Native ORACLE Psi, PARALLAX and DREAMSTATE evidence is attached by the engine.
    This tool cannot authorize execution, sizing, broker actions or production promotion.
    """
    try:
        signals = json.loads(signals_json or "{}")
        evidence = json.loads(evidence_json or "[]")
        subsystem_outputs = json.loads(subsystem_outputs_json or "{}")
    except json.JSONDecodeError as ex:
        return {"error": f"PANTHEON JSON input is invalid: {ex}"}
    if not isinstance(signals, dict):
        return {"error": "signals_json must decode to an object"}
    if not isinstance(evidence, list):
        return {"error": "evidence_json must decode to a list"}
    if not isinstance(subsystem_outputs, dict):
        return {"error": "subsystem_outputs_json must decode to an object"}
    body: Dict[str, Any] = {
        "asset": asset.strip().upper(),
        "observed_at": observed_at.strip(),
        "horizon_ms": int(horizon_ms),
        "signals": signals,
        "evidence": evidence,
        "subsystem_outputs": subsystem_outputs,
    }
    if source_commit.strip():
        body["source_commit"] = source_commit.strip()
    if observation_id.strip():
        body["observation_id"] = observation_id.strip()
    return _safe_engine(lambda: _engine_post("/admin/pantheon/observe", body))

@mcp.tool()
def record_engine_veritas_reconciliation(
    observation_id: str,
    source_observation_id: str,
    observed_at: str,
    confidence: float,
    evidence_json: str,
) -> dict:
    """Reconcile one immutable VERITAS certificate against a later PANTHEON observation.

    Realized direction and mechanism signatures are derived by the engine from
    the immutable source observation; callers cannot inject either outcome here.
    A correct endpoint is not reinforcement-eligible unless that path reconciles.
    """
    try:
        evidence = json.loads(evidence_json or "[]")
    except json.JSONDecodeError as ex:
        return {"error": f"VERITAS JSON input is invalid: {ex}"}
    if not isinstance(evidence, list) or not evidence:
        return {"error": "evidence_json must decode to a non-empty list"}
    body: Dict[str, Any] = {
        "observation_id": observation_id.strip(),
        "source_observation_id": source_observation_id.strip(),
        "observed_at": observed_at.strip(),
        "confidence": float(confidence),
        "evidence": evidence,
    }
    return _safe_engine(lambda: _engine_post("/admin/pantheon/veritas", body))


@mcp.tool()
def record_engine_aether_claim(
    observation_id: str,
    agent_id: str,
    thesis: str,
    direction: str = "unknown",
    confidence: float = 0.5,
    falsifier: str = "",
    evidence_json: str = "[]",
) -> dict:
    """Commit one immutable blind-first-pass AETHER research claim.

    The engine verifies that agent_id was spawned for observation_id. This MCP
    wrapper never supplies peer context and the resulting claim has no execution authority.
    """
    try:
        evidence = json.loads(evidence_json or "[]")
    except json.JSONDecodeError as ex:
        return {"error": f"evidence_json is invalid JSON: {ex}"}
    if not isinstance(evidence, list):
        return {"error": "evidence_json must decode to a list"}
    body: Dict[str, Any] = {
        "observation_id": observation_id.strip(),
        "agent_id": agent_id.strip(),
        "peer_context_used": False,
        "claim": {
            "thesis": thesis.strip(),
            "direction": direction.strip().lower(),
            "confidence": float(confidence),
            "falsifier": falsifier.strip(),
            "evidence": evidence,
        },
    }
    return _safe_engine(lambda: _engine_post("/admin/pantheon/claim", body))

@mcp.tool()
def engine_sibyl_state(asset: str = "NQ") -> dict:
    """Read SIBYL Omega causal as-of future-lightcone state."""
    return _safe_engine(lambda: _engine_get("/api/sibyl", asset=asset.strip().upper()))


@mcp.tool()
def record_engine_sibyl_evidence(
    asset: str,
    source: str,
    domain: str,
    observed_at: str,
    direction: float,
    confidence: float,
    horizon_seconds: int,
    magnitude: float = 1.0,
    source_commit: str = "",
    target_price: Optional[float] = None,
    invalidation_price: Optional[float] = None,
    payload_json: str = "{}",
) -> dict:
    """Publish one provenance-bearing SIBYL research evidence row.

    The reserved pantheon-ananke identity cannot be submitted through this
    generic tool; PANTHEON uses its internal validated bridge.
    """
    try:
        payload = json.loads(payload_json or "{}")
    except json.JSONDecodeError as ex:
        return {"error": f"payload_json is invalid JSON: {ex}"}
    if not isinstance(payload, dict):
        return {"error": "payload_json must decode to an object"}
    if source.strip().lower() == "pantheon-ananke":
        return {"error": "pantheon-ananke is reserved for the internal validated PANTHEON bridge"}
    body: Dict[str, Any] = {
        "asset": asset.strip().upper(),
        "source": source.strip().lower(),
        "domain": domain.strip().lower(),
        "observed_at": observed_at.strip(),
        "direction": float(direction),
        "magnitude": float(magnitude),
        "confidence": float(confidence),
        "horizon_seconds": int(horizon_seconds),
        "payload": payload,
    }
    if source_commit.strip():
        body["source_commit"] = source_commit.strip()
    if target_price is not None:
        body["target_price"] = float(target_price)
    if invalidation_price is not None:
        body["invalidation_price"] = float(invalidation_price)
    return _safe_engine(lambda: _engine_post("/admin/sibyl/evidence", body))


@mcp.tool()
def record_engine_sibyl_forecast(
    asset: str,
    horizons_json: str = "[60,300,900,3600,14400]",
    observed_at: str = "",
    current_price: Optional[float] = None,
    volatility_pct: float = 0.0025,
    source_commit: str = "",
) -> dict:
    """Persist one immutable SIBYL forecast.

    Historical forecasts must supply both observed_at and current_price; the
    engine refuses to borrow the live market price for replay.
    """
    try:
        horizons = json.loads(horizons_json or "[]")
    except json.JSONDecodeError as ex:
        return {"error": f"horizons_json is invalid JSON: {ex}"}
    if not isinstance(horizons, list) or not horizons:
        return {"error": "horizons_json must decode to a non-empty list"}
    body: Dict[str, Any] = {
        "asset": asset.strip().upper(),
        "horizons": horizons,
        "volatility_pct": float(volatility_pct),
    }
    if observed_at.strip():
        body["observed_at"] = observed_at.strip()
    if current_price is not None:
        body["current_price"] = float(current_price)
    if source_commit.strip():
        body["source_commit"] = source_commit.strip()
    return _safe_engine(lambda: _engine_post("/admin/sibyl/forecast", body))


@mcp.tool()
def record_engine_sibyl_outcome(
    forecast_id: str,
    horizon_seconds: int,
    observed_at: str,
    realized_price: float,
    evidence_json: str = "[]",
) -> dict:
    """Score one matured SIBYL forecast horizon exactly once."""
    try:
        evidence = json.loads(evidence_json or "[]")
    except json.JSONDecodeError as ex:
        return {"error": f"evidence_json is invalid JSON: {ex}"}
    if not isinstance(evidence, list):
        return {"error": "evidence_json must decode to a list"}
    return _safe_engine(lambda: _engine_post("/admin/sibyl/outcome", {
        "forecast_id": forecast_id.strip(),
        "horizon_seconds": int(horizon_seconds),
        "observed_at": observed_at.strip(),
        "realized_price": float(realized_price),
        "evidence": evidence,
    }))


@mcp.tool()
def record_engine_sibyl_scenario(
    asset: str,
    interventions_json: str,
    horizons_json: str = "[60,300,900,3600,14400]",
    as_of: str = "",
    current_price: Optional[float] = None,
    volatility_pct: float = 0.0025,
) -> dict:
    """Run one non-persistent SIBYL counterfactual future map."""
    try:
        interventions = json.loads(interventions_json or "[]")
        horizons = json.loads(horizons_json or "[]")
    except json.JSONDecodeError as ex:
        return {"error": f"SIBYL scenario JSON is invalid: {ex}"}
    if not isinstance(interventions, list) or not interventions:
        return {"error": "interventions_json must decode to a non-empty list"}
    if not isinstance(horizons, list) or not horizons:
        return {"error": "horizons_json must decode to a non-empty list"}
    body: Dict[str, Any] = {
        "asset": asset.strip().upper(),
        "interventions": interventions,
        "horizons": horizons,
        "volatility_pct": float(volatility_pct),
    }
    if as_of.strip():
        body["as_of"] = as_of.strip()
    if current_price is not None:
        body["current_price"] = float(current_price)
    return _safe_engine(lambda: _engine_post("/admin/sibyl/scenario", body))


@mcp.tool()
def engine_source_reliability() -> dict:
    """Read causal source/stream reliability measurements from ICARUS."""
    return _safe_engine(lambda: _engine_get("/api/source-reliability"))


@mcp.tool()
def record_engine_source_reliability_observation(
    source_id: str,
    stream: str,
    observed_at: str,
    event_time: str,
    retrieval_time: str,
    expected_freshness_seconds: float,
    complete: bool,
    evidence_hash: str,
    revision: bool = False,
    agreement_bps: Optional[float] = None,
    agreement_tolerance_bps: Optional[float] = None,
) -> dict:
    """Record one immutable causal-time source reliability observation."""
    return _safe_engine(lambda: _engine_post("/admin/source-reliability/observation", {
        "source_id": source_id,
        "stream": stream,
        "observed_at": observed_at,
        "event_time": event_time,
        "retrieval_time": retrieval_time,
        "expected_freshness_seconds": float(expected_freshness_seconds),
        "complete": bool(complete),
        "agreement_bps": agreement_bps,
        "agreement_tolerance_bps": agreement_tolerance_bps,
        "revision": bool(revision),
        "evidence_hash": evidence_hash,
    }))


# ── Continuous learning / replay / calibration tools ──
@mcp.tool()
def engine_learning_state() -> dict:
    """Read the continuous ICARUS learning/replay/calibration state."""
    return _safe_engine(lambda: _engine_get("/api/learning"))


@mcp.tool()
def engine_learning_scorecards() -> dict:
    """Read empirical scorecards by producer, asset, regime and horizon."""
    return _safe_engine(lambda: _engine_get("/api/learning/scorecards"))


@mcp.tool()
def engine_learning_datasets() -> dict:
    """Read catalogued historical datasets and protected training runs."""
    return _safe_engine(lambda: _engine_get("/api/learning/datasets"))


@mcp.tool()
def engine_learning_experience() -> dict:
    """Read realized historical/live-sim trade experience summaries."""
    return _safe_engine(lambda: _engine_get("/api/learning/experience"))

@mcp.tool()
def engine_learning_health() -> dict:
    """Read durable Continuous Learning Fabric health, staleness and backlog."""
    return _safe_engine(lambda: _engine_get("/api/learning/health"))



@mcp.tool()
def configure_engine_learning(config_json: str) -> dict:
    """Configure the bounded research-only continual-learning loop."""
    body, error = _apex_json_object(config_json, "config_json")
    if error:
        return error
    return _safe_engine(lambda: _engine_post("/admin/learning/config", body))


@mcp.tool()
def record_engine_learning_prediction(prediction_json: str) -> dict:
    """Record a standardized research prediction for later observed settlement."""
    body, error = _apex_json_object(prediction_json, "prediction_json")
    if error:
        return error
    return _safe_engine(lambda: _engine_post("/admin/learning/prediction", body))


@mcp.tool()
def record_engine_learning_outcome(outcome_json: str) -> dict:
    """Record a matured observed outcome for a standardized research prediction."""
    body, error = _apex_json_object(outcome_json, "outcome_json")
    if error:
        return error
    return _safe_engine(lambda: _engine_post("/admin/learning/outcome", body))


@mcp.tool()
def scan_engine_learning_history() -> dict:
    """Scan configured local history lanes for new/deduplicated research data."""
    return _safe_engine(lambda: _engine_post("/admin/learning/scan", {}))


@mcp.tool()
def backfill_engine_learning_dataset(dataset_id: str, slots: str = "logit") -> dict:
    """Run protected historical trainer slots for a catalogued dataset."""
    did = str(dataset_id or "").strip()
    if not did:
        return {"error": "dataset_id is required"}
    parsed = [x.strip().lower() for x in str(slots or "").split(",") if x.strip()]
    if not parsed:
        return {"error": "at least one slot is required"}
    return _safe_engine(lambda: _engine_post("/admin/learning/backfill", {"dataset_id": did, "slots": parsed}))


@mcp.tool()
def run_engine_learning_cycle() -> dict:
    """Run one bounded research-only learning/harvest/replay cycle immediately."""
    return _safe_engine(lambda: _engine_post("/admin/learning/tick", {}))


# ── APEX Ω research / world-intelligence tools ──
def _apex_route(path: str, *, asset: str = "", as_of: str = "") -> str:
    params = []
    asset = asset.strip().upper()
    as_of = as_of.strip()
    if asset:
        params.append("asset=" + quote(asset, safe=""))
    if as_of:
        params.append("as_of=" + quote(as_of, safe=""))
    return path + (("?" + "&".join(params)) if params else "")


def _apex_json_object(raw: str, label: str) -> tuple[dict | None, dict | None]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as ex:
        return None, {"error": f"{label} is invalid JSON: {ex}"}
    if not isinstance(value, dict):
        return None, {"error": f"{label} must decode to an object"}
    return value, None


@mcp.tool()
def engine_apex_state(asset: str = "", as_of: str = "") -> dict:
    """Read the full APEX Ω research-only world-state snapshot."""
    return _safe_engine(lambda: _engine_get(_apex_route("/api/apex", asset=asset, as_of=as_of)))


@mcp.tool()
def engine_apex_participants(asset: str = "NQ", as_of: str = "") -> dict:
    """Read APEX Ω participant-state reconstruction. Hidden account positions are never claimed as observed."""
    return _safe_engine(lambda: _engine_get(_apex_route("/api/apex/participants", asset=asset, as_of=as_of)))


@mcp.tool()
def engine_apex_crowdhunt(asset: str = "NQ", as_of: str = "") -> dict:
    """Read CROWDHUNT Ω retail crowd/stop/trap reconstruction with explicit uncertainty."""
    return _safe_engine(lambda: _engine_get(_apex_route("/api/apex/crowdhunt", asset=asset, as_of=as_of)))


@mcp.tool()
def engine_apex_forces(asset: str = "NQ", as_of: str = "") -> dict:
    """Read the APEX Ω market-pressure tensor. Opposing forces remain separate contributions."""
    return _safe_engine(lambda: _engine_get(_apex_route("/api/apex/forces", asset=asset, as_of=as_of)))


@mcp.tool()
def engine_apex_cascades(as_of: str = "") -> dict:
    """Read persisted APEX Ω cascade topology."""
    return _safe_engine(lambda: _engine_get(_apex_route("/api/apex/cascades", as_of=as_of)))


@mcp.tool()
def engine_apex_causality(as_of: str = "") -> dict:
    """Read typed APEX Ω causal claims; correlation alone is never promoted to causal proof."""
    return _safe_engine(lambda: _engine_get(_apex_route("/api/apex/causality", as_of=as_of)))


@mcp.tool()
def engine_apex_worlds(as_of: str = "") -> dict:
    """Read durable APEX Ω counterfactual world hypotheses."""
    return _safe_engine(lambda: _engine_get(_apex_route("/api/apex/worlds", as_of=as_of)))


@mcp.tool()
def engine_apex_epistemics(as_of: str = "") -> dict:
    """Read APEX Ω epistemic-kernel health, evidence/belief counts and store integrity."""
    return _safe_engine(lambda: _engine_get(_apex_route("/api/apex/epistemics", as_of=as_of)))


@mcp.tool()
def engine_apex_self(as_of: str = "") -> dict:
    """Read APEX Ω model-health / reality-gap / self-model state."""
    return _safe_engine(lambda: _engine_get(_apex_route("/api/apex/self", as_of=as_of)))


@mcp.tool()
def engine_apex_conscience(as_of: str = "") -> dict:
    """Read persisted independent APEX Ω conscience verdicts."""
    return _safe_engine(lambda: _engine_get(_apex_route("/api/apex/conscience", as_of=as_of)))


@mcp.tool()
def record_engine_apex_evidence(evidence_json: str) -> dict:
    """Persist one provenance-bearing APEX Ω research evidence object. Never authorizes execution."""
    body, error = _apex_json_object(evidence_json, "evidence_json")
    if error:
        return error
    return _safe_engine(lambda: _engine_post("/admin/apex/evidence", body))


@mcp.tool()
def record_engine_apex_outcome(outcome_json: str) -> dict:
    """Persist one APEX Ω research outcome record. Never changes a position or strategy input."""
    body, error = _apex_json_object(outcome_json, "outcome_json")
    if error:
        return error
    return _safe_engine(lambda: _engine_post("/admin/apex/outcome", body))


@mcp.tool()
def record_engine_apex_model_observation(observation_json: str) -> dict:
    """Persist one APEX Ω model/reality-gap observation for research credibility accounting."""
    body, error = _apex_json_object(observation_json, "observation_json")
    if error:
        return error
    return _safe_engine(lambda: _engine_post("/admin/apex/model-observation", body))


@mcp.tool()
def propose_engine_apex_experiment(experiment_json: str) -> dict:
    """Record/evaluate an APEX Ω research experiment proposal. This cannot deploy a model."""
    body, error = _apex_json_object(experiment_json, "experiment_json")
    if error:
        return error
    return _safe_engine(lambda: _engine_post("/admin/apex/experiment", body))

@mcp.tool()
def engine_performance_proof() -> dict:
    """Read causal forecast/outcome/replay proof, calibration and closed-sample metrics."""
    return _safe_engine(lambda: _engine_get("/api/performance-proof"))


@mcp.tool()
def engine_pending_performance_settlements(limit: int = 100, as_of: str = "") -> dict:
    """Read matured forecasts that still require an observed immutable outcome."""
    bounded = max(1, min(1000, int(limit)))
    return _safe_engine(lambda: _engine_get(
        "/api/performance-proof/pending",
        limit=bounded,
        as_of=as_of.strip() or None,
    ))


@mcp.tool()
def record_engine_performance_forecast(
    candidate_id: str,
    asset: str,
    regime: str,
    decision_at: str,
    matures_at: str,
    probability_success: float,
    success_definition: str,
    source_repo: str,
    source_commit: str,
    dataset_hash: str,
    evidence_hash: str,
) -> dict:
    """Record one immutable research/shadow forecast before its outcome matures."""
    return _safe_engine(lambda: _engine_post("/admin/performance-proof/forecast", {
        "candidate_id": candidate_id,
        "asset": asset,
        "regime": regime,
        "decision_at": decision_at,
        "matures_at": matures_at,
        "probability_success": float(probability_success),
        "success_definition": success_definition,
        "source_repo": source_repo,
        "source_commit": source_commit,
        "dataset_hash": dataset_hash,
        "evidence_hash": evidence_hash,
    }))


@mcp.tool()
def record_engine_performance_outcome(
    forecast_id: str,
    observed_at: str,
    success: bool,
    outcome_hash: str,
    source: str,
    realized_value: Optional[float] = None,
) -> dict:
    """Settle one matured proof forecast exactly once; conflicting rewrites fail closed."""
    return _safe_engine(lambda: _engine_post("/admin/performance-proof/outcome", {
        "forecast_id": forecast_id,
        "observed_at": observed_at,
        "success": bool(success),
        "realized_value": realized_value,
        "outcome_hash": outcome_hash,
        "source": source,
    }))


@mcp.tool()
def record_engine_replay_proof(
    subject: str,
    source_commit: str,
    input_hash: str,
    first_output_hash: str,
    second_output_hash: str,
    observed_at: str,
) -> dict:
    """Record a deterministic replay comparison for one exact input and source revision."""
    return _safe_engine(lambda: _engine_post("/admin/performance-proof/replay", {
        "subject": subject,
        "source_commit": source_commit,
        "input_hash": input_hash,
        "first_output_hash": first_output_hash,
        "second_output_hash": second_output_hash,
        "observed_at": observed_at,
    }))


@mcp.tool()
def engine_latency_telemetry() -> dict:
    """Read measured ICARUS processing latency percentiles and budget status."""
    return _safe_engine(lambda: _engine_get("/api/latency"))


@mcp.tool()
def engine_possibility_state(asset: str = "NQ") -> dict:
    """Read ICARUS Ψ latent-pressure, possibility-space and information-wave diagnostics."""
    asset = asset.strip().upper()
    return _safe_engine(lambda: _engine_get(f"/api/possibility?asset={asset}"))

@mcp.tool()
def engine_possibility_evidence(
    asset: str = "NQ",
    limit: int = 100,
    include_expired: bool = False,
    as_of: str = "",
) -> dict:
    """Read the durable ICARUS Ψ evidence ledger and causal active as-of selection."""
    from urllib.parse import quote
    asset = asset.strip().upper()
    limit = max(1, min(1000, int(limit)))
    query = f"/api/possibility/evidence?asset={asset}&limit={limit}&include_expired={'true' if include_expired else 'false'}"
    if as_of.strip():
        query += "&as_of=" + quote(as_of.strip(), safe="")
    return _safe_engine(lambda: _engine_get(query))


@mcp.tool()
def record_engine_possibility_evidence(
    asset: str,
    source: str,
    values_json: str,
    observed_at: str = "",
    ttl_seconds: float = 300.0,
) -> dict:
    """Publish provenance-labelled optional force evidence to ICARUS Ψ.

    Supported force names are validated by the engine. This is research/shadow
    evidence only and cannot authorize a trade or production decision.
    """
    try:
        values = json.loads(values_json or "{}")
    except json.JSONDecodeError as ex:
        return {"error": f"values_json is invalid JSON: {ex}"}
    if not isinstance(values, dict):
        return {"error": "values_json must decode to an object"}
    body: Dict[str, Any] = {
        "asset": asset.strip().upper(),
        "source": source.strip(),
        "values": values,
        "ttl_seconds": float(ttl_seconds),
    }
    if observed_at.strip():
        body["observed_at"] = observed_at.strip()
    return _safe_engine(lambda: _engine_post("/admin/possibility/evidence", body))


@mcp.tool()
def engine_parallax_state() -> dict:
    """Read the shadow-only PARALLAX decision/branch/ablation ledger."""
    return _safe_engine(lambda: _engine_get("/api/parallax"))


@mcp.tool()
def engine_dreamstate_state() -> dict:
    """Read DREAMSTATE hypothesis state derived from observed PARALLAX evidence."""
    return _safe_engine(lambda: _engine_get("/api/dreamstate"))


@mcp.tool()
def record_current_parallax_decision_with_psi(
    asset: str,
    action: str,
    regime: str = "unknown",
    context_json: str = "{}",
    subsystem_votes_json: str = "{}",
    branches_json: str = "",
    decision_id: str = "",
    source_commit: str = "",
) -> dict:
    """Atomically capture the current Psi vote and record a causal PARALLAX decision."""
    try:
        context = json.loads(context_json or "{}")
        votes = json.loads(subsystem_votes_json or "{}")
        branches = json.loads(branches_json) if branches_json.strip() else None
    except json.JSONDecodeError as ex:
        return {"error": f"invalid JSON argument: {ex}"}
    if not isinstance(context, dict) or not isinstance(votes, dict):
        return {"error": "context_json and subsystem_votes_json must decode to objects"}
    if "psi" in votes:
        return {"error": "psi vote is captured atomically by the engine; omit it"}
    if branches is not None and not isinstance(branches, list):
        return {"error": "branches_json must decode to a list"}
    if source_commit.strip():
        source_sha = source_commit.strip().lower()
        if len(source_sha) != 40 or any(ch not in "0123456789abcdef" for ch in source_sha):
            return {"error": "source_commit must be an exact 40-character hexadecimal git SHA"}
    body: Dict[str, Any] = {
        "asset": asset.strip().upper(),
        "action": action.strip().lower(),
        "regime": regime.strip() or "unknown",
        "context": context,
        "subsystem_votes": votes,
    }
    if branches is not None:
        body["branches"] = branches
    if decision_id.strip():
        body["decision_id"] = decision_id.strip()
    if source_commit.strip():
        body["source_commit"] = source_sha
    return _safe_engine(lambda: _engine_post("/admin/parallax/decision/current", body))


@mcp.tool()
def record_engine_parallax_outcome(
    decision_id: str,
    label: str,
    utility: float,
    metrics_json: str = "{}",
    evidence_json: str = "[]",
    observed_at: str = "",
) -> dict:
    """Record one actually observed PARALLAX branch outcome; never infer an unobserved branch."""
    try:
        metrics = json.loads(metrics_json or "{}")
        evidence = json.loads(evidence_json or "[]")
    except json.JSONDecodeError as ex:
        return {"error": f"invalid JSON argument: {ex}"}
    if not isinstance(metrics, dict) or not isinstance(evidence, list):
        return {"error": "metrics_json must be an object and evidence_json a list"}
    body: Dict[str, Any] = {
        "decision_id": decision_id.strip(),
        "label": label.strip().lower(),
        "utility": float(utility),
        "metrics": metrics,
        "evidence": evidence,
    }
    if observed_at.strip():
        body["observed_at"] = observed_at.strip()
    return _safe_engine(lambda: _engine_post("/admin/parallax/outcome", body))


@mcp.tool()
def refresh_engine_dreamstate(min_samples: int = 5) -> dict:
    """Re-screen DREAMSTATE hypotheses from observed PARALLAX outcomes."""
    return _safe_engine(lambda: _engine_post("/admin/dreamstate/refresh", {"min_samples": int(min_samples)}))


@mcp.tool()
def record_historical_parallax_decision(
    asset: str,
    action: str,
    observed_at: str,
    source_commit: str,
    regime: str = "unknown",
    context_json: str = "{}",
    subsystem_votes_json: str = "{}",
    branches_json: str = "",
    decision_id: str = "",
) -> dict:
    """Record a historical PARALLAX decision with already-captured causal votes.

    No current Psi snapshot is injected into this route.
    """
    try:
        context = json.loads(context_json or "{}")
        votes = json.loads(subsystem_votes_json or "{}")
        branches = json.loads(branches_json) if branches_json.strip() else None
    except json.JSONDecodeError as ex:
        return {"error": f"invalid JSON argument: {ex}"}
    if not isinstance(context, dict) or not isinstance(votes, dict):
        return {"error": "context_json and subsystem_votes_json must decode to objects"}
    if branches is not None and not isinstance(branches, list):
        return {"error": "branches_json must decode to a list"}
    if not observed_at.strip():
        return {"error": "observed_at is required for historical PARALLAX decisions"}
    source_sha = source_commit.strip().lower()
    if len(source_sha) != 40 or any(ch not in "0123456789abcdef" for ch in source_sha):
        return {"error": "source_commit must be an exact 40-character hexadecimal git SHA"}
    body: Dict[str, Any] = {
        "asset": asset.strip().upper(),
        "action": action.strip().lower(),
        "regime": regime.strip() or "unknown",
        "observed_at": observed_at.strip(),
        "source_commit": source_sha,
        "context": context,
        "subsystem_votes": votes,
    }
    if branches is not None:
        body["branches"] = branches
    if decision_id.strip():
        body["decision_id"] = decision_id.strip()
    return _safe_engine(lambda: _engine_post("/admin/parallax/decision", body))


@mcp.tool()
def evaluate_engine_dreamstate_candidate(
    candidate_id: str,
    validation_json: str,
    evidence_json: str = "[]",
) -> dict:
    """Apply explicit validation-gate results to a DREAMSTATE research candidate."""
    try:
        validation = json.loads(validation_json or "{}")
        evidence = json.loads(evidence_json or "[]")
    except json.JSONDecodeError as ex:
        return {"error": f"invalid JSON argument: {ex}"}
    if not isinstance(validation, dict) or not validation:
        return {"error": "validation_json must decode to a non-empty object"}
    if not isinstance(evidence, list):
        return {"error": "evidence_json must decode to a list"}
    candidate_id = candidate_id.strip()
    if not candidate_id:
        return {"error": "candidate_id is required"}
    return _safe_engine(lambda: _engine_post("/admin/dreamstate/evaluate", {
        "candidate_id": candidate_id,
        "validation": validation,
        "evidence": evidence,
    }))


@mcp.tool()
def retire_engine_dreamstate_candidate(candidate_id: str, reason: str) -> dict:
    """Retire a DREAMSTATE research candidate with an explicit evidence reason."""
    candidate_id = candidate_id.strip()
    reason = reason.strip()
    if not candidate_id:
        return {"error": "candidate_id is required"}
    if not reason:
        return {"error": "reason is required"}
    return _safe_engine(lambda: _engine_post("/admin/dreamstate/retire", {
        "candidate_id": candidate_id,
        "reason": reason,
    }))


# ── control tools (state-changing) ──
@mcp.tool()
def pause_trading(reason: str = "paused via MCP") -> dict:
    """Stop acting on new alerts (they are still journaled). Existing positions/stops are untouched."""
    return _safe(lambda: _post("/admin/pause", {"reason": reason}))


@mcp.tool()
def resume_trading() -> dict:
    """Resume acting on alerts after a pause (manual or daily-loss breaker)."""
    return _safe(lambda: _post("/admin/resume"))


@mcp.tool()
def flatten_all(confirm: bool = False, reason: str = "flatten via MCP") -> dict:
    """EMERGENCY: cancel every open order and close every paper position. Requires confirm=true."""
    if not confirm:
        return {"error": "refused: call again with confirm=true"}
    return _safe(lambda: _post("/admin/flatten", {"confirm": True, "reason": reason}))


@mcp.tool()
def simulate_alert(side: str = "long", contracts: float = 5, position_after: Optional[float] = None,
                   ticker: str = "NQ1!", order_price: float = 20000.0, order_id: str = "", comment: str = "",
                   system: str = "RATE", tp1: float = 15, tp2: float = 30, sl: float = 45, q1: float = 2, q2: float = 3,
                   raw_json: str = "") -> dict:
    """Inject a synthetic TradingView order-fill alert into the pipeline (bypasses the webhook secret).
    Either pass raw_json (exactly what TradingView would send) or describe the fill:
      side=long/short, contracts=fill size, position_after=signed position AFTER the fill (default = ±contracts).
    In shadow mode nothing leaves the machine; in mirror/bracket mode this places REAL paper orders."""
    if raw_json.strip():
        return _safe(lambda: _post("/admin/simulate", raw=raw_json))
    pos = position_after if position_after is not None else (contracts if side == "long" else -contracts)
    mp = "flat" if abs(pos) < 1e-9 else ("long" if pos > 0 else "short")
    payload = {
        "event": "order_fill", "ticker": ticker, "action": "buy" if side == "long" else "sell",
        "contracts": str(contracts), "order_id": order_id or ("Long" if side == "long" else "Short"),
        "comment": comment, "order_price": str(order_price), "position_size": str(abs(pos)),
        "market_position": mp, "prev_market_position": "flat" if abs(pos) >= abs(contracts) - 1e-9 else mp,
        "bar_close": str(order_price), "time": "simulated",
        "meta": f"sys={system};side={side};tp1={tp1};tp2={tp2};sl={sl};q1={q1};q2={q2};ref={order_price}",
    }
    return _safe(lambda: _post("/admin/simulate", raw=json.dumps(payload)))


@mcp.tool()
def set_state(key: str, value: str) -> dict:
    """Write a runtime state key in the bridge journal (e.g. notes). 'paused' is reserved — use pause/resume."""
    try:
        val: Any = json.loads(value)
    except json.JSONDecodeError:
        val = value
    return _safe(lambda: _post("/admin/state", {"key": key, "value": val}))


@mcp.resource("icarus://status")
def status_resource() -> str:
    """Live bridge status as JSON."""
    return json.dumps(_safe(lambda: _get("/status")), indent=2, default=str)


def main() -> None:
    mcp.run()   # stdio transport


if __name__ == "__main__":
    main()
