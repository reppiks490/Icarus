# Grok (xAI) — 2026-09-22. Whole file.
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Family:
    name: str
    index: str
    label: str
    min_rows: int
    notes: str

FAMILIES = {
    "clock_minutes": Family("clock_minutes", "clock", "next_clock_return_sign", 400, "1m-20m time bars."),
    "clock_hours": Family("clock_hours", "clock", "next_clock_return_sign", 250, "1h-4h time bars."),
    "clock_seconds": Family("clock_seconds", "clock", "next_clock_return_sign", 800, "1s-30s. Not tick."),
    "clock_daily": Family("clock_daily", "session", "next_session_return_sign", 80, "True daily only."),
    "clock_weekly": Family("clock_weekly", "session", "next_session_return_sign", 40, "True weekly."),
    "renko": Family("renko", "brick", "next_brick_direction", 300, "Next brick sign. Time is not the index."),
    "range": Family("range", "range", "next_range_direction", 300, "Next range-bar sign."),
    "tick": Family("tick", "tick", "next_tickbar_direction", 300, "N-tick bars. Do not resample to minutes."),
}
CHART_TO_FAMILY = {
    "minutes": "clock_minutes", "hours": "clock_hours", "seconds": "clock_seconds",
    "daily": "clock_daily", "weekly": "clock_weekly",
    "renko": "renko", "range": "range", "tick": "tick",
}

def family_for(chart_type: str, schema: str = "ohlc") -> str:
    if schema == "close_only":
        raise ValueError("close_only has no trainer")
    name = CHART_TO_FAMILY.get(chart_type)
    if not name:
        raise ValueError(f"no family for chart_type={chart_type!r}")
    return name
