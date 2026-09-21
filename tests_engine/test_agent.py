# Grok (xAI) — 2026-09-21. Field Agent panel: paper is not a broker.
from icarus_engine.agent import paste_pack, report


def test_agent_report_never_arms_and_does_not_execute():
    r = report()
    assert r["broker_armed"] is False
    assert r["executed"] is False
    assert any(x["id"] == "yahoo" for x in r["recipes"])
    assert "127.0.0.1" in r["sidecar"]
    assert "claude" in r["prefixes"]
    assert "xAI" in r["_grok"]


def test_paste_pack_is_claude_not_pulse_rewrite():
    p = paste_pack("claude", "Where is Pulse?")
    assert "pulse.py" in p
    assert "Do not scrape" in p
    assert "Where is Pulse?" in p
    g = paste_pack("grok", "QQQ?")
    assert "QQQ is not NQ" in g
