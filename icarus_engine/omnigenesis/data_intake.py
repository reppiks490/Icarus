"""Phase 17: offline, provenance-bounded inspection of operator-supplied market tapes.

This is NOT a feed connector, a vendor authenticity verifier, a trading input,
an MBO reconstruction engine, or a license attestation. The only verified fact
about an accepted file is that its exact bytes match the operator's declared
SHA-256 and the normalized events pass the stated structural/time contracts.
No raw rows are copied into the ICARUS research ledger.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .contracts import identity, utc

_AUTHORITY = {"research_only": True, "execution_authorized": False,
              "production_decision_authorized": False, "auto_promote": False}
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SYMBOL = re.compile(r"^[A-Z0-9._-]{1,32}$")
_FIELDS = {"event_id", "sequence", "contract", "observed_at", "received_at",
           "event_type", "side", "price_ticks", "quantity"}
_MANIFEST_FIELDS = {"schema_version", "dataset_id", "provider", "venue", "asset",
                    "source_category", "license_reference", "expected_sha256",
                    "expected_records", "contracts", "capture_cutoff"}
_CONTRACT_FIELDS = {"symbol", "start_at", "end_at", "tick_size"}
_EVENT_KINDS = {"trade", "limit_add", "limit_cancel", "limit_modify"}


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def _int(value: Any, minimum: int, maximum: int, name: str) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("invalid " + name)
    return value


def _text(value: Any, max_chars: int, name: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= max_chars or not value.isprintable():
        raise ValueError("invalid " + name)
    return value


def _manifest(source: Mapping[str, Any]) -> tuple[dict, list[tuple[datetime, datetime, str]]]:
    if not isinstance(source, Mapping) or set(source) != _MANIFEST_FIELDS:
        raise ValueError("invalid intake manifest schema")
    if source["schema_version"] != "icarus-omnigenesis-market-manifest-v1":
        raise ValueError("unsupported intake manifest")
    out = dict(source)
    for key in ("dataset_id", "provider", "venue", "license_reference"):
        _text(out[key], 128, key)
    if not isinstance(out["asset"], str) or not _SYMBOL.fullmatch(out["asset"]):
        raise ValueError("invalid asset")
    if out["source_category"] not in {"MBO_NORMALIZED", "MBP_NORMALIZED", "TRADES_NORMALIZED"}:
        raise ValueError("unsupported declared source category")
    if not isinstance(out["expected_sha256"], str) or not _HEX64.fullmatch(out["expected_sha256"]):
        raise ValueError("expected SHA-256 required")
    _int(out["expected_records"], 1, 2_000_000, "expected record count")
    cutoff = utc(out["capture_cutoff"])
    cs = out["contracts"]
    if not isinstance(cs, list) or not 1 <= len(cs) <= 48:
        raise ValueError("invalid contract schedule")
    ranges = []
    previous_end = None
    seen = set()
    for contract in cs:
        if not isinstance(contract, Mapping) or set(contract) != _CONTRACT_FIELDS:
            raise ValueError("invalid contract record")
        symbol = contract["symbol"]
        if not isinstance(symbol, str) or not _SYMBOL.fullmatch(symbol) or symbol in seen:
            raise ValueError("duplicate or invalid contract")
        seen.add(symbol)
        start, end = utc(contract["start_at"]), utc(contract["end_at"])
        if not start < end <= cutoff:
            raise ValueError("contract interval outside capture")
        if previous_end is not None and start < previous_end:
            raise ValueError("ambiguous overlapping roll periods")
        previous_end = end
        tick_size = contract["tick_size"]
        # Decimal strings avoid floating-point tick identity mistakes.
        if not isinstance(tick_size, str) or not re.fullmatch(r"(?:[1-9][0-9]{0,5}|0)\.[0-9]{1,8}|[1-9][0-9]{0,5}", tick_size):
            raise ValueError("invalid decimal tick size")
        from decimal import Decimal
        if Decimal(tick_size) <= 0:
            raise ValueError("tick size must be positive")
        ranges.append((start, end, symbol))
    return out, ranges


def inspect_market_tape(path: str | Path, manifest: Mapping[str, Any], *,
                        max_bytes: int = 250_000_000,
                        max_records: int = 2_000_000) -> dict:
    """Verify a local JSONL tape without recording raw rows or contacting a vendor.

    The operator MUST separately establish licensing and upstream provenance.
    Structural timestamps, file checksums, and declared roll intervals are not
    proof that exchanges, brokers, or aggregators supplied the bytes.
    """
    max_bytes = _int(max_bytes, 1, 2_000_000_000, "byte budget")
    max_records = _int(max_records, 1, 2_000_000, "record budget")
    m, schedule = _manifest(manifest)
    if m["expected_records"] > max_records:
        raise ValueError("record budget exceeded")
    tape = Path(path)
    if tape.is_symlink() or not tape.is_file():
        raise ValueError("tape must be an explicit regular, non-symlink local file")
    if tape.stat().st_size > max_bytes:
        raise ValueError("byte budget exceeded")
    sha = hashlib.sha256()
    previous_key = None
    seen = set()
    counts = Counter()
    nbytes = 0
    first_received = last_received = None
    lag_min = lag_max = None
    earliest_observed = None
    contracts_seen = set()
    with tape.open("rb") as fp:
        for line in fp:
            nbytes += len(line)
            if nbytes > max_bytes or len(line) > 8192:
                raise ValueError("byte or line budget exceeded")
            sha.update(line)
            if not line.strip():
                raise ValueError("empty record line")
            if sum(counts.values()) >= max_records:
                raise ValueError("record budget exceeded")
            try:
                record = json.loads(line.decode("utf-8"), object_pairs_hook=_unique_pairs,
                                    parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
            except (ValueError, UnicodeError, TypeError) as exc:
                raise ValueError("invalid JSONL tape") from exc
            if not isinstance(record, dict) or set(record) != _FIELDS:
                raise ValueError("record fields mismatch")
            eid = _text(record["event_id"], 128, "event ID")
            if eid in seen:
                raise ValueError("duplicate event ID")
            seen.add(eid)
            sequence = _int(record["sequence"], 0, 2**63 - 1, "sequence")
            name = record["contract"]
            if not isinstance(name, str) or name not in {x[2] for x in schedule}:
                raise ValueError("undeclared futures contract")
            observed = utc(record["observed_at"])
            received = utc(record["received_at"])
            if observed > received or received > utc(m["capture_cutoff"]):
                raise ValueError("future record or post-capture arrival")
            if not any(start <= observed < end and sym == name for start, end, sym in schedule):
                raise ValueError("event outside declared contract roll interval")
            key = (received, sequence)
            if previous_key is not None and key <= previous_key:
                raise ValueError("out-of-order received time / sequence")
            previous_key = key
            kind = record["event_type"]
            if kind not in _EVENT_KINDS:
                raise ValueError("unsupported event kind")
            if record["side"] not in {"buy", "sell"}:
                raise ValueError("invalid side")
            _int(record["price_ticks"], 1, 10**12, "integer tick price")
            _int(record["quantity"], 1, 10**9, "quantity")
            counts[kind] += 1
            contracts_seen.add(name)
            lag = int((received - observed).total_seconds() * 1_000_000)
            lag_min = lag if lag_min is None else min(lag_min, lag)
            lag_max = lag if lag_max is None else max(lag_max, lag)
            earliest_observed = observed if earliest_observed is None else min(earliest_observed, observed)
            if first_received is None:
                first_received = received
            last_received = received
    if sum(counts.values()) != m["expected_records"]:
        raise ValueError("declared record count mismatch")
    if sha.hexdigest() != m["expected_sha256"]:
        raise ValueError("SHA-256 mismatch against operator-declared digest")
    result = {
        "schema_version": "icarus-omnigenesis-market-intake-v1",
        "evidence_kind": "DECLARED_OBSERVED_BYTES_CHECKED",
        "authority": dict(_AUTHORITY),
        "dataset_id": m["dataset_id"],
        "source_category": m["source_category"],
        "manifest_sha256": identity(m),
        "tape_sha256": sha.hexdigest(),
        "record_count": sum(counts.values()),
        "byte_count": nbytes,
        "contract_count": len(contracts_seen),
        "event_kind_counts": dict(sorted(counts.items())),
        "first_received_at": first_received.isoformat(),
        "last_received_at": last_received.isoformat(),
        "earliest_observed_at": earliest_observed.isoformat(),
        "min_receive_lag_us": lag_min,
        "max_receive_lag_us": lag_max,
        "futures_roll_interval_checked": True,
        "source_authenticity_verified": False,
        "provider_license_verified": False,
        "exchange_sequence_completeness_verified": False,
        "production_qualified": False,
        "next_gate": "NEXUS independent vendor receipt and rights validation",
    }
    result["report_id"] = identity(result)
    return result
