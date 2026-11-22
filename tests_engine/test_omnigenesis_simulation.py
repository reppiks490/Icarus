"""Phase 5 synthetic matching engine invariants and determinism."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

import pytest

from icarus_engine.omnigenesis.simulation import replay_book, synthetic_scenario


def event(i, kind, actor, side, qty, price, oid):
    t = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=i * 10)
    return {
        "event_id": f"event_{i}", "observed_at": t.isoformat(),
        "received_at": (t + timedelta(milliseconds=1)).isoformat(),
        "kind": kind, "order_id": oid, "actor": actor, "side": side,
        "quantity": qty, "price_ticks": price,
    }


def test_price_time_and_conservation():
    events = [
        event(0, "limit", "seller_a", "sell", 2, 100, "a"),
        event(1, "limit", "seller_b", "sell", 3, 100, "b"),
        event(2, "market", "buyer", "buy", 4, None, "take"),
    ]
    report = replay_book(events)
    assert [x["maker_order"] for x in report["trades"]] == ["a", "b"]
    assert [x["quantity"] for x in report["trades"]] == [2, 2]
    assert report["executed_quantity"] == 4
    assert report["resting_sell_quantity"] == 1
    assert report["best_ask_ticks"] == 100
    assert report["evidence_kind"] == "SYNTHETIC"
    assert report["authority"]["execution_authorized"] is False


def test_price_priority_before_arrival_priority():
    events = [
        event(0, "limit", "maker_a", "sell", 1, 102, "a"),
        event(1, "limit", "maker_b", "sell", 1, 100, "b"),
        event(2, "market", "taker", "buy", 2, None, "take"),
    ]
    report = replay_book(events)
    assert [r["price_ticks"] for r in report["trades"]] == [100, 102]


def test_partial_limit_matching_resting_residual():
    events = [
        event(0, "limit", "seller", "sell", 2, 100, "ask"),
        event(1, "limit", "buyer", "buy", 5, 101, "bid"),
    ]
    report = replay_book(events)
    assert report["executed_quantity"] == 2
    assert report["resting_buy_quantity"] == 3
    assert report["resting_sell_quantity"] == 0
    assert report["best_bid_ticks"] == 101


def test_self_match_prevention():
    events = [
        event(0, "limit", "same", "sell", 2, 100, "ask"),
        event(1, "market", "same", "buy", 2, None, "buy"),
    ]
    report = replay_book(events)
    assert report["trade_count"] == 0
    assert report["resting_sell_quantity"] == 2


def test_cancellation_ownership():
    events = [
        event(0, "limit", "maker", "buy", 3, 99, "bid"),
        event(1, "cancel", "maker", None, 0, None, "bid"),
    ]
    assert replay_book(events)["resting_orders"] == 0
    events[-1]["actor"] = "intruder"
    with pytest.raises(ValueError, match="other actor"):
        replay_book(events)


def test_replay_seeded_scenarios_reproducible():
    stream = synthetic_scenario(19, 500)
    assert stream == synthetic_scenario(19, 500)
    first = replay_book(stream)
    assert first == replay_book(stream)
    assert first["event_count"] == 500
    assert first["evidence_kind"] == "SYNTHETIC"
    assert all(r["buyer"] != r["seller"] for r in first["trades"])


def test_duplicate_id_future_timestamp_and_negative_quantity_rejected():
    events = [event(0, "limit", "seller", "sell", 2, 100, "ask")]
    broken = copy.deepcopy(events)
    broken.append(event(1, "limit", "buyer", "buy", 1, 101, "ask"))
    with pytest.raises(ValueError, match="duplicate order"):
        replay_book(broken)
    broken = copy.deepcopy(events)
    broken[0]["received_at"] = "2025-01-01T00:00:00Z"
    with pytest.raises(ValueError, match="future synthetic"):
        replay_book(broken)
    broken = copy.deepcopy(events)
    broken[0]["quantity"] = -1
    with pytest.raises(ValueError, match="quantity"):
        replay_book(broken)
