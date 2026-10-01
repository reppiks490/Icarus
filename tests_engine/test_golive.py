# Grok (xAI) — 2026-09-21. Go-live integrity: paper is not a broker.
from icarus_engine.golive import from_status


def _status(**kw):
    nq = {
        "symbol": "NQ",
        "price": 30090.25,
        "price_age": 8,
        "feed_delay": 600,
        "bar_age": 12,
        "bar_index": 40,
        "market": {"describe": "open RTH"},
        "state": {"in_session": True, "entry_allowed": True},
        "live_profit": 0.0,
        "open_profit": 0.0,
    }
    nq.update(kw.pop("nq", {}))
    base = {
        "now": 1_779_000_000.0,
        "net": 214815.13,
        "live_profit": 0.0,
        "open_profit": 0.0,
        "positions": 0,
        "assets": [nq],
    }
    base.update(kw)
    return base


def test_warmup_is_separated_from_live_and_broker_never_armed(tmp_path):
    r = from_status(_status(), feed="yahoo", env={"ALPACA_PAPER": "true"}, base_dir=str(tmp_path))
    assert r["broker_armed"] is False
    assert r["verdict"] == "PAPER_ONLY"
    assert r["warmup_pnl"] == 214815.13
    assert r["live_pnl"] == 0.0
    assert "QQQ" in r["brains"]["A"]
    assert any(g["id"] == "qqq_is_not_nq" and g["ok"] is False for g in r["gates"])
    assert any(g["id"] == "broker" and g["ok"] is False for g in r["gates"])


def test_file_feed_identity_and_live_keys_forbidden(tmp_path):
    r = from_status(_status(), feed="file", env={"ALPACA_PAPER": "true"}, base_dir=str(tmp_path))
    assert r["feed"] == "file"
    assert "CSV" in r["identity"] or "FileFeed" in r["identity"]
    bad = from_status(_status(), feed="yahoo", env={"ALPACA_PAPER": "false"}, base_dir=str(tmp_path))
    assert bad["verdict"] == "LIVE_KEYS_FORBIDDEN"


def test_no_tape_verdict(tmp_path):
    r = from_status(
        _status(assets=[{"symbol": "NQ", "price": None, "bar_index": -1, "market": {}, "state": {}}]),
        feed="yahoo",
        env={"ALPACA_PAPER": "true"},
        base_dir=str(tmp_path),
    )
    assert r["verdict"] == "NO_TAPE"
