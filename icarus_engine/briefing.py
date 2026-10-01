# Grok (xAI) — 2026-09-21. Whole file.
"""Field Manual briefing. Architecture, parity IDs, RTH clock.

Does not scrape TradingView. Does not invent ticks. Does not arm a broker.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .strategy.inputs import Inputs

try:
    from zoneinfo import ZoneInfo
    _NY = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover
    _NY = timezone.utc

EQUITY_CLOSED = frozenset({"2026-04-03", "2026-12-25", "2027-01-01", "2027-03-26"})


def session_clock(now: Optional[float] = None) -> Dict[str, Any]:
    ts = datetime.fromtimestamp(now if now is not None else datetime.now(tz=_NY).timestamp(), tz=_NY)
    minutes = ts.hour * 60 + ts.minute
    date_et = ts.date().isoformat()
    weekend = ts.weekday() >= 5
    holiday = date_et in EQUITY_CLOSED
    rth = (not weekend) and (not holiday) and (9 * 60 + 30) <= minutes < (16 * 60 + 15)
    if weekend:
        reason = "Weekend. Globex is not a Pulse trade."
    elif holiday:
        reason = "CME equity holiday (closed)."
    elif minutes < 9 * 60 + 30:
        reason = "Before 09:30 ET. Outside Pulse RTH."
    elif minutes >= 16 * 60 + 15:
        reason = "After 16:15 ET. Session closed."
    else:
        reason = "RTH open — Pulse may take session entries"
    fomc = date_et in {p.strip() for p in str(Inputs().fomc_dates or "").split(",") if p.strip()}
    return {
        "date_et": date_et,
        "weekday": ts.strftime("%a"),
        "hhmm_et": ts.strftime("%H:%M"),
        "rth": rth,
        "fomc": fomc,
        "reason": reason,
        "broker_armed": False,
    }


def report(now: Optional[float] = None) -> Dict[str, Any]:
    return {
        "verdict": "PAPER_ONLY",
        "session": session_clock(now),
        "brains": {
            "A": "TV Pine → icarus-bridge → Alpaca QQQ. Not NQ.",
            "B": "Engine dashboard. Yahoo or FileFeed. Local emulator.",
            "futures": "TradersPost or PickMyTrade → Tradovate. Not this process.",
        },
        "parity": ["A1", "A2", "A3", "A4", "A5", "A9", "Roll", "Fills", "HA"],
        "ml": "grid search + locked holdout. No LSTM. execution_authorized false.",
        "dont": [
            "scrape TradingView",
            "invent ticks",
            "treat QQQ as NQ",
            "ALPACA_PAPER=false",
            "bind off loopback",
        ],
        "_grok": "Grok (xAI) 2026-09-21. Field Manual briefing. Never arms a broker.",
    }
