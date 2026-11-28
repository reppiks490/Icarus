"""Phase 5: deterministic synthetic limit-order-book research sandbox.

This is an educational discrete-event exchange with strict quantity
conservation, price/time priority, and self-match prevention. It is NOT a
calibrated exchange simulator or evidence of a profitable trading strategy.
All outputs are explicitly tagged synthetic and have zero trading authority.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from .contracts import identity, utc

_AUTHORITY = {"research_only": True, "execution_authorized": False,
              "production_decision_authorized": False, "auto_promote": False}
_KINDS = {"limit", "market", "cancel"}
_SIDES = {"buy", "sell"}


def _integer(x: Any, name: str, minimum: int, maximum: int) -> int:
    if type(x) is not int or not minimum <= x <= maximum:
        raise ValueError(f"{name} must be integer in [{minimum}, {maximum}]")
    return x


def _str(x: Any, name: str, limit: int = 64) -> str:
    if not isinstance(x, str) or not 1 <= len(x) <= limit:
        raise ValueError(f"invalid {name}")
    return x


def replay_book(events: list[Mapping[str, Any]]) -> dict:
    """Replay observed event ordering into a *synthetic* exchange state."""
    if not isinstance(events, list) or len(events) > 10000:
        raise ValueError("0–10000 synthetic events required")
    resting = {}
    used_ids = set()
    used_events = set()
    trades = []
    total_submitted = 0
    total_canceled = 0
    total_unfilled_market = 0
    previous_received = None
    event_count = 0
    for row in events:
        required = {"event_id", "observed_at", "received_at", "kind",
                    "order_id", "actor", "side", "quantity", "price_ticks"}
        if not isinstance(row, Mapping) or set(row) != required:
            raise ValueError("invalid synthetic event schema")
        eid = _str(row["event_id"], "event ID")
        if eid in used_events:
            raise ValueError("duplicate event ID")
        used_events.add(eid)
        observed, received = utc(row["observed_at"]), utc(row["received_at"])
        if received < observed:
            raise ValueError("future synthetic event")
        if previous_received is not None and received <= previous_received:
            raise ValueError("non-increasing receive time")
        previous_received = received
        kind, oid, actor = row["kind"], _str(row["order_id"], "order ID"), _str(row["actor"], "actor")
        if kind not in _KINDS:
            raise ValueError("unsupported order kind")
        if kind == "cancel":
            if row["side"] is not None or row["quantity"] != 0 or row["price_ticks"] is not None:
                raise ValueError("cancel must not carry price, side or size")
            order = resting.get(oid)
            if order is None or order["actor"] != actor:
                raise ValueError("cannot cancel missing/other actor order")
            total_canceled += order["quantity"]
            del resting[oid]
            event_count += 1
            continue
        side, qty = row["side"], row["quantity"]
        if side not in _SIDES:
            raise ValueError("invalid side")
        qty = _integer(qty, "quantity", 1, 1_000_000)
        total_submitted += qty
        price = row["price_ticks"]
        if kind == "limit":
            price = _integer(price, "price_ticks", 1, 1_000_000_000)
        elif price is not None:
            raise ValueError("market order must not specify limit price")
        if oid in used_ids:
            raise ValueError("duplicate order ID")
        used_ids.add(oid)
        remaining = qty
        # Price-time priority: buy takes lowest ask, sell takes highest bid.
        candidates = [
            (key, order) for key, order in resting.items()
            if order["side"] != side and order["actor"] != actor
            and (kind == "market" or
                 (order["price_ticks"] <= price if side == "buy"
                  else order["price_ticks"] >= price))
        ]
        candidates.sort(key=lambda item: (
            item[1]["price_ticks"] if side == "buy" else -item[1]["price_ticks"],
            item[1]["sequence"],
        ))
        for maker_id, maker in candidates:
            if remaining == 0:
                break
            filled = min(remaining, maker["quantity"])
            if filled <= 0:
                raise AssertionError("nonpositive trade impossible")
            trades.append({
                "event_id": eid, "maker_order": maker_id,
                "taker_order": oid, "buyer": actor if side == "buy" else maker["actor"],
                "seller": actor if side == "sell" else maker["actor"],
                "quantity": filled, "price_ticks": maker["price_ticks"],
            })
            maker["quantity"] -= filled
            remaining -= filled
            if maker["quantity"] == 0:
                del resting[maker_id]
        if kind == "market":
            total_unfilled_market += remaining
        if kind == "limit" and remaining:
            if len(resting) >= 5000:
                raise ValueError("synthetic book capacity exceeded")
            resting[oid] = {"actor": actor, "side": side,
                            "price_ticks": price, "quantity": remaining,
                            "sequence": event_count}
        event_count += 1
    buys = [row for row in resting.values() if row["side"] == "buy"]
    sells = [row for row in resting.values() if row["side"] == "sell"]
    resting_quantity = sum(r["quantity"] for r in resting.values())
    executed_quantity = sum(row["quantity"] for row in trades)
    # Every trade consumes one maker unit AND one taker unit.
    conserved = (total_submitted == (
        resting_quantity + total_canceled + total_unfilled_market
        + 2 * executed_quantity
    ))
    if not conserved:
        raise AssertionError("synthetic exchange quantity conservation failed")
    return {
        "schema_version": "icarus-omnigenesis-synthetic-book-v1",
        "evidence_kind": "SYNTHETIC",
        "authority": dict(_AUTHORITY),
        "event_count": event_count,
        "trade_count": len(trades),
        "executed_quantity": executed_quantity,
        "submitted_quantity": total_submitted,
        "canceled_quantity": total_canceled,
        "unfilled_market_quantity": total_unfilled_market,
        "quantity_conserved": conserved,
        "best_bid_ticks": max((r["price_ticks"] for r in buys), default=None),
        "best_ask_ticks": min((r["price_ticks"] for r in sells), default=None),
        "resting_buy_quantity": sum(r["quantity"] for r in buys),
        "resting_sell_quantity": sum(r["quantity"] for r in sells),
        "resting_orders": len(resting),
        "trades": trades,
        "scenario_id": identity({"events": events}),
    }


def synthetic_scenario(seed: int, steps: int = 100, anchor_ticks: int = 10000) -> list[dict]:
    """Deterministically generate toy book-flow; not sampled from real markets."""
    seed = _integer(seed, "seed", 0, 2**32 - 1)
    steps = _integer(steps, "steps", 2, 10000)
    anchor_ticks = _integer(anchor_ticks, "anchor_ticks", 10, 1_000_000_000)
    rng = random.Random(seed)
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = []
    for i in range(steps):
        side = "buy" if rng.randrange(2) == 0 else "sell"
        kind = "limit" if i < 10 or rng.random() < 0.72 else "market"
        # Resting limit orders are placed either side of the synthetic mid.
        price = (anchor_ticks + (-rng.randint(1, 8) if side == "buy"
                                 else rng.randint(1, 8))) if kind == "limit" else None
        ts = t + timedelta(milliseconds=10 * i)
        result.append({
            "event_id": f"evt_{i:06d}",
            "observed_at": ts.isoformat(),
            "received_at": (ts + timedelta(milliseconds=1)).isoformat(),
            "kind": kind,
            "order_id": f"ord_{i:06d}",
            "actor": f"agent_{rng.randrange(16)}",
            "side": side,
            "quantity": rng.randint(1, 30),
            "price_ticks": price,
        })
    return result
