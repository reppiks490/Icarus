"""Dashboard + JSON API for the engine (standard library only).

  GET  /                          dashboard (open /?asset=NQ for a single-asset tab)
  GET  /status/public             portfolio + every asset's strategy state
  GET  /api/chart/<SYM>?n=240     bars, overlays (RATE line, TP/SL, VWAP, Kalman), fills
  GET  /api/trades/<SYM>          closed trades (this run: history + live)
  GET  /api/inputs/<SYM>          effective inputs, their sources, and per-input metadata
  GET  /api/input-meta            every input: label, group, kind, default, range, options, tooltip
  GET  /api/presets               presets/*.json (name + _meta)
  GET  /api/assets                asset registry (what can be added)
  GET  /api/commands              the command list the dashboard palette renders
  GET  /api/export/<SYM>.csv      the asset's trade list as CSV
  GET  /api/golive                paper≠live integrity (Grok). Never arms a broker.
  GET  /api/agent                 Field Agent recipes + paste-packs (Grok). Never executes. Never arms a broker.
  GET  /api/system/audit          latest local GitHub/MCP repository + CI audit snapshot
  GET  /api/integrity             export checklist, corpus, repairs, and MCP change receipts
  POST /admin/pause | /admin/resume        {"asset": "NQ"} or all          (Bearer token)
  POST /admin/flatten                      {"confirm": true, "asset"?: "NQ"}
  POST /admin/inputs                       {"asset": "NQ"|"*", "values": {...}, "chart": {...}, "persist": true}  → re-warm
  POST /admin/inputs/reset                 {"asset": "NQ"}  (deletes inputs.<SYM>.json, re-warm)
  POST /admin/preset                       {"asset": "NQ", "preset": "NQ-10m-original"|null}
  POST /admin/assets/add                   {"symbol": "GC", "tf": "20", "preset"?: ...}
  POST /admin/assets/remove                {"symbol": "GC"}
  POST /admin/system/audit                 {"audit": {...}}  local diagnostic state only; never changes trading
  POST /admin/system/event                 {"event": {...}}  append important MCP repair/audit/evolution event
  POST /admin/system/loop                  {"loop": {...}}   upsert one loop durability receipt/status
  POST /admin/integrity/event              fully-provenanced, idempotent MCP audit receipt; never changes trading
  POST /admin/rewarm                       {"asset": "NQ"}
"""
from __future__ import annotations

import hmac
import json
import os
import re
import sys
import time
import threading
from contextlib import ExitStack
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from . import brand
from .assets import REGISTRY, apply_chart_config, chart_capabilities, parse_spec, pin_config, resolve, validate_chart_config
from .backtest import JOBS, start_job
from .parity import compare_lists, engine_trades_from_rows, read_tv_trades_text
from .golive import report as golive_report
from .agent import report as agent_report
from .briefing import report as briefing_report
from .runtime import Portfolio, _clean, _read_json, apply_spec_meta, preset_path
from .strategy.meta import load_meta
from .advisory import MAX_BODY_BYTES, strict_json
from .research_service import ResearchWorkspace
from .system_audit import (
    LoopIntelligenceSync,
    append_system_event,
    load_repository_audit,
    save_repository_audit,
    upsert_loop_status,
)
from .integrity import integrity_snapshot, record_integrity_event


def _no_json_constants(name: str):
    raise ValueError(f"{name} is not allowed")


def _json_default(obj: Any) -> Any:
    item = getattr(obj, "item", None)
    if callable(item):
        try:
            obj = item()
        except Exception:
            return str(obj)
    if isinstance(obj, float):
        return None if obj != obj or obj in (float("inf"), float("-inf")) else obj
    return str(obj)


def dumps_safe(obj: Any) -> bytes:
    """Never raise. Empty reply is what made the dashboard say ENGINE UNREACHABLE."""
    try:
        return json.dumps(_clean(obj), allow_nan=False, default=_json_default).encode("utf-8")
    except Exception as ex:
        sys.stderr.write(f"icarus json dump failed: {type(ex).__name__}: {ex}\n")
        return json.dumps({"ok": False, "detail": f"json: {type(ex).__name__}: {ex}"}).encode("utf-8")


def _reason(body: Dict[str, Any], default: str = "manual") -> str:
    """Free text that ends up in the journal: printable, short."""
    return re.sub(r"[^\w .:()/-]", "", str(body.get("reason", default)))[:40] or default

COMMANDS = [
    {"id": "backtest", "label": "Backtest (Strategy Tester)", "desc": "Run the strategy on the cached bars with any preset / inputs / fill mode and read TradingView's Strategy Tester numbers.", "scope": "asset", "danger": False},
    {"id": "pause", "label": "Pause entries", "desc": "No new entries on the selected asset (or all). Exits keep running.", "scope": "asset|all", "danger": False},
    {"id": "resume", "label": "Resume entries", "desc": "Lift a pause.", "scope": "asset|all", "danger": False},
    {"id": "flatten", "label": "Flatten", "desc": "Close every open paper position now, at the last price.", "scope": "asset|all", "danger": True},
    {"id": "rewarm", "label": "Re-warm", "desc": "Rebuild the asset's engine from the cached history (after editing inputs).", "scope": "asset", "danger": False},
    {"id": "inputs", "label": "Edit inputs", "desc": "Open the Inputs tab for the asset.", "scope": "asset", "danger": False},
    {"id": "preset", "label": "Apply preset", "desc": "Load one of the presets/ configurations onto the asset and re-warm.", "scope": "asset", "danger": False},
    {"id": "reset-inputs", "label": "Reset asset overrides", "desc": "Delete inputs.<SYM>.json so the asset falls back to the preset.", "scope": "asset", "danger": True},
    {"id": "add-asset", "label": "Add asset", "desc": "Start a new asset (NQ ES YM GC SI PL PA BTCF MBT BTC ETH SOL …).", "scope": "all", "danger": False},
    {"id": "remove-asset", "label": "Remove asset", "desc": "Stop and drop an asset from the engine.", "scope": "asset", "danger": True},
    {"id": "export", "label": "Export trades CSV", "desc": "Download the asset's trade list (TradingView-like columns).", "scope": "asset", "danger": False},
    {"id": "open-tab", "label": "Open in its own tab", "desc": "Full-screen view of one asset in a new browser tab.", "scope": "asset", "danger": False},
    {"id": "golive", "label": "Go-live integrity", "desc": "Paper ≠ live. Tape identity, warmup P&L, RTH, QQQ≠NQ. Never arms a broker.", "scope": "all", "danger": False},
    {"id": "agent", "label": "Field Agent", "desc": "Copy plant recipes and Claude/ChatGPT paste-packs. Does not execute. Never arms a broker.", "scope": "all", "danger": False},
]


def serve(port: Portfolio, http_port: int = 8791, token: str = "icarus", start: bool = True):
    html_path = Path(__file__).parent / "dashboard.html"
    meta = load_meta()
    research = ResearchWorkspace(port)
    loop_intelligence_sync = LoopIntelligenceSync(port.base_dir)

    class H(BaseHTTPRequestHandler):
        server_version = "icarus"
        sys_version = ""
        timeout = 30                                              # idle connections must not hold a thread forever

        def log_message(self, *a: Any) -> None:  # quiet
            pass

        def _send(self, code: int, body: bytes, ctype: str = "application/json", extra: Dict[str, str] | None = None) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text") else ""))
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-src https://www.youtube-nocookie.com; frame-ancestors 'none'")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj: Any) -> None:
            self._send(code, dumps_safe(obj))

        def _host_ok(self) -> bool:
            """Loopback only: a DNS-rebinding page carries its own hostname in Host."""
            host = self.headers.get("Host", "").rsplit(":", 1)[0].strip("[]").lower()
            return host in ("127.0.0.1", "localhost", "::1")

        def _auth(self) -> bool:
            scheme, _, tok = self.headers.get("Authorization", "").partition(" ")
            return bool(token) and scheme.lower() == "bearer" and hmac.compare_digest(tok, token)

        def _int(self, q: Dict[str, Any], key: str, default: int, lo: int, hi: int) -> int:
            try:
                return max(lo, min(hi, int(q.get(key, [default])[0])))
            except (TypeError, ValueError):
                return default

        def _runner(self, sym: str):
            try:
                key = resolve(sym or "").symbol
            except ValueError:
                return None
            return port.runners.get(key)

        def do_GET(self) -> None:  # noqa: N802
            if not self._host_ok():
                return self._json(403, {"detail": "bad host"})
            p = urlparse(self.path)
            q = parse_qs(p.query)
            if p.path == "/":
                return self._send(200, brand.render(html_path.read_bytes()), "text/html")
            if p.path == "/research-ui.js":
                return self._send(200, (html_path.parent / "research-ui.js").read_bytes(), "text/javascript")
            if p.path == "/sources-ui.js":
                return self._send(200, (html_path.parent / "sources-ui.js").read_bytes(), "text/javascript")
            if p.path == "/integrity-ui.js":
                return self._send(200, (html_path.parent / "integrity-ui.js").read_bytes(), "text/javascript")
            if p.path in ("/experience-ui.js", "/experience-ui.css"):
                ctype = "text/javascript" if p.path.endswith(".js") else "text/css"
                return self._send(200, (html_path.parent / p.path[1:]).read_bytes(), ctype)
            if p.path == "/healthz":
                return self._json(200, {"ok": True, "assets": list(port.order), "warm": all(r.warm for r in port.runners.values()) if port.runners else False})
            if p.path == "/status/public":
                try:
                    return self._json(200, port.status())
                except Exception as ex:
                    sys.stderr.write(f"status/public failed: {type(ex).__name__}: {ex}\n")
                    return self._json(500, {"ok": False, "detail": f"{type(ex).__name__}: {ex}", "assets": []})
            if p.path == "/api/golive":
                return self._json(200, golive_report(port))
            if p.path == "/api/agent":
                return self._json(200, agent_report())
            if p.path == "/api/briefing":
                return self._json(200, briefing_report())
            if p.path == "/api/system/audit":
                return self._json(200, load_repository_audit(port.base_dir))
            if p.path == "/api/integrity":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                return self._json(200, integrity_snapshot(port.base_dir))
            if p.path == "/api/input-meta":
                return self._json(200, meta)
            if p.path.startswith("/api/research"):
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                try:
                    if p.path == "/api/research":
                        return self._json(200, research.status())
                    if p.path == "/api/research/adaptation":
                        return self._json(200, research.adaptation.status())
                    if p.path == "/api/research/source-watch":
                        return self._json(200, research.source_watch.status())
                    if p.path == "/api/research/events":
                        return self._json(200, research.events(q.get("asset", [""])[0]))
                    if p.path == "/api/research/analysis":
                        return self._json(200, research.analysis.status())
                    if p.path.startswith("/api/research/analysis/"):
                        return self._json(200, research.analysis.job(p.path.rsplit("/", 1)[1]))
                    if p.path == "/api/research/activation":
                        return self._json(200, research.activation.status())
                    if p.path == "/api/research/sources":
                        return self._json(200, research.market_sources.status())
                    if p.path == "/api/research/records":
                        return self._json(200, research.market_sources.records(kind=q.get("kind", ["asset"])[0],
                            asset=q.get("asset", [None])[0], cik=q.get("cik", [None])[0],
                            limit=int(q.get("limit", ["100"])[0])))
                    if p.path.startswith("/api/research/jobs/"):
                        return self._json(200, research.job(p.path.rsplit("/", 1)[1]))
                    if p.path.startswith("/api/research/proposals/"):
                        return self._json(200, research.ledger.get_proposal(p.path.rsplit("/", 1)[1]))
                except (ValueError, TypeError, KeyError) as ex:
                    return self._json(400, {"detail": str(ex)})
                return self._json(404, {"detail": "unknown research resource"})
            if p.path == "/api/presets":
                out = []
                pdir = os.path.join(port.base_dir, "presets")
                if os.path.isdir(pdir):
                    for f in sorted(os.listdir(pdir)):
                        if f.endswith(".json"):
                            d = _read_json(os.path.join(pdir, f))
                            out.append({"name": f[:-5], "meta": d.get("_meta", {}), "count": len([k for k in d if not k.startswith("_")])})
                return self._json(200, out)
            if p.path == "/api/assets":
                return self._json(200, {"registry": [{
                                            "symbol": s.symbol, "name": s.name, "feed": s.feed, "calendar": s.calendar,
                                            "mintick": s.mintick, "multiplier": s.multiplier, "kind": s.kind,
                                            "continuous_symbol": s.tv_symbol if s.kind == "futures" else None,
                                            "provider_symbol": s.ticker,
                                            "contract_policy": "continuous_only" if s.kind == "futures" else "not_applicable",
                                        } for s in REGISTRY.values()],
                                        "running": list(port.order), "chart_capabilities": chart_capabilities()})
            if p.path == "/api/commands":
                return self._json(200, COMMANDS)
            if p.path.startswith("/api/export/"):
                r = self._runner(p.path.rsplit("/", 1)[1].replace(".csv", ""))
                if not r:
                    return self._json(404, {"error": "unknown asset"})
                return self._send(200, r.export_csv().encode("utf-8"), "text/csv", {"Content-Disposition": f'attachment; filename="{r.symbol}_trades.csv"'})
            if p.path.startswith("/api/chart/"):
                r = self._runner(p.path.rsplit("/", 1)[1])
                if not r:
                    return self._json(404, {"error": "unknown asset"})
                return self._json(200, r.chart(self._int(q, "n", 240, 20, 800)))
            if p.path.startswith("/api/trades/"):
                r = self._runner(p.path.rsplit("/", 1)[1])
                if not r:
                    return self._json(404, {"error": "unknown asset"})
                return self._json(200, r.trades(self._int(q, "limit", 100, 1, 2000)))
            if p.path.startswith("/api/market-data/"):
                rest = p.path[len("/api/market-data/"):]
                parts = [x for x in rest.split("/") if x]
                if len(parts) != 2:
                    return self._json(404, {"error": "market-data route is /api/market-data/<asset>/<capabilities|ticks|depth>"})
                r = self._runner(parts[0])
                if not r:
                    return self._json(404, {"error": "unknown asset"})
                kind = parts[1]
                feed = r.feed
                if kind == "capabilities":
                    caps = feed.capabilities() if hasattr(feed, "capabilities") else {}
                    metadata = feed.meta(r.spec.ticker) if hasattr(feed, "meta") else {}
                    return self._json(200, {"asset": r.symbol, "provider": type(feed).__name__.lower(),
                                            "capabilities": caps, "metadata": metadata})
                if kind == "ticks":
                    if not hasattr(feed, "trades"):
                        return self._json(409, {"error": f"{type(feed).__name__} does not expose trade ticks"})
                    limit = self._int(q, "limit", 1000, 1, 10000)
                    since = self._int(q, "since_ts", 0, 0, 4_294_967_295)
                    try:
                        rows = feed.trades(r.spec.ticker, since_ts=(since or None), limit=limit)
                    except ValueError as ex:
                        return self._json(400, {"error": str(ex)})
                    except Exception as ex:
                        port.journal.log("WARN", f"market-data ticks {r.symbol}: {type(ex).__name__}: {ex}")
                        return self._json(502, {"error": f"{type(ex).__name__}: {ex}"})
                    return self._json(200, {"asset": r.symbol, "provider": type(feed).__name__.lower(),
                                            "ticks": [vars(x) if hasattr(x, "__dict__") else x for x in rows]})
                if kind == "depth":
                    if not hasattr(feed, "depth_events"):
                        return self._json(409, {"error": f"{type(feed).__name__} does not expose order-book depth"})
                    schema = str(q.get("schema", ["mbp-10"])[0]).strip().lower()
                    if schema not in ("mbp-10", "mbo"):
                        return self._json(400, {"error": "schema must be mbp-10 or mbo"})
                    limit = self._int(q, "limit", 1000, 1, 10000)
                    try:
                        rows = feed.depth_events(r.spec.ticker, schema=schema, limit=limit)
                    except ValueError as ex:
                        return self._json(400, {"error": str(ex)})
                    except Exception as ex:
                        port.journal.log("WARN", f"market-data depth {r.symbol}: {type(ex).__name__}: {ex}")
                        return self._json(502, {"error": f"{type(ex).__name__}: {ex}"})
                    return self._json(200, {"asset": r.symbol, "provider": type(feed).__name__.lower(),
                                            "schema": schema, "events": rows})
                return self._json(404, {"error": "unknown market-data resource"})
            if p.path.startswith("/api/backtest/"):
                rest = p.path[len("/api/backtest/"):]
                job_id, _, tail = rest.partition("/")
                job = JOBS.get(job_id)
                if not job:
                    return self._json(404, {"error": "unknown backtest job"})
                if tail == "trades.csv":
                    if job["status"] != "done":
                        return self._json(409, {"error": "not finished"})
                    return self._send(200, job["result"]["csv"].encode("utf-8"), "text/csv",
                                      {"Content-Disposition": f'attachment; filename="backtest_{job["result"]["asset"]}_{job_id}.csv"'})
                out = {k: job[k] for k in ("id", "status", "progress", "started", "params", "error")}
                out["finished"] = job.get("finished")
                if job["status"] == "done" and q.get("full", ["1"])[0] != "0":
                    out["result"] = {k: v for k, v in job["result"].items() if k != "csv"}
                return self._json(200, out)
            if p.path.startswith("/api/inputs/"):
                r = self._runner(p.path.rsplit("/", 1)[1])
                if not r:
                    return self._json(404, {"error": "unknown asset"})
                over = _read_json(os.path.join(port.base_dir, f"inputs.{r.symbol}.json"))
                return self._json(200, {"asset": r.symbol, "effective": r.inputs.to_dict(), "base": r.inputs_base.to_dict(), "sources": r.cfg.sources,
                                        "overrides": {k: v for k, v in over.items() if not k.startswith("_")}, "preset": r.cfg.preset, "pts_scale": r.pts_scale,
                                        "instrument": {
                                            "kind": r.spec.kind,
                                            "continuous_symbol": r.spec.tv_symbol if r.spec.kind == "futures" else None,
                                            "provider_symbol": r.spec.ticker,
                                            "contract_policy": "continuous_only" if r.spec.kind == "futures" else "not_applicable",
                                        },
                                        "chart": {"timeframe": r.spec.chart_tf, "chart_type": r.spec.chart_type,
                                                  "fill_on": r.spec.fill_on, "security_source": r.spec.security_source},
                                        "chart_capabilities": r.chart_capability_view()})
            self._json(404, {"error": "not found"})

        def _drain_body(self) -> None:
            # Claude (Opus 5.5) 2026-09-27. Answering before the body is read and then closing makes the OS reset
            # the connection, and the client can lose the answer (WinError 10053, 3 in 500 requests). Every early
            # POST rejection discards the body unparsed; never more than MAX_BODY_BYTES, bounded by the timeout.
            try:
                n = int(self.headers.get("Content-Length", "0") or 0)
            except ValueError:
                return
            if 0 < n <= MAX_BODY_BYTES and not self.headers.get("Transfer-Encoding"):
                self.rfile.read(n)

        def do_POST(self) -> None:  # noqa: N802
            if not self._host_ok():
                self._drain_body()
                return self._json(403, {"detail": "bad host"})
            p = urlparse(self.path)
            if p.path == "/research/events":
                secret = os.environ.get("ICARUS_INGEST_SECRET", "")
                if not secret:
                    self._drain_body()
                    return self._json(503, {"detail": "event receiver is not configured"})
                if not self.headers.get("X-Icarus-Signature") or not self.headers.get("X-Icarus-Timestamp"):
                    self._drain_body()
                    return self._json(401, {"detail": "signed event required"})
                try:
                    n = int(self.headers.get("Content-Length", "0"))
                    if not 0 < n <= MAX_BODY_BYTES or self.headers.get("Transfer-Encoding"):
                        return self._json(413, {"detail": "invalid event body length"})
                    event = research.ledger.ingest_signed_event(self.rfile.read(n), self.headers["X-Icarus-Timestamp"],
                                                                self.headers["X-Icarus-Signature"], secret)
                    return self._json(200, {"ok": True, "event_id": event["event_id"], "execution_authorized": False})
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if not p.path.startswith("/admin/"):
                self._drain_body()
                return self._json(404, {"error": "not found"})
            if not self._auth():                                  # authenticate BEFORE parsing any body
                self._drain_body()                                # discard it unread, or the 401 can be lost
                return self._json(401, {"detail": "bad admin token"})
            try:
                n = int(self.headers.get("Content-Length", "0") or 0)
            except ValueError:
                return self._json(400, {"detail": "bad Content-Length"})
            if n < 0 or n > (1 << 20):
                return self._json(413, {"detail": "body too large"})
            raw = self.rfile.read(n) if n else b""
            try:
                body = strict_json(raw) if p.path.startswith(("/admin/research/", "/admin/integrity/")) else (json.loads(raw, parse_constant=_no_json_constants) if raw else {})
            except ValueError as ex:
                return self._json(400, {"detail": f"bad JSON body: {ex}"})
            if not isinstance(body, dict):
                return self._json(400, {"detail": "JSON body must be an object"})
            if p.path == "/admin/system/audit":
                try:
                    audit = save_repository_audit(port.base_dir, body.get("audit", body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                return self._json(200, {"ok": True, "audit": audit, "note": "system intelligence snapshot recorded"})
            if p.path == "/admin/system/event":
                try:
                    audit = append_system_event(port.base_dir, body.get("event", body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                return self._json(200, {"ok": True, "audit": audit, "note": "system intelligence event recorded"})
            if p.path == "/admin/system/loop":
                try:
                    audit = upsert_loop_status(port.base_dir, body.get("loop", body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                return self._json(200, {"ok": True, "audit": audit, "note": "loop status recorded"})
            if p.path == "/admin/integrity/event":
                try:
                    return self._json(200, record_integrity_event(port.base_dir, body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            asset = str(body.get("asset") or body.get("symbol") or "").upper()
            # Add is the one admin route whose subject is intentionally not already
            # running. Do not reject it through the generic runner lookup.
            adding_asset = p.path == "/admin/assets/add"
            targets = [] if adding_asset else (
                [self._runner(asset)] if asset and asset != "*" else list(port.runner_list())
            )
            if not adding_asset and asset and asset != "*" and targets == [None]:
                return self._json(404, {"detail": f"unknown asset {asset}"})
            try:
                if p.path == "/admin/research/studies":
                    return self._json(200, research.start(body))
                if p.path == "/admin/research/adaptation":
                    return self._json(200, research.configure_adaptation(body))
                if p.path == "/admin/research/source-watch":
                    return self._json(200, research.configure_source_watch(body))
                if p.path == "/admin/research/cancel":
                    return self._json(200, research.cancel(body.get("job")))
                if p.path == "/admin/research/proposals":
                    return self._json(200, research.propose_study(body))
                if p.path == "/admin/research/export":
                    candidate = research.export(body.get("proposal_id"))
                    return self._json(200, candidate)
                if p.path == "/admin/research/analysis":
                    return self._json(200, research.analysis.start(body))
                if p.path == "/admin/research/analysis/cancel":
                    if set(body) != {"id"}:
                        raise ValueError("analysis cancellation requires id only")
                    return self._json(200, research.analysis.journal.cancel(body["id"]))
                if p.path == "/admin/research/activate":
                    return self._json(200, research.activate(body))
                if p.path == "/admin/research/rollback":
                    return self._json(200, research.rollback(body))
                if p.path == "/admin/research/recover":
                    return self._json(200, research.recover(body))
                if p.path == "/admin/research/collect":
                    if not {"source"} <= set(body) or set(body) - {"source", "options"}:
                        raise ValueError("collection requires source and optional options")
                    return self._json(200, research.market_sources.collect(body["source"], body.get("options")))
                if p.path == "/admin/pause":
                    for r in targets:
                        r.set_paused(True)
                    if not asset or asset == "*":
                        port.paused = True
                    port.journal.log("WARN", f"PAUSED {asset or 'ALL'}: {_reason(body)}")
                    return self._json(200, {"ok": True, "note": f"paused {asset or 'all'} - no new entries"})
                if p.path == "/admin/resume":
                    for r in targets:
                        r.set_paused(False)
                    if not asset or asset == "*":
                        port.paused = False
                    port.journal.log("INFO", f"RESUMED {asset or 'ALL'}")
                    return self._json(200, {"ok": True, "note": f"resumed {asset or 'all'}"})
                if p.path == "/admin/flatten":
                    if not body.get("confirm"):
                        return self._json(400, {"detail": "pass {\"confirm\": true}"})
                    closed = {r.symbol: r.flatten(_reason(body, "dashboard")) for r in targets}
                    return self._json(200, {"ok": True, "closed": closed, "note": f"flattened {sum(closed.values())} position(s)"})
                if p.path == "/admin/market-data/mbo-snapshot":
                    if len(targets) != 1 or targets[0] is None:
                        raise ValueError("MBO snapshot requires exactly one running asset")
                    r = targets[0]
                    if not hasattr(r.feed, "mbo_snapshot"):
                        return self._json(409, {"error": f"{type(r.feed).__name__} does not expose MBO snapshots"})
                    timeout = max(0.1, min(30.0, float(body.get("timeout", 5.0))))
                    try:
                        rows = r.feed.mbo_snapshot(r.spec.ticker, timeout=timeout)
                    except TimeoutError as ex:
                        port.journal.log("WARN", f"market-data MBO snapshot {r.symbol}: {ex}")
                        return self._json(504, {"error": str(ex)})
                    except ValueError as ex:
                        return self._json(400, {"error": str(ex)})
                    except Exception as ex:
                        port.journal.log("WARN", f"market-data MBO snapshot {r.symbol}: {type(ex).__name__}: {ex}")
                        return self._json(502, {"error": f"{type(ex).__name__}: {ex}"})
                    return self._json(200, {"asset": r.symbol, "provider": type(r.feed).__name__.lower(),
                                            "schema": "mbo", "snapshot": rows})
                if p.path in ("/admin/inputs", "/admin/inputs/reset", "/admin/preset", "/admin/rewarm"):
                    from .runtime import resolve_inputs as _resolve
                    vals = body.get("values", {}) if p.path == "/admin/inputs" else None
                    if vals is not None and not isinstance(vals, dict):
                        raise ValueError("values must be an object")
                    chart = validate_chart_config(body.get("chart")) if p.path == "/admin/inputs" else {}
                    kwargs = {}
                    if p.path == "/admin/preset":
                        name = body.get("preset") or None
                        if name and not os.path.exists(preset_path(port.base_dir, str(name))):
                            return self._json(404, {"detail": f"preset {name} not found"})
                        kwargs["preset"] = name
                    reset = p.path == "/admin/inputs/reset"
                    with ExitStack() as locks:
                        # Hold every target from preflight through replay: no fill
                        # may race between acceptance and a later worker thread.
                        for r in sorted(targets, key=lambda r: r.symbol):
                            locks.enter_context(r.lock)
                            r.ensure_configurable()
                        # Preflight the entire batch before the first asset is persisted/replayed.
                        for r in targets:
                            sp = replace(r.cfg.base_spec or r.spec)
                            sp.preset = r.spec.preset
                            name = port.preset_for(r)
                            if "preset" in kwargs:
                                sp.preset = kwargs["preset"]
                                name = kwargs["preset"] or port.preset
                            inp, meta, _ = _resolve(sp, port.base_dir, port.profile, name, vals,
                                                   skip_asset_overrides=reset)
                            sp = apply_spec_meta(sp, meta)
                            sp = apply_chart_config(sp, chart)
                            r.ensure_cached_timeframes(inp)
                            r.ensure_cached_chart_timeframe(sp.chart_tf)
                        equity_epoch_before = port.equity_epoch
                        snapshots = {}
                        for r in targets:
                            override_path = os.path.join(port.base_dir, f"inputs.{r.symbol}.json")
                            snapshots[r.symbol] = {
                                "runtime": r.configuration_snapshot(),
                                "override_path": override_path,
                                "override_bytes": (Path(override_path).read_bytes() if os.path.exists(override_path) else None),
                            }
                        applied = []
                        try:
                            for r in targets:
                                port.rewarm_asset(r.symbol, vals, bool(body.get("persist", True)) if vals is not None else False,
                                                  reset=reset, chart=chart, **kwargs)
                                applied.append(r)
                        except Exception as apply_ex:
                            port.equity_epoch = equity_epoch_before
                            rollback_errors = []
                            for r in reversed(applied):
                                snap = snapshots[r.symbol]
                                try:
                                    pth = snap["override_path"]
                                    raw_before = snap["override_bytes"]
                                    if raw_before is None:
                                        if os.path.exists(pth):
                                            os.remove(pth)
                                    else:
                                        tmp = pth + ".batch-rollback.tmp"
                                        Path(tmp).write_bytes(raw_before)
                                        os.replace(tmp, pth)
                                    r.restore_configuration_snapshot(snap["runtime"])
                                except Exception as rollback_ex:
                                    rollback_errors.append(f"{r.symbol}: {type(rollback_ex).__name__}: {rollback_ex}")
                            if rollback_errors:
                                raise RuntimeError(
                                    f"batch configuration failed ({type(apply_ex).__name__}: {apply_ex}); "
                                    f"rollback incomplete: {'; '.join(rollback_errors)}"
                                ) from apply_ex
                            raise
                        # One successful batch = one paper-engine epoch. All runners were rebuilt.
                        cutover = time.time()
                        for r in targets:
                            r.live_from_ts = int(cutover)
                            r.live_closed_start = len(r.em.closed)
                        port.equity_epoch = cutover
                    done = [r.symbol for r in targets]
                    return self._json(200, {"ok": True, "note": f"configuration applied and re-warmed {done}", "assets": done,
                                            "chart": chart or None})
                if p.path == "/admin/assets/add":
                    tok = str(body.get("symbol", "")).strip()
                    if not tok:
                        return self._json(400, {"detail": "symbol required"})
                    running = port.runner_list()
                    default_tf = str(body.get("tf") or (running[0].spec.chart_tf if running else "20"))
                    spec = parse_spec(tok, default_tf)
                    if body.get("tf") not in (None, "") and "@" not in tok:
                        spec = pin_config(spec, "timeframe")
                    spec = apply_chart_config(spec, {k: body[k] for k in ("chart_type", "fill_on", "security_source") if body.get(k) not in (None, "")}, pin=True)
                    if body.get("preset"):
                        name = str(body["preset"])
                        if not os.path.exists(preset_path(port.base_dir, name)):
                            return self._json(404, {"detail": f"preset {name} not found"})
                        spec.preset = name
                    r = port.add_asset(spec)
                    return self._json(200, {"ok": True, "note": f"{r.symbol} added ({spec.name}, {spec.chart_tf}m); warming up", "asset": r.symbol})
                if p.path == "/admin/assets/remove":
                    ok = port.remove_asset(str(body.get("symbol", "")))
                    return self._json(200 if ok else 404, {"ok": ok, "note": f"{body.get('symbol')} {'removed' if ok else 'not found'}"})
                if p.path == "/admin/backtest":
                    from .backtest import validate_backtest_params
                    r = self._runner(asset)
                    if not r:
                        return self._json(404, {"detail": f"unknown asset {asset}"})
                    if not r.warm:
                        return self._json(409, {"detail": f"{r.symbol} is still warming up"})
                    fields = ("preset", "fill_on", "chart_type", "timeframe", "security_source", "session",
                              "slippage_ticks", "commission", "capital", "leverage", "window_start", "window_end", "inputs")
                    params = validate_backtest_params({k: body[k] for k in fields if k in body})
                    params["asset"] = r.symbol
                    if "preset" in params and not os.path.exists(preset_path(port.base_dir, params["preset"])):
                        return self._json(404, {"detail": f"preset {params['preset']} not found"})
                    job_id = start_job(port, params)
                    return self._json(200, {"ok": True, "job": job_id, "note": f"backtest {r.symbol} started"})
                if p.path == "/admin/backtest/compare":
                    job = JOBS.get(str(body.get("job", "")))
                    if not job or job["status"] != "done":
                        return self._json(404, {"detail": "unknown or unfinished backtest job"})
                    text = str(body.get("csv", ""))
                    if not text.strip():
                        return self._json(400, {"detail": "csv text required"})
                    tv = read_tv_trades_text(text)
                    eng = engine_trades_from_rows(job["result"]["trades"])
                    rep_ = compare_lists(eng, tv, int(job["result"]["config"]["tf"]) * 60, int(body.get("tol", 1) or 1))
                    return self._json(200, {"ok": True, "report": rep_})
            except (ValueError, TypeError) as ex:
                return self._json(400, {"detail": str(ex)})
            except Exception as ex:
                port.journal.log("ERROR", f"admin {p.path}: {type(ex).__name__}: {ex}")
                return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            self._json(404, {"error": "not found"})

    class ResearchHTTPServer(ThreadingHTTPServer):
        def serve_forever(self, poll_interval=.5):
            research.start_background()
            loop_intelligence_sync.start()
            try:
                return super().serve_forever(poll_interval)
            finally:
                loop_intelligence_sync.close()
                research.close()

        def server_close(self):
            loop_intelligence_sync.close()
            research.close()
            return super().server_close()

    srv = ResearchHTTPServer(("127.0.0.1", http_port), H)
    srv.research = research
    srv.loop_intelligence_sync = loop_intelligence_sync
    srv.daemon_threads = True
    if not start:
        return srv
    srv.serve_forever()
