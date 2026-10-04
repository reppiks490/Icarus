# CL (Claude, Anthropic) — 2026-10-04 — tests for icarus_futures.risk (portfolio risk governor)
from datetime import datetime, timezone

from icarus_futures.orders import Intent
from icarus_futures.risk import PortfolioState, RiskConfig, RiskGovernor

NOW = datetime(2026, 10, 5, 14, 0, tzinfo=timezone.utc)


def _st(**kw):
    st = PortfolioState(marks={"MNQZ26": 20000.0, "NQZ26": 20000.0, "ESZ26": 6000.0, "MGCZ26": 2500.0},
                        data_age_s={"MNQZ26": 1, "NQZ26": 1, "ESZ26": 1, "MGCZ26": 1})
    for k, v in kw.items():
        setattr(st, k, v)
    return st


def _it(sym, side, qty, **kw):
    return Intent("t", sym, side, qty, "MARKET", signal_ts="x", **kw)


def test_micro_and_full_size_share_one_economic_budget():
    g = RiskGovernor(RiskConfig(max_full_equiv={"NQ": 1.0}))
    st = _st(positions={"NQZ26": 1})
    d = g.evaluate(_it("MNQZ26", "BUY", 1), st, NOW)
    assert not d.allowed and "ASSET_LIMIT" in d.codes            # 1 NQ + 0.1 = 1.1 > 1.0
    assert g.evaluate(_it("MNQZ26", "BUY", 1), _st(), NOW).allowed


def test_cluster_notional_counts_nq_and_es_together():
    g = RiskGovernor(RiskConfig(max_cluster_notional={"equity_index": 700_000.0}))
    st = _st(positions={"NQZ26": 1})                              # 400k notional
    d = g.evaluate(_it("ESZ26", "BUY", 1), st, NOW)                # +300k = 700k: at the limit
    assert d.allowed
    d = g.evaluate(_it("ESZ26", "BUY", 2), st, NOW)                # +600k = 1.0M
    assert not d.allowed and "CLUSTER_LIMIT" in d.codes


def test_state_gates_each_veto_with_reason_codes():
    g = RiskGovernor(RiskConfig(event_blackouts=[("2026-10-05T13:55:00+00:00", "2026-10-05T14:05:00+00:00", "CPI")]))
    d = g.evaluate(_it("MNQZ26", "BUY", 1), _st(paused=True, broker_mismatch=True,
                                                data_age_s={"MNQZ26": 99}, vol_ratio={"MNQZ26": 5.0}), NOW)
    assert set(d.codes) >= {"GLOBAL_PAUSE", "BROKER_MISMATCH", "STALE_DATA", "VOL_SHOCK", "EVENT_BLACKOUT"}
    assert len(d.reasons) == len(d.codes)


def test_loss_limits():
    g = RiskGovernor(RiskConfig(daily_loss_limit=1000, rolling_loss_limit=2000, rolling_days=3, max_drawdown=3000))
    assert "DAILY_LOSS" in g.evaluate(_it("MNQZ26", "BUY", 1), _st(pnl_today=-1000), NOW).codes
    assert "ROLLING_LOSS" in g.evaluate(_it("MNQZ26", "BUY", 1), _st(pnl_history=[-900, -900], pnl_today=-300), NOW).codes
    assert "DRAWDOWN" in g.evaluate(_it("MNQZ26", "BUY", 1), _st(equity=7000, equity_peak=10000), NOW).codes


def test_reducing_is_always_allowed_and_reduce_only_cannot_add():
    g = RiskGovernor()
    st = _st(positions={"MNQZ26": 3}, paused=True, broker_mismatch=True, pnl_today=-99999)
    assert g.evaluate(_it("MNQZ26", "SELL", 2), st, NOW).allowed
    assert not g.evaluate(_it("MNQZ26", "SELL", 5), st, NOW).allowed            # would flip short
    d = g.evaluate(_it("MNQZ26", "BUY", 1, reduce_only=True), st, NOW)
    assert not d.allowed and d.codes == ["REDUCE_ONLY_WOULD_ADD"]


def test_session_window():
    g = RiskGovernor(RiskConfig(session_windows=[("13:30", "20:00")]))
    assert g.evaluate(_it("MNQZ26", "BUY", 1), _st(), NOW).allowed
    late = datetime(2026, 10, 5, 21, 0, tzinfo=timezone.utc)
    assert "SESSION_CLOSED" in g.evaluate(_it("MNQZ26", "BUY", 1), _st(), late).codes
