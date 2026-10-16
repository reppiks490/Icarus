"""Validated provenance receipts for historical OHLCV batches entering Pulse."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
    expected_bar_count: int | None
    dropped_count: int
    duplicate_count: int
    interval_gap_count: int
    gap_validation_status: str
    timestamp_alignment_status: str
    timestamp_normalization: str
    session_validation_status: str
    bar_close_status: str
    checksum_sha256: str
    fetched_at_ns: int
    received_at_ns: int
    historical_bars_qualified: bool
    execution_authorized: bool = False
    calendar_timezone: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_bar_batch_receipt(
    *, instrument_id: str, provider: str, expected_provider_symbol: str,
    observed_provider_symbol: str | None, interval_seconds: int,
    requested_start_ts: int, requested_end_ts: int, bars: Iterable[Bar],
    fetched_at_ns: int, received_at_ns: int, entitlement_status: str = "UNKNOWN",
    session_validation_status: str = "UNKNOWN", provider_mapping_status: str = "VERIFIED",
    alignment_validator: Callable[[int], bool] | None = None,
    expected_bar_timestamps: Iterable[int] | None = None,
    calendar_timezone: str | None = None,
    bar_close_status: str = "UNKNOWN",
    timestamp_normalization: str = "NONE",
) -> tuple[list[Bar], BarBatchReceipt]:
    """Validate exact response identity and OHLCV before returning bars to runtime.

    Missing provider identity or entitlement does not turn into a positive claim;
    it is recorded as unverified and keeps the receipt unqualified.
    A qualifying receipt also needs the complete expected bar-start schedule,
    generated from the instrument's authoritative exchange calendar for the
    requested session window; a pairwise gap callback cannot prove edge coverage.
    """
    if not instrument_id or not provider or not expected_provider_symbol:
        raise ValueError("bar receipt requires instrument, provider, and expected symbol")
    if type(interval_seconds) is not int or interval_seconds <= 0:
        raise ValueError("bar receipt interval must be a positive integer")
    if provider_mapping_status not in ("VERIFIED", "UNVERIFIED", "UNKNOWN"):
        raise ValueError("invalid provider mapping status")
    if entitlement_status not in ("UNKNOWN", "VERIFIED", "FAILED"):
        raise ValueError("invalid entitlement status")
    if session_validation_status not in ("UNKNOWN", "VERIFIED", "FAILED"):
        raise ValueError("invalid session validation status")
    if bar_close_status not in ("UNKNOWN", "VERIFIED", "FAILED"):
        raise ValueError("invalid bar close status")
    if timestamp_normalization not in ("NONE", "YAHOO_SESSION_CLOSE_TO_SESSION_OPEN"):
        raise ValueError("invalid bar timestamp normalization")
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
    expected = None if expected_bar_timestamps is None else list(expected_bar_timestamps)
    if expected is not None:
        if any(type(ts) is not int or not start <= ts < end for ts in expected):
            raise ValueError("expected bar timestamps must be integer starts inside the requested window")
        if expected != sorted(set(expected)):
            raise ValueError("expected bar timestamps must be strictly increasing and unique")
        try:
            calendar_zone = ZoneInfo(calendar_timezone) if calendar_timezone else None
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise ValueError("calendar_timezone must name a valid IANA timezone") from exc

        def is_dst_shortened_calendar_interval(earlier: int, later: int) -> bool:
            if calendar_zone is None or interval_seconds < 86400 or interval_seconds % 86400:
                return False
            earlier_local = datetime.fromtimestamp(earlier, timezone.utc).astimezone(calendar_zone)
            later_local = datetime.fromtimestamp(later, timezone.utc).astimezone(calendar_zone)
            wall_delta = later_local.replace(tzinfo=None) - earlier_local.replace(tzinfo=None)
            offset_delta = later_local.utcoffset() - earlier_local.utcoffset()
            return (offset_delta > timedelta(0)
                    and later - earlier == interval_seconds - int(offset_delta.total_seconds())
                    and wall_delta == timedelta(seconds=interval_seconds))

        if any(later - earlier < interval_seconds and not is_dst_shortened_calendar_interval(earlier, later)
               for earlier, later in zip(expected, expected[1:])):
            raise ValueError("expected bar timestamps cannot be closer than the declared interval")
    observed = str(observed_provider_symbol) if observed_provider_symbol else None
    if observed is not None and observed.upper() != expected_provider_symbol.upper():
        raise ValueError(
            f"provider symbol mismatch: expected {expected_provider_symbol!r}, received {observed!r}"
        )
    previous = None
    gap_count = 0
    gaps_validated = expected is not None
    aligned = bool(rows) and alignment_validator is not None
    observed_timestamps = []
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
        observed_timestamps.append(ts)
        if alignment_validator is not None:
            try:
                if alignment_validator(ts) is not True:
                    aligned = False
            except Exception as exc:
                raise ValueError("bar timestamp alignment validation failed") from exc
        if previous is not None and ts - previous > interval_seconds:
            gap_count += max(0, (ts - previous) // interval_seconds - 1)
        previous = ts
        values = (row.o, row.h, row.l, row.c, row.v)
        if not all(math.isfinite(float(value)) for value in values):
            raise ValueError(f"bar at {ts} contains non-finite OHLCV")
        if row.v < 0 or row.l > min(row.o, row.c) or row.h < max(row.o, row.c):
            raise ValueError(f"bar at {ts} has malformed OHLCV")

    if expected is not None:
        unexpected = set(observed_timestamps) - set(expected)
        if unexpected:
            raise ValueError(f"bar timestamp {min(unexpected)} is outside the expected market-session schedule")
        gap_count = len(set(expected) - set(observed_timestamps))

    encoded = json.dumps(
        [[int(row.ts), float(row.o), float(row.h), float(row.l), float(row.c), float(row.v)] for row in rows],
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    checksum = hashlib.sha256(encoded).hexdigest()
    provider_symbol_match_status = "MATCHED" if observed is not None else "UNKNOWN"
    identity_status = ("VERIFIED" if provider_symbol_match_status == "MATCHED" and provider_mapping_status == "VERIFIED"
                       else "PROVISIONAL" if provider_symbol_match_status == "MATCHED" else "UNKNOWN")
    qualified = (identity_status == "VERIFIED" and entitlement_status == "VERIFIED"
                 and session_validation_status == "VERIFIED" and bar_close_status == "VERIFIED"
                 and aligned and gaps_validated and gap_count == 0 and bool(rows))
    validation_evidence = {
        "provider_symbol_match_status": provider_symbol_match_status,
        "provider_mapping_status": provider_mapping_status,
        "identity_status": identity_status,
        "entitlement_status": entitlement_status,
        "expected_schedule_sha256": hashlib.sha256(
            json.dumps(expected, separators=(",", ":")).encode("utf-8")
        ).hexdigest() if expected is not None else None,
        "calendar_timezone": calendar_timezone,
        "interval_gap_count": gap_count,
        "gap_validation_status": "VERIFIED" if gaps_validated else "UNKNOWN",
        "timestamp_alignment_status": "UNKNOWN" if alignment_validator is None else "VERIFIED" if aligned else "FAILED",
        "timestamp_normalization": timestamp_normalization,
        "session_validation_status": session_validation_status,
        "bar_close_status": bar_close_status,
        "checksum_sha256": checksum,
    }
    receipt_identity = json.dumps(
        [instrument_id, provider, expected_provider_symbol, interval_seconds, start, end, validation_evidence],
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
        expected_bar_count=len(expected) if expected is not None else None,
        dropped_count=0,
        duplicate_count=0,
        interval_gap_count=gap_count,
        gap_validation_status="UNKNOWN" if expected is None else "VERIFIED",
        timestamp_alignment_status=("UNKNOWN" if alignment_validator is None else "VERIFIED" if aligned else "FAILED"),
        timestamp_normalization=timestamp_normalization,
        session_validation_status=session_validation_status,
        bar_close_status=bar_close_status,
        checksum_sha256=checksum,
        fetched_at_ns=fetched_at_ns,
        received_at_ns=received_at_ns,
        historical_bars_qualified=qualified,
        calendar_timezone=calendar_timezone,
    )
    return rows, receipt
