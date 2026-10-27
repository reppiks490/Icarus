"""ICARUS -> HFTBacktest Event-column CSV staging (research only).

This deliberately produces CSV, NOT numpy structured arrays, a runnable replay,
real queue states, MBO order IDs, or broker-ready orders. Input is operator-
attested market-by-price L2 updates/trades with both exchange and arrival clocks.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import tempfile

FIELDS = ("sequence", "contract_id", "kind", "side", "exchange_ts_ns",
          "local_ts_ns", "price", "quantity")
OUTPUT = ("ev", "exch_ts", "local_ts", "px", "qty", "order_id", "ival", "fval")
FLAG_EXCH = 1 << 31
FLAG_LOCAL = 1 << 30
FLAG_BUY = 1 << 29
FLAG_SELL = 1 << 28
DEPTH_EVENT = 1
TRADE_EVENT = 2
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
MAX_I64 = 2**63 - 1
MAX_U64 = 2**64 - 1


class DepthAdmissionError(ValueError):
    """Unverifiable L2 input is refused with no published output."""


def _grid(value: str, step: Decimal, label: str, line: int, zero: bool) -> str:
    try:
        dec = Decimal(value)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise DepthAdmissionError(f"row {line}: invalid {label}") from exc
    if not dec.is_finite() or dec < 0 or (not zero and dec <= 0):
        raise DepthAdmissionError(f"row {line}: nonpositive/nonfinite {label}")
    if dec % step != 0:
        raise DepthAdmissionError(f"row {line}: {label} off declared tick/lot grid")
    number = float(dec)
    if not math.isfinite(number) or abs(Decimal(repr(number)) - dec) > step / 1_000_000:
        raise DepthAdmissionError(f"row {line}: {label} loses float64 precision")
    return repr(number)


def _positive_decimal(value: str, label: str) -> Decimal:
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise DepthAdmissionError(f"invalid {label}") from exc
    if not number.is_finite() or number <= 0:
        raise DepthAdmissionError(f"invalid {label}")
    return number


def _int(text: str, limit: int, label: str, line: int) -> int:
    if not isinstance(text, str) or not text.isascii() or not text.isdigit():
        raise DepthAdmissionError(f"row {line}: invalid {label}")
    n = int(text)
    if n > limit:
        raise DepthAdmissionError(f"row {line}: {label} outside integer bounds")
    return n


def stage_mbp_events(
    source: Path,
    output_dir: Path,
    *,
    contract_id: str,
    source_id: str,
    tick_size: str,
    lot_size: str,
) -> dict[str, object]:
    """Normalize recorded physical-contract MBP L2 events with no sampling cap.

    Strict clocks: nondecreasing exchange/local timestamps and local >= exch.
    Missing clock synchronization or out-of-order feeds require a distinct
    audited reorder/offset adapter and cannot be guessed here.
    """
    if not IDENTIFIER.fullmatch(contract_id) or not IDENTIFIER.fullmatch(source_id):
        raise DepthAdmissionError("physical contract_id and source_id are required")
    tick, lot = _positive_decimal(tick_size, "tick_size"), _positive_decimal(lot_size, "lot_size")
    original = Path(source)
    if original.is_symlink():
        raise DepthAdmissionError("symlinked inputs are refused")
    source = original.resolve(strict=True)
    if not source.is_file() or source.is_symlink():
        raise DepthAdmissionError("source must be a regular file")
    output_dir = Path(output_dir)
    if output_dir.is_symlink() or output_dir.exists():
        raise DepthAdmissionError("output already exists")
    if not output_dir.parent.is_dir():
        raise DepthAdmissionError("output parent must already exist")
    if source.parent == output_dir:
        raise DepthAdmissionError("input cannot be output directory")
    scratch = Path(tempfile.mkdtemp(prefix=".icarus-mbp-", dir=output_dir.parent))
    digest = hashlib.sha256()
    count = depth_count = trade_count = 0
    first_exchange = last_exchange = first_local = last_local = None
    previous_seq = None
    try:
        with source.open("rb") as incoming, (scratch / "hft-events.csv").open(
            "w", encoding="utf-8", newline=""
        ) as outgoing:
            def decode():
                for i, data in enumerate(incoming):
                    digest.update(data)
                    try:
                        yield data.decode("utf-8-sig" if i == 0 else "utf-8")
                    except UnicodeError as exc:
                        raise DepthAdmissionError("input is not UTF-8") from exc
            reader = csv.DictReader(decode(), strict=True)
            if reader.fieldnames != list(FIELDS):
                raise DepthAdmissionError("invalid exact MBP input columns")
            writer = csv.DictWriter(outgoing, fieldnames=OUTPUT, lineterminator="\n")
            writer.writeheader()
            try:
                for line, record in enumerate(reader, 2):
                    if None in record or any(v is None for v in record.values()):
                        raise DepthAdmissionError(f"row {line}: malformed row")
                    if record["contract_id"] != contract_id:
                        raise DepthAdmissionError(f"row {line}: mixed actual contracts")
                    seq = _int(record["sequence"], MAX_U64, "sequence", line)
                    exch = _int(record["exchange_ts_ns"], MAX_I64, "exchange_ts_ns", line)
                    local = _int(record["local_ts_ns"], MAX_I64, "local_ts_ns", line)
                    if previous_seq is not None and seq <= previous_seq:
                        raise DepthAdmissionError(f"row {line}: duplicate/reordered sequence")
                    if local < exch:
                        raise DepthAdmissionError(f"row {line}: negative arrival latency")
                    if last_exchange is not None and (exch < last_exchange or local < last_local):
                        raise DepthAdmissionError(f"row {line}: nonmonotonic clocks")
                    kind, side = record["kind"], record["side"]
                    if kind == "depth_update" and side in ("bid", "ask"):
                        flag = DEPTH_EVENT | (FLAG_BUY if side == "bid" else FLAG_SELL)
                        depth_count += 1
                        zero_qty = True
                    elif kind == "trade" and side in ("buy", "sell"):
                        flag = TRADE_EVENT | (FLAG_BUY if side == "buy" else FLAG_SELL)
                        trade_count += 1
                        zero_qty = False
                    else:
                        raise DepthAdmissionError(f"row {line}: unsupported L2 event/side")
                    price = _grid(record["price"], tick, "price", line, False)
                    quantity = _grid(record["quantity"], lot, "quantity", line, zero_qty)
                    writer.writerow({
                        "ev": flag | FLAG_EXCH | FLAG_LOCAL,
                        "exch_ts": exch, "local_ts": local, "px": price, "qty": quantity,
                        "order_id": 0, "ival": 0, "fval": "0.0",
                    })
                    previous_seq = seq
                    last_exchange, last_local = exch, local
                    first_exchange = exch if first_exchange is None else first_exchange
                    first_local = local if first_local is None else first_local
                    count += 1
            except csv.Error as exc:
                raise DepthAdmissionError("malformed CSV quoting") from exc
        if count == 0 or depth_count == 0:
            raise DepthAdmissionError("nonempty depth-update evidence required")
        output_hash = hashlib.sha256()
        with (scratch / "hft-events.csv").open("rb") as file:
            for block in iter(lambda: file.read(1024 * 1024), b""):
                output_hash.update(block)
        manifest = {
            "schema_version": "icarus-hftbacktest-l2-csv-v1",
            "format": "hftbacktest_event_csv_staging_not_numpy",
            "actual_contract_id": contract_id,
            "source_id": source_id,
            "feed_kind": "MBP_L2_depth_updates_and_trades",
            "tick_size": str(tick), "lot_size": str(lot),
            "exchange_clock_unit": "unix_epoch_nanoseconds",
            "arrival_clock_unit": "unix_epoch_nanoseconds",
            "input_sha256": digest.hexdigest(),
            "export_sha256": output_hash.hexdigest(),
            "rows": count, "depth_updates": depth_count, "trades": trade_count,
            "first_exchange_ns": first_exchange, "last_exchange_ns": last_exchange,
            "first_local_ns": first_local, "last_local_ns": last_local,
            "vendor_authenticity_verified": False,
            "entitlement_verified": False,
            "clock_sync_verified": False,
            "book_snapshot_verified": False,
            "mbo_order_ids_available": False,
            "queue_position_validated": False,
            "hftbacktest_runtime_verified": False,
            "backtest_fills_verified": False,
            "execution_authorized": False,
        }
        (scratch / "manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        if output_dir.is_symlink() or output_dir.exists():
            raise DepthAdmissionError("output appeared during processing")
        scratch.rename(output_dir)
        return manifest
    finally:
        if scratch.exists():
            shutil.rmtree(scratch)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--contract-id", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--tick-size", required=True)
    parser.add_argument("--lot-size", required=True)
    args = parser.parse_args(argv)
    try:
        report = stage_mbp_events(
            args.input, args.output, contract_id=args.contract_id,
            source_id=args.source_id, tick_size=args.tick_size, lot_size=args.lot_size
        )
    except (DepthAdmissionError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
