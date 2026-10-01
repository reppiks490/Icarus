# Grok (xAI) — 2026-09-21. /status/public must never empty-reply (dashboard ENGINE UNREACHABLE).
import json

from icarus_engine.runtime import _clean
from icarus_engine.server import dumps_safe


def test_clean_strips_nan_and_inf():
    out = _clean({"hurst": float("nan"), "px": float("inf"), "ok": 1.5, "nested": [float("-inf"), 2]})
    assert out["hurst"] is None
    assert out["px"] is None
    assert out["ok"] == 1.5
    assert out["nested"] == [None, 2]


def test_dumps_safe_never_raises_on_nan():
    raw = dumps_safe({"equity": float("nan"), "assets": [{"symbol": "NQ", "price": float("inf")}]})
    d = json.loads(raw)
    assert d["equity"] is None
    assert d["assets"][0]["price"] is None


def test_dumps_safe_fallback_on_cycle():
    a = {}
    a["self"] = a
    raw = dumps_safe(a)
    d = json.loads(raw)
    assert d.get("ok") is False
    assert "detail" in d
