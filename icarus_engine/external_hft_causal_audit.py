"""Read-only as-of MBP L2 partial-book causal audit; NOT HFTBacktest replay.

All input bytes are independently source-anchored and verified by the native
consumer before this diagnostic. A partial price-level map is not a full
exchange book or a queue-position/fill model. No orders are ever submitted.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path

from .external_hft_native_verify import (
    EVENT, NativeVerificationError, _header, _safe, _sha_file,
    verify_native_l2,
)
from .external_hft_stage import FLAG_BUY, FLAG_SELL

BLOCKERS = (
    "SOURCE_AUTHENTICITY_UNVERIFIED",
    "MARKET_DATA_ENTITLEMENT_UNVERIFIED",
    "INITIAL_FULL_BOOK_SNAPSHOT_UNAVAILABLE",
    "EXCHANGE_LOCAL_CLOCK_SYNCHRONIZATION_UNVERIFIED",
    "VENUE_SEQUENCE_GAP_POLICY_UNVERIFIED",
    "QUEUE_POSITION_MODEL_UNCALIBRATED",
    "ORDER_LATENCY_MODEL_UNCALIBRATED",
    "FEES_SLIPPAGE_AND_REAL_FILL_PARITY_UNVERIFIED",
    "HFTBACKTEST_SIMULATOR_NOT_EXECUTED",
    "PROTECTED_HOLDOUT_NOT_APPROVED",
)


class CausalAuditError(ValueError):
    """Fail-closed offline causal research audit."""


def audit_causal_l2(
    source, staging, native_dir, *, expected_contract_id,
    expected_source_id, expected_input_sha256, expected_tick_size,
    expected_lot_size, diagnostic_latency_threshold_ns=None,
):
    """Inspect every verified event in arrival order, with no sampling ceiling.

    The observed map only includes price levels that occurred in this feed;
    missing initial snapshots mean it MUST NOT be interpreted as the true
    exchange book or used to derive fill probabilities.
    """
    if diagnostic_latency_threshold_ns is not None and (
        type(diagnostic_latency_threshold_ns) is not int
        or not 0 < diagnostic_latency_threshold_ns < 2**63
    ):
        raise CausalAuditError("diagnostic latency threshold must be positive nanoseconds")
    try:
        tick = Decimal(expected_tick_size)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise CausalAuditError("invalid tick size") from exc
    if not tick.is_finite() or tick <= 0:
        raise CausalAuditError("invalid tick size")

    receipt = verify_native_l2(
        source, staging, native_dir,
        expected_contract_id=expected_contract_id,
        expected_source_id=expected_source_id,
        expected_input_sha256=expected_input_sha256,
        expected_tick_size=expected_tick_size,
        expected_lot_size=expected_lot_size,
    )
    native = _safe(Path(native_dir) / "hft-events.npy")
    bids, asks = {}, {}
    depth = trades = crossed = two_sided = trades_without_book = 0
    max_exchange_gap = max_arrival_gap = 0
    min_latency = None
    max_latency = latency_sum = latency_over_threshold = 0
    min_observed_spread_ticks = None
    previous_exchange = previous_local = None
    digest = hashlib.sha256()

    with native.open("rb") as stream:
        digest.update(_header(stream, receipt["rows"]))
        for index in range(1, receipt["rows"] + 1):
            data = stream.read(EVENT.size)
            if len(data) != EVENT.size:
                raise CausalAuditError("native event truncated during audit")
            digest.update(data)
            ev, exchange, arrival, price, qty, order_id, ival, fval = EVENT.unpack(data)
            if arrival < exchange:
                raise CausalAuditError("negative arrival latency")
            if previous_exchange is not None:
                if exchange < previous_exchange or arrival < previous_local:
                    raise CausalAuditError("nonmonotonic as-of clocks")
                max_exchange_gap = max(max_exchange_gap, exchange - previous_exchange)
                max_arrival_gap = max(max_arrival_gap, arrival - previous_local)
            previous_exchange, previous_local = exchange, arrival
            latency = arrival - exchange
            latency_sum += latency
            min_latency = latency if min_latency is None else min(min_latency, latency)
            max_latency = max(max_latency, latency)
            if diagnostic_latency_threshold_ns is not None and latency > diagnostic_latency_threshold_ns:
                latency_over_threshold += 1

            kind = ev & 0xff
            if kind == 1:
                depth += 1
                if ev & FLAG_BUY:
                    book = bids
                elif ev & FLAG_SELL:
                    book = asks
                else:
                    raise CausalAuditError("depth side missing")
                if qty == 0:
                    book.pop(price, None)
                else:
                    book[price] = qty
            elif kind == 2:
                trades += 1
                if not (bids and asks):
                    trades_without_book += 1
            else:
                raise CausalAuditError("unsupported native event kind")

            if bids and asks:
                two_sided += 1
                best_bid, best_ask = max(bids), min(asks)
                if best_bid >= best_ask:
                    crossed += 1
                else:
                    # This is a partial-book *observation*, not a venue NBBO.
                    ticks = (Decimal(str(best_ask)) - Decimal(str(best_bid))) / tick
                    if ticks != ticks.to_integral_value():
                        raise CausalAuditError("observed spread violates tick grid")
                    min_observed_spread_ticks = (
                        int(ticks) if min_observed_spread_ticks is None
                        else min(min_observed_spread_ticks, int(ticks))
                    )
        if stream.read(1):
            raise CausalAuditError("native event file grew during audit")

    if depth != receipt["depth_updates"] or trades != receipt["trades"]:
        raise CausalAuditError("native event counts changed during audit")
    if digest.hexdigest() != receipt["native_sha256"] or _sha_file(native) != digest.hexdigest():
        raise CausalAuditError("native bytes changed during audit")
    if _sha_file(source) != expected_input_sha256:
        raise CausalAuditError("original source changed during audit")
    if _sha_file(Path(staging) / "hft-events.csv") != receipt["staged_csv_sha256"]:
        raise CausalAuditError("staged data changed during audit")

    return {
        "schema_version": "icarus-hft-partial-book-causal-audit-v1",
        "status": "REPLAY_READINESS_BLOCKED",
        "contract_id": expected_contract_id,
        "source_sha256": expected_input_sha256,
        "native_sha256": receipt["native_sha256"],
        "rows_examined": receipt["rows"],
        "depth_updates": depth,
        "trades": trades,
        "min_observed_arrival_lag_ns": min_latency,
        "max_observed_arrival_lag_ns": max_latency,
        "sum_observed_arrival_lag_ns": latency_sum,
        "max_consecutive_exchange_gap_ns": max_exchange_gap,
        "max_consecutive_arrival_gap_ns": max_arrival_gap,
        "diagnostic_latency_threshold_ns": diagnostic_latency_threshold_ns,
        "events_above_diagnostic_latency_threshold": (
            latency_over_threshold if diagnostic_latency_threshold_ns is not None else None
        ),
        "events_with_observed_two_sided_levels": two_sided,
        "trades_without_observed_two_sided_levels": trades_without_book,
        "observed_locked_or_crossed_events": crossed,
        "minimum_positive_observed_spread_ticks": min_observed_spread_ticks,
        "active_observed_bid_levels_at_end": len(bids),
        "active_observed_ask_levels_at_end": len(asks),
        "book_state_scope": "PARTIAL_OBSERVED_LEVELS_ONLY_NO_INITIAL_SNAPSHOT",
        "as_of_clock": "local_ts_ns",
        "book_snapshot_verified": False,
        "venue_nbbo_verified": False,
        "queue_position_verified": False,
        "simulator_executed": False,
        "empirical_fill_quality_verified": False,
        "training_approved": False,
        "execution_authorized": False,
        "authority_granted": "NONE",
        "blocking_gates": list(BLOCKERS),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("source", "staging", "native-dir"):
        parser.add_argument("--" + key, type=Path, required=True)
    for key in ("contract-id", "source-id", "expected-input-sha256",
                "tick-size", "lot-size"):
        parser.add_argument("--" + key, required=True)
    parser.add_argument("--diagnostic-latency-threshold-ns", type=int)
    args = parser.parse_args(argv)
    try:
        result = audit_causal_l2(
            args.source, args.staging, args.native_dir,
            expected_contract_id=args.contract_id,
            expected_source_id=args.source_id,
            expected_input_sha256=args.expected_input_sha256,
            expected_tick_size=args.tick_size,
            expected_lot_size=args.lot_size,
            diagnostic_latency_threshold_ns=args.diagnostic_latency_threshold_ns,
        )
    except (CausalAuditError, NativeVerificationError, ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
