"""Transparent one-snapshot execution-cost estimates for Databento MBP-10.

These estimates reprice an immediate market-order sweep against displayed depth.
They are counterfactual research outputs, not simulated queue fills or broker bills.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Iterable, Mapping


_FEE_COMPONENTS = (
    "broker_per_contract",
    "exchange_per_contract",
    "clearing_per_contract",
    "regulatory_per_contract",
    "other_per_contract",
    "per_order",
)


def _finite_nonnegative(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite non-negative number")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{name} must be a finite non-negative number") from None
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{name} must be a finite non-negative number")
    return number


@dataclass(frozen=True)
class FeeSchedule:
    """User-supplied fee schedule, denominated per side in one currency."""

    broker_per_contract: float = 0.0
    exchange_per_contract: float = 0.0
    clearing_per_contract: float = 0.0
    regulatory_per_contract: float = 0.0
    other_per_contract: float = 0.0
    per_order: float = 0.0
    currency: str = "USD"
    source: str = ""
    effective_date: str = ""

    def __post_init__(self):
        for name in _FEE_COMPONENTS:
            object.__setattr__(self, name, _finite_nonnegative(getattr(self, name), name))
        if not isinstance(self.currency, str) or not self.currency.strip() or len(self.currency) > 8:
            raise ValueError("fee schedule currency must be a short non-empty string")
        if not isinstance(self.source, str) or not self.source.strip() or len(self.source) > 240:
            raise ValueError("fee schedule source is required (for example, broker rate card)")
        if not isinstance(self.effective_date, str) or len(self.effective_date) > 32:
            raise ValueError("fee schedule effective_date must be a short string")
        object.__setattr__(self, "currency", self.currency.strip().upper())
        object.__setattr__(self, "source", self.source.strip())
        object.__setattr__(self, "effective_date", self.effective_date.strip())

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "FeeSchedule":
        if not isinstance(value, Mapping):
            raise ValueError("fee_schedule must be an object")
        extra = set(value) - set(_FEE_COMPONENTS) - {"currency", "source", "effective_date"}
        if extra:
            raise ValueError(f"unknown fee schedule fields: {sorted(extra)}")
        components = {name: _finite_nonnegative(value.get(name, 0), name) for name in _FEE_COMPONENTS}
        currency = value.get("currency", "USD")
        source = value.get("source", "")
        effective_date = value.get("effective_date", "")
        if not isinstance(currency, str) or not currency.strip() or len(currency) > 8:
            raise ValueError("fee schedule currency must be a short non-empty string")
        if not isinstance(source, str) or not source.strip() or len(source) > 240:
            raise ValueError("fee schedule source is required (for example, broker rate card)")
        if not isinstance(effective_date, str) or len(effective_date) > 32:
            raise ValueError("fee schedule effective_date must be a short string")
        return cls(**components, currency=currency, source=source, effective_date=effective_date)

    def breakdown(self, filled_contracts: int) -> dict[str, float]:
        if type(filled_contracts) is not int or filled_contracts < 0:
            raise ValueError("filled_contracts must be a non-negative integer")
        result = {name: getattr(self, name) * filled_contracts for name in _FEE_COMPONENTS[:-1]}
        result["per_order"] = self.per_order if filled_contracts else 0.0
        result["total_one_side"] = sum(result.values())
        if not all(math.isfinite(amount) for amount in result.values()):
            raise ValueError("fee schedule total overflowed; use finite, correctly scaled rates")
        return result


def estimate_book_sweep(
    events: Iterable[Mapping[str, Any]],
    *,
    side: str,
    quantity: int,
    tick_size: float,
    point_value: float,
    fee_schedule: FeeSchedule,
) -> dict[str, Any]:
    """Estimate an immediate market order against the latest valid MBP-10 book.

    The sweep fills only the quantity visible in the supplied top-ten snapshot.
    It never extrapolates beyond displayed depth. ``events`` should come from the
    Databento ``depth_events(..., schema="mbp-10")`` adapter.
    """
    if side not in ("buy", "sell"):
        raise ValueError("side must be 'buy' or 'sell'")
    if type(quantity) is not int or quantity <= 0:
        raise ValueError("quantity must be a positive integer contract count")
    tick_size = _finite_nonnegative(tick_size, "tick_size")
    point_value = _finite_nonnegative(point_value, "point_value")
    if tick_size == 0 or point_value == 0:
        raise ValueError("tick_size and point_value must be positive")
    if not isinstance(fee_schedule, FeeSchedule):
        raise ValueError("fee_schedule must be a validated FeeSchedule")

    candidates = []
    for event in events:
        if not isinstance(event, Mapping) or event.get("schema") != "mbp-10":
            continue
        levels = event.get("levels")
        if not isinstance(levels, list) or not levels:
            continue
        try:
            recv_ns = int(event.get("ts_recv_ns") or event.get("ts_event_ns") or 0)
        except (TypeError, ValueError, OverflowError):
            continue
        if recv_ns > 0:
            candidates.append((recv_ns, event, levels))
    if not candidates:
        raise ValueError("no timestamped Databento MBP-10 depth snapshot is available")

    recv_ns, event, levels = max(candidates, key=lambda item: (item[0], int(item[1].get("sequence") or 0)))
    book = {"bid": [], "ask": []}
    for level in levels:
        if not isinstance(level, Mapping):
            continue
        for label, px_key, size_key in (("bid", "bid_px", "bid_sz"), ("ask", "ask_px", "ask_sz")):
            try:
                price = float(level.get(px_key))
                size = int(level.get(size_key) or 0)
            except (TypeError, ValueError, OverflowError):
                continue
            if math.isfinite(price) and size > 0:
                book[label].append((price, size))
    book["bid"].sort(key=lambda item: item[0], reverse=True)
    book["ask"].sort(key=lambda item: item[0])
    if not book["bid"] or not book["ask"]:
        raise ValueError("snapshot does not contain positive displayed size on both best bid and ask")
    best_bid, best_ask = book["bid"][0][0], book["ask"][0][0]
    if best_bid >= best_ask:
        raise ValueError("snapshot is crossed or locked; no estimate produced")

    reference_mid = (best_bid + best_ask) / 2.0
    if not math.isfinite(reference_mid):
        raise ValueError("book midpoint overflowed; snapshot prices are out of range")
    contra = book["ask"] if side == "buy" else book["bid"]
    best_execution_price = contra[0][0]
    remaining = quantity
    notional = 0.0
    fills = []
    for price, displayed in contra:
        take = min(remaining, displayed)
        if take:
            fills.append({"price": price, "contracts": take})
            notional += price * take
            remaining -= take
        if remaining == 0:
            break
    filled = quantity - remaining
    vwap = notional / filled if filled else None
    direction = 1.0 if side == "buy" else -1.0
    slippage_points = direction * (vwap - reference_mid) if vwap is not None else None
    slippage_dollars = slippage_points * point_value * filled if slippage_points is not None else None
    spread_points = direction * (best_execution_price - reference_mid) if filled else None
    impact_points = direction * (vwap - best_execution_price) if vwap is not None else None
    fee_breakdown = fee_schedule.breakdown(filled)
    fee_round_trip = fee_schedule.breakdown(filled)["total_one_side"] * 2.0 if filled else 0.0
    if not math.isfinite(fee_round_trip):
        raise ValueError("round-trip fee estimate overflowed; check fee schedule scale")
    age_ns = time.time_ns() - recv_ns
    computed_costs = (slippage_dollars,
                      spread_points * point_value * filled if spread_points is not None else None,
                      impact_points * point_value * filled if impact_points is not None else None)
    if vwap is not None and (not math.isfinite(vwap) or not all(math.isfinite(x) for x in computed_costs if x is not None)):
        raise ValueError("book cost calculation overflowed; check the price scale and order quantity")
    one_side_cost = (slippage_dollars + fee_breakdown["total_one_side"]
                     if slippage_dollars is not None else None)
    if one_side_cost is not None and not math.isfinite(one_side_cost):
        raise ValueError("all-in cost calculation overflowed; check price and fee scales")
    return {
        "estimate_type": "counterfactual_displayed_book_sweep",
        "asset": str(event.get("symbol") or ""),
        "side": side,
        "requested_contracts": quantity,
        "estimated_filled_contracts": filled,
        "unpriced_contracts": remaining,
        "complete_book_coverage": remaining == 0,
        "book_source": "Databento MBP-10",
        "book_event_ns": event.get("ts_event_ns"),
        "book_received_ns": recv_ns,
        "book_age_seconds": age_ns / 1_000_000_000.0 if age_ns >= 0 else None,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "midpoint_reference": reference_mid,
        "sweep_vwap": vwap,
        "estimated_slippage_points_vs_mid": slippage_points,
        "estimated_slippage_ticks_vs_mid": slippage_points / tick_size if slippage_points is not None else None,
        "estimated_slippage_currency": slippage_dollars,
        "estimated_complete_order_slippage_currency": slippage_dollars if remaining == 0 else None,
        "spread_cost_currency": spread_points * point_value * filled if spread_points is not None else None,
        "displayed_depth_impact_currency": impact_points * point_value * filled if impact_points is not None else None,
        "estimated_one_side_cost_for_estimated_fills_currency": one_side_cost,
        "estimated_complete_one_side_cost_currency": one_side_cost if remaining == 0 else None,
        "fees_currency": fee_schedule.currency,
        "fee_schedule_source": fee_schedule.source,
        "fee_schedule_effective_date": fee_schedule.effective_date or None,
        "fees_one_side_for_estimated_fills": fee_breakdown,
        "fees_round_trip_if_same_schedule": fee_round_trip,
        "components": fills,
        "actual_costs_verified": False,
        "execution_authorized": False,
        "limitations": [
            "A static displayed-book sweep is not a fill simulation or a broker invoice.",
            "No queue priority, latency, hidden liquidity, cancellation, routing, or market response is modeled.",
            "Only displayed top-ten size is priced; any remaining quantity is explicitly unpriced.",
            "Fee values and source are supplied by the operator and are not verified by Databento.",
            "A one-sided book snapshot cannot establish round-trip slippage.",
        ],
    }


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def summarize_book_sweep_window(
    events: Iterable[Mapping[str, Any]],
    *,
    side: str,
    quantity: int,
    tick_size: float,
    point_value: float,
    fee_schedule: FeeSchedule,
) -> dict[str, Any]:
    """Summarize the same hypothetical sweep across captured Databento updates.

    Each update is a sample; this is update-weighted, not time-weighted or an
    independent-trial estimate. Only snapshots with enough displayed quantity
    contribute to complete-order cost percentiles.
    """
    rows = list(events)
    unique = {}
    for event in rows:
        if not isinstance(event, Mapping) or event.get("schema") != "mbp-10":
            continue
        try:
            received = int(event.get("ts_recv_ns") or event.get("ts_event_ns") or 0)
            sequence = int(event.get("sequence") or 0)
        except (TypeError, ValueError, OverflowError):
            continue
        if received > 0 and isinstance(event.get("levels"), list):
            unique[(received, sequence)] = event

    estimates = []
    for event in unique.values():
        try:
            estimates.append(estimate_book_sweep(
                [event], side=side, quantity=quantity, tick_size=tick_size,
                point_value=point_value, fee_schedule=fee_schedule))
        except ValueError:
            continue
    complete = [row for row in estimates if row["complete_book_coverage"]]
    slips = [float(row["estimated_complete_order_slippage_currency"]) for row in complete]
    ticks = [float(row["estimated_slippage_ticks_vs_mid"]) for row in complete]
    spread = [float(row["spread_cost_currency"]) for row in complete]
    impact = [float(row["displayed_depth_impact_currency"]) for row in complete]
    fees_per_order = fee_schedule.breakdown(quantity)["total_one_side"] if complete else None
    total_costs = [value + fees_per_order for value in slips] if fees_per_order is not None else []
    timestamps = sorted(key[0] for key in unique)
    return {
        "sample_method": "Databento MBP-10 book updates; update-weighted",
        "sampled_book_updates": len(estimates),
        "complete_order_samples": len(complete),
        "incomplete_or_invalid_updates": len(unique) - len(estimates),
        "incomplete_depth_samples": len(estimates) - len(complete),
        "window_start_received_ns": timestamps[0] if timestamps else None,
        "window_end_received_ns": timestamps[-1] if timestamps else None,
        "complete_order_slippage_currency": {
            "p50": _percentile(slips, .50), "p90": _percentile(slips, .90),
            "p95": _percentile(slips, .95), "p99": _percentile(slips, .99),
        },
        "complete_order_cost_currency_including_fees": {
            "p50": _percentile(total_costs, .50), "p90": _percentile(total_costs, .90),
            "p95": _percentile(total_costs, .95), "p99": _percentile(total_costs, .99),
        },
        "slippage_ticks_vs_mid": {
            "p50": _percentile(ticks, .50), "p90": _percentile(ticks, .90),
            "p95": _percentile(ticks, .95), "p99": _percentile(ticks, .99),
        },
        "spread_cost_currency": {"p50": _percentile(spread, .50), "p90": _percentile(spread, .90)},
        "displayed_depth_impact_currency": {"p50": _percentile(impact, .50), "p90": _percentile(impact, .90)},
        "fees_per_complete_order_one_side": fees_per_order,
        "limitations": [
            "The feed retains a bounded live window; this is not a full historical distribution.",
            "Updates are event-weighted, clustered, and not statistically independent or time-weighted.",
            "Percentiles exclude updates where the requested order exceeded displayed top-ten depth.",
        ],
    }


def reconcile_fills(
    events: Iterable[Mapping[str, Any]],
    fills: Iterable[Mapping[str, Any]],
    *,
    tick_size: float,
    point_value: float,
    fee_schedule: FeeSchedule,
) -> list[dict[str, Any]]:
    """Compare supplied fill records with the latest preceding MBP-10 snapshot."""
    snapshots = []
    for event in events:
        if not isinstance(event, Mapping) or event.get("schema") != "mbp-10" or not isinstance(event.get("levels"), list):
            continue
        try:
            received = int(event.get("ts_recv_ns") or event.get("ts_event_ns") or 0)
        except (TypeError, ValueError, OverflowError):
            continue
        if received > 0:
            snapshots.append((received, event))
    snapshots.sort(key=lambda item: item[0])
    fill_rows = list(fills)
    if len(fill_rows) > 500:
        raise ValueError("fills is limited to 500 records per request")
    output = []
    for index, fill in enumerate(fill_rows):
        if not isinstance(fill, Mapping):
            raise ValueError(f"fills[{index}] must be an object")
        fill_id = fill.get("fill_id")
        if fill_id is not None and (not isinstance(fill_id, str) or len(fill_id) > 128):
            raise ValueError(f"fills[{index}].fill_id must be a string of at most 128 characters")
        extra = set(fill) - {"timestamp_ns", "side", "quantity", "price", "actual_fee", "actual_fee_currency", "fill_id"}
        required = {"timestamp_ns", "side", "quantity", "price"}
        if extra or required - set(fill):
            raise ValueError(f"fills[{index}] requires {sorted(required)}; unknown={sorted(extra)}")
        ts_ns = fill["timestamp_ns"]
        if type(ts_ns) is not int or ts_ns <= 0:
            raise ValueError(f"fills[{index}].timestamp_ns must be a positive epoch-nanosecond integer")
        side = fill["side"]
        if side not in ("buy", "sell"):
            raise ValueError(f"fills[{index}].side must be 'buy' or 'sell'")
        quantity = fill["quantity"]
        if type(quantity) is not int or quantity <= 0:
            raise ValueError(f"fills[{index}].quantity must be a positive integer")
        price = fill["price"]
        if isinstance(price, bool):
            raise ValueError(f"fills[{index}].price must be finite")
        try:
            price = float(price)
        except (TypeError, ValueError, OverflowError):
            raise ValueError(f"fills[{index}].price must be finite") from None
        if not math.isfinite(price):
            raise ValueError(f"fills[{index}].price must be finite")
        actual_fee = fill.get("actual_fee")
        if actual_fee is not None:
            actual_fee = _finite_nonnegative(actual_fee, f"fills[{index}].actual_fee")
            actual_currency = fill.get("actual_fee_currency", fee_schedule.currency)
            if actual_currency != fee_schedule.currency:
                raise ValueError(f"fills[{index}].actual_fee_currency must match fee_schedule currency")
        prior = [event for received, event in snapshots if received <= ts_ns]
        if not prior:
            output.append({"fill_id": fill_id, "status": "NO_PRECEDING_BOOK_SNAPSHOT",
                           "timestamp_ns": ts_ns, "comparison": None})
            continue
        snapshot = max(prior, key=lambda event: int(event.get("ts_recv_ns") or event.get("ts_event_ns") or 0))
        received = int(snapshot.get("ts_recv_ns") or snapshot.get("ts_event_ns") or 0)
        try:
            book_estimate = estimate_book_sweep(
                [snapshot], side=side, quantity=quantity, tick_size=tick_size,
                point_value=point_value, fee_schedule=fee_schedule)
        except ValueError as ex:
            output.append({"fill_id": fill_id, "status": "BOOK_UNUSABLE",
                           "timestamp_ns": ts_ns, "book_received_ns": received,
                           "reason": str(ex), "comparison": None})
            continue
        direction = 1.0 if side == "buy" else -1.0
        actual_slippage = direction * (price - book_estimate["midpoint_reference"]) * point_value * quantity
        if not math.isfinite(actual_slippage):
            raise ValueError(f"fills[{index}] slippage calculation overflowed")
        complete = book_estimate["complete_book_coverage"]
        book_age_ms = (ts_ns - received) / 1_000_000.0
        row = {
            "fill_id": fill_id, "status": "MATCHED",
            "timestamp_ns": ts_ns, "book_received_ns": received,
            "book_age_ms_at_fill": book_age_ms,
            "side": side, "quantity": quantity, "fill_price": price,
            "midpoint_at_preceding_book": book_estimate["midpoint_reference"],
            "actual_slippage_currency_vs_preceding_midpoint": actual_slippage,
            "actual_fee_currency": actual_fee,
            "actual_fee_verified": False,
            "modeled_fee_currency_for_fill": fee_schedule.breakdown(quantity)["total_one_side"],
            "actual_minus_modeled_fee_currency": actual_fee - fee_schedule.breakdown(quantity)["total_one_side"] if actual_fee is not None else None,
            "same_snapshot_sweep_vwap": book_estimate["sweep_vwap"] if complete else None,
            "same_snapshot_sweep_slippage_currency": book_estimate["estimated_complete_order_slippage_currency"],
            "actual_minus_sweep_slippage_currency": actual_slippage - book_estimate["estimated_complete_order_slippage_currency"] if complete else None,
            "fee_schedule_source": fee_schedule.source,
        }
        output.append(row)
    return output
