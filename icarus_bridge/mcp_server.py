"""MCP (stdio) control surface for the running bridge.

Register with Claude Code:
  claude mcp add icarus-bridge -e ICARUS_BRIDGE_URL=http://127.0.0.1:8787 -e ICARUS_ADMIN_TOKEN=<token> -- <python> -m icarus_bridge.mcp_server

Every tool is a thin call to the bridge's admin API, so the daemon stays the
single source of truth and Claude can never race the webhook thread.
"""
from __future__ import annotations

import json
import os
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
        "results. pause_trading / resume_trading / flatten_all / simulate_alert change live paper state — "
        "confirm with the user before calling them unless they asked for exactly that action."
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
    """Latest local GitHub/MCP repository + CI audit snapshot, including the System-panel evolution ledger."""
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
def engine_system_evolution() -> dict:
    """Important MCP repairs, audits, integrations and subsystem evolutions mirrored in the ICARUS System panel."""
    return _safe_engine(lambda: _engine_get("/api/system/evolution"))


@mcp.tool()
def record_engine_system_evolution(evolution_json: str) -> dict:
    """Persist the MCP evolution ledger rendered by the ICARUS System panel.

    This writes diagnostic/provenance state only. It cannot change assets, timeframes,
    strategy inputs, broker state, positions, orders, or production authority.
    """
    try:
        evolution = json.loads(evolution_json)
    except json.JSONDecodeError as ex:
        return {"error": f"evolution_json is invalid JSON: {ex}"}
    if not isinstance(evolution, dict):
        return {"error": "evolution_json must decode to an object"}
    return _safe_engine(lambda: _engine_post("/admin/system/evolution", {"evolution": evolution}))


@mcp.tool()
def record_engine_system_evolution_item(item_json: str) -> dict:
    """Add or update one important MCP repair/audit/evolution in the ICARUS System panel.

    This additive path preserves all sibling items already in the ledger. It is the
    preferred mirror path after an MCP repair or validation milestone.
    """
    try:
        item = json.loads(item_json)
    except json.JSONDecodeError as ex:
        return {"error": f"item_json is invalid JSON: {ex}"}
    if not isinstance(item, dict):
        return {"error": "item_json must decode to an object"}
    return _safe_engine(lambda: _engine_post("/admin/system/evolution/item", {"item": item}))


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
