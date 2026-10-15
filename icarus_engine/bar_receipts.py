"""Validated provenance receipts for historical OHLCV batches entering Pulse."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from typing import Any, Iterable

from .pine.timeframe import Bar


@dataclass(frozen=True)
class BarBatchReceipt:
    schema_version: str
    receipt_id: str
    instrument_id: str
    provider: str
    expected_provider_symbol: str
    observed_provider_symbol: str | None
    provider_symbol_match_status: str
    provider_mapping_status: str
    identity_status: str
    entitlement_status: str
    interval_seconds: int
    requested_start_ts: int
    requested_end_ts: int
    received_start_ts: int | None
    received_end_ts: int | None
    row_count: int
    dropped_count: int
    duplicate_count: int
    interval_gap_count: int | None
    expected_bar_count: int | None
    missing_bar_count: int | None
    coverage_status: str
    timestamp_alignment_status: str
    session_validation_status: str
    checksum_sha256: str
    fetched_at_ns: int
    received_at_ns: int
    historical_bars_qualified: bool
    execution_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_bar_batch_receipt(
    *, instrument_id: str, provider: str, expected_provider_symbol: str,
    observed_provider_symbol: str | None, interval_seconds: int,
    requested_start_ts: int, requested_end_ts: int, bars: Iterable[Bar],
    fetched_at_ns: int, received_at_ns: int, entitlement_status: str = "UNKNOWN",
    session_validation_status: str = "UNKNOWN", provider_mapping_status: str = "VERIFIED",
    expected_timestamps: Iterable[int] | None = None,
) -> tuple[list[Bar], BarBatchReceipt]:
    """Validate exact response identity and OHLCV before returning bars to runtime.

    Missing provider identity or entitlement does not turn into a positive claim;
    it is recorded as unverified and keeps the receipt unqualified.
    """
    if not instrument_id or not provider or not expected_provider_symbol:
        raise ValueError("bar receipt requires instrument, provider, and expected symbol")
    if type(interval_seconds) is not int or interval_seconds <= 0:
        raise ValueError("bar receipt interval must be a positive integer")
    if provider_mapping_status not in ("VERIFIED", "UNVERIFIED", "UNKNOWN"):
        raise ValueError("invalid provider mapping status")
    for name, value in (("requested_start_ts", requested_start_ts), ("requested_end_ts", requested_end_ts),
                        ("fetched_at_ns", fetched_at_ns), ("received_at_ns", received_at_ns)):
        if type(value) is not int:
            raise ValueError(f"{name} must be an integer")
    start, end = requested_start_ts, requested_end_ts
    if end < start:
        raise ValueError("bar receipt requested window is reversed")
    if fetched_at_ns < 0 or received_at_ns < fetched_at_ns:
        raise ValueError("bar receipt fetch/receive times are invalid or reversed")
    rows = list(bars)
    expected = None if expected_timestamps is None else list(expected_timestamps)
    if expected is not None:
        if any(type(ts) is not int or not start <= ts < end for ts in expected):
            raise ValueError("expected bar timestamps must be integers inside the requested window")
        if any(later <= earlier for earlier, later in zip(expected, expected[1:])):
            raise ValueError("expected bar timestamps must be strictly increasing without duplicates")
    observed = str(observed_provider_symbol) if observed_provider_symbol else None
    if observed is not None and observed.upper() != expected_provider_symbol.upper():
        raise ValueError(
            f"provider symbol mismatch: expected {expected_provider_symbol!r}, received {observed!r}"
        )
    previous = None
    gap_count = None if expected is None else 0
    aligned = None if expected is None else True
    for row in rows:
        if not isinstance(row, Bar):
            raise ValueError("bar batch contains a non-Bar row")
        if type(row.ts) is not int:
            raise ValueError("bar timestamp must be an integer")
        ts = row.ts
        if not start <= ts < end:
            raise ValueError(f"bar timestamp {ts} is outside requested [{start}, {end}) window")
        if previous is not None and ts <= previous:
            raise ValueError("bar batch timestamps must be strictly increasing without duplicates")
        previous = ts
        values = (row.o, row.h, row.l, row.c, row.v)
        if not all(math.isfinite(float(value)) for value in values):
            raise ValueError(f"bar at {ts} contains non-finite OHLCV")
        if row.v < 0 or row.l > min(row.o, row.c) or row.h < max(row.o, row.c):
            raise ValueError(f"bar at {ts} has malformed OHLCV")

    observed_timestamps = {row.ts for row in rows}
    if expected is None:
        expected_count = None
        missing_count = None
        coverage_status = "UNKNOWN"
        aligned = None
    else:
        expected_set = set(expected)
        unexpected = observed_timestamps - expected_set
        if unexpected:
            raise ValueError(f"bar timestamp {min(unexpected)} is outside expected session schedule")
        aligned = observed_timestamps.issubset(expected_set)
        missing_count = len(expected_set - observed_timestamps)
        expected_count = len(expected)
        gap_count = missing_count
        coverage_status = "VERIFIED" if missing_count == 0 else "FAILED"

    encoded = json.dumps(
        [[int(row.ts), float(row.o), float(row.h), float(row.l), float(row.c), float(row.v)] for row in rows],
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    checksum = hashlib.sha256(encoded).hexdigest()
    provider_symbol_match_status = "MATCHED" if observed is not None else "UNKNOWN"
    identity_status = ("VERIFIED" if provider_symbol_match_status == "MATCHED" and provider_mapping_status == "VERIFIED"
                       else "PROVISIONAL" if provider_symbol_match_status == "MATCHED" else "UNKNOWN")
    if session_validation_status not in ("UNKNOWN", "VERIFIED", "FAILED"):
        raise ValueError("invalid session validation status")
    qualified = (identity_status == "VERIFIED" and entitlement_status == "VERIFIED"
                 and session_validation_status == "VERIFIED" and aligned is True and gap_count == 0
                 and coverage_status == "VERIFIED" and bool(rows))
    receipt_identity = json.dumps(
        [instrument_id, provider, expected_provider_symbol, interval_seconds, start, end, expected, checksum],
        separators=(",", ":"),
    ).encode("utf-8")
    receipt = BarBatchReceipt(
        schema_version="icarus.bar-batch-receipt.v1",
        receipt_id=hashlib.sha256(receipt_identity).hexdigest(),
        instrument_id=instrument_id,
        provider=provider,
        expected_provider_symbol=expected_provider_symbol,
        observed_provider_symbol=observed,
        provider_symbol_match_status=provider_symbol_match_status,
        provider_mapping_status=provider_mapping_status,
        identity_status=identity_status,
        entitlement_status=entitlement_status,
        interval_seconds=interval_seconds,
        requested_start_ts=start,
        requested_end_ts=end,
        received_start_ts=rows[0].ts if rows else None,
        received_end_ts=rows[-1].ts if rows else None,
        row_count=len(rows),
        dropped_count=0,
        duplicate_count=0,
        interval_gap_count=gap_count,
        expected_bar_count=expected_count,
        missing_bar_count=missing_count,
        coverage_status=coverage_status,
        timestamp_alignment_status=("UNKNOWN" if aligned is None else
                                    "VERIFIED" if aligned else "FAILED"),
        session_validation_status=session_validation_status,
        checksum_sha256=checksum,
        fetched_at_ns=fetched_at_ns,
        received_at_ns=received_at_ns,
        historical_bars_qualified=qualified,
    )
    return rows, receipt
