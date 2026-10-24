"""Live runtime: one AssetRunner per asset (feed → sub-bars → timeframe chains → strategy →
broker emulator), a Portfolio that owns them, and the journal.

Warm-up is built exactly like live operation: every chart bar after `T_w` (the
start of the warm-up window, aligned to a session boundary of the asset's
calendar) is aggregated from the finest sub-bars the feed offers, so there is no
seam between history and realtime. Slower timeframes get deeper native history
before `T_w` so their SuperTrend/ADX are seeded before the chart bars start.
All fetched sub-bars are kept in memory, so changing inputs re-warms an asset in
seconds without touching the network.
"""
from __future__ import annotations

import collections
import copy
import csv
import hashlib
import importlib.util
import dataclasses
import io
import json
import math
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional, Tuple

from .assets import AssetSpec, apply_chart_config, chart_capabilities, chart_timeframe_parts, normalize_chart_timeframe, resolve, validate_chart_config
from .calendar import get_calendar
from .emulator import Emulator, Fill
from .shadow_twin import MirroredEmulator
from .feeds import Coinbase, Kraken
from .feeds.events import event_bar_to_bar, make_event_feed
from .feeds.bars import HistoryHub, detect_granularity, file_feed_mode, find_history, parse_ohlcv_csv, read_text_csv  # Grok (xAI) — 2026-09-20
from .feeds.databento import Databento
from .feeds.yahoo import Yahoo
from .bar_receipts import make_bar_batch_receipt
from .microstructure import TickAggregator, TradeAggregator, TradeEvent
from .pine.series import NAN, na
from .pine.timeframe import Aggregator, Bar, tf_minutes
from .strategy.inputs import Inputs, crypto_profile
from .strategy.meta import load_meta
from .strategy.pulse import PulseStrategy
from .strategy.security import TFChain


def _session_mode(cal) -> str:
    """Human/reporting session mode; 24/7 calendars must never masquerade as ETH."""
    return "24/7" if getattr(cal, "open_24_7", False) else str(getattr(cal, "session", "eth"))


def _clean(x: Any) -> Any:
    """NaN / Inf → None so json.dumps(..., allow_nan=False) cannot empty-reply."""
    item = getattr(x, "item", None)
    if callable(item) and not isinstance(x, (bytes, str, dict, list, tuple, int, float, bool)):
        try:
            if getattr(x, "shape", None) == ():
                return _clean(item())
        except Exception:
            return None
    if isinstance(x, float):
        return None if x != x or x in (float("inf"), float("-inf")) else x
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    return x


# ──────────────────────────────────────────────────────────────────────
# Journal
# ──────────────────────────────────────────────────────────────────────
class Journal:
    """SQLite journal (WAL) + small in-memory tails for the dashboard."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        self.con = sqlite3.connect(path, check_same_thread=False)
        self._closed = False
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.executescript("""
        CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY, symbol TEXT, entry_id TEXT, direction INTEGER, qty INTEGER,
            entry_price REAL, entry_ts INTEGER, exit_price REAL, exit_ts INTEGER, exit_comment TEXT, profit REAL, live INTEGER);
        CREATE TABLE IF NOT EXISTS fills (id INTEGER PRIMARY KEY, symbol TEXT, ts INTEGER, entry_id TEXT, side TEXT, qty INTEGER,
            price REAL, kind TEXT, comment TEXT, profit REAL, position_after INTEGER, live INTEGER);
        CREATE TABLE IF NOT EXISTS equity (ts REAL, equity REAL);
        CREATE TABLE IF NOT EXISTS log (ts REAL, level TEXT, msg TEXT);
        """)
        self.run_id = int(time.time())                        # every process start is a run; rows carry it (audit D2)
        for table, col, typ in (
            ("trades", "piece", "INTEGER DEFAULT 0"),
            ("trades", "bars", "INTEGER DEFAULT 0"),
            ("trades", "run_id", "INTEGER DEFAULT 0"),
            ("trades", "lot_id", "INTEGER DEFAULT 0"),
            ("trades", "entry_qty", "INTEGER DEFAULT 0"),
            ("trades", "strategy_fingerprint", "TEXT"),
            ("trades", "strategy_context_json", "TEXT"),
            ("fills", "run_id", "INTEGER DEFAULT 0"),
            ("log", "run_id", "INTEGER DEFAULT 0"),
        ):
            cols = [r[1] for r in self.con.execute(f"PRAGMA table_info({table})")]
            if col not in cols:
                self.con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        # warm-up replays are journaled once per run: a unique index keeps repeats out (INSERT OR IGNORE below).
        # `piece` distinguishes two pieces of one position that close identically on the same bar (audit D1);
        # fills are distinguished by the position they leave behind.
        self.con.executescript("""
        DROP INDEX IF EXISTS trades_uq; DROP INDEX IF EXISTS trades_uq2; DROP INDEX IF EXISTS fills_uq;
        DELETE FROM trades WHERE rowid NOT IN (
            SELECT MIN(rowid) FROM trades
            GROUP BY run_id,symbol,entry_id,direction,qty,entry_price,entry_ts,exit_price,exit_ts,exit_comment,piece,lot_id
        );
        DELETE FROM fills WHERE rowid NOT IN (SELECT MIN(rowid) FROM fills GROUP BY run_id,symbol,ts,entry_id,side,qty,price,kind,comment,position_after);
        CREATE UNIQUE INDEX IF NOT EXISTS trades_uq3 ON trades (
            run_id,symbol,entry_id,direction,qty,entry_price,entry_ts,exit_price,exit_ts,exit_comment,piece,lot_id
        );
        CREATE UNIQUE INDEX IF NOT EXISTS fills_uq2 ON fills (run_id,symbol,ts,entry_id,side,qty,price,kind,comment,position_after);
        """)
        self.con.execute("DELETE FROM log WHERE ts < ?", (time.time() - 14 * 86400,))
        self.con.commit()
        self.log_tail: Deque[Dict[str, Any]] = collections.deque(maxlen=400)
        self._trade_generation = self._equity_generation = 0
        self._dashboard_views = None
        self._display_stop, self._display_wake = threading.Event(), threading.Event()
        self._display_lifecycle_lock = threading.Lock()
        self._display_thread = None
        self._display_since_ts = None
        # Initial journal reads belong to startup, never an HTTP request.
        self.publish_dashboard_views()

    def close(self) -> None:
        """Close the SQLite connection; safe to call more than once."""
        self._display_stop.set()
        self._display_wake.set()
        worker = self._display_thread
        if worker is not None and worker is not threading.current_thread():
            worker.join(timeout=1)
        with self._lock:
            if self._closed:
                return
            self.con.close()
            self._closed = True

    def log(self, level: str, msg: str) -> None:
        row = {"ts": time.time(), "level": level, "msg": msg}
        with self._lock:
            self.log_tail.append(row)
            self.con.execute("INSERT INTO log (ts,level,msg,run_id) VALUES (?,?,?,?)", (row["ts"], level, msg, self.run_id))
            self.con.commit()

    def add_trade(self, symbol: str, t, live: bool, piece: int = 0, *, context: Optional[Dict[str, Any]] = None) -> None:
        ctx = _clean(dict(context or {}))
        if not isinstance(ctx, dict):
            raise ValueError("trade context must be an object")
        fingerprint = ctx.get("strategy_fingerprint")
        if fingerprint not in (None, ""):
            fingerprint = str(fingerprint).lower()
            if len(fingerprint) != 64 or any(ch not in "0123456789abcdef" for ch in fingerprint):
                raise ValueError("strategy_fingerprint must be a 64-character SHA-256 hex digest")
            ctx["strategy_fingerprint"] = fingerprint
            ctx.setdefault("provenance_quality", "CLOSURE_TIME_CONFIG")
        context_json = json.dumps(ctx, sort_keys=True, separators=(",", ":"), allow_nan=False)
        lot_id = int(getattr(t, "lot_id", 0) or 0)
        entry_qty = int(getattr(t, "entry_qty", 0) or 0)
        with self._lock:
            self.con.execute(
                "INSERT OR IGNORE INTO trades "
                "(symbol,entry_id,direction,qty,entry_price,entry_ts,exit_price,exit_ts,exit_comment,profit,live,piece,run_id,lot_id,entry_qty,strategy_fingerprint,strategy_context_json,bars) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    symbol, t.entry_id, t.direction, t.qty, t.entry_price, t.entry_ts,
                    t.exit_price, t.exit_ts, t.exit_comment, t.profit, int(live), int(piece),
                    self.run_id, lot_id, entry_qty, fingerprint, context_json, int(getattr(t, "bars", 0) or 0),
                ),
            )
            self.con.commit()
            self._trade_generation += 1
            self._display_wake.set()

    def performance_review(self, symbol: str, *, limit: int = 30, min_lots: int = 12, since_ts: int = 0) -> Dict[str, Any]:
        """Rolling settled-lot scorecard for this process's live paper trades.

        Partial exits are combined by lot, so a scale-out is one outcome. Regime
        attribution is explicitly marked as closure-time until entry snapshots exist.
        """
        with self._lock:
            rows = self.con.execute(
                "SELECT lot_id,entry_ts,entry_qty,qty,profit,exit_ts,bars,strategy_context_json "
                "FROM trades WHERE symbol=? AND live=1 AND entry_ts>=? AND exit_ts>=? ORDER BY exit_ts,id",
                (symbol, int(since_ts or 0), int(since_ts or 0)),
            ).fetchall()
        lots: Dict[Tuple[int, int], Dict[str, Any]] = {}
        for lot_id, entry_ts, entry_qty, qty, profit, exit_ts, bars, raw_ctx in rows:
            key = (int(lot_id or 0), int(entry_ts or 0))
            lot = lots.setdefault(key, {"qty": 0, "entry_qty": int(entry_qty or 0), "profit": 0.0,
                                       "bars": 0, "entry_ts": int(entry_ts or 0), "exit_ts": 0,
                                       "regime": "unknown", "attribution": "legacy_or_unknown"})
            lot["qty"] += int(qty or 0)
            lot["entry_qty"] = max(lot["entry_qty"], int(entry_qty or 0))
            lot["profit"] += float(profit or 0.0)
            lot["bars"] = max(lot["bars"], int(bars or 0))
            lot["exit_ts"] = max(lot["exit_ts"], int(exit_ts or 0))
            try:
                ctx = json.loads(raw_ctx or "{}")
                lot["regime"] = str(ctx.get("regime") or "unknown")
                lot["attribution"] = str(ctx.get("regime_attribution") or "legacy_or_unknown")
            except (TypeError, json.JSONDecodeError):
                pass
        settled = [v for v in lots.values() if v["entry_qty"] > 0 and v["qty"] >= v["entry_qty"]]
        settled.sort(key=lambda x: x["exit_ts"])
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for lot in settled:
            groups.setdefault(lot["regime"], []).append(lot)
        scorecards = {}
        for regime, group in groups.items():
            sample = group[-limit:]
            count = len(sample)
            wins = sum(x["profit"] > 0 for x in sample)
            win_rate = wins / count if count else None
            status = "INSUFFICIENT_SAMPLE" if count < min_lots else ("PRESSURE" if win_rate < .75 else ("WATCH" if win_rate < .85 else "HEALTHY"))
            gains = sum(x["profit"] for x in sample if x["profit"] > 0)
            losses = -sum(x["profit"] for x in sample if x["profit"] < 0)
            scorecards[regime] = {"status": status, "sample_lots": count, "wins": wins,
                "win_rate": win_rate, "net_profit": sum(x["profit"] for x in sample),
                "profit_factor": gains / losses if losses else (None if gains == 0 else "infinite"),
                "average_hold_bars": sum(x["bars"] for x in sample) / count if count else None,
                "average_hold_seconds": sum(max(0, x["exit_ts"] - x["entry_ts"]) for x in sample) / count if count else None,
                "regime_attribution": sorted({x["attribution"] for x in sample})}
        return {"window_lots": limit, "minimum_lots": min_lots, "since_ts": int(since_ts or 0), "scorecards": scorecards,
                "execution_authorized": False, "basis": "live paper fills; fully closed lots only"}

    def add_fill(self, symbol: str, f: Fill, live: bool) -> None:
        with self._lock:
            self.con.execute("INSERT OR IGNORE INTO fills (symbol,ts,entry_id,side,qty,price,kind,comment,profit,position_after,live,run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                             (symbol, f.ts, f.entry_id, f.side, f.qty, f.price, f.kind, f.comment, f.profit, f.position_after, int(live), self.run_id))
            self.con.commit()

    def add_equity(self, equity: float) -> None:
        with self._lock:
            self.con.execute("INSERT INTO equity VALUES (?,?)", (time.time(), equity))
            self.con.commit()
            self._equity_generation += 1
            self._display_wake.set()

    def publish_dashboard_views(self, *, since_ts=None, blocking=True) -> bool:
        """Publish bounded journal views outside request handlers.

        A single immutable assignment binds values, their receipt clock and the
        committed generation. Writers invalidate cached values immediately;
        readers never wait for the journal lock or query SQLite.
        """
        if not self._lock.acquire(blocking=blocking):
            return False
        try:
            if self._closed:
                return False
            now = int(time.time())
            # SQLite's data_version catches other connections; total_changes
            # catches every committed write on this connection, including
            # fixture/import writes outside add_trade. Unchanged images need
            # a lightweight validation, not another full-ledger scan every 2s.
            revision = (self.con.total_changes, self.con.execute("PRAGMA data_version").fetchone()[0])
            previous = self._dashboard_views
            reusable = (previous is not None and previous.get("source_revision") == revision
                        and now >= previous["captured_at"] and not previous["closed"].get("reason")
                        and previous.get("since_ts") == since_ts)
            closed = previous["closed"] if reusable else self.closed_paper_profit(as_of_ts=now)
            equity = previous["equity"] if reusable else self.equity_series(max_points=600, since_ts=since_ts)
            self._dashboard_views = {"captured_at": now, "closed": closed,
                                     "equity": equity, "trade_generation": self._trade_generation,
                                     "equity_generation": self._equity_generation,
                                     "source_revision": revision, "since_ts": since_ts}
            return True
        finally:
            self._lock.release()

    def start_display_publisher(self, *, since_ts=None) -> None:
        """The portfolio owns this worker; journal close drains it."""
        self._display_since_ts = since_ts
        def publish():
            while not self._display_stop.is_set():
                try:
                    self.publish_dashboard_views(since_ts=self._display_since_ts, blocking=False)
                except Exception:
                    # Keep the previous timestamp; expiry/dirty checks make
                    # failure explicit without writing recursively to this DB.
                    pass
                self._display_wake.wait(2)
                self._display_wake.clear()
        with self._display_lifecycle_lock:
            if self._display_thread is not None or self._display_stop.is_set():
                return
            self._display_thread = threading.Thread(target=publish, daemon=True,
                                                    name="journal-display-publisher")
            self._display_thread.start()

    def _cached_dashboard_view(self, kind, *, as_of_ts=None):
        now = time.time() if as_of_ts is None else as_of_ts
        view = self._dashboard_views
        generation = self._trade_generation if kind == "closed" else self._equity_generation
        reason = None
        if view is None:
            reason = "JOURNAL_VIEW_UNAVAILABLE"
        elif self._closed:
            reason = "JOURNAL_CLOSED"
        elif view["equity_generation" if kind == "equity" else "trade_generation"] != generation:
            reason = "JOURNAL_VIEW_PENDING"
        elif now < view["captured_at"]:
            reason = "JOURNAL_VIEW_IN_FUTURE"
        elif now - view["captured_at"] > 90:
            reason = "JOURNAL_VIEW_STALE"
        if reason:
            return None, {"view_stale": True, "view_captured_at": view["captured_at"] if view else None,
                          "reason": reason}
        return copy.deepcopy(view[kind]), {"view_stale": False,
                                          "view_captured_at": view["captured_at"]}

    def closed_paper_profit(self, *, as_of_ts=None, nonblocking=False) -> Dict[str, Any]:
        """Validated persisted closures after the paper cutover, across runs.

        A trade can enter during warmup and close after cutover. Invalid rows
        make realized P&L unknown; an actually empty ledger remains zero.
        """
        if nonblocking:
            closed, metadata = self._cached_dashboard_view("closed", as_of_ts=as_of_ts)
            if closed is None:
                closed = {"realized_pnl": None, "closed_pieces": None, "last_close_ts": None}
            return {**closed, **metadata}
        from .workspace_performance import read_persisted_trades
        now = time.time() if as_of_ts is None else as_of_ts
        rows, reason = read_persisted_trades(self, as_of_ts=now)
        unknown = {"realized_pnl": None, "closed_pieces": None, "last_close_ts": None}
        if reason:
            return {**unknown, "reason": reason}
        try:
            profit = math.fsum(row['profit'] for row in rows)
        except (OverflowError, ValueError):
            return {**unknown, "reason": "NONFINITE_AGGREGATE"}
        if not math.isfinite(profit):
            return {**unknown, "reason": "NONFINITE_AGGREGATE"}
        return {"realized_pnl": profit, "closed_pieces": len(rows),
                "last_close_ts": rows[-1]['exit_ts'] if rows else None}

    def export_trades_csv(self, path: str, *, live_only: bool = False) -> int:
        with self._lock:
            return write_paper_csv(self.con, path, live_only=live_only)

    def equity_series(self, since_sec: float = 86400.0, max_points: int = 600, *, since_ts: Optional[float] = None,
                      nonblocking: bool = False) -> List[Dict[str, float]]:
        cutoff = float(since_ts) if since_ts is not None else (time.time() - since_sec)
        if nonblocking:
            rows, _ = self._cached_dashboard_view("equity")
            rows = [row for row in rows or [] if row["ts"] >= cutoff]
            if len(rows) > max_points:
                step = len(rows) / max_points
                rows = [rows[int(k * step)] for k in range(max_points)] + [rows[-1]]
            return rows
        with self._lock:
            rows = self.con.execute("SELECT ts, equity FROM equity WHERE ts >= ? ORDER BY ts", (cutoff,)).fetchall()
        if len(rows) > max_points:
            step = len(rows) / max_points
            rows = [rows[int(k * step)] for k in range(max_points)] + [rows[-1]]
        return [{"ts": r[0], "equity": r[1]} for r in rows]


def export_paper_book(db_path: str, out_path: str, *, live_only: bool = False) -> int:
    """Read-only dump of the paper book. Safe while the engine holds the WAL.

    Grok (xAI) — 2026-09-20. Do not construct ``Journal(db)`` for export: that
    migrates schema and DELETEs duplicate rows on a live file.
    """
    abs_db = os.path.abspath(db_path)
    uri = "file:" + abs_db.replace("\\", "/") + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        return write_paper_csv(con, out_path, live_only=live_only)
    finally:
        con.close()


def write_paper_csv(con: sqlite3.Connection, path: str, *, live_only: bool = False) -> int:
    """Write the paper book. Not a broker statement. Not CME.

    Grok (xAI) — 2026-09-20. Journal ``live=0`` is replay; ``live=1`` records fills processed live. In-memory epoch metrics reset on successful warm/re-warm.
    """
    from datetime import datetime, timezone
    try:
        from zoneinfo import ZoneInfo
        ny = ZoneInfo("America/New_York")
    except Exception:
        ny = timezone.utc

    def iso(ts: int) -> str:
        if not ts:
            return ""
        return datetime.fromtimestamp(int(ts), tz=ny).isoformat()

    q = "SELECT run_id,live,symbol,direction,qty,entry_id,entry_ts,entry_price,exit_ts,exit_price,exit_comment,profit,piece FROM trades"
    if live_only:
        q += " WHERE live=1"
    q += " ORDER BY exit_ts, id"
    rows = con.execute(q).fetchall()
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([
            "run_id", "live", "symbol", "side", "qty", "entry_id",
            "entry_ts", "entry_time_et", "entry_price",
            "exit_ts", "exit_time_et", "exit_price", "exit_comment", "profit", "piece",
            "disclaimer",
        ])
        disclaimer = "Icarus paper emulator — not a broker statement, not CME"
        for r in rows:
            run_id, live, symbol, direction, qty, entry_id, entry_ts, entry_price, exit_ts, exit_price, exit_comment, profit, piece = r
            side = "long" if int(direction or 0) > 0 else "short"
            w.writerow([
                run_id, int(live or 0), symbol, side, qty, entry_id,
                entry_ts, iso(entry_ts), entry_price,
                exit_ts, iso(exit_ts), exit_price, exit_comment, profit, piece,
                disclaimer,
            ])
    return len(rows)


# ──────────────────────────────────────────────────────────────────────
# Inputs resolution (defaults → profile → preset → inputs.json → inputs.<SYM>.json)
# ──────────────────────────────────────────────────────────────────────
def _read_json(path: str) -> Dict[str, Any]:
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        try:
            d = json.load(fh, parse_constant=_no_constants)
        except ValueError as ex:
            raise ValueError(f"{os.path.basename(path)}: not valid JSON ({ex})") from None
    if not isinstance(d, dict):
        raise ValueError(f"{os.path.basename(path)}: expected a JSON object")
    return d


def _no_constants(name: str):
    raise ValueError(f"{name} is not allowed in inputs")


_PRESET_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _.+\-]{0,60}")
_INPUT_TYPES = {f.name: str(f.type) for f in dataclasses.fields(Inputs)}
_UNCHANGED = object()


def preset_path(base_dir: str, name: str) -> str:
    """presets/<name>.json, confined to the presets directory."""
    if not name or not _PRESET_RE.fullmatch(str(name)):
        raise ValueError(f"bad preset name {name!r}")
    root = os.path.realpath(os.path.join(base_dir, "presets"))
    p = os.path.realpath(os.path.join(root, f"{name}.json"))
    if os.path.commonpath([root, p]) != root:
        raise ValueError(f"bad preset name {name!r}")
    return p


def validate_values(vals: Dict[str, Any]) -> None:
    """Type/range/option checks for input values (dataclass field types + the Pine's min/max/options)."""
    meta = {e["name"]: e for e in load_meta()}
    for k, v in list(vals.items()):
        t = _INPUT_TYPES.get(k, "")
        if t == "bool" and not isinstance(v, bool):
            raise ValueError(f"{k}: expected true/false, got {v!r}")
        if t == "int" and (isinstance(v, bool) or not isinstance(v, int)):
            if isinstance(v, float) and v.is_integer():
                vals[k] = v = int(v)
            else:
                raise ValueError(f"{k}: expected an integer, got {v!r}")
        if t == "float":
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError(f"{k}: expected a finite number, got {v!r}")
        if t == "str" and not isinstance(v, str):
            raise ValueError(f"{k}: expected a string, got {v!r}")
        e = meta.get(k)
        if e:
            if e.get("options") and v not in e["options"]:
                raise ValueError(f"{k}: must be one of {e['options']}")
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                if e.get("minval") is not None and v < e["minval"]:
                    raise ValueError(f"{k}: below the script's minimum {e['minval']}")
                if e.get("maxval") is not None and v > e["maxval"]:
                    raise ValueError(f"{k}: above the script's maximum {e['maxval']}")
            if e.get("kind") == "timeframe":
                tf_minutes(v)
            if e.get("kind") == "session" and not re.fullmatch(r"\d{4}-\d{4}", str(v)):
                raise ValueError(f"{k}: sessions are HHMM-HHMM")


def resolve_inputs(spec: AssetSpec, base_dir: str, profile: str = "nq", preset: Optional[str] = None,
                   extra: Optional[Dict[str, Any]] = None, *, skip_asset_overrides: bool = False,
                   extra_label: str = "override") -> Tuple[Inputs, Dict[str, Any], List[str]]:
    """Returns (inputs, preset_meta, sources). Values later in the chain override earlier ones."""
    base = (crypto_profile(0.0, spec.mintick) if profile == "crypto" else Inputs()).to_dict()
    known = set(base)
    sources: List[str] = [f"profile:{profile}"]
    meta: Dict[str, Any] = {}

    def apply(d: Dict[str, Any], label: str) -> None:
        nonlocal meta
        if not d:
            return
        m = d.get("_meta")
        if isinstance(m, dict):
            meta = {**meta, **m}
        vals = {k: v for k, v in d.items() if not k.startswith("_")}
        bad = [k for k in vals if k not in known]
        if bad:
            raise ValueError(f"{label}: unknown input names {bad}")
        validate_values(vals)
        base.update(vals)
        sources.append(f"{label} ({len(vals)})")

    name = preset or spec.preset
    if name:
        apply(_read_json(preset_path(base_dir, name)), f"preset:{name}")
    apply(_read_json(os.path.join(base_dir, "inputs.json")), "inputs.json")
    # The owner's explicit restart template supplies defaults for new assets.
    # Later per-asset edits and revisioned workspace overrides keep precedence.
    from .restart_defaults import owner_default_overrides
    apply(owner_default_overrides(base_dir, spec.symbol), "owner:NQ-defaults")
    if not skip_asset_overrides:
        apply(_read_json(os.path.join(base_dir, f"inputs.{spec.symbol}.json")), f"inputs.{spec.symbol}.json")
    if extra:
        apply(dict(extra), extra_label)
    return Inputs(**base), meta, sources


def apply_spec_meta(spec: AssetSpec, meta: Optional[Dict[str, Any]]) -> AssetSpec:
    """Apply Properties metadata without overriding explicit startup/API pins."""
    out = replace(spec)
    meta = meta or {}
    pins = set(getattr(out, "config_pins", ()) or ())
    chart = {k: meta[k] for k in ("chart_type", "fill_on", "security_source")
             if k not in pins and meta.get(k) not in (None, "")}
    if "timeframe" not in pins and meta.get("timeframe") not in (None, ""):
        chart["timeframe"] = meta["timeframe"]
    out = apply_chart_config(out, chart)
    if "slippage_ticks" not in pins and meta.get("slippage_ticks") is not None:
        out.slippage_ticks = int(meta["slippage_ticks"])
    if "commission" not in pins and meta.get("commission") is not None:
        out.commission = float(meta["commission"])
    if "capital" not in pins and meta.get("capital") is not None:
        out.capital = float(meta["capital"])
    if "session" not in pins and meta.get("session") in ("rth", "eth") and out.calendar == "cme":
        out.session = str(meta["session"])
    return out


class HeikinAshi:
    """TradingView Heikin Ashi transform, computed on the chart timeframe. TradingView quantises the HA
    series to the symbol's tick (every HA open/close in the owner's export is a tick multiple; the audit's
    rounded replay reproduces 11/15 known HA opens exactly vs 0/15 unrounded), so `mintick` rounds each
    recursion step; `mintick=None` keeps the exact arithmetic."""
    def __init__(self, mintick: Optional[float] = None):
        self.prev_open = NAN
        self.prev_close = NAN
        self.mintick = mintick

    def _q(self, x: float) -> float:
        return round(round(x / self.mintick) * self.mintick, 10) if self.mintick else x

    def transform(self, b: Bar) -> Bar:
        ha_close = self._q((b.o + b.h + b.l + b.c) / 4.0)
        ha_open = self._q((b.o + b.c) / 2.0 if na(self.prev_open) else (self.prev_open + self.prev_close) / 2.0)
        ha_high = max(b.h, ha_open, ha_close)
        ha_low = min(b.l, ha_open, ha_close)
        self.prev_open, self.prev_close = ha_open, ha_close
        return Bar(b.ts, ha_open, ha_high, ha_low, ha_close, b.v)


# ──────────────────────────────────────────────────────────────────────
# AssetRunner
# ──────────────────────────────────────────────────────────────────────
@dataclass
class RunnerConfig:
    spec: AssetSpec
    inputs: Inputs
    warmup_bars: int = 1200
    pts_ref_price: float = 0.0        # NQ price used to rescale *_pts inputs to this asset (0 = literal points)
    sources: Optional[List[str]] = None
    profile: str = "nq"
    preset: Optional[str] = None
    fixed_pts_scale: Optional[float] = None  # cached replay scale; never fetch a current reference
    mintick: Optional[float] = None          # cached replay tick; avoid product metadata network calls
    scale_known_at: Optional[int] = None    # actual receipt/computation time, never inferred from a price's date
    base_dir: Optional[str] = None          # Grok (xAI) — plant root; warmup looks here, not cwd
    base_spec: Optional[AssetSpec] = None    # startup/API-pinned baseline before preset/global/asset metadata
    shadow_real_fills: bool = False          # same-decision real-bar emulator; observation only


class FlattenUnavailableError(RuntimeError):
    """Administrative flatten could not safely close an open position."""


class AssetRunner:
    def __init__(self, cfg: RunnerConfig, journal: Journal, feeds: Optional[Dict[str, Any]] = None):
        self.cfg = cfg
        self.spec = cfg.spec
        if self.cfg.base_spec is None:
            self.cfg.base_spec = replace(cfg.spec)
        self.symbol = self.spec.symbol
        self.journal = journal
        # Bound by the server when measured live-decision telemetry is available.
        # Warm-up/replay bars never contribute to live hot-path latency claims.
        self.latency_telemetry = None
        feeds = feeds or {}
        self.feed = feeds.get(self.spec.feed) or (Yahoo() if self.spec.feed == "yahoo" else Coinbase())
        self.history_feed = feeds.get("databento_history")
        self.kraken = Kraken()
        self.cal = get_calendar(self.spec.calendar, self.spec.anchor_et, session=self.spec.session, group=self.spec.group)
        self.chart_mode, self.chart_value = chart_timeframe_parts(self.spec.chart_tf)
        self.chart_minutes = self.chart_value if self.chart_mode == "minutes" else 0
        self.chart_seconds = self.chart_value * 60 if self.chart_mode == "minutes" else (self.chart_value if self.chart_mode == "seconds" else None)
        # Tick metadata is part of the registered asset contract. Never infer it
        # from a provider response or silently substitute a generic increment.
        self.mintick = cfg.mintick if cfg.mintick is not None else self.spec.mintick
        self.last_bar_batch_receipt: Optional[Dict[str, Any]] = None
        self.bar_batch_receipts: List[Dict[str, Any]] = []
        self.trade_events: List[TradeEvent] = []
        self.event_feed = feeds.get("events")
        if self.chart_mode != "minutes" and self.event_feed is None:
            self.event_feed = make_event_feed(self.spec, self.mintick)
        self.event_chart_agg = None
        self.event_minute_agg = None
        self._event_chart_session: Optional[str] = None
        # Active futures never resolve to expiring month-coded contracts. The provider-native
        # continuous ticker is the live/data ticker; tv_symbol carries the TradingView 1! identity.
        self.live_ticker = self.spec.ticker                 # compatibility alias: always provider-native continuous for futures
        self.feed_time: float = 0.0                         # the feed's own clock (Yahoo: regularMarketTime)
        self.feed_delay: float = 0.0
        self.inputs_base: Inputs = cfg.inputs
        self.inputs: Inputs = cfg.inputs
        self.pts_scale = cfg.fixed_pts_scale if cfg.fixed_pts_scale is not None else 1.0
        self.last_price: Optional[float] = None
        self.last_price_ts: float = 0.0
        self.last_bar_wall: float = 0.0
        self.subbars: List[Tuple[Bar, int]] = []            # everything fed since T_w (for fast re-warm)
        self.deep: Dict[int, List[Tuple[Bar, int]]] = {}    # chain minutes → deep history (before T_w)
        self.T_w: Optional[int] = None
        self._build_engine()
        self.bar_index = -1
        self.bars: Deque[Bar] = collections.deque(maxlen=2000)
        self.overlays: Deque[Dict[str, Any]] = collections.deque(maxlen=2000)
        self.state: Dict[str, Any] = {}
        self.live_from_ts: Optional[int] = None
        self.live_closed_start: int = 0               # exact closed-trade boundary; avoids bar-start timestamp misclassification
        self.last_sub_ts: Optional[int] = None
        self._file_waiting: bool = False
        self._fills_seen = 0
        self._closed_seen = 0
        self.paused = False
        self._performance_guard: Dict[str, Any] = {"status": "INSUFFICIENT_SAMPLE", "scorecards": {}}
        self._performance_guard_since_ts = 0
        self._lot_entry_regimes: Dict[int, str] = {}
        self.errors = 0
        self.last_error = ""
        self.feed_error = ""
        self.runtime_error = ""
        self.last_poll_ok = 0.0
        self.warm = False
        self.rewarming = False
        self._removed = False
        self.lock = threading.RLock()
        self._public_views = None
        self.recent_fills: Deque[Dict[str, Any]] = collections.deque(maxlen=300)
        self.recent_events: Deque[Dict[str, Any]] = collections.deque(maxlen=300)

    # ── engine construction (also used by re-warm) ──
    def _build_engine(self) -> None:
        sp = self.spec
        self.chart_mode, self.chart_value = chart_timeframe_parts(sp.chart_tf)
        self.chart_minutes = self.chart_value if self.chart_mode == "minutes" else 0
        self.chart_seconds = self.chart_value * 60 if self.chart_mode == "minutes" else (self.chart_value if self.chart_mode == "seconds" else None)
        self.cal = get_calendar(sp.calendar, sp.anchor_et, session=sp.session, group=sp.group)   # a preset may switch the chart session
        primary_emulator = Emulator(sp.capital, sp.commission, self.mintick, sp.multiplier, pyramiding=2, slippage_ticks=sp.slippage_ticks)
        self.em = (MirroredEmulator(primary_emulator, asset=self.symbol)
                   if self.cfg.shadow_real_fills else primary_emulator)
        self.strat: Optional[PulseStrategy] = None
        ib = self.inputs_base
        self.htf_tfs = [tf_minutes(t) for t in (ib.htf_tf_1, ib.htf_tf_2, ib.htf_tf_3, ib.htf_tf_4, ib.htf_tf_5)]
        ha_chains = sp.chart_type == "heikin_ashi" and sp.security_source == "chart"      # TradingView: request.security on an HA chart returns HA data
        self.chains: Dict[int, TFChain] = {m: TFChain(m, self.cal.bucket_start, self.cal.bucket_end, ha=ha_chains, ltf_intrabar=ib.ltf_intrabar, mintick=self.mintick)
                                           for m in sorted(set(self.htf_tfs + [2, 5]))}
        self.chart_agg = Aggregator(self.chart_minutes, self.cal.bucket_start, self.cal.bucket_end) if self.chart_mode == "minutes" else None
        self.event_chart_agg = None
        self.event_minute_agg = None
        self._event_chart_session = None
        self.ha = HeikinAshi(mintick=self.mintick) if sp.chart_type == "heikin_ashi" else None
        self._real_ohlc_warned = False

    def _asset_ref_price(self, fallback: float) -> float:
        """The asset's last completed daily close (the same instant as the NQ reference) - reproducible run to run."""
        if self.spec.feed == "yahoo":
            try:
                rows = self.feed.daily_volume(self.spec.ticker, 6)
                so = self.cal.bucket_start(int(time.time()), 1440)
                done = [r for r in rows if r[0] < so]
                if done:
                    return float(done[-1][1])
            except Exception as ex:
                self.journal.log("WARN", f"[{self.symbol}] daily close for point scaling unavailable ({ex}); using the first bar")
        return fallback

    def _init_strategy(self, price: float) -> None:
        inp = self.inputs_base
        if self.cfg.fixed_pts_scale is not None:
            k = self.cfg.fixed_pts_scale
        else:
            price = self._asset_ref_price(price) if self.cfg.pts_ref_price > 0 else price
            k = price / self.cfg.pts_ref_price if self.cfg.pts_ref_price > 0 and price > 0 else 1.0
            if self.cfg.pts_ref_price > 0:
                self.cfg.scale_known_at = math.ceil(time.time())
        if self.cfg.pts_ref_price > 0 or self.cfg.fixed_pts_scale is not None:
            self.pts_scale = k
            if abs(k - 1.0) > 1e-6:
                inp = replace(inp, tp1_pts=inp.tp1_pts * k, tp2_pts=inp.tp2_pts * k, sl_pts=inp.sl_pts * k,
                              be_offset_pts=max(self.mintick, inp.be_offset_pts * k))
                self.journal.log("INFO", f"[{self.symbol}] NQ-point inputs rescaled x{k:.4g}: tp1 {inp.tp1_pts:.6g} tp2 {inp.tp2_pts:.6g} sl {inp.sl_pts:.6g}")
        if abs(inp.point_value - self.spec.multiplier) > 1e-9 and inp.point_value == Inputs().point_value:
            inp = replace(inp, point_value=self.spec.multiplier)          # the Pine's 20 = NQ; Risk-$ sizing needs this asset's $/point
        self.inputs = inp
        self.strat = PulseStrategy(inp, self.em, mintick=self.mintick, tf_minutes=max(1, self.chart_minutes), session_key=self.cal.session_id)

    # ── core bar path ──
    def _on_chart_bar(self, real: Bar, live: bool, *, time_close: Optional[int] = None) -> None:
        latency_started_ns = (
            time.perf_counter_ns()
            if live and self.latency_telemetry is not None
            else None
        )
        if self.strat is None:
            self._init_strategy(real.c)
        ha_bar = self.ha.transform(real) if self.ha else None
        # "Use Real OHLC for Calculations": the script re-requests its own symbol with request.security(syminfo.tickerid, ...)
        # which, on a Heikin Ashi chart, returns HA data again (the ticker id carries the HA modifier) - a no-op in
        # TradingView (security_source="chart"). security_source="standard" honours the toggle's intent (real bars).
        if ha_bar is not None and self.inputs_base.use_real_ohlc and self.spec.security_source == "standard":
            chart = real
        else:
            chart = ha_bar or real
            if ha_bar is not None and self.inputs_base.use_real_ohlc and not self._real_ohlc_warned:
                self._real_ohlc_warned = True
                self.journal.log("WARN", f"[{self.symbol}] use_real_ohlc is on but TradingView's request.security(syminfo.tickerid) returns Heikin Ashi data on an HA chart - ignored (security_source=chart); set security_source=standard to use real bars")
        fill_bar = (ha_bar or real) if self.spec.fill_on == "chart" else real
        self.bar_index += 1
        self.strat.paused = self.paused
        if self.paused:
            self._cancel_pending_entries()
        if isinstance(self.em, MirroredEmulator):
            self.em.process_bar(fill_bar, self.bar_index, real_bar=real)
        else:
            self.em.process_bar(fill_bar, self.bar_index)
        entry_regime = str((self.state or {}).get("rate_regime_str") or "unknown")
        for opened in getattr(self.em, "open", ()):
            self._lot_entry_regimes.setdefault(int(opened.seq), entry_regime)
        htf = [self.chains[m].htf_values(chart.ts) for m in self.htf_tfs]
        if time_close is not None:
            t_close = int(time_close)
        elif self.chart_mode == "minutes":
            t_close = self.cal.bucket_end(chart.ts, self.chart_minutes)
        elif self.chart_mode == "seconds":
            t_close = int(chart.ts) + int(self.chart_value)
        else:
            t_close = int(chart.ts) + 1
        security_chart_minutes = self.chart_minutes if self.chart_mode == "minutes" else 0
        ltf = [self.chains[2].ltf_values(chart.ts, security_chart_minutes, t_close), self.chains[5].ltf_values(chart.ts, security_chart_minutes, t_close)]
        st = self.strat.on_bar(chart, self.bar_index, htf, ltf, time_close=t_close)
        self.state = st
        if latency_started_ns is not None:
            try:
                self.latency_telemetry.observe_ns(
                    "shadow_decision_total",
                    time.perf_counter_ns() - latency_started_ns,
                )
            except Exception:
                # Telemetry is observational only and must never break the decision path.
                pass
        self.bars.append(chart)
        self.last_bar_wall = time.time()
        self.overlays.append({"ts": chart.ts, "st": st["rate_st_line"], "up": st["rate_uptrend"], "tp1": st["tp1_price"], "tp2": st["tp2_price"],
                              "sl": st["sl_price"], "vwap": st["vwap"], "kf": st["kf_level"], "pos": st["rate_qty_open"] * (1 if st["rate_pos_long"] else -1),
                              "tide_hi": st["tide_hi"], "tide_lo": st["tide_lo"], "pulse": max(st["pulse_l"], st["pulse_s"]), "real_c": real.c})
        self._record_new_execution(live=live)
        for ev in self.strat.events:
            self.recent_events.append(dict(ev, live=live))
            if live:
                self.journal.log("INFO", f"[{self.symbol}] {ev['text']}")
        self.strat.events.clear()

    def _record_new_execution(self, *, live: bool) -> None:
        """Journal emulator fills from both market bars and manual paper flatten."""
        for f in self.em.fills[self._fills_seen:]:
            self.recent_fills.append({"ts": f.ts, "bar": f.bar, "id": f.entry_id, "side": f.side, "qty": f.qty, "price": f.price,
                                      "kind": f.kind, "comment": f.comment, "profit": f.profit, "pos": f.position_after, "live": live})
            if live or not self.rewarming:
                self.journal.add_fill(self.symbol, f, live)
            if live:
                self.journal.log("INFO", f"[{self.symbol}] FILL {f.side.upper()} {f.qty} @ {f.price:.6g} {f.kind} {f.comment}" + (f" P&L {f.profit:+.2f}" if f.profit is not None else "") + f" -> pos {f.position_after:+d}")
        self._fills_seen = len(self.em.fills)
        closed_before_count = self._closed_seen
        for idx in range(self._closed_seen, len(self.em.closed)):
            t = self.em.closed[idx]
            if live or not self.rewarming:
                key = (t.entry_id, t.entry_ts, t.exit_ts, t.exit_comment, t.qty, t.exit_price)
                piece = sum(1 for u in self.em.closed[:idx] if (u.entry_id, u.entry_ts, u.exit_ts, u.exit_comment, u.qty, u.exit_price) == key)
                self.journal.add_trade(self.symbol, t, live, piece,
                                       context=self._trade_learning_context(self._lot_entry_regimes.get(int(t.lot_id or 0))))
        self._closed_seen = len(self.em.closed)
        if live and len(self.em.closed) > closed_before_count:
            self._refresh_performance_guard()

    def on_sub_bar(self, b: Bar, sub_minutes: int, live: bool, record: bool = True) -> None:
        """Feed one genuine minute-or-coarser sub-bar to HTF chains and minute charts."""
        with self.lock:
            if self._removed:
                return
            if self.last_sub_ts is not None and b.ts <= self.last_sub_ts:
                return
            if not self.cal.is_open(b.ts):
                return
            self.last_sub_ts = b.ts
            if record:
                self.subbars.append((b, sub_minutes))
            intraday = self.cal.intraday_open(b.ts)
            for ch in self.chains.values():
                if sub_minutes <= ch.minutes and ch.minutes % sub_minutes == 0 and (ch.minutes >= 1440 or intraday):
                    ch.push_sub_bar(b, sub_minutes)
            if self.chart_mode == "minutes" and intraday and self.chart_minutes % sub_minutes == 0:
                for cb in self.chart_agg.push(b, sub_minutes):
                    self._on_chart_bar(cb, live)
            self.last_price = b.c

    def _reset_event_chart_aggregator(self, event: TradeEvent) -> None:
        contiguous = str(event.venue).startswith("coinbase")
        if self.chart_mode == "seconds":
            self.event_chart_agg = TradeAggregator(event.venue, event.instrument, seconds=self.chart_value,
                                                   contiguous_sequence=contiguous)
        elif self.chart_mode == "ticks":
            self.event_chart_agg = TickAggregator(event.venue, event.instrument, self.chart_value,
                                                  contiguous_sequence=contiguous)
        else:
            self.event_chart_agg = None
        self._event_chart_session = self.cal.session_id(event.event_ns // 1_000_000_000)

    def _ensure_event_aggregators(self, event: TradeEvent) -> None:
        contiguous = str(event.venue).startswith("coinbase")
        if self.event_minute_agg is None:
            self.event_minute_agg = TradeAggregator(event.venue, event.instrument, seconds=60,
                                                    contiguous_sequence=contiguous)
        session = self.cal.session_id(event.event_ns // 1_000_000_000)
        if self.event_chart_agg is None or self._event_chart_session != session:
            self._reset_event_chart_aggregator(event)

    def on_trade_event(self, event: TradeEvent, live: bool, record: bool = True) -> None:
        """Feed one authentic trade event. Never synthesizes an empty second or fake tick."""
        with self.lock:
            ts = event.event_ns // 1_000_000_000
            if not self.cal.is_open(ts):
                return
            self._ensure_event_aggregators(event)
            if record:
                self.trade_events.append(event)

            for raw in self.event_minute_agg.push(event):
                minute = event_bar_to_bar(raw, self.mintick)
                self.on_sub_bar(minute, 1, live=live, record=True)

            if self.chart_mode in ("seconds", "ticks") and self.cal.intraday_open(ts):
                for raw in self.event_chart_agg.push(event):
                    bar = event_bar_to_bar(raw, self.mintick)
                    end_ns = int(raw.get("end_ns") or raw.get("start_ns") or event.event_ns)
                    if self.chart_mode == "seconds":
                        end_ns = int(raw["start_ns"]) + self.chart_value * 1_000_000_000
                    self._on_chart_bar(bar, live, time_close=max(bar.ts + 1, (end_ns + 999_999_999) // 1_000_000_000))
            self.last_price = event.price_ticks * self.mintick
            self.last_price_ts = max(self.last_price_ts, event.received_ns / 1_000_000_000)

    # ── warm-up ──
    def warmup(self, now_ts: Optional[int] = None) -> None:
        now = int(now_ts or time.time())
        base = self.cfg.base_dir or os.getcwd()
        hist, minutes = find_history(base, self.symbol, self.chart_minutes)  # Grok (xAI) — 2026-09-20: prefer history/ over Yahoo; plant root over cwd
        span = self.cfg.warmup_bars * self.chart_minutes * 60
        if not self.cal.open_24_7:
            if getattr(self.cal, "session", "eth") == "rth":  # ~20 bars per trading day (09:30-16:15 ET), 5 days a week
                per_day = max(1, 405 // self.chart_minutes)
                span = int(self.cfg.warmup_bars / per_day * 7 / 5 * 86400) + 3 * 86400
            else:                                             # 5 sessions of 23h per week → stretch the calendar window
                span = int(span * 7 / 5 * 24 / 23) + 86400
        provider_days = None
        if not hist and type(self.feed).__name__ == "Yahoo" and 0 < self.chart_minutes < 1440:
            # Use Yahoo's available intraday range when the configured bar count is
            # shorter. The current replay path uses 1m candles (29d) for charts
            # below 5m and 5m+1m candles (59d) for 5m-aligned charts. Never extend
            # the requested window past the bars the provider can actually supply.
            provider_days = 59 if self.chart_minutes >= 5 and self.chart_minutes % 5 == 0 else 29
            span = max(span, provider_days * 86400)
        databento_feed = self.spec.kind == "futures" and type(self.feed).__name__ == "Databento"
        databento_primary = not hist and databento_feed
        databento_days = self._databento_history_days() if databento_feed else 0
        history_floor = now - databento_days * 86400 if databento_feed else None
        if databento_primary:
            provider_days = databento_days
        T_w = self.cal.bucket_start(now - span, 1440)
        if history_floor is not None:
            T_w = max(T_w, history_floor)
        self.T_w = T_w
        display_capacity = max(2000, self.cfg.warmup_bars)
        if provider_days:
            if getattr(self.cal, "session", "eth") == "rth":
                per_day = max(1, 405 // self.chart_minutes)
            else:
                per_day = max(1, (23 * 60) // self.chart_minutes)
            sessions = math.ceil(provider_days * 5 / 7)
            display_capacity = max(display_capacity, per_day * sessions + 2)
        display_capacity = min(50000, display_capacity)
        self.bars = collections.deque(self.bars, maxlen=display_capacity)
        self.overlays = collections.deque(self.overlays, maxlen=display_capacity)
        if hist:
            src = f"history/{os.path.basename(hist)} ({minutes}m)"
        elif file_feed_mode():
            src = f"HistoryHub ({base}/history) — no CSV yet, Yahoo is not contacted"
        else:
            src = self.spec.feed
        horizon = f", source horizon up to {provider_days}d" if provider_days else ""
        if databento_primary:
            horizon = f", Databento-only history up to {databento_days}d"
        self.journal.log("INFO", f"[{self.symbol}] warm-up requested from {time.strftime('%Y-%m-%d %H:%M', time.gmtime(T_w))}Z ({self.cfg.warmup_bars} x {self.chart_minutes}m bars requested{horizon}, {src}) mintick={self.mintick} x{self.spec.multiplier} slip={self.spec.slippage_ticks}t chart={self.spec.chart_type} fills={self.spec.fill_on} session={_session_mode(self.cal)} security={self.spec.security_source}" + (f" continuous={self.spec.tv_symbol or self.spec.ticker}" if self.spec.kind == "futures" else ""))
        if hist:
            self._warmup_from_csv(hist, now, source_minutes=minutes, history_floor=history_floor)
            self._file_waiting = False
        elif file_feed_mode():
            self._file_waiting = True
            self.journal.log("WARN", f"[{self.symbol}] ICARUS_FEED=file and no history/{self.symbol}_*m.csv — waiting for drop ingest; Yahoo is not contacted")
        elif self.spec.feed == "yahoo":
            self._warmup_yahoo(T_w, now, history_floor=history_floor)  # selected primary feed only; provider series are never stitched
            if databento_primary and not self.subbars:
                raise RuntimeError(f"[{self.symbol}] Databento returned no replay bars inside the configured history window")
        else:
            self._warmup_coinbase(T_w, now)
        self.live_from_ts = now
        self.live_closed_start = len(self.em.closed)
        self.warm = True
        if file_feed_mode() and self.last_sub_ts is None and not self._file_waiting:
            self.last_sub_ts = now  # a later drop must not replay years of history as live fills
        if self.last_price is None:
            self.last_price = self.feed.ticker(self.spec.ticker)
        self._refresh_performance_guard()
        self.journal.log("INFO", f"[{self.symbol}] warm-up done: {self.bar_index + 1} chart bars, {len(self.em.closed)} historical trades, net {self.em.netprofit:+.2f}; market {self.cal.describe(now)}")

    def reset_failed_startup_warmup(self) -> None:
        """Discard partial startup replay state before retrying a failed feed fetch."""
        with self.lock:
            self._build_engine()
            self.bar_index = -1
            self.bars.clear()
            self.overlays.clear()
            self.deep.clear()
            self.subbars.clear()
            self.state = {}
            self.live_from_ts = None
            self.live_closed_start = 0
            self.last_sub_ts = None
            self.last_price = None
            self.last_price_ts = 0.0
            self.last_bar_wall = 0.0
            self.last_poll_ok = 0.0
            self.feed_time = 0.0
            self.feed_delay = 0.0
            self.feed_error = ""
            self._fills_seen = 0
            self._closed_seen = 0
            self._file_waiting = False
            self.T_w = None
            self.warm = False
            self.rewarming = False
            # Publish the reset WARMING/error state. A failed source must stay
            # observable while the next retry waits, rather than emptying Main.
            self.publish_read_views()

    @staticmethod
    def _databento_history_days() -> int:
        raw = os.environ.get("ICARUS_DATABENTO_HISTORY_DAYS", "365").strip()
        try:
            days = int(raw)
        except ValueError as ex:
            raise ValueError("ICARUS_DATABENTO_HISTORY_DAYS must be an integer from 1 to 3650") from ex
        if not 1 <= days <= 3650:
            raise ValueError("ICARUS_DATABENTO_HISTORY_DAYS must be between 1 and 3650")
        return days

    def _closed_only(self, bars: List[Bar], ticker: str, *, feed: Any = None) -> List[Bar]:
        """Drop the feed's still-forming minute: closed <=> ts + 60 <= the feed's clock (regularMarketTime)."""
        source = feed if feed is not None else self.feed
        ft = int((getattr(source, "_meta", {}).get(ticker) or {}).get("regularMarketTime") or 0)
        if ft:
            self.feed_time = ft
            return [b for b in bars if b.ts + 60 <= ft]
        return bars[:-1] if bars else bars

    def _push_deep(self, ch: TFChain, b: Bar, sub_min: int) -> None:
        if not self.cal.is_open(b.ts):
            return
        if ch.minutes < 1440 and not self.cal.intraday_open(b.ts):
            return
        if ch.minutes < 1440 and self.cal.bucket_start(b.ts, sub_min) != b.ts:
            return                                                # a native bar not aligned to this chart's buckets (e.g. :00 hourly on a :30 chain)
        ch.push_sub_bar(b, sub_min)

    def _feed_deep(self, minutes_list: List[int], bars: List[Bar], sub_min: int) -> None:
        for m in minutes_list:
            ch = self.chains.get(m)
            if ch is None:
                continue
            self.deep.setdefault(m, []).extend((b, sub_min) for b in bars)
            for b in bars:
                self._push_deep(ch, b, sub_min)

    def _fetch_historical_candles(self, feed: Any, symbol: str, interval_seconds: int,
                                 start_ts: int, end_ts: int) -> List[Bar]:
        """Fetch one history batch, reject malformed rows, and retain its audit receipt."""
        fetched_at_ns = time.time_ns()
        bars = feed.candles(symbol, interval_seconds, start_ts, end_ts)
        received_at_ns = time.time_ns()
        adapter = feed
        visited = set()
        while id(adapter) not in visited:
            visited.add(id(adapter))
            wrapped = getattr(adapter, "_feed", None)
            if wrapped is None:
                break
            adapter = wrapped
        observed_symbol = None
        expected_provider_symbol = symbol
        # Yahoo embeds the requested symbol in the response metadata. Do not
        # infer identity for other adapters unless they expose an explicit field.
        if isinstance(adapter, Yahoo):
            metadata = adapter.meta(symbol)
            observed_symbol = metadata.get("symbol") or metadata.get("provider_symbol")
        elif isinstance(adapter, Databento):
            metadata = adapter.meta(symbol)
            expected_provider_symbol = adapter.continuous_symbol(symbol, adapter.roll_rule)
            observed_symbol = metadata.get("continuous_symbol")
        else:
            metadata = getattr(adapter, "_meta", {}).get(symbol, {})
            observed_symbol = metadata.get("provider_symbol") or metadata.get("symbol")
        provider = "databento" if isinstance(adapter, Databento) else (
            "yahoo" if isinstance(adapter, Yahoo) else self.spec.feed)
        instrument_id = f"icarus:{self.spec.kind}:{self.spec.symbol.upper()}"
        checked, receipt = make_bar_batch_receipt(
            instrument_id=instrument_id, provider=provider,
            expected_provider_symbol=expected_provider_symbol, observed_provider_symbol=observed_symbol,
            interval_seconds=interval_seconds, requested_start_ts=start_ts,
            requested_end_ts=end_ts, bars=bars, fetched_at_ns=fetched_at_ns,
            received_at_ns=received_at_ns, entitlement_status="UNKNOWN",
        )
        self.last_bar_batch_receipt = receipt.to_dict()
        self.bar_batch_receipts.append(self.last_bar_batch_receipt)
        if len(self.bar_batch_receipts) > 100:
            del self.bar_batch_receipts[:-100]
        return checked

    def _warmup_coinbase(self, T_w: int, now: int) -> None:
        cb = self.feed
        deep = {10080: (86400, 800 * 86400), 1440: (86400, 400 * 86400), 240: (3600, 45 * 86400), 120: (3600, 45 * 86400), 60: (3600, 45 * 86400),
                30: (900, 8 * 86400), 20: (300, 5 * 86400), 15: (900, 8 * 86400), 10: (300, 5 * 86400)}
        cache: Dict[Tuple[int, int], List[Bar]] = {}
        for m in self.chains:
            if m not in deep:
                continue
            g, depth = deep[m]
            key = (g, depth)
            if key not in cache:
                cache[key] = self._fetch_historical_candles(cb, self.spec.ticker, g, T_w - depth, T_w)
            self._feed_deep([m], cache[key], g // 60)
        ones = self._fetch_historical_candles(cb, self.spec.ticker, 60, T_w, now - 60)
        self.journal.log("INFO", f"[{self.symbol}] {len(ones)} one-minute candles fetched; replaying")
        for b in ones:
            self.on_sub_bar(b, 1, live=False)

    def _warmup_yahoo(self, T_w: int, now: int, *, history_floor: Optional[int] = None) -> None:
        y: Yahoo = self.feed
        tk = self.spec.ticker                                 # provider-native continuous symbol (e.g. NQ=F)
        tki = self.spec.ticker                                # intraday also stays continuous; no month-coded expiry contract
        bounded = lambda start: max(start, history_floor) if history_floor is not None else start
        daily_start = bounded(T_w - 900 * 86400)
        daily = self._fetch_historical_candles(y, tk, 86400, daily_start, T_w) if daily_start < T_w else []
        daily = [Bar(self.cal.bucket_start(b.ts, 1440), b.o, b.h, b.l, b.c, b.v) for b in daily]   # stamp at the session open
        self._feed_deep([m for m in self.chains if m >= 1440], daily, 1440)
        rth = getattr(self.cal, "session", "eth") == "rth"
        if rth:                                               # RTH hourly buckets sit at :30 - build them from 15-minute bars (60 days)
            hourly = []
        else:
            hourly_start = bounded(max(T_w - 400 * 86400, now - 729 * 86400))
            hourly = self._fetch_historical_candles(y, tki, 3600, hourly_start, T_w) if hourly_start < T_w else []
            self._feed_deep([m for m in self.chains if 60 <= m < 1440], hourly, 60)
        q15_start = bounded(max(T_w - 40 * 86400, now - 59 * 86400))
        q15 = self._fetch_historical_candles(y, tki, 900, q15_start, T_w) if q15_start < T_w else []
        self._feed_deep([m for m in self.chains if 15 <= m < 1440 and m % 15 == 0 and (rth or m < 60)], q15, 15)
        fives_deep_start = bounded(max(T_w - 20 * 86400, now - 59 * 86400))
        fives_deep = self._fetch_historical_candles(y, tki, 300, fives_deep_start, T_w) if fives_deep_start < T_w else []
        self._feed_deep([m for m in self.chains if 5 <= m < 15 and m % 5 == 0], fives_deep, 5)
        one_from = bounded(max(T_w, now - 29 * 86400))
        fives = self._fetch_historical_candles(y, tki, 300, bounded(T_w), one_from) if one_from > bounded(T_w) else []
        ones = self._closed_only(self._fetch_historical_candles(y, tki, 60, one_from, now), tki) if one_from < now else []
        self.journal.log("INFO", f"[{self.symbol}] deep {len(daily)}d/{len(hourly)}h/{len(q15)}x15m/{len(fives_deep)}x5m; {len(fives)} five-minute + {len(ones)} one-minute sub-bars; replaying")
        for b in fives:
            self.on_sub_bar(b, 5, live=False)
        for b in ones:
            if fives and b.ts < fives[-1].ts + 300:
                continue
            self.on_sub_bar(b, 1, live=False)

    def _warmup_from_csv(
        self, path: str, now: int, source_minutes: Optional[int] = None,
        *, history_floor: Optional[int] = None,
    ) -> None:
        """Warm up from a TradingView Supercharts export (or canonical history/*.csv).

        Grok (xAI) — 2026-09-20. Prefer a 1-minute dump: HTF/LTF chains then
        aggregate the same way live 1m sub-bars do. A chart-TF export is accepted
        as a fallback (HTF built from those coarser bars). The live feed, if it
        answers, fills the tail after the last exported bar. No interpolated ticks.
        """
        rows = parse_ohlcv_csv(read_text_csv(path))
        if source_minutes is None:
            source_minutes = max(1, detect_granularity(rows) // 60)
        source_minutes = int(source_minutes)
        display_capacity = min(50000, max(self.bars.maxlen, len(rows)))
        if display_capacity > self.bars.maxlen:
            self.bars = collections.deque(self.bars, maxlen=display_capacity)
            self.overlays = collections.deque(self.overlays, maxlen=display_capacity)
        span = (
            time.strftime("%Y-%m-%d", time.gmtime(rows[0].ts)) + " → " +
            time.strftime("%Y-%m-%d", time.gmtime(rows[-1].ts))
        ) if rows else "-"
        how = "HTF chains from 1m" if source_minutes == 1 else "chart bars from the export, HTF built from them"
        self.journal.log("INFO", f"[{self.symbol}] history/{os.path.basename(path)}: {len(rows)} {source_minutes}m bars ({span}); {how}")
        for b in rows:
            self.on_sub_bar(b, source_minutes, live=False)
        if rows:
            self.T_w = rows[0].ts
            if file_feed_mode():
                return  # Grok (xAI) — offline plant: the CSV is the whole tape; do not call Yahoo for a tail
            tail_from = rows[-1].ts + source_minutes * 60
            try:
                tail_start = max(tail_from, now - 29 * 86400)
                if history_floor is not None:
                    tail_start = max(tail_start, history_floor)
                ones = self._fetch_historical_candles(self.feed, self.spec.ticker, 60, tail_start, now)
                if self.spec.feed == "yahoo":
                    ones = self._closed_only(ones, self.spec.ticker)
                for b in ones:
                    if b.ts < tail_from:
                        continue
                    self.on_sub_bar(b, 1, live=False)
            except Exception as ex:
                self.journal.log("WARN", f"[{self.symbol}] could not fetch the 1-minute tail after the export: {ex}")

    def configuration_snapshot(self) -> Dict[str, Any]:
        """Exact in-memory state needed to make a failed configuration change a no-op."""
        return {
            "spec": copy.deepcopy(self.spec),
            "cfg_inputs": self.cfg.inputs,
            "cfg_sources": list(self.cfg.sources or []),
            "cfg_fixed_pts_scale": self.cfg.fixed_pts_scale,
            "cfg_scale_known_at": self.cfg.scale_known_at,
            "cfg_preset": self.cfg.preset,
            "inputs_base": self.inputs_base,
            "inputs": self.inputs,
            "pts_scale": self.pts_scale,
            "cal": self.cal,
            "chart_minutes": self.chart_minutes,
            "chart_mode": self.chart_mode,
            "chart_value": self.chart_value,
            "chart_seconds": self.chart_seconds,
            "event_minute_agg": self.event_minute_agg,
            "event_chart_agg": self.event_chart_agg,
            "_event_chart_session": self._event_chart_session,
            "_public_views": self._public_views,
            "em": self.em,
            "strat": self.strat,
            "htf_tfs": list(self.htf_tfs),
            "chains": self.chains,
            "chart_agg": self.chart_agg,
            "ha": self.ha,
            "_real_ohlc_warned": self._real_ohlc_warned,
            "bar_index": self.bar_index,
            "bars": collections.deque(self.bars, maxlen=self.bars.maxlen),
            "overlays": collections.deque(self.overlays, maxlen=self.overlays.maxlen),
            "state": self.state,
            "live_from_ts": self.live_from_ts,
            "live_closed_start": self.live_closed_start,
            "last_sub_ts": self.last_sub_ts,
            "last_price": self.last_price,
            "last_price_ts": self.last_price_ts,
            "last_bar_wall": self.last_bar_wall,
            "_fills_seen": self._fills_seen,
            "_closed_seen": self._closed_seen,
            "recent_fills": collections.deque(self.recent_fills, maxlen=self.recent_fills.maxlen),
            "recent_events": collections.deque(self.recent_events, maxlen=self.recent_events.maxlen),
            "runtime_error": self.runtime_error,
            "last_error": self.last_error,
        }

    def restore_configuration_snapshot(self, snap: Dict[str, Any]) -> None:
        """Restore a snapshot without replaying, preserving exact paper accounting."""
        self.spec.__dict__.clear()
        self.spec.__dict__.update(copy.deepcopy(snap["spec"].__dict__))
        self.cfg.spec = self.spec
        self.cfg.inputs = snap["cfg_inputs"]
        self.cfg.sources = list(snap["cfg_sources"])
        self.cfg.fixed_pts_scale = snap["cfg_fixed_pts_scale"]
        self.cfg.scale_known_at = snap["cfg_scale_known_at"]
        self.cfg.preset = snap["cfg_preset"]
        self.inputs_base = snap["inputs_base"]
        self.inputs = snap["inputs"]
        self.pts_scale = snap["pts_scale"]
        for name in ("cal", "chart_minutes", "chart_mode", "chart_value", "chart_seconds",
                     "event_minute_agg", "event_chart_agg", "_event_chart_session", "_public_views",
                     "em", "strat", "chains", "chart_agg", "ha", "_real_ohlc_warned",
                     "bar_index", "state", "live_from_ts", "live_closed_start", "last_sub_ts", "last_price",
                     "last_price_ts", "last_bar_wall", "_fills_seen", "_closed_seen", "runtime_error", "last_error"):
            setattr(self, name, snap[name])
        self.htf_tfs = list(snap["htf_tfs"])
        self.bars = collections.deque(snap["bars"], maxlen=snap["bars"].maxlen)
        self.overlays = collections.deque(snap["overlays"], maxlen=snap["overlays"].maxlen)
        self.recent_fills = collections.deque(snap["recent_fills"], maxlen=snap["recent_fills"].maxlen)
        self.recent_events = collections.deque(snap["recent_events"], maxlen=snap["recent_events"].maxlen)
        self.rewarming = False

    # ── re-warm with new inputs (no network) ──
    def rewarm(self, inputs: Inputs, sources: Optional[List[str]] = None, *, reset_live_boundary: bool = False, _publish_views: bool = True) -> None:
        with self.lock:
            self.ensure_configurable()
            self.ensure_cached_timeframes(inputs)
            if _publish_views:
                self.publish_read_views()
            self.rewarming = True
            try:
                self.cfg.fixed_pts_scale = self.pts_scale
                self.cfg.inputs = inputs
                self.inputs_base = inputs
                if sources is not None:
                    self.cfg.sources = sources
                self._build_engine()
                self.bar_index = -1
                self.bars.clear(); self.overlays.clear(); self.recent_fills.clear(); self.recent_events.clear()
                self._fills_seen = 0; self._closed_seen = 0; self.last_sub_ts = None; self.state = {}
                for m, rows in self.deep.items():
                    ch = self.chains.get(m)
                    if ch:
                        for b, sub in rows:
                            self._push_deep(ch, b, sub)
                for b, sub in list(self.subbars):
                    self.on_sub_bar(b, sub, live=False, record=False)
                if reset_live_boundary:
                    self.live_from_ts = int(time.time())
                    self.live_closed_start = len(self.em.closed)
                self.journal.log("INFO", f"[{self.symbol}] re-warmed with new inputs: {self.bar_index + 1} chart bars, {len(self.em.closed)} historical trades, net {self.em.netprofit:+.2f}")
                self.runtime_error = ""
                self.last_error = self.feed_error
            finally:
                self.rewarming = False

    # ── live polling ──
    def _feed_delay_at(self, now: int) -> float:
        """The feed's lag behind the wall clock - meaningful only while the market trades (the feed clock stops at the close)."""
        if self.spec.feed != "yahoo" or not self.cal.is_open(now):
            return 0.0
        return self.feed_delay

    def _feed_failed(self, message):
        with self.lock:
            if self._removed:
                return
            self.errors += 1
            self.feed_error = str(message)
            self.last_error = self.runtime_error or self.feed_error

    def poll(self) -> None:
        now = time.time()
        with self.lock:
            if self._removed:
                return
        if file_feed_mode() and self._file_waiting:
            base = self.cfg.base_dir or os.getcwd()
            hist, minutes = find_history(base, self.symbol, self.chart_minutes)
            if hist:
                with self.lock:
                    if self._removed:
                        return
                    self._warmup_from_csv(hist, int(now), source_minutes=minutes)
                    self._file_waiting = False
                    if self.last_price is None:
                        self.last_price = self.feed.ticker(self.spec.ticker)
            return
        feed_now = now
        px = None
        ft = 0
        try:
            source_seconds = getattr(self.feed, "native_interval_seconds", 60)
            if (type(source_seconds) is not int or not 60 <= source_seconds <= 86400
                    or source_seconds % 60 or self.chart_minutes * 60 % source_seconds):
                raise ValueError("feed native interval cannot supply the configured chart without inventing finer bars")
            if self.spec.feed == "yahoo":
                bars, ft, px = self.feed.recent_ex(self.spec.ticker, source_seconds, since_ts=self.last_sub_ts)
                if not ft:                                          # no feed clock in the response: the last aligned minute is the only safe clock
                    ft = (bars[-1].ts + source_seconds) if bars else int(self.feed_time or 0)
            else:
                bars = self.feed.recent(self.spec.ticker, source_seconds)
        except Exception as ex:
            if self.spec.feed == "coinbase":
                try:
                    bars = self.kraken.recent(self.spec.ticker, 1)
                    source_seconds = 60
                except Exception as ex2:
                    self._feed_failed(f"{ex} / {ex2}"); return
            else:
                self._feed_failed(str(ex)); return
        # Provider I/O runs without the runner lock. Removal may complete while
        # that request is in flight; a retired runner must not mutate afterward.
        with self.lock:
            if self._removed:
                return
            if self.spec.feed == "yahoo":
                if not ft:
                    if not self.cal.is_open(int(now)):
                        self.last_poll_ok = now
                        if self.feed_error and self.last_error == self.feed_error:
                            self.last_error = self.runtime_error
                        self.feed_error = ""
                        return
                    self._feed_failed("feed returned no clock and no bars")
                    return
                self.feed_time = ft
                feed_now = ft  # Close on the source clock, never on wall time.
                self.feed_delay = now - ft
            closed_before = feed_now if self.spec.feed == "yahoo" else now - 5
            closed_rows = [b for b in bars if b.ts + source_seconds <= closed_before]
            new = [b for b in closed_rows if self.last_sub_ts is None or b.ts > self.last_sub_ts]
            if new:
                from .corpus_intake import CorpusDataset
                dataset = getattr(self.feed, "dataset", None)
                if isinstance(dataset, CorpusDataset):
                    # Native reads cannot bypass the corpus feed's same-contract
                    # gate merely because the chart aggregates those rows later.
                    contracts = {bar.ts: identity for bar, identity in zip(dataset.bars, dataset.contract_ids)}
                    identities = {contracts.get(bar.ts) for bar in new}
                    if self.last_sub_ts is not None:
                        identities.add(contracts.get(self.last_sub_ts))
                    if None in identities or len(identities) != 1:
                        self._feed_failed("corpus strategy polling requires one verified contract identity; context reads remain available")
                        return
            for b in new:
                self.on_sub_bar(b, source_seconds // 60, live=True)
            for ch in self.chains.values():
                ch.flush_if_stale(feed_now - 45)
            stale = self.chart_agg.flush_if_stale(feed_now - 45)
            if stale is not None:
                self._on_chart_bar(stale, True)
            if source_seconds > 60:
                # Coarse-source quotes have no separate observation timestamp.
                # Use only a demonstrably closed row for strategy valuation.
                px = closed_rows[-1].c if closed_rows else None
            elif px is None and bars:
                px = bars[-1].c
            if px:
                self.last_price = px
                self.last_price_ts = feed_now
            self.last_poll_ok = now
            if self.feed_error and self.last_error == self.feed_error:
                self.last_error = self.runtime_error
            self.feed_error = ""

    # ── admin ──
    def _cancel_pending_entries(self) -> int:
        """Caller holds lock. Keep exits/close orders protecting existing positions."""
        pending = list(self.em._pending_entries)
        ids = {p.id for p in pending}
        if isinstance(self.em, MirroredEmulator):
            # A limit may fill in the primary while it remains pending in the
            # real-price lane. Admin pause/flatten still has to cancel that
            # shadow-only remainder before processing another bar.
            ids.update(p.id for p in self.em.shadow._pending_entries)
            self.em.cancel_pending_entries(ids)
        else:
            self.em._pending_entries.clear()
            for eid, order in list(self.em._exits.items()):
                if order.from_entry in ids and not self.em.qty_open(order.from_entry):
                    self.em._exits.pop(eid)
            self.em._pending_closes[:] = [c for c in self.em._pending_closes
                                         if c.entry_id not in ids or self.em.qty_open(c.entry_id)]
        if self.strat is not None:
            # RATE snapshots are appended when intent is submitted. Filled/closed
            # positions still own the earlier queue entries; only remove the tail.
            for _ in (p for p in pending if p.id in ("Long", "Short")):
                if self.strat.w_slot_queue:
                    self.strat.w_slot_queue.pop()
                if self.strat.tod_hour_queue:
                    self.strat.tod_hour_queue.pop()
            self.strat.rate_pend_dir = 0
            self.strat.rate_pend_bar = -999
        return len(ids)

    def set_paused(self, paused: bool) -> int:
        with self.lock:
            if not paused and getattr(self, "_activation_quarantine", None):
                raise ValueError(f"{self.symbol}: activation recovery is required before resuming entries")
            if not paused and getattr(self, "_performance_guard", {}).get("status") == "PRESSURE":
                raise ValueError(f"{self.symbol}: rolling live paper win rate is below 75%; qualify and activate a reviewed replacement before resuming")
            self.paused = paused
            if self.strat is not None:
                self.strat.paused = paused
            return self._cancel_pending_entries() if paused else 0

    def _refresh_performance_guard(self) -> None:
        """Review settled live paper lots and pause new entries under the 75% floor."""
        report = self.journal.performance_review(self.symbol, since_ts=self._performance_guard_since_ts)
        scorecards = report["scorecards"]
        pressure = {regime: row for regime, row in scorecards.items() if row["status"] == "PRESSURE"}
        prior = getattr(self, "_performance_guard", {})
        status = "PRESSURE" if pressure else ("WATCH" if any(x["status"] == "WATCH" for x in scorecards.values())
                                               else ("HEALTHY" if scorecards else "INSUFFICIENT_SAMPLE"))
        self._performance_guard = {**report, "status": status, "pressure_regimes": sorted(pressure)}
        if pressure and not self.paused:
            self.paused = True
            if self.strat is not None:
                self.strat.paused = True
            cancelled = self._cancel_pending_entries()
            self.journal.log("ERROR", f"[{self.symbol}] performance pressure: rolling paper win rate below 75% "
                             f"for regime(s) {', '.join(sorted(pressure))}; new entries paused, {cancelled} pending intent(s) cancelled")
        elif status != prior.get("status"):
            self.journal.log("INFO", f"[{self.symbol}] rolling paper performance review: {status}")

    def ensure_configurable(self, *, allow_overlay: bool = False) -> None:
        """Must be called while holding lock, before any configuration mutation."""
        if not allow_overlay and (getattr(self, "_activation_version_id", None)
                                  or getattr(self, "_activation_quarantine", None)):
            raise ValueError(f"{self.symbol}: roll back or recover the activation overlay before changing configuration")
        if not self.warm:
            raise ValueError(f"{self.symbol}: initial warm-up must finish before changing configuration")
        if self.em.open or self.em._pending_entries or self.em._pending_closes:
            raise ValueError(f"{self.symbol}: flatten open positions and cancel pending orders before changing configuration")
        if self.rewarming:
            raise ValueError(f"{self.symbol}: configuration replay already running")

    def ensure_cached_timeframes(self, inputs: Inputs) -> None:
        requested = {tf_minutes(getattr(inputs, f"htf_tf_{n}")) for n in range(1, 6)}
        available = set(self.chains) | {m for m, rows in self.deep.items() if rows}
        missing = requested - available
        if missing:
            raise ValueError(f"{self.symbol}: cached history unavailable for requested HTF minutes {sorted(missing)}; fetch compatible history first")


    def ensure_cached_chart_timeframe(self, timeframe: object) -> str:
        """Prove the cache contains genuine bars fine enough for the requested chart.

        Mixed caches are valid: e.g. Yahoo may retain older 5m bars for HTF state
        plus a recent 1m tail. For a 1m/2m chart the 5m rows still feed compatible
        HTF chains, while the chart aggregator naturally ignores them. No finer
        chart bars are synthesized from coarser data.
        """
        tf = normalize_chart_timeframe(timeframe)
        minutes = tf_minutes(tf)
        if minutes == self.chart_minutes:
            return tf
        if not self.subbars:
            raise ValueError(f"{self.symbol}: no cached sub-bars are available to rebuild a {tf} chart")
        compatible = [(b, int(sub)) for b, sub in self.subbars if int(sub) <= minutes and minutes % int(sub) == 0]
        if not compatible:
            have = sorted({int(sub) for _, sub in self.subbars})
            raise ValueError(
                f"{self.symbol}: cached source bars {have}m cannot be losslessly rebuilt as {tf}; "
                "load 1-minute history first"
            )
        return tf

    def chart_capability_view(self) -> Dict[str, Any]:
        """Static engine support plus what the current cached tape can rebuild now."""
        caps = dict(chart_capabilities())
        have = sorted({int(sub) for _, sub in self.subbars})
        available: List[str] = []
        for tf in caps["timeframes"]:
            minutes = tf_minutes(tf)
            if minutes == self.chart_minutes or any(sub <= minutes and minutes % sub == 0 for sub in have):
                available.append(tf)
        caps["available_from_cache"] = available
        caps["cached_source_resolutions_minutes"] = have
        caps["current_timeframe"] = self.spec.chart_tf
        return caps

    def flatten(self, reason: str = "manual") -> int:
        with self.lock:
            cancelled = self._cancel_pending_entries()
            open_positions = list(self.em.open)
            if isinstance(self.em, MirroredEmulator):
                open_positions.extend(self.em.shadow.open)
            entry_ids = {t.entry_id for t in open_positions}
            has_primary_open = bool(self.em.open)
            has_shadow_open = isinstance(self.em, MirroredEmulator) and bool(self.em.shadow.open)
            has_open = has_primary_open or has_shadow_open
            if has_primary_open and (self.last_price is None or not math.isfinite(float(self.last_price))):
                raise FlattenUnavailableError(
                    f"[{self.symbol}] cannot flatten open positions: no finite last market price is available")
            for entry_id in entry_ids:
                comment = "FLAT_" + reason.upper()[:8]
                if isinstance(self.em, MirroredEmulator):
                    # The operator close is not a standard-price market event.
                    # Close the authoritative primary and censor the mirrored
                    # hypothetical position in the explicit admin path below.
                    self.em.primary.close(entry_id, comment=comment)
                else:
                    self.em.close(entry_id, comment=comment)
            if has_open:
                if isinstance(self.em, MirroredEmulator):
                    fake = None
                    if has_primary_open:
                        mark = float(self.last_price)
                        fake = Bar(int(time.time()), mark, mark, mark, mark, 0.0)
                    self.em.process_administrative_flatten(
                        fake, self.bar_index, entry_ids, reason=reason)
                else:
                    mark = float(self.last_price)
                    fake = Bar(int(time.time()), mark, mark, mark, mark, 0.0)
                    self.em.process_bar(fake, self.bar_index)
                self._record_new_execution(live=True)
                self.publish_read_views()
            self.journal.log("WARN", f"[{self.symbol}] FLATTEN ({reason}): {len(entry_ids)} position(s), {cancelled} pending entry intent(s) cancelled")
            return len(entry_ids)

    def export_csv(self) -> str:
        with self.lock:
            return self._export_csv()

    def _export_csv(self) -> str:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Trade #", "Type", "Date/Time (UTC)", "Signal", "Price", "Contracts", "Profit", "Cum. Profit", "Live"])
        cum = 0.0
        for k, t in enumerate(self.em.closed, 1):
            cum += t.profit
            side = "long" if t.direction > 0 else "short"
            live = int(self.live_from_ts is not None and (k - 1) >= self.live_closed_start)
            w.writerow([k, f"Entry {side}", time.strftime("%Y-%m-%d %H:%M", time.gmtime(t.entry_ts)), t.entry_comment or t.entry_id, f"{t.entry_price:.10g}", t.qty, "", "", live])
            w.writerow([k, f"Exit {side}", time.strftime("%Y-%m-%d %H:%M", time.gmtime(t.exit_ts)), t.exit_comment, f"{t.exit_price:.10g}", t.qty, f"{t.profit:.2f}", f"{cum:.2f}", live])
        return buf.getvalue()

    # ── views ──
    def market(self) -> Dict[str, Any]:
        now = int(time.time())
        return {"open": self.cal.is_open(now), "calendar": self.cal.name, "describe": self.cal.describe(now),
                "next_open": self.cal.next_open(now), "session": self.cal.session_id(now)}

    def publish_read_views(self) -> None:
        """Publish immutable display-only views while holding the runner lock."""
        captured = time.time()
        self._public_views = ((self._summary(), captured), (self._chart(self.bars.maxlen), captured))

    def _busy_read_view(self, index: int) -> Dict[str, Any]:
        views = self._public_views
        if views is None or views[index] is None:
            raise RuntimeError(f"{self.symbol}: initial view is not ready; retry shortly")
        row = copy.deepcopy(views[index][0])
        row.update(view_stale=True, view_captured_at=views[index][1], rewarming=self.rewarming)
        return row

    def summary(self, *, nonblocking: bool = False) -> Dict[str, Any]:
        if not nonblocking:
            with self.lock:
                return self._summary()
        views = self._public_views
        if views is None or views[0] is None:
            raise RuntimeError(f"{self.symbol}: initial view is not ready; retry shortly")
        source, captured = views[0]
        row = copy.deepcopy(source)
        elapsed = time.time() - captured
        acquired = self.lock.acquire(blocking=False)
        if acquired:
            self.lock.release()
        row.update(view_cached=True, view_captured_at=captured,
                   view_stale=not acquired or self.rewarming or elapsed < 0 or elapsed > 90,
                   view_age=max(0.0, elapsed), view_age_adjusted=True, rewarming=self.rewarming)
        # These scalar lifecycle/error observations do not require an emulator
        # scan. Keep their receipt distinct from the older market-data view.
        row.update(paused=self.paused, errors=self.errors, last_error=self.last_error,
                   runtime_state_observed_at=time.time())
        for key in ("price_age", "bar_age", "poll_age"):
            age = row.get(key)
            if type(age) in (int, float) and math.isfinite(age) and age >= 0:
                row[key] = age + max(0.0, elapsed)
        return row

    def _feed_health_view(self) -> Dict[str, Any]:
        """Return provider health from memory only; status endpoints must never do I/O."""
        cached_meta = getattr(self.feed, "cached_meta", None)
        if callable(cached_meta):
            return cached_meta(self.spec.ticker)
        if type(self.feed).__name__ == "Databento" and hasattr(self.feed, "meta"):
            return self.feed.meta(self.spec.ticker)
        cached = getattr(self.feed, "_meta", None)
        if isinstance(cached, dict):
            value = cached.get(self.spec.ticker, {})
            return dict(value) if isinstance(value, dict) else {}
        return {}

    def _trade_learning_context(self, entry_regime: Optional[str] = None) -> Dict[str, Any]:
        """Immutable configuration receipt captured when a trade piece closes."""
        inputs_payload = _clean(self.inputs_base.to_dict())
        inputs_json = json.dumps(inputs_payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        inputs_hash = hashlib.sha256(inputs_json.encode("utf-8")).hexdigest()
        scope = _clean({
            "asset": self.symbol,
            "provider_symbol": self.spec.ticker,
            "continuous_symbol": self.spec.tv_symbol or self.spec.ticker,
            "chart_type": self.spec.chart_type,
            "timeframe": self.spec.chart_tf,
            "fill_on": self.spec.fill_on,
            "security_source": self.spec.security_source,
            "session_mode": _session_mode(self.cal),
            "profile": self.cfg.profile,
            "preset": self.cfg.preset or self.spec.preset,
            "slippage_ticks": self.spec.slippage_ticks,
            "commission": self.spec.commission,
            "multiplier": self.spec.multiplier,
            "mintick": self.mintick,
            "pts_scale": self.pts_scale,
            "inputs_hash": inputs_hash,
        })
        raw = json.dumps(scope, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return {
            **scope,
            "strategy_fingerprint": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            "provenance_quality": "CLOSURE_TIME_CONFIG",
            "regime": str(entry_regime or (self.state or {}).get("rate_regime_str") or "unknown"),
            "regime_attribution": "entry_fill_previous_closed_bar" if entry_regime else "closure_time_fallback",
        }

    def _summary(self) -> Dict[str, Any]:
        st = self.state or {}
        mark = self.last_price or (self.bars[-1].c if self.bars else None)
        open_trades = [{"id": t.entry_id, "dir": t.direction, "qty": t.qty, "qty_orig": t.qty_orig, "entry": t.entry_price, "entry_ts": t.entry_ts,
                        "upl": (t.direction * (mark - t.entry_price) * t.qty * self.em.contract_size) if mark else None} for t in self.em.open]
        live_trades = self.em.closed[self.live_closed_start:] if self.live_from_ts is not None else []
        wins = sum(1 for t in self.em.closed if t.profit > 0)
        forming = self.chart_agg.forming_bar()
        return _clean({
            "symbol": self.symbol, "name": self.spec.name, "product": self.spec.ticker, "feed": self.spec.feed, "kind": self.spec.kind,
            "continuous_contract": bool(self.spec.kind == "futures"), "contract_policy": "continuous_only" if self.spec.kind == "futures" else "not_applicable",
            "continuous_symbol": self.spec.tv_symbol or self.spec.ticker,
            "provider_symbol": self.spec.ticker,
            "feed_provider": getattr(self.feed, "provider_name", None) or (
                "databento" if type(self.feed).__name__ == "Databento" else self.spec.feed),
            "feed_capabilities": (self.feed.capabilities() if hasattr(self.feed, "capabilities") else {}),
            "feed_health": self._feed_health_view(),
            "last_bar_batch_receipt": self.last_bar_batch_receipt,
            "bar_batch_receipts": list(self.bar_batch_receipts),
            "session_mode": _session_mode(self.cal), "security_source": self.spec.security_source,
            "tf": self.chart_minutes, "mintick": self.mintick, "contract_size": self.em.contract_size, "multiplier": self.spec.multiplier,
            "chart_type": self.spec.chart_type, "fill_on": self.spec.fill_on, "slippage_ticks": self.spec.slippage_ticks,
            "calculation_basis": {
                "timeframe": self.spec.chart_tf, "timeframe_minutes": self.chart_minutes,
                "chart_type": self.spec.chart_type, "fill_on": self.spec.fill_on,
                "security_source": self.spec.security_source, "session": _session_mode(self.cal),
            },
            "chart_capabilities": self.chart_capability_view(),
            "preset": self.cfg.preset or self.spec.preset, "inputs_sources": self.cfg.sources or [], "pts_scale": self.pts_scale,
            "price": mark, "price_age": (time.time() - self.last_price_ts) if self.last_price_ts else None,
            "feed_delay": self._feed_delay_at(int(time.time())),
            "warm": self.warm, "rewarming": self.rewarming, "paused": self.paused, "errors": self.errors, "last_error": self.last_error,
            "poll_age": (time.time() - self.last_poll_ok) if self.last_poll_ok else None,
            "bar_age": (time.time() - self.last_bar_wall) if self.last_bar_wall else None,
            "bar_index": self.bar_index, "last_bar_ts": self.bars[-1].ts if self.bars else None,
            "market": self.market(),
            "forming": (forming.__dict__ if forming else None),
            "equity": self.em.equity(mark), "capital": self.spec.capital, "netprofit": self.em.netprofit,
            "open_profit": self.em.open_profit(mark) if mark else 0.0, "position": self.em.position_size,
            "open_trades": open_trades, "exits": self.em.live_exits(), "pending": self.em.pending_view(),
            "real_price_shadow": ({**self.em.summary(live_from_ts=self.live_from_ts),
                                   "primary_fill_basis": self.spec.fill_on,
                                   "provenance": {
                                       "instrument_id": self.symbol,
                                       "provider_symbol": self.spec.ticker,
                                       "asset_kind": self.spec.kind,
                                       "price_provider": (
                                           "file_history_hub" if file_feed_mode() else
                                           "databento" if type(self.feed).__name__ == "Databento" else
                                           self.spec.feed),
                                       "feed_mode": (
                                           "file" if file_feed_mode() else
                                           "databento" if type(self.feed).__name__ == "Databento" else
                                           "provider"),
                                       "timeframe_minutes": self.chart_minutes,
                                       "calendar": self.cal.name,
                                       "session_mode": _session_mode(self.cal),
                                       "chart_type": self.spec.chart_type,
                                       "primary_fill_basis": self.spec.fill_on,
                                       "shadow_fill_basis": "standard_real_ohlc",
                                       "security_source": self.spec.security_source,
                                       "feed_health": self._feed_health_view(),
                                   }}
                                  if isinstance(self.em, MirroredEmulator) else None),
            "trades_total": len(self.em.closed), "wins_total": wins,
            "performance_guard": getattr(self, "_performance_guard", {"status": "INSUFFICIENT_SAMPLE", "scorecards": {}}),
            "live_trades": len(live_trades), "live_profit": sum(t.profit for t in live_trades),
            "state": {k: st.get(k) for k in ("ts", "c", "rate_uptrend", "rate_st_line", "rate_regime", "rate_regime_str", "hurst", "fdi",
                                             "rate_adx", "atr14", "armed_long", "armed_short", "bars_since_flip", "htf_dirs", "htf_bull", "htf_bear",
                                             "ltf", "votes", "final_l", "final_s", "eff_thresh", "gate_long", "gate_short", "conf_long", "conf_short",
                                             "entry_allowed", "in_session", "diverge_veto_l", "diverge_veto_s", "cycle_rising", "phase_deg", "vwap", "kf_vel",
                                             "pe_norm", "trc", "po3", "struct_bias", "pd_zone", "tide_hi", "tide_lo", "tide_broke_above",
                                             "tide_broke_below", "tide_inrange_closes", "pulse_l", "pulse_s", "pulse_state", "shock_mult",
                                             "families_l", "families_s", "rate_qty_open", "rate_pos_long", "rate_avg_price", "rate_qty_plan",
                                             "rate_tp1_done", "rate_be_armed", "runner_stop", "runner_tag", "tp1_price", "tp2_price", "sl_price",
                                             "h4_qty_open", "h4_pos_long", "h4_avg_price", "exec", "bars_since_stop", "daily_pnl",
                                             "w_trade_count", "active_votes", "avg_weight", "tp1_dist", "tp2_dist", "sl_dist")},
            "chains": {str(m): ch.state() for m, ch in self.chains.items()},
            "htf_tfs": self.htf_tfs,
        })

    def chart(self, n: int = 240, *, offset: int = 0, nonblocking: bool = False) -> Dict[str, Any]:
        n = max(1, min(int(n), 5000))
        offset = max(0, min(int(offset), 50000))
        def page(row: Dict[str, Any]) -> Dict[str, Any]:
            total = len(row["bars"])
            end = max(0, total - offset)
            start = max(0, end - n)
            row["bars"] = row["bars"][start:end]
            row["overlays"] = row["overlays"][start:end]
            row["fills"] = [f for f in row["fills"] if row["bars"] and row["bars"][0][0] <= f["ts"] <= row["bars"][-1][0]]
            row["history"] = {"available": total, "offset": offset, "page_size": n, "has_older": start > 0, "has_newer": offset > 0}
            return row
        if not nonblocking:
            with self.lock:
                return page(self._chart(self.bars.maxlen))
        if not self.lock.acquire(timeout=0.05):
            row = self._busy_read_view(1)
            return page(row)
        try:
            row = self._chart(self.bars.maxlen)
            views = self._public_views or (None, None)
            self._public_views = (views[0], (row, time.time()))
        finally:
            self.lock.release()
        return page(copy.deepcopy(row))

    def _chart(self, n: int = 240) -> Dict[str, Any]:
        bars = list(self.bars)[-n:]
        ov = list(self.overlays)[-n:]
        fills = [f for f in self.recent_fills if bars and f["ts"] >= bars[0].ts]
        forming = self.chart_agg.forming_bar()
        f_row = None
        if forming:
            f_row = [forming.ts, forming.o, forming.h, forming.l, self.last_price or forming.c, forming.v]
        elif bars and self.last_price and self.last_price_ts and self.cal.intraday_open(int(self.last_price_ts)):
            nb = self.cal.bucket_start(int(self.last_price_ts), self.chart_minutes)
            if nb > bars[-1].ts:
                f_row = [nb, self.last_price, self.last_price, self.last_price, self.last_price, 0.0]
        return _clean({"symbol": self.symbol, "tf": self.chart_minutes, "mintick": self.mintick,
                       "chart_type": self.spec.chart_type, "fill_on": self.spec.fill_on,
                       "security_source": self.spec.security_source, "session": _session_mode(self.cal),
                       "bars": [[b.ts, b.o, b.h, b.l, b.c, b.v] for b in bars], "forming": f_row,
                       "overlays": ov, "fills": fills, "live_from": self.live_from_ts})

    def trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        out = []
        start = max(0, len(self.em.closed) - limit)
        for idx, t in enumerate(self.em.closed[start:], start=start):
            out.append({"id": t.entry_id, "dir": t.direction, "qty": t.qty, "entry": t.entry_price, "entry_ts": t.entry_ts, "exit": t.exit_price,
                        "exit_ts": t.exit_ts, "comment": t.exit_comment, "profit": t.profit, "kind": t.exit_kind,
                        "live": self.live_from_ts is not None and idx >= self.live_closed_start})
        return out


# ──────────────────────────────────────────────────────────────────────
# Portfolio
# ──────────────────────────────────────────────────────────────────────
class Portfolio:
    def __init__(self, journal: Journal, base_dir: str, poll_sec: float = 5.0, profile: str = "nq",
                 preset: Optional[str] = None, warmup_bars: int = 1200, pts_ref_symbol: str = "NQ",
                 feeds: Optional[Dict[str, Any]] = None, shadow_real_fills: bool = False):
        self.journal = journal
        self.base_dir = base_dir
        self.poll_sec = poll_sec
        self.profile = profile
        self.preset = preset
        self.warmup_bars = warmup_bars
        self.shadow_real_fills = bool(shadow_real_fills)
        self.pts_ref_symbol = pts_ref_symbol
        self.pts_ref_price = 0.0
        # ICARUS_FEED selects the market-data transport without changing stable AssetSpec
        # identities. Futures remain continuous-only regardless of provider.
        self._owns_feeds = feeds is None
        requested_feed = os.environ.get("ICARUS_FEED", "").strip().lower()
        if feeds is not None:
            self.feeds = feeds
            self.feed_mode = "file" if file_feed_mode() else ("databento" if requested_feed == "databento" else "live")
            self.feeds.setdefault("databento_history", None)
        elif file_feed_mode():
            hub = HistoryHub(base_dir)
            self.feeds = {"yahoo": hub, "coinbase": hub, "databento_history": None}
            self.feed_mode = "file"
            journal.log("INFO", f"ICARUS_FEED=file — HistoryHub at {base_dir}/history; Yahoo/Coinbase are not contacted")
        elif requested_feed == "databento":
            db_feed = Databento()
            self.feeds = {"yahoo": db_feed, "coinbase": Coinbase(), "databento_history": Yahoo()}
            self.feed_mode = "databento"
            journal.log("INFO", "ICARUS_FEED=databento — CME futures use Databento GLBX.MDP3 as the sole replay source")
        else:
            self.feeds = {"yahoo": Yahoo(), "coinbase": Coinbase(), "databento_history": None}
            self.feed_mode = "live"
            if os.environ.get("DATABENTO_API_KEY", "").strip():
                try:
                    if importlib.util.find_spec("databento") is None:
                        raise RuntimeError("Databento SDK is not installed; install ICARUS with .[databento]")
                    self.feeds["databento_history"] = Databento()
                    journal.log("INFO", "Databento auxiliary history configured; Yahoo remains the replay source because provider roll bases are not reconciled")
                except Exception as ex:
                    journal.log("WARN", f"Databento historical source unavailable; using Yahoo-only warm-up ({type(ex).__name__}: {ex})")
            else:
                journal.log("INFO", "Databento history key is not configured; CME warm-up uses Yahoo's available history")
        self.runners: Dict[str, AssetRunner] = {}
        self.order: List[str] = []
        self.started = time.time()
        self.equity_epoch = self.started
        self._public_equity_epoch = self.equity_epoch  # display snapshot epoch during replay
        self._continuous_refresh_day = int(self.started // 86400)
        self.paused = False
        self._threads: Dict[str, threading.Thread] = {}
        self._sampler_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.RLock()
        # Optional measured latency sink. The HTTP server binds one instance and
        # make_runner propagates it to assets added after startup.
        self.latency_telemetry = None
        # A200 historical Pulse remains isolated from the normal asset/emulator
        # registry and is initialized only by an explicit qualified-batch call.
        self._a200_pulse_research = None

    # ── assets ──
    def _ref_price(self, now: Optional[int] = None) -> float:
        if self.pts_ref_price > 0:
            return self.pts_ref_price
        try:
            from .assets import resolve
            ref = resolve(self.pts_ref_symbol)
            feed = self.feeds[ref.feed]
            px = None
            if ref.feed == "yahoo":                            # last COMPLETED session's close: reproducible run to run, immune to Yahoo's mid-session roll
                rows = feed.daily_volume(ref.ticker, 6)
                so = get_calendar("cme").bucket_start(int(now or time.time()), 1440)
                done = [r for r in rows if r[0] < so]
                px = done[-1][1] if done else None
            if not px:
                px = feed.ticker(ref.ticker)
            if px:
                self.pts_ref_price = float(px)
                self.journal.log("INFO", f"point-scaling reference: {ref.symbol} = {px:.6g} (last completed session close)")
        except Exception as ex:
            self.journal.log("WARN", f"could not fetch the NQ reference price ({ex}); *_pts inputs are used literally")
        return self.pts_ref_price

    def make_runner(self, spec: AssetSpec) -> AssetRunner:
        if self.feed_mode == "file" and spec.kind == "futures":
            self.journal.log("INFO", f"[{spec.symbol}] continuous futures identity preserved in file mode ({spec.tv_symbol or spec.ticker}); no expiry-contract roller")
        base_spec = replace(spec)
        inputs, meta, sources = resolve_inputs(spec, self.base_dir, self.profile, self.preset)
        if meta:
            spec = apply_spec_meta(spec, meta)
        scale = self._ref_price() if (spec.symbol != self.pts_ref_symbol) else 0.0
        cfg = RunnerConfig(spec=spec, inputs=inputs, warmup_bars=self.warmup_bars, sources=sources, profile=self.profile,
                           preset=self.preset or spec.preset, pts_ref_price=scale, base_dir=self.base_dir,
                           base_spec=base_spec, shadow_real_fills=self.shadow_real_fills)
        runner = AssetRunner(cfg, self.journal, self.feeds)
        runner.latency_telemetry = self.latency_telemetry
        return runner

    def add_asset(self, spec: AssetSpec, start: bool = True) -> AssetRunner:
        with self._lock:
            if spec.symbol in self.runners:
                raise ValueError(f"{spec.symbol} already running")
        r = self.make_runner(spec)                            # may touch the network (tick size, NQ reference price)
        # Seed the first immutable display view during startup. HTTP readers
        # never build summaries, calendars, provider capabilities or charts.
        with r.lock:
            r.publish_read_views()
        # A portfolio-wide pause is a durable desired state. Assets added while
        # that intent is active must never begin accepting entries unpaused.
        if self.paused:
            r.set_paused(True)
        with self._lock:
            if spec.symbol in self.runners:
                raise ValueError(f"{spec.symbol} already running")
            self.runners[spec.symbol] = r
            self.order.append(spec.symbol)
        try:
            if start:
                prepare = getattr(r.feed, "prepare_live", None)
                if r.spec.kind == "futures" and callable(prepare):
                    prepare([r.spec.ticker])
                    self._prepare_depth_context(r.feed, [r.spec.ticker])
                self._spawn(r)
            return r
        except Exception:
            with self._lock:
                self.runners.pop(spec.symbol, None)
                self.order = [s for s in self.order if s != spec.symbol]
            detach = getattr(r.feed, "stop_live", None)
            if callable(detach):
                try:
                    detach(r.spec.ticker)
                except Exception:
                    pass
            raise

    def ingest_a200_research_history(self, instrument_id: str, bars, receipt, *,
                                     chart_minutes: int = 5) -> Dict[str, Any]:
        """Feed a qualified A200 historical batch into isolated Pulse research.

        This entry point never registers an asset in the live Portfolio, starts a
        feed thread, records trades to the Portfolio journal, or authorizes a
        broker. Current unqualified catalog rows return explicit blockers.
        """
        from .a200_runtime_feed import A200PulseResearchRuntime

        with self._lock:
            if self._a200_pulse_research is None:
                self._a200_pulse_research = A200PulseResearchRuntime(chart_minutes=chart_minutes)
            elif self._a200_pulse_research.chart_minutes != chart_minutes:
                raise ValueError("A200 Pulse research chart timeframe is fixed for this Portfolio instance")
            runtime = self._a200_pulse_research
        return runtime.ingest_history(instrument_id, bars, receipt)

    def fetch_a200_research_history(self, instrument_id: str, interval_seconds: int,
                                    start_ts: int, end_ts: int, *, provider: str = "yahoo",
                                    chart_minutes: int = 5) -> Dict[str, Any]:
        """Fail closed until a provider can attest entitlement and bar-close status.

        MarketUniverseAdapter intentionally emits UNKNOWN for those fields. Calling
        it here would make a network request whose result cannot enter Pulse, so
        this API reports the missing capability without contacting a provider.
        """
        return {
            "admission": {
                "admitted": False,
                "instrument_id": str(instrument_id),
                "symbol": None,
                "provider": str(provider),
                "reasons": ["PROVIDER_ADAPTER_NOT_QUALIFICATION_CAPABLE"],
                "receipt_id": None,
                "execution_authorized": False,
                "live_authorized": False,
            },
            "provider_call_made": False,
            "processed_bars": 0,
            "pulse": None,
            "research_only": True,
            "execution_authorized": False,
            "live_authorized": False,
        }

    def remove_asset(self, symbol: str) -> bool:
        raw = str(symbol).strip().upper()
        key = raw if raw in self.runners else resolve(symbol).symbol
        with self._lock:
            r = self.runners.get(key)
            if not r:
                return False
            with r.lock:
                if r.em.open or r.em._pending_entries or r.em._pending_closes:
                    raise ValueError(
                        f"{key}: flatten open positions and cancel pending orders before removing the asset"
                    )
                if r.rewarming:
                    raise ValueError(f"{key}: configuration replay is running; wait before removing the asset")
                self.runners.pop(key, None)
                self.order = [s for s in self.order if s != key]
                r.paused = True
                r._removed = True
        # Shared live feeds cannot unsubscribe at the gateway, but they can detach
        # this asset's local routing immediately without disrupting sibling assets.
        detach = getattr(r.feed, "stop_live", None)
        if self._owns_feeds and callable(detach):
            try:
                detach(r.spec.ticker)
            except Exception as ex:
                self.journal.log("WARN", f"[{key}] feed detach: {type(ex).__name__}: {ex}")
        self.journal.log("WARN", f"[{key}] removed from the engine")
        return True

    def preset_for(self, r: AssetRunner) -> Optional[str]:
        """The asset's current preset: set per asset (dashboard 'Apply preset', GC:NAME token) else the portfolio's."""
        return r.cfg.preset or r.spec.preset or self.preset

    def rewarm_asset(self, symbol: str, overrides: Optional[Dict[str, Any]] = None, persist: bool = False,
                     *, preset: Any = _UNCHANGED, reset: bool = False,
                     chart: Optional[Dict[str, Any]] = None,
                     _publish_views: bool = True) -> AssetRunner:
        """Atomically apply strategy/chart configuration, then persist only after replay succeeds."""
        raw = str(symbol).strip().upper()
        key = raw if raw in self.runners else resolve(symbol).symbol
        r = self.runners[key]
        with r.lock:
            r.ensure_configurable()
            requested_chart = validate_chart_config(chart)

            # Rebuild from the startup baseline every time. This makes reset deterministic:
            # preset/global/asset metadata are reapplied in order instead of leaking stale
            # chart/session/cost values from the previous runtime object.
            spec = replace(r.cfg.base_spec or r.spec)
            spec.preset = r.spec.preset
            if preset is not _UNCHANGED:
                spec.preset = preset
            name = self.preset_for(r) if preset is _UNCHANGED else preset or self.preset

            inputs, meta, sources = resolve_inputs(spec, self.base_dir, self.profile, name, overrides,
                                                  skip_asset_overrides=reset)
            spec = apply_spec_meta(spec, meta)
            spec = apply_chart_config(spec, requested_chart)

            path = os.path.join(self.base_dir, f"inputs.{r.symbol}.json")
            pending_file: Optional[Dict[str, Any]] = None
            delete_file = bool(reset and os.path.exists(path))

            if persist and (overrides is not None or requested_chart):
                # Build the exact next file in memory and resolve against that candidate.
                # Nothing reaches disk until the paper-engine replay has completed.
                pending_file = _read_json(path)
                if overrides:
                    pending_file.update(overrides)
                if requested_chart:
                    m = pending_file.get("_meta")
                    m = dict(m) if isinstance(m, dict) else {}
                    m.update(requested_chart)
                    pending_file["_meta"] = m
                inputs, meta, sources = resolve_inputs(
                    spec, self.base_dir, self.profile, name, pending_file,
                    skip_asset_overrides=True, extra_label=f"inputs.{r.symbol}.json"
                )
                spec = apply_spec_meta(spec, meta)
                spec = apply_chart_config(spec, requested_chart)

            r.ensure_cached_timeframes(inputs)
            spec.chart_tf = r.ensure_cached_chart_timeframe(spec.chart_tf)

            r.publish_read_views()
            runtime_before = r.configuration_snapshot()
            tmp = path + ".tmp"
            try:
                for field in ("chart_tf", "chart_type", "fill_on", "security_source", "slippage_ticks",
                              "commission", "capital", "session", "preset", "config_pins"):
                    setattr(r.spec, field, getattr(spec, field))
                if preset is not _UNCHANGED:
                    r.cfg.preset = spec.preset
                r.rewarm(inputs, sources, reset_live_boundary=True, _publish_views=False)

                # Commit persistence after the successful replay. A failed replay therefore
                # cannot leave the next process start on a configuration the live engine rejected.
                if pending_file is not None:
                    with open(tmp, "w", encoding="utf-8") as fh:
                        json.dump(pending_file, fh, indent=1, ensure_ascii=False)
                    os.replace(tmp, path)
                elif delete_file:
                    os.remove(path)
                self.equity_epoch = time.time()
                # The pre-replay view deliberately exposes only committed old
                # state while this lock is held. Replace it only after settings,
                # persistence and the equity epoch have all committed.
                if _publish_views:
                    r.publish_read_views()
            except Exception:
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except OSError:
                    pass
                r.restore_configuration_snapshot(runtime_before)
                raise
        return r

    # ── threads ──
    def _spawn(self, r: AssetRunner) -> None:
        t = threading.Thread(target=self._run, args=(r,), daemon=True, name=f"runner-{r.symbol}")
        t.start()
        self._threads[r.symbol] = t

    def start(self) -> None:
        self.journal.start_display_publisher(since_ts=self.started)
        # Start shared live transports before historical warm-up. Databento buffers
        # real-time seconds/trades while each runner replays history, eliminating the
        # history-to-live seam without opening one session per futures symbol.
        groups: Dict[int, Tuple[Any, List[str]]] = {}
        for r in self.runner_list():
            prepare = getattr(r.feed, "prepare_live", None)
            if r.spec.kind == "futures" and callable(prepare):
                group = groups.setdefault(id(r.feed), (r.feed, []))
                group[1].append(r.spec.ticker)
        for feed, tickers in groups.values():
            feed.prepare_live(tickers)
            self._prepare_depth_context(feed, tickers)
        for s in list(self.order):
            self._spawn(self.runners[s])
        self._sampler_thread = threading.Thread(target=self._sampler, daemon=True, name="equity-sampler")
        self._sampler_thread.start()

    def _prepare_depth_context(self, feed: Any, tickers: Sequence[str]) -> None:
        """Subscribe isolated MBP-10 context without making it a core-feed dependency."""
        if self.feed_mode != "databento":
            return
        try:
            feed.prepare_live(tickers, include_depth="mbp-10")
        except Exception as ex:
            self.journal.log(
                "WARN",
                f"Databento MBP-10 depth unavailable; core feed remains active ({type(ex).__name__})",
            )

    def _run(self, r: AssetRunner) -> None:
        if not self._warmup_with_retry(r):
            return
        try:
            from .activation_runtime import load_startup_overlay
            load_startup_overlay(self, r)
        except Exception as ex:
            r.errors += 1
            r.last_error = f"startup overlay failed: {type(ex).__name__}: {ex}"
            r.runtime_error = r.last_error
            self.journal.log("ERROR", f"[{r.symbol}] {r.last_error}")
        interval = self.poll_sec if r.spec.feed == "coinbase" else max(self.poll_sec, 15.0)
        while not self._stop.is_set() and not r._removed:
            try:
                if not r.rewarming:
                    r.poll()
                    self._publish_runner_read_views(r)
            except Exception as ex:
                r.errors += 1
                r.last_error = f"{type(ex).__name__}: {ex}"
                r.runtime_error = r.last_error
                self.journal.log("ERROR", f"[{r.symbol}] poll: {r.last_error}")
            self._stop.wait(interval)

    @staticmethod
    def _publish_runner_read_views(runner) -> None:
        publish = getattr(runner, "publish_read_views", None)
        if callable(publish):
            with runner.lock:
                publish()

    def _warmup_with_retry(self, r: AssetRunner) -> bool:
        """Keep transient startup feed failures in WARMING and retry with backoff."""
        delay = 5.0
        while not self._stop.is_set():
            try:
                r.warmup()
                if r.spec.kind == "futures" and r.spec.feed == "yahoo" and r.bar_index < 0:
                    raise RuntimeError("Yahoo warm-up returned no chart bars")
                r.runtime_error = ""
                r.last_error = ""
                r.feed_error = ""
                self._publish_runner_read_views(r)
                return True
            except Exception as ex:
                r.errors += 1
                message = f"warm-up failed; retrying in {delay:g}s: {type(ex).__name__}: {ex}"
                r.last_error = message
                r.runtime_error = message
                r.warm = False
                self.journal.log("ERROR", f"[{r.symbol}] {message}")
                r.reset_failed_startup_warmup()
                if self._stop.wait(delay):
                    return False
                delay = min(delay * 2.0, 60.0)
        return False

    def _refresh_continuous_feeds(self, now: Optional[float] = None) -> bool:
        """Re-resolve provider continuous symbols once per UTC date.

        Databento volume/open-interest ranks are based on the prior day and existing
        Live continuous subscriptions do not remap themselves. Reopening the one
        shared dataset session with the same smart symbols keeps ICARUS continuous-
        only without any dated-contract rollover configuration.
        """
        wall = float(now if now is not None else time.time())
        day = int(wall // 86400)
        if day == self._continuous_refresh_day:
            return False

        groups: Dict[int, Tuple[Any, List[str]]] = {}
        for r in self.runner_list():
            refresh = getattr(r.feed, "refresh_live", None)
            if r.spec.kind == "futures" and callable(refresh):
                group = groups.setdefault(id(r.feed), (r.feed, []))
                group[1].append(r.spec.ticker)

        replay_from = max(0, int(wall) - 300)
        for feed, tickers in groups.values():
            feed.refresh_live(tickers, start_ts=replay_from)
        self._continuous_refresh_day = day
        if groups:
            self.journal.log(
                "INFO",
                f"continuous futures live mappings refreshed for UTC day {day}; "
                f"replay from {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(replay_from))}Z",
            )
        return bool(groups)

    def _sampler(self) -> None:
        while not self._stop.is_set():
            try:
                self._refresh_continuous_feeds()
                if self.runners and all(r.warm for r in self.runners.values()):
                    self.journal.add_equity(self.equity())
            except Exception as ex:
                self.journal.log("WARN", f"portfolio sampler: {type(ex).__name__}: {ex}")
            self._stop.wait(20)

    def stop(self) -> None:
        self._stop.set()

        # Do not tear down a live transport underneath a runner or sampler already
        # inside a feed call. Give all worker threads one bounded shutdown window.
        deadline = time.monotonic() + 5.0
        current = threading.current_thread()
        threads = ([self._sampler_thread] if self._sampler_thread is not None else [])
        threads.extend(self._threads.values())
        for thread in threads:
            if thread is current or not thread.is_alive():
                continue
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            thread.join(remaining)

        if self._a200_pulse_research is not None:
            try:
                self._a200_pulse_research.close()
            except Exception as ex:
                self.journal.log("WARN", f"A200 research shutdown: {type(ex).__name__}: {ex}")

        # Paid/live adapters own background network sessions. Close each distinct
        # feed once so supervised restarts do not leak or reopen Databento connections.
        if self._owns_feeds:
            seen = set()
            for feed in self.feeds.values():
                if id(feed) in seen:
                    continue
                seen.add(id(feed))
                try:
                    if hasattr(feed, "close"):
                        feed.close()
                    elif hasattr(feed, "stop_live"):
                        feed.stop_live()
                except Exception as ex:
                    self.journal.log("WARN", f"feed shutdown: {type(ex).__name__}: {ex}")

    # ── views ──
    def equity(self) -> float:
        return sum(r.em.equity(r.last_price) for r in self.runners.values())

    def runner_list(self) -> List[AssetRunner]:
        return [self.runners[s] for s in self.order if s in self.runners]

    @staticmethod
    def _withhold_shadow_metrics(shadow: Dict[str, Any]) -> Dict[str, Any]:
        """Redact comparison values from a non-ready public shadow snapshot."""
        view = dict(shadow)
        view["metrics_available"] = False
        view["metrics_unavailable_reason"] = (
            "per-asset comparisons require READY shadow evidence")
        for field in (
            "intents", "primary_entry_fills", "shadow_entry_fills", "entry_fill_parity",
            "primary_only_entry_fills", "shadow_only_entry_fills",
            "matched_entry_intents",
            "entry_price_delta_points_shadow_minus_primary",
            "entry_price_delta_ticks_shadow_minus_primary",
            "entry_price_delta_dollars_shadow_minus_primary", "recent_entry_fill_pairs",
            "primary_only_closed_episodes", "shadow_only_closed_episodes",
            "pairable_closed_episodes", "excluded_admin_flatten_lot_trade_pieces",
            "administrative_censored_shadow_positions", "recent_administrative_censors",
            "outcome_agreement_denominator", "outcome_agreement_rate",
            "outcome_agreement_count", "outcome_matrix", "primary_break_even_episodes",
            "shadow_break_even_episodes", "primary_win_count",
            "primary_win_preserved_count", "primary_win_preservation", "primary",
            "real_price_shadow", "net_realization_ratio",
            "net_realization_ratio_unavailable_reason", "paired_profit_capture",
            "paired_profit_capture_unavailable_reason", "paired_primary_winner_net",
            "paired_shadow_net_on_primary_winners", "primary_closed_episode_excursions",
            "real_price_shadow_closed_episode_excursions",
            "matched_closed_episode_favorable_excursion_delta_shadow_minus_primary",
            "matched_closed_episode_adverse_excursion_delta_shadow_minus_primary",
            "bar_close_equity_observations", "primary_bar_close_max_drawdown",
            "real_price_shadow_bar_close_max_drawdown", "open_primary", "open_shadow",
            "recent_intents",
        ):
            if field in view:
                view[field] = None
        return view

    def status(self, *, nonblocking: bool = False) -> Dict[str, Any]:
        runners = tuple(self.runners.values()) if nonblocking else self.runner_list()
        rs = [r.summary(nonblocking=True) if nonblocking else r.summary() for r in runners]
        shadow_rows = [x["real_price_shadow"] for x in rs if x.get("real_price_shadow")]
        eq = sum(x["equity"] or 0.0 for x in rs)
        cap = sum(x["capital"] for x in rs)
        stale = nonblocking and any(x.get("view_stale") for x in rs)
        epoch = getattr(self, "_public_equity_epoch", self.equity_epoch) if stale else self.equity_epoch
        if nonblocking and not stale:
            self._public_equity_epoch = epoch
        live_profit = sum(x["live_profit"] for x in rs)
        shadow_status = ("INVALID" if any(x["status"] == "INVALID" for x in shadow_rows)
                         else "DEGRADED" if any(x["status"] != "READY" for x in shadow_rows)
                         else "READY") if shadow_rows else "DISABLED"
        metrics_available = shadow_status == "READY"
        primary_entries = sum(x["primary_entry_fills"] for x in shadow_rows)
        shadow_entries = sum(x["shadow_entry_fills"] for x in shadow_rows)
        matched_entries = sum(x["matched_entry_intents"] for x in shadow_rows)
        agreement_denominator = sum(x["outcome_agreement_denominator"] for x in shadow_rows)
        agree_count = sum(x["outcome_agreement_count"] for x in shadow_rows)
        primary_win_count = sum(x["primary_win_count"] for x in shadow_rows)
        preserved_count = sum(x["primary_win_preserved_count"] for x in shadow_rows)
        portfolio_primary_net = sum(x["primary"]["net"] for x in shadow_rows)
        portfolio_shadow_net = sum(x["real_price_shadow"]["net"] for x in shadow_rows)
        portfolio_primary_winner_net = sum(x["paired_primary_winner_net"] for x in shadow_rows)
        portfolio_shadow_on_primary_winners = sum(
            x["paired_shadow_net_on_primary_winners"] for x in shadow_rows)
        portfolio_outcome_matrix = {
            primary: {
                shadow: sum(x["outcome_matrix"][primary][shadow] for x in shadow_rows)
                for shadow in ("win", "loss", "break_even")
            }
            for primary in ("win", "loss", "break_even")
        }
        portfolio_epsilon = max(1e-8, abs(portfolio_primary_net) * 1e-12)
        portfolio_realization_ratio = (
            portfolio_shadow_net / portfolio_primary_net
            if portfolio_primary_net > portfolio_epsilon else None)
        portfolio_profit_capture = (
            portfolio_shadow_on_primary_winners / portfolio_primary_winner_net
            if portfolio_primary_winner_net > 1e-8 else None)
        summaries_by_asset = {str(row.get("symbol")): row for row in rs if row.get("symbol")}

        def observed_bar_age(summary: Dict[str, Any]) -> Optional[float]:
            age = summary.get("bar_age")
            captured_at = summary.get("view_captured_at")
            if age is None:
                return None
            if summary.get("view_stale") and not summary.get("view_age_adjusted") and captured_at is not None:
                try:
                    age = float(age) + max(0.0, time.time() - float(captured_at))
                except (TypeError, ValueError):
                    pass
            return age

        shadow_portfolio = ({
            "schema": "icarus.real_price_shadow.portfolio/1",
            "enabled": True,
            "status": shadow_status,
            "metrics_available": metrics_available,
            "metrics_unavailable_reason": (
                None if metrics_available else
                "portfolio comparisons require every evidenced asset to be READY"),
            "metrics_time_basis": (
                "historical emulator evidence through each asset's last observed bar; "
                "current feed health is reported separately"),
            "execution_authorized": False,
            "asset_count": len(shadow_rows),
            "primary_entry_fills": primary_entries,
            "shadow_entry_fills": shadow_entries,
            "entry_fill_parity": matched_entries / primary_entries if primary_entries else None,
            "matched_entry_intents": matched_entries,
            "primary_only_entry_fills": sum(x["primary_only_entry_fills"] for x in shadow_rows),
            "shadow_only_entry_fills": sum(x["shadow_only_entry_fills"] for x in shadow_rows),
            "administrative_censored_shadow_positions": sum(
                x["administrative_censored_shadow_positions"] for x in shadow_rows),
            "pairable_closed_episodes": sum(x["pairable_closed_episodes"] for x in shadow_rows),
            "outcome_agreement_denominator": agreement_denominator,
            "outcome_agreement_rate": agree_count / agreement_denominator if agreement_denominator else None,
            "outcome_matrix": portfolio_outcome_matrix,
            "primary_win_preservation": preserved_count / primary_win_count if primary_win_count else None,
            "primary_net": round(portfolio_primary_net, 8),
            "real_price_shadow_net": round(portfolio_shadow_net, 8),
            "net_realization_ratio": portfolio_realization_ratio,
            "net_realization_ratio_unavailable_reason": (
                None if portfolio_realization_ratio is not None else
                "portfolio primary net is non-positive or too close to zero"),
            "paired_profit_capture": portfolio_profit_capture,
            "paired_profit_capture_unavailable_reason": (
                None if portfolio_profit_capture is not None else
                "no positive pairable primary-winner P&L denominator"),
            "paired_primary_winner_net": round(portfolio_primary_winner_net, 8),
            "paired_shadow_net_on_primary_winners": round(portfolio_shadow_on_primary_winners, 8),
            "primary_warmup_net": round(sum(x["primary"]["warmup_net"] for x in shadow_rows), 8),
            "primary_live_net": round(sum(x["primary"]["live_net"] for x in shadow_rows), 8),
            "real_price_shadow_warmup_net": round(sum(x["real_price_shadow"]["warmup_net"] for x in shadow_rows), 8),
            "real_price_shadow_live_net": round(sum(x["real_price_shadow"]["live_net"] for x in shadow_rows), 8),
            "drawdown_aggregation": "per_asset_only; cross_asset_close_timestamps_are_not_yet_aligned",
            "assets": [{"asset": x["asset"], "status": x["status"], "reason": x["reason"],
                        "administrative_censored_shadow_positions": (
                            x["administrative_censored_shadow_positions"]
                            if x["status"] == "READY" else None),
                        "last_bar_ts": summaries_by_asset.get(x["asset"], {}).get("last_bar_ts"),
                        "bar_age_seconds": observed_bar_age(summaries_by_asset.get(x["asset"], {})),
                        "view_stale": bool(summaries_by_asset.get(x["asset"], {}).get("view_stale")),
                        "feed_health": ((x.get("provenance") or {}).get("feed_health")
                                        or summaries_by_asset.get(x["asset"], {}).get("feed_health")),
                        "provenance": x.get("provenance")}
                       for x in shadow_rows],
        } if shadow_rows else None)
        if shadow_portfolio is not None and not metrics_available:
            # Never present a mixture of current primary results and a frozen or
            # invalid shadow lane as a portfolio comparison. Keep status, asset
            # count, reasons, and provenance available for diagnosis.
            unavailable_metrics = (
                "primary_entry_fills", "shadow_entry_fills", "entry_fill_parity",
                "matched_entry_intents", "primary_only_entry_fills",
                "shadow_only_entry_fills", "administrative_censored_shadow_positions",
                "pairable_closed_episodes", "outcome_agreement_denominator",
                "outcome_agreement_rate", "outcome_matrix", "primary_win_preservation",
                "primary_net", "real_price_shadow_net", "net_realization_ratio",
                "net_realization_ratio_unavailable_reason", "paired_profit_capture",
                "paired_profit_capture_unavailable_reason", "paired_primary_winner_net",
                "paired_shadow_net_on_primary_winners", "primary_warmup_net",
                "primary_live_net", "real_price_shadow_warmup_net",
                "real_price_shadow_live_net",
            )
            for field in unavailable_metrics:
                shadow_portfolio[field] = None
        for row in rs:
            shadow = row.get("real_price_shadow")
            if shadow is None:
                continue
            if shadow.get("status") == "READY":
                shadow["metrics_available"] = True
                shadow["metrics_unavailable_reason"] = None
            else:
                row["real_price_shadow"] = self._withhold_shadow_metrics(shadow)
        return _clean({
            "now": time.time(), "uptime_sec": time.time() - self.started, "paused": self.paused,
            "global_pause_intent": self.paused,
            "paused_assets": sorted(x["symbol"] for x in rs if x["paused"]),
            "mixed_pause_state": any(x["paused"] != self.paused for x in rs),
            "equity": eq, "capital": cap, "net": eq - cap, "live_profit": live_profit,
            "open_profit": sum(x["open_profit"] or 0.0 for x in rs), "positions": sum(1 for x in rs if x["position"]),
            "assets": rs, "log": list(self.journal.log_tail)[-80:],
            "real_price_shadow": shadow_portfolio,
            "equity_epoch": epoch,
            "view_stale": bool(stale),
            "equity_series": self.journal.equity_series(max_points=600, since_ts=max(self.started, epoch),
                                                       nonblocking=nonblocking),
            "equity_series_view": self.journal._cached_dashboard_view("equity")[1] if nonblocking else None,
            "all_warm": all(x["warm"] for x in rs) if rs else False,
            "preset": self.preset, "profile": self.profile, "pts_ref": {"symbol": self.pts_ref_symbol, "price": self.pts_ref_price},
        })

    def publish_shadow_evidence(self, fabric, *, run_id: str, received_at: str) -> Dict[str, Any]:
        """Explicitly publish current per-asset shadow snapshots as one batch.

        Unlike `status()`, this method is an intentional write. All eligible
        events are validated before the first append so malformed asset state
        cannot produce a knowingly partial batch. Retries are idempotent.
        """
        from .intelligence_fabric import IntelligenceFabric
        from .shadow_evidence_events import shadow_evidence_event

        if not isinstance(fabric, IntelligenceFabric):
            raise ValueError("fabric must be an IntelligenceFabric")
        staged = []
        failures = []
        skipped = []
        for runner in self.runner_list():
            row = runner.summary()
            shadow = row.get("real_price_shadow")
            if shadow is None:
                skipped.append(row.get("symbol", "unknown"))
                continue
            stamp = row.get("last_bar_ts")
            if isinstance(stamp, bool) or not isinstance(stamp, (int, float)) or stamp <= 0:
                failures.append({"asset": row.get("symbol", "unknown"),
                                 "reason": "missing valid last_bar_ts"})
                continue
            observed_at = datetime.fromtimestamp(float(stamp), timezone.utc).isoformat().replace("+00:00", "Z")
            try:
                event = shadow_evidence_event(
                    shadow, run_id=run_id, observed_at=observed_at, received_at=received_at)
                event.normalized()  # validate all envelopes before writing any asset event
                staged.append((str(row.get("symbol", shadow.get("asset", "unknown"))), event))
            except (ValueError, OverflowError, OSError) as exc:
                failures.append({"asset": row.get("symbol", "unknown"),
                                 "reason": f"{type(exc).__name__}: {exc}"})
        if failures:
            return {"schema": "icarus.real_price_shadow.publication/1", "status": "BLOCKED",
                    "published_count": 0, "skipped_assets": skipped, "failures": failures,
                    "execution_authorized": False, "production_decision_authorized": False}
        receipts = []
        for asset, event in staged:
            try:
                receipts.append({"asset": asset, **fabric.publish(event)})
            except Exception as exc:
                return {"schema": "icarus.real_price_shadow.publication/1",
                        "status": "PARTIAL" if receipts else "FAILED",
                        "published_count": len(receipts), "receipts": receipts,
                        "failed_asset": asset, "failure": f"{type(exc).__name__}: {exc}",
                        "execution_authorized": False, "production_decision_authorized": False}
        return {"schema": "icarus.real_price_shadow.publication/1",
                "status": "PUBLISHED" if receipts else "NO_ELIGIBLE_ASSETS",
                "published_count": len(receipts), "receipts": receipts,
                "skipped_assets": skipped,
                "execution_authorized": False, "production_decision_authorized": False}
