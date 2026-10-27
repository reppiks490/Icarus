"""Independent read-only verification of HFTBacktest L2 event CSV staging.

The consumer never imports the producer, calls a provider, runs a simulator,
writes artifacts, or grants training/execution authority. A caller-provided
source SHA-256 must come from a separately trusted receipt.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation
import hashlib
from itertools import zip_longest
import json
import math
from pathlib import Path
import re
import stat

SOURCE = ("sequence", "contract_id", "kind", "side", "exchange_ts_ns",
          "local_ts_ns", "price", "quantity")
EXPORT = ("ev", "exch_ts", "local_ts", "px", "qty", "order_id", "ival", "fval")
DENIED = ("vendor_authenticity_verified", "entitlement_verified",
          "clock_sync_verified", "book_snapshot_verified",
          "mbo_order_ids_available", "queue_position_validated",
          "hftbacktest_runtime_verified", "backtest_fills_verified",
          "execution_authorized")
FIXED = {"schema_version": "icarus-hftbacktest-l2-csv-v1",
         "format": "hftbacktest_event_csv_staging_not_numpy",
         "feed_kind": "MBP_L2_depth_updates_and_trades",
         "exchange_clock_unit": "unix_epoch_nanoseconds",
         "arrival_clock_unit": "unix_epoch_nanoseconds"}
REQUIRED = set(FIXED) | set(DENIED) | {
    "actual_contract_id", "source_id", "tick_size", "lot_size",
    "input_sha256", "export_sha256", "rows", "depth_updates", "trades",
    "first_exchange_ns", "last_exchange_ns", "first_local_ns", "last_local_ns"}
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
MAX_I64 = 2**63 - 1
MAX_U64 = 2**64 - 1
EXCH, LOCAL, BUY, SELL = 1 << 31, 1 << 30, 1 << 29, 1 << 28


class L2VerificationError(ValueError):
    """Untrusted staged data fails structural admission."""


def _no_duplicates(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise L2VerificationError(f"duplicate JSON key: {key}")
        obj[key] = value
    return obj


def _reject_constant(value):
    raise L2VerificationError(f"nonstandard JSON constant: {value}")


def _regular(path):
    path = Path(path).absolute()
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink():
            raise L2VerificationError("symlink path refused")
    try:
        mode = path.stat().st_mode
    except OSError as exc:
        raise L2VerificationError("missing/unreadable input") from exc
    if not stat.S_ISREG(mode):
        raise L2VerificationError("expected regular file")
    return path


def _positive(value, label):
    if not isinstance(value, str):
        raise L2VerificationError(f"{label} must be decimal text")
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise L2VerificationError(f"invalid {label}") from exc
    if not number.is_finite() or number <= 0:
        raise L2VerificationError(f"invalid {label}")
    return number


def _integer(value, max_value, label, row):
    if (not isinstance(value, str) or not value.isascii() or not value.isdigit()
            or len(value) > 20):
        raise L2VerificationError(f"row {row}: invalid {label}")
    n = int(value)
    if n > max_value:
        raise L2VerificationError(f"row {row}: {label} exceeds bound")
    return n


def _float_grid(value, step, label, row, allow_zero=False):
    if not isinstance(value, str):
        raise L2VerificationError(f"row {row}: invalid {label}")
    try:
        number = Decimal(value)
        on_grid = number % step == 0
    except (InvalidOperation, ValueError) as exc:
        raise L2VerificationError(f"row {row}: invalid {label}") from exc
    if (not number.is_finite() or number < 0
            or (not allow_zero and number == 0) or not on_grid):
        raise L2VerificationError(f"row {row}: {label} invalid/off grid")
    try:
        converted = float(number)
    except (OverflowError, ValueError) as exc:
        raise L2VerificationError(f"row {row}: {label} outside float64") from exc
    if (not math.isfinite(converted)
            or abs(Decimal(repr(converted)) - number) > step / 1_000_000):
        raise L2VerificationError(f"row {row}: {label} loses precision")
    return repr(converted)


def _csv_lines(file, digest):
    for index, data in enumerate(file):
        digest.update(data)
        try:
            yield data.decode("utf-8-sig" if index == 0 else "utf-8")
        except UnicodeError as exc:
            raise L2VerificationError("non-UTF-8 CSV") from exc


def _row(record, index):
    if record is None or None in record or any(v is None for v in record.values()):
        raise L2VerificationError(f"row {index}: missing/extra CSV fields")
    return record


def _manifest(path):
    if path.stat().st_size > 65536:
        raise L2VerificationError("manifest exceeds safety bound")
    try:
        data = json.loads(path.read_text(encoding="utf-8"),
                          object_pairs_hook=_no_duplicates,
                          parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise L2VerificationError("invalid UTF-8/JSON manifest") from exc
    if not isinstance(data, dict) or set(data) != REQUIRED:
        raise L2VerificationError("unexpected/missing manifest fields")
    for key, value in FIXED.items():
        if data[key] != value:
            raise L2VerificationError(f"manifest {key} mismatch")
    for key in DENIED:
        if data[key] is not False:
            raise L2VerificationError(f"authority flag {key} must be false")
    for key in ("input_sha256", "export_sha256"):
        if not isinstance(data[key], str) or not SHA256.fullmatch(data[key]):
            raise L2VerificationError(f"manifest invalid {key}")
    for key in ("rows", "depth_updates", "trades", "first_exchange_ns",
                "last_exchange_ns", "first_local_ns", "last_local_ns"):
        value = data[key]
        if type(value) is not int or value < 0 or value > MAX_I64:
            raise L2VerificationError(f"manifest invalid {key}")
    if data["rows"] < 1 or data["depth_updates"] < 1:
        raise L2VerificationError("empty depth context")
    return data


def verify_hft_l2(source, staged_dir, *, expected_contract_id,
                  expected_source_id, expected_input_sha256,
                  expected_tick_size, expected_lot_size):
    """Independently compare every staged event against the original source."""
    if (not IDENTIFIER.fullmatch(expected_contract_id)
            or not IDENTIFIER.fullmatch(expected_source_id)):
        raise L2VerificationError("invalid physical contract/source identifier")
    if not SHA256.fullmatch(expected_input_sha256):
        raise L2VerificationError("independent input SHA-256 required")
    tick = _positive(expected_tick_size, "expected tick size")
    lot = _positive(expected_lot_size, "expected lot size")
    source = _regular(source)
    staged_dir = Path(staged_dir).absolute()
    for ancestor in (staged_dir, *staged_dir.parents):
        if ancestor.is_symlink():
            raise L2VerificationError("symlink staging path refused")
    if not staged_dir.is_dir():
        raise L2VerificationError("staging directory missing")
    if {p.name for p in staged_dir.iterdir()} != {"manifest.json", "hft-events.csv"}:
        raise L2VerificationError("staging directory has missing/unexpected files")
    manifest_file = _regular(staged_dir / "manifest.json")
    export = _regular(staged_dir / "hft-events.csv")
    if source in (manifest_file, export):
        raise L2VerificationError("original source must be separate")
    manifest = _manifest(manifest_file)
    if (manifest["actual_contract_id"] != expected_contract_id
            or manifest["source_id"] != expected_source_id):
        raise L2VerificationError("declared physical contract/source mismatch")
    if (_positive(manifest["tick_size"], "manifest tick size") != tick
            or _positive(manifest["lot_size"], "manifest lot size") != lot):
        raise L2VerificationError("tick/lot contract mismatch")
    if manifest["input_sha256"] != expected_input_sha256:
        raise L2VerificationError("manifest source digest differs from independent anchor")
    source_digest, output_digest = hashlib.sha256(), hashlib.sha256()
    counts = {"rows": 0, "depth_updates": 0, "trades": 0}
    first_exch = first_local = last_exch = last_local = None
    previous_sequence = None
    try:
        with source.open("rb") as src_file, export.open("rb") as out_file:
            src_rows = csv.DictReader(_csv_lines(src_file, source_digest), strict=True)
            out_rows = csv.DictReader(_csv_lines(out_file, output_digest), strict=True)
            if src_rows.fieldnames != list(SOURCE):
                raise L2VerificationError("source header mismatch")
            if out_rows.fieldnames != list(EXPORT):
                raise L2VerificationError("export header mismatch")
            for row_no, (raw, event) in enumerate(zip_longest(src_rows, out_rows), 2):
                raw, event = _row(raw, row_no), _row(event, row_no)
                if raw["contract_id"] != expected_contract_id:
                    raise L2VerificationError(f"row {row_no}: mixed physical contract")
                seq = _integer(raw["sequence"], MAX_U64, "sequence", row_no)
                exch = _integer(raw["exchange_ts_ns"], MAX_I64, "exchange timestamp", row_no)
                local = _integer(raw["local_ts_ns"], MAX_I64, "arrival timestamp", row_no)
                if previous_sequence is not None and seq <= previous_sequence:
                    raise L2VerificationError(f"row {row_no}: sequence not increasing")
                if (local < exch or (last_exch is not None
                                    and (exch < last_exch or local < last_local))):
                    raise L2VerificationError(f"row {row_no}: clock/arrival ordering invalid")
                kind, side = raw["kind"], raw["side"]
                if kind == "depth_update" and side in ("bid", "ask"):
                    flags = 1 | (BUY if side == "bid" else SELL)
                    counts["depth_updates"] += 1
                    zero_qty = True
                elif kind == "trade" and side in ("buy", "sell"):
                    flags = 2 | (BUY if side == "buy" else SELL)
                    counts["trades"] += 1
                    zero_qty = False
                else:
                    raise L2VerificationError(f"row {row_no}: unsupported event type/side")
                expected = {
                    "ev": str(flags | EXCH | LOCAL),
                    "exch_ts": str(exch), "local_ts": str(local),
                    "px": _float_grid(raw["price"], tick, "price", row_no),
                    "qty": _float_grid(raw["quantity"], lot, "quantity", row_no,
                                       allow_zero=zero_qty),
                    "order_id": "0", "ival": "0", "fval": "0.0"}
                if event != expected:
                    raise L2VerificationError(f"row {row_no}: event differs from source")
                previous_sequence = seq
                first_exch = exch if first_exch is None else first_exch
                first_local = local if first_local is None else first_local
                last_exch, last_local = exch, local
                counts["rows"] += 1
    except csv.Error as exc:
        raise L2VerificationError("malformed CSV quoting") from exc
    if counts["depth_updates"] < 1:
        raise L2VerificationError("no depth updates")
    if source_digest.hexdigest() != expected_input_sha256:
        raise L2VerificationError("original input bytes do not match independent anchor")
    if output_digest.hexdigest() != manifest["export_sha256"]:
        raise L2VerificationError("export bytes do not match manifest")
    if counts != {key: manifest[key] for key in counts}:
        raise L2VerificationError("manifest event counts inconsistent")
    for key, actual in (
        ("first_exchange_ns", first_exch), ("last_exchange_ns", last_exch),
        ("first_local_ns", first_local), ("last_local_ns", last_local)):
        if manifest[key] != actual:
            raise L2VerificationError(f"manifest {key} inconsistent")
    return {
        "status": "STRUCTURALLY_VERIFIED_QUARANTINED",
        "actual_contract_id": expected_contract_id,
        "source_id": expected_source_id,
        "input_sha256": source_digest.hexdigest(),
        "export_sha256": output_digest.hexdigest(),
        **counts,
        "vendor_authenticity_verified": False,
        "entitlement_verified": False,
        "clock_sync_verified": False,
        "book_snapshot_verified": False,
        "native_hftbacktest_replay_verified": False,
        "empirical_fill_quality_verified": False,
        "training_approved": False,
        "execution_authorized": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--contract-id", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--expected-input-sha256", required=True)
    parser.add_argument("--tick-size", required=True)
    parser.add_argument("--lot-size", required=True)
    args = parser.parse_args(argv)
    try:
        receipt = verify_hft_l2(
            args.source, args.staging,
            expected_contract_id=args.contract_id,
            expected_source_id=args.source_id,
            expected_input_sha256=args.expected_input_sha256,
            expected_tick_size=args.tick_size, expected_lot_size=args.lot_size)
    except (L2VerificationError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(receipt, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
