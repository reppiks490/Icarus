"""Read-only arrival-time causality audit for independently pinned NautilusTrader quotes.

This observer is not an order simulator, backtester, Brain input or authority gate.
It verifies the entire source-to-native quote stream before answering any as-of query.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

from icarus_engine.external_nautilus_quote_bridge import (
    QuoteAdmissionError,
    verify_native,
)

# Every persisted or returned authority flag must remain false, even after passing.
DENIALS = (
    "execution_authorized",
    "training_approved",
    "fill_parity_verified",
    "native_backtest_executed",
    "source_authenticity_verified",
    "license_verified",
    "initial_book_snapshot_verified",
)


def _unique_pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise QuoteAdmissionError("duplicate quote JSON key")
        obj[key] = value
    return obj


def _requests(values: Iterable[int]) -> list[int]:
    requested = []
    last = None
    for value in values:
        if type(value) is not int or not 0 <= value <= (2**64 - 1):
            raise QuoteAdmissionError("as-of query must be a uint64 UTC nanosecond integer")
        if last is not None and value < last:
            raise QuoteAdmissionError("as-of queries must be nondecreasing")
        requested.append(value)
        last = value
    if not requested:
        raise QuoteAdmissionError("at least one as-of query is required")
    return requested


def audit_quote_asof(
    source: Path,
    staging: Path,
    *,
    instrument_id: str,
    source_id: str,
    producer_revision: str,
    expected_source_sha256: str,
    expected_export_sha256: str,
    expected_manifest_sha256: str,
    observation_ns: Iterable[int],
) -> dict:
    """Observe only quotes received as of each requested UTC nanosecond.

    Every staged quote passes the parent's actual native QuoteTick roundtrip
    and full source verification. Streaming observation is based on ts_init
    (reception), never ts_event (exchange time). All records, even those later
    than the final observation, are consumed and rehashed. No record cap.
    """
    times = _requests(observation_ns)
    verified = verify_native(
        source, staging, instrument_id=instrument_id, source_id=source_id,
        producer_revision=producer_revision,
        expected_source_sha256=expected_source_sha256,
        expected_export_sha256=expected_export_sha256,
        expected_manifest_sha256=expected_manifest_sha256,
    )
    if verified.get("status") != "NATIVE_QUOTE_ROUNDTRIP_STRUCTURAL_ONLY":
        raise QuoteAdmissionError("native quote parity receipt missing")
    if any(verified.get(k) is not False for k in DENIALS if k in verified):
        raise QuoteAdmissionError("unexpected native verification authority")
    # Rehash during the independent as-of pass: never trust a post-verification
    # reread if the staged artifact changed between verification and observation.
    digest = hashlib.sha256()
    latest = None
    count = 0
    next_time = 0
    snapshots = []
    with (Path(staging) / "quotes.jsonl").open("rb") as stream:
        for line in stream:
            if len(line) > 4096:
                raise QuoteAdmissionError("oversized staged quote record")
            digest.update(line)
            try:
                row = json.loads(line.decode("utf-8"), object_pairs_hook=_unique_pairs)
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise QuoteAdmissionError("invalid staged quote JSON") from exc
            if not isinstance(row, dict) or type(row.get("ts_init")) is not int:
                raise QuoteAdmissionError("invalid staged quote arrival timestamp")
            arrival = row["ts_init"]
            # Complete all earlier observations before releasing this event.
            while next_time < len(times) and times[next_time] < arrival:
                snapshots.append(_snapshot(times[next_time], latest))
                next_time += 1
            latest = row
            count += 1
        while next_time < len(times):
            snapshots.append(_snapshot(times[next_time], latest))
            next_time += 1
    if digest.hexdigest() != expected_export_sha256 or count != verified["rows_verified"]:
        raise QuoteAdmissionError("source/quote stream changed during causal audit")
    return {
        "status": "NATIVE_QUOTE_ASOF_CAUSAL_OBSERVATION_ONLY",
        "instrument_id": instrument_id,
        "source_sha256": expected_source_sha256,
        "export_sha256": expected_export_sha256,
        "manifest_sha256": expected_manifest_sha256,
        "records_fully_scanned": count,
        "observations": snapshots,
        **{key: False for key in DENIALS},
        "queue_model_calibrated": False,
        "latency_model_calibrated": False,
        "empirical_edge_verified": False,
    }


def _snapshot(asof: int, row: dict | None) -> dict:
    if row is None:
        return {"asof_arrival_ns": asof, "available": False, "quote": None}
    # Deliberately exclude source sequence and any future-derived information.
    return {
        "asof_arrival_ns": asof,
        "available": True,
        "quote": {
            "instrument_id": row["instrument_id"],
            "bid_price": row["bid_price"],
            "ask_price": row["ask_price"],
            "bid_size": row["bid_size"],
            "ask_size": row["ask_size"],
            "ts_event": row["ts_event"],
            "ts_init": row["ts_init"],
        },
    }
