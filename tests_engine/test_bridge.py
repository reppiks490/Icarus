# Grok (xAI) — 2026-09-20. Whole file. Bridge mapping / planner / alert parser — no Alpaca, no network.
"""icarus_bridge money path, offline."""
from __future__ import annotations

import json
import pytest

from icarus_bridge.config import Settings
from icarus_bridge.executor import plan_mirror
from icarus_bridge.mapping import levels_from_alert, map_symbol, shares_per_contract, target_shares
from icarus_bridge.models import Alert, AlertParseError, parse_alert


def _cfg(**kw) -> Settings:
    s = Settings()
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def test_map_symbol_nq1_is_qqq_not_a_cme_contract():
    m = _cfg().symbol_map
    assert map_symbol("NQ1!", m) == "QQQ"
    assert map_symbol("CME_MINI:NQ1!", m) == "QQQ"
    assert map_symbol("NQZ2026", m) == "QQQ"
    assert map_symbol("ES1!", m) == "SPY"
    assert map_symbol("NOPE", m) is None


def test_levels_are_percent_of_futures_ref_not_points_on_qqq():
    """45 NQ pts at 20_000 is 0.225% — that % is what QQQ gets, not 45 QQQ points."""
    a = Alert(event="order_fill", ticker="NQ1!", meta={"tp1": 15, "tp2": 30, "sl": 45, "ref": 20000.0})
    lev = levels_from_alert(a, _cfg())
    assert lev.source == "meta"
    assert abs(lev.sl_pct - 45 / 20000) < 1e-12
    assert abs(lev.tp1_pct - 15 / 20000) < 1e-12
    tqqq = levels_from_alert(a, _cfg(leverage_factor=3.0))
    assert abs(tqqq.sl_pct - 3 * 45 / 20000) < 1e-12


def test_notional_sizing_and_max_clamp():
    cfg = _cfg(sizing_mode="notional", notional_per_contract_usd=20000.0, max_position_shares=400)
    spc = shares_per_contract(cfg, 500.0)  # 20000/500 = 40 QQQ per NQ
    assert abs(spc - 40.0) < 1e-9
    assert target_shares(5, spc, cfg.max_position_shares) == 200
    assert target_shares(20, spc, cfg.max_position_shares) == 400  # clamp
    assert target_shares(-2, spc, cfg.max_position_shares) == -80


def test_plan_mirror_cannot_flip_equities_in_one_order():
    acts = plan_mirror(40, -40, protective_stop_price=99.0)
    kinds = [a.kind for a in acts]
    assert kinds[:2] == ["close", "market"]
    assert acts[0].purpose == "reverse" and acts[1].purpose == "reverse"
    assert any(a.kind == "stop" and a.side == "buy" for a in acts)


def test_plan_mirror_noop_when_already_in_sync():
    acts = plan_mirror(0, 0)
    assert len(acts) == 1 and acts[0].kind == "noop"


def test_parse_alert_rejects_unsubstituted_placeholders():
    with pytest.raises(AlertParseError, match="placeholders"):
        parse_alert('{"event":"order_fill","ticker":"{{ticker}}","secret":"x"}', expected_secret="x")


def test_parse_alert_short_signs_position_and_checks_secret():
    body = json.dumps({
        "secret": "s3cret", "event": "order_fill", "ticker": "NQ1!",
        "action": "sell", "contracts": "5", "order_id": "Short",
        "position_size": "5", "market_position": "short",
        "prev_market_position": "flat", "order_price": "24700",
        "meta": "sys=RATE;side=short;sl=45;ref=24700",
    })
    a = parse_alert(body, expected_secret="s3cret")
    assert a.position_size == -5 and a.is_entry
    with pytest.raises(AlertParseError, match="secret"):
        parse_alert(body, expected_secret="wrong")
