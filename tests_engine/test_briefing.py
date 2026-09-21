# Grok (xAI) — 2026-09-21. Field Manual briefing clock.
from datetime import datetime
from zoneinfo import ZoneInfo

from icarus_engine.briefing import report, session_clock

NY = ZoneInfo("America/New_York")


def _ts(s: str) -> float:
    return datetime.fromisoformat(s).replace(tzinfo=NY).timestamp()


def test_sunday_is_outside_rth():
    c = session_clock(_ts("2026-09-20T20:00:00"))
    assert c["rth"] is False
    assert c["broker_armed"] is False
    assert "Weekend" in c["reason"]


def test_monday_rth_open():
    c = session_clock(_ts("2026-09-21T10:00:00"))
    assert c["rth"] is True


def test_briefing_never_arms():
    r = report(_ts("2026-09-21T10:00:00"))
    assert r["verdict"] == "PAPER_ONLY"
    assert r["session"]["broker_armed"] is False
    assert "A5" in r["parity"]
    assert "LSTM" in r["ml"]
