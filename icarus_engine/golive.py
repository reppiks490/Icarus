# Grok (xAI) — 2026-09-21. Whole file.
"""Go-live integrity report. Paper is not a broker.

This exists so warmup P&L, Yahoo NQ=F, Alpaca QQQ, and a CME fill cannot
be mistaken for each other. It never arms a broker. It never places NQ.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional

from .feeds.bars import file_feed_mode, find_history
from .strategy.inputs import Inputs

try:
    from zoneinfo import ZoneInfo
    _NY = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover
    _NY = timezone.utc


def _today_et(now: Optional[float] = None) -> str:
    ts = datetime.fromtimestamp(now or time.time(), tz=_NY)
    return ts.date().isoformat()


def _env_secret_ok(env: Mapping[str, str], key: str, bad: tuple[str, ...]) -> bool:
    val = (env.get(key) or "").strip()
    return bool(val) and val not in bad


def _fomc_today(now: Optional[float] = None) -> bool:
    raw = Inputs().fomc_dates or ""
    days = {p.strip() for p in str(raw).split(",") if p.strip()}
    return _today_et(now) in days


def from_status(
    status: Mapping[str, Any],
    *,
    feed: str,
    env: Mapping[str, str],
    base_dir: str,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Pure report. ``status`` is ``Portfolio.status()``. No network."""
    now = float(now if now is not None else status.get("now") or time.time())
    assets = list(status.get("assets") or [])
    nq = next((a for a in assets if a.get("symbol") == "NQ"), assets[0] if assets else {})
    live_pnl = float(status.get("live_profit") or 0.0)
    open_pnl = float(status.get("open_profit") or 0.0)
    net = float(status.get("net") or 0.0)
    warmup_pnl = net - (live_pnl + open_pnl)
    hist_1m, hist_min = find_history(base_dir, "NQ", 20)
    price_age = nq.get("price_age")
    feed_delay = nq.get("feed_delay")
    bar_age = nq.get("bar_age")
    market = nq.get("market") or {}
    describe = str(market.get("describe") or "")
    rth_open = describe.startswith("open")
    in_session = bool((nq.get("state") or {}).get("in_session"))
    entry_allowed = bool((nq.get("state") or {}).get("entry_allowed"))
    paper_key = _env_secret_ok(env, "ALPACA_API_KEY", ("", "replace-me", "your-key"))
    paper_flag = (env.get("ALPACA_PAPER") or "true").strip().lower() in ("1", "true", "yes")
    secret_ok = _env_secret_ok(env, "WEBHOOK_SECRET", ("", "replace-me", "change-me"))
    token_ok = _env_secret_ok(env, "ADMIN_TOKEN", ("", "replace-me", "replace-me-too", "change-me-too"))

    tape = "file" if feed == "file" else "yahoo"
    identity = (
        "FileFeed — last Supercharts CSV you dropped (not a live CME stream)"
        if tape == "file"
        else "Yahoo NQ=F — delayed, continuous, not NQ1!"
    )

    gates = [
        {
            "id": "broker",
            "ok": False,
            "level": "block",
            "detail": "This process cannot place NQ. No CME, no Tradovate, no Alpaca futures.",
        },
        {
            "id": "qqq_is_not_nq",
            "ok": False,
            "level": "block",
            "detail": "Brain A (bridge) maps NQ1! → Alpaca QQQ shares. Percent-mapped equity. Not a futures fill.",
        },
        {
            "id": "warmup_is_not_money",
            "ok": True,
            "level": "info",
            "detail": f"Warm-up replay P&L {warmup_pnl:,.2f} is historical emulator, not a deposit. Live book {live_pnl + open_pnl:,.2f}.",
        },
        {
            "id": "tape",
            "ok": bool(nq.get("price") or hist_1m),
            "level": "warn" if not (nq.get("price") or hist_1m) else "ok",
            "detail": identity + (f" · history {os.path.basename(hist_1m)} {hist_min}m" if hist_1m else " · no NQ CSV in history/"),
        },
        {
            "id": "session_rth",
            "ok": rth_open and in_session,
            "level": "info",
            "detail": (describe or "session unknown")
            + (" · Pulse in session" if in_session else " · Pulse outside RTH (09:30–16:15 ET)")
            + ("" if entry_allowed else " · entries blocked"),
        },
        {
            "id": "fomc",
            "ok": not _fomc_today(now),
            "level": "warn" if _fomc_today(now) else "ok",
            "detail": "FOMC decision window today — Pulse may flatten/block. Not a prediction."
            if _fomc_today(now)
            else "Not an FOMC decision day on the bundled calendar.",
        },
        {
            "id": "fill_model",
            "ok": True,
            "level": "info",
            "detail": "Emulator: next-bar open, slippage 0, Bar Magnifier off. Live TV LTF uses last intrabar (parity A5) — live chart ≠ this backtest.",
        },
        {
            "id": "feed_age",
            "ok": (price_age is None) or (float(price_age) < 120) or tape == "file",
            "level": "warn",
            "detail": f"price_age={price_age}s bar_age={bar_age}s yahoo_delay={feed_delay}s"
            + (" · file mode does not poll Yahoo" if tape == "file" else " · Yahoo is typically ~10 minutes late"),
        },
        {
            "id": "alpaca_paper_flag",
            "ok": paper_flag,
            "level": "block" if not paper_flag else "info",
            "detail": "ALPACA_PAPER=true" if paper_flag else "ALPACA_PAPER is not true — do not use live keys.",
        },
        {
            "id": "bridge_secrets",
            "ok": (not paper_key) or (secret_ok and token_ok),
            "level": "warn",
            "detail": "Bridge secrets look set."
            if secret_ok and token_ok
            else "WEBHOOK_SECRET / ADMIN_TOKEN still default or missing — required only when Brain A is on.",
        },
        {
            "id": "open_paper_positions",
            "ok": int(status.get("positions") or 0) == 0,
            "level": "info",
            "detail": f"{int(status.get('positions') or 0)} open paper position(s). A broker would not inherit these.",
        },
    ]

    blocked = [g for g in gates if g["level"] == "block"]
    verdict = "PAPER_ONLY"
    headline = "Paper engine. Not a broker. Not CME."
    if not paper_flag:
        verdict = "LIVE_KEYS_FORBIDDEN"
        headline = "Alpaca paper flag is off. Stop. Do not send live keys to this plant."
    elif not any(a.get("price") or a.get("bar_index", -1) >= 0 for a in assets):
        verdict = "NO_TAPE"
        headline = "No tape yet. Yahoo still warming or CSV not ingested."

    return {
        "_grok": "Grok (xAI) 2026-09-21. Go-live integrity. Never arms a broker.",
        "verdict": verdict,
        "headline": headline,
        "broker_armed": False,
        "feed": tape,
        "identity": identity,
        "warmup_pnl": warmup_pnl,
        "live_pnl": live_pnl,
        "open_pnl": open_pnl,
        "brains": {
            "A": "TradingView Pine → icarus-bridge → Alpaca QQQ (not NQ). Off unless you started the bridge.",
            "B": "This dashboard. Yahoo NQ=F or FileFeed CSV. Local emulator fills.",
        },
        "live_would_mean": [
            "Futures NQ/MNQ: TradersPost or PickMyTrade → Tradovate/Rithmic. Not this process.",
            "Equity proxy: Alpaca paper QQQ via icarus-bridge. Never ALPACA_PAPER=false until paper is boring.",
            "This panel turning green does not arm a broker.",
            "Parity A5: live TradingView LTF last-intrabar ≠ Icarus first-intrabar backtest.",
        ],
        "gates": gates,
        "blocks": [g["id"] for g in blocked],
        "nq_history": {"path": hist_1m, "minutes": hist_min},
        "export": "py -3 -m icarus_engine.cli paper-export",
    }


def report(port, env: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    """Live engine entry. ``port`` is a Portfolio."""
    return from_status(
        port.status(),
        feed="file" if file_feed_mode() else "yahoo",
        env=env if env is not None else os.environ,
        base_dir=port.base_dir,
    )
