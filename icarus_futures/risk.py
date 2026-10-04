# CL (Claude, Anthropic) — 2026-10-04 — icarus_futures.risk: portfolio-wide risk governor above every strategy
"""Evaluated BEFORE an intent can reach any venue adapter; nothing downstream can
override a veto. Exposure is economic, not unit counts: full-size equivalents (MNQ =
0.1 NQ), notional = qty x price x point value, cluster budgets (equity index: NQ/ES/YM/
RTY and micros; metals: GC/SI and micros), gross notional, loss limits (daily, rolling,
drawdown), and state gates (global pause, broker/engine mismatch, stale data, volatility
shock, event blackout, session window). Reducing an existing position is always allowed
so risk can come off in every state; everything else returns reason codes."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .contracts import SPECS, ContractSpec

_CODE = re.compile(r"^([A-Z0-9]+?)[FGHJKMNQUVXZ]\d{2}$")


def spec_of(contract: str) -> ContractSpec:
    m = _CODE.match(contract)
    if not m or m.group(1) not in SPECS:
        raise ValueError(f"unknown dated contract {contract!r}")
    return SPECS[m.group(1)]


@dataclass
class RiskConfig:
    max_full_equiv: dict = field(default_factory=lambda: {"NQ": 2.0, "ES": 2.0, "YM": 2.0, "RTY": 2.0,
                                                          "GC": 1.0, "SI": 1.0})
    max_cluster_notional: dict = field(default_factory=lambda: {"equity_index": 1_200_000.0, "metals": 500_000.0})
    max_gross_notional: float = 1_500_000.0
    daily_loss_limit: float = 1_500.0
    rolling_loss_limit: float = 4_000.0
    rolling_days: int = 5
    max_drawdown: float = 6_000.0
    max_data_age_s: float = 15.0
    vol_shock_ratio: float = 3.0
    event_blackouts: list = field(default_factory=list)   # [(start_iso, end_iso, label)]
    session_windows: Optional[list] = None                # [(start "HH:MM", end "HH:MM")] UTC; None = always


@dataclass
class PortfolioState:
    positions: dict = field(default_factory=dict)      # contract -> signed qty
    marks: dict = field(default_factory=dict)          # contract -> last price
    pnl_today: float = 0.0                             # realized + unrealized, USD
    pnl_history: list = field(default_factory=list)    # prior sessions' P&L, USD
    equity: float = 0.0
    equity_peak: float = 0.0
    data_age_s: dict = field(default_factory=dict)     # contract -> seconds since last tick
    vol_ratio: dict = field(default_factory=dict)      # contract -> current/median range
    paused: bool = False
    broker_mismatch: bool = False
    ambiguous_orders: int = 0


@dataclass
class Decision:
    allowed: bool
    codes: list
    reasons: list
    reducing: bool


def _in_window(now: datetime, start: str, end: str) -> bool:
    t = now.strftime("%H:%M")
    return start <= t < end if start <= end else (t >= start or t < end)


class RiskGovernor:
    def __init__(self, cfg: Optional[RiskConfig] = None):
        self.cfg = cfg or RiskConfig()

    def evaluate(self, intent, st: PortfolioState, now: datetime) -> Decision:
        c, codes, why = self.cfg, [], []
        spec = spec_of(intent.symbol)
        pos = st.positions.get(intent.symbol, 0)
        new = pos + intent.signed_qty
        reducing = pos != 0 and abs(new) < abs(pos) and (new == 0 or (new > 0) == (pos > 0))
        if intent.reduce_only and not reducing:
            return Decision(False, ["REDUCE_ONLY_WOULD_ADD"], ["reduce-only intent would add or flip exposure"], False)
        if reducing:
            return Decision(True, [], ["reduces existing exposure"], True)

        def veto(code, msg):
            codes.append(code)
            why.append(msg)

        if st.broker_mismatch:
            veto("BROKER_MISMATCH", "engine and broker positions disagree; reconcile first")
        if st.ambiguous_orders:
            veto("AMBIGUOUS_ORDERS", f"{st.ambiguous_orders} order(s) in unknown venue state")
        if st.paused:
            veto("GLOBAL_PAUSE", "global pause is on")
        age = st.data_age_s.get(intent.symbol)
        if age is None or age > c.max_data_age_s:
            veto("STALE_DATA", f"market data age {age}s exceeds {c.max_data_age_s}s")
        vr = st.vol_ratio.get(intent.symbol)
        if vr is not None and vr > c.vol_shock_ratio:
            veto("VOL_SHOCK", f"range ratio {vr:.2f} exceeds {c.vol_shock_ratio}")
        for s, e, label in c.event_blackouts:
            if datetime.fromisoformat(s) <= now < datetime.fromisoformat(e):
                veto("EVENT_BLACKOUT", f"inside blackout {label}")
        if c.session_windows is not None and not any(_in_window(now, s, e) for s, e in c.session_windows):
            veto("SESSION_CLOSED", "outside configured session windows")
        if st.pnl_today <= -c.daily_loss_limit:
            veto("DAILY_LOSS", f"daily P&L {st.pnl_today:.0f} at or beyond -{c.daily_loss_limit:.0f}")
        roll = sum(st.pnl_history[-(c.rolling_days - 1):]) + st.pnl_today if c.rolling_days > 1 else st.pnl_today
        if roll <= -c.rolling_loss_limit:
            veto("ROLLING_LOSS", f"{c.rolling_days}-session P&L {roll:.0f} at or beyond -{c.rolling_loss_limit:.0f}")
        if st.equity_peak - st.equity >= c.max_drawdown:
            veto("DRAWDOWN", f"drawdown {st.equity_peak - st.equity:.0f} at or beyond {c.max_drawdown:.0f}")

        after = dict(st.positions)
        after[intent.symbol] = new
        price = st.marks.get(intent.symbol, intent.price)
        if price is None:
            veto("NO_PRICE", "no mark price to size the exposure")
        else:
            full = sum(q * spec_of(k).ratio_to_full for k, q in after.items() if spec_of(k).full_root == spec.full_root)
            lim = c.max_full_equiv.get(spec.full_root)
            if lim is not None and abs(full) > lim + 1e-9:
                veto("ASSET_LIMIT", f"{spec.full_root} exposure {full:+.1f} full-size equiv exceeds {lim}")
            marks = dict(st.marks)
            marks[intent.symbol] = price
            notional = {k: spec_of(k).notional(q, marks.get(k, price)) for k, q in after.items() if q}
            cl = sum(v for k, v in notional.items() if spec_of(k).cluster == spec.cluster)
            climit = c.max_cluster_notional.get(spec.cluster)
            if climit is not None and cl > climit:
                veto("CLUSTER_LIMIT", f"{spec.cluster} notional {cl:,.0f} exceeds {climit:,.0f}")
            if sum(notional.values()) > c.max_gross_notional:
                veto("GROSS_LIMIT", f"gross notional {sum(notional.values()):,.0f} exceeds {c.max_gross_notional:,.0f}")
        return Decision(not codes, codes, why, False)
