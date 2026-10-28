"""Offline, fail-closed NautilusTrader QuoteTick staging and native readback.

No collector, broker, order, model, replay, fill, or UI integration. Input must
be an independently authorized physical-contract top-of-book quote source.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import importlib.metadata
from itertools import zip_longest
import json
from pathlib import Path
import re
import shutil
import tempfile

VERSION = "1.221.0"
SCHEMA = "icarus-nautilus-quote-staging-v1"
COLUMNS = ("sequence", "instrument_id", "event_ts_ns", "arrival_ts_ns",
           "bid_price", "ask_price", "bid_size", "ask_size")
RECORD_KEYS = ("sequence", "instrument_id", "ts_event", "ts_init",
               "bid_price", "ask_price", "bid_size", "ask_size")
ID = re.compile(r"[A-Z0-9_-]{2,32}\.[A-Z0-9_-]{2,16}\Z")
SOURCE_ID = re.compile(r"[A-Za-z0-9_.:-]{1,100}\Z")
NUMBER = re.compile(r"(?:0|[1-9][0-9]{0,15})(?:\.[0-9]{1,9})?\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
REVISION = re.compile(r"[0-9a-f]{40}\Z")
MAX_TS = (1 << 63) - 1
DENIED = ("source_authenticity_verified", "license_verified",
          "initial_book_snapshot_verified", "fill_parity_verified",
          "training_approved", "execution_authorized")


class QuoteAdmissionError(ValueError):
    """Reject unsupported or unverified quote evidence."""


def _decimal(value: str, label: str) -> Decimal:
    if not isinstance(value, str) or not NUMBER.fullmatch(value):
        raise QuoteAdmissionError(f"invalid canonical {label}")
    try:
        dec = Decimal(value)
    except InvalidOperation as exc:
        raise QuoteAdmissionError(f"invalid {label}") from exc
    if dec <= 0:
        raise QuoteAdmissionError(f"nonpositive {label}")
    return dec


def _integer(value: str, label: str, limit: int = MAX_TS) -> int:
    if not isinstance(value, str) or len(value) > 20 or not value.isascii() or not value.isdigit():
        raise QuoteAdmissionError(f"invalid {label}")
    number = int(value)
    if not 0 < number <= limit:
        raise QuoteAdmissionError(f"out-of-bounds {label}")
    return number


def _require_source(path: Path) -> Path:
    path = Path(path)
    if path.is_symlink():
        raise QuoteAdmissionError("symlink source forbidden")
    path = path.resolve(strict=True)
    if not path.is_file():
        raise QuoteAdmissionError("source must be a regular file")
    return path


def _source_rows(path: Path, instrument: str, tick: Decimal, lot: Decimal,
                 digest: hashlib._Hash):
    last_sequence = last_event = last_arrival = None
    with path.open("rb") as handle:
        def lines():
            for raw in handle:
                digest.update(raw)
                try:
                    yield raw.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise QuoteAdmissionError("source is not UTF-8") from exc
        reader = csv.DictReader(lines(), strict=True)
        if reader.fieldnames != list(COLUMNS):
            raise QuoteAdmissionError("incorrect exact quote CSV columns")
        try:
            for line, row in enumerate(reader, 2):
                if None in row or any(v is None for v in row.values()):
                    raise QuoteAdmissionError(f"row {line}: malformed CSV record")
                if row["instrument_id"] != instrument:
                    raise QuoteAdmissionError(f"row {line}: mixed physical contracts")
                sequence = _integer(row["sequence"], "sequence", (1 << 64) - 1)
                event = _integer(row["event_ts_ns"], "event timestamp")
                arrival = _integer(row["arrival_ts_ns"], "arrival timestamp")
                if last_sequence is not None and sequence <= last_sequence:
                    raise QuoteAdmissionError(f"row {line}: nonincreasing sequence")
                if arrival < event:
                    raise QuoteAdmissionError(f"row {line}: negative reception latency")
                if last_event is not None and (event < last_event or arrival < last_arrival):
                    raise QuoteAdmissionError(f"row {line}: nonmonotonic exchange/arrival clocks")
                prices = (row["bid_price"], row["ask_price"])
                sizes = (row["bid_size"], row["ask_size"])
                if len(prices[0].partition(".")[2]) != len(prices[1].partition(".")[2]):
                    raise QuoteAdmissionError(f"row {line}: unequal bid/ask price precision")
                if len(sizes[0].partition(".")[2]) != len(sizes[1].partition(".")[2]):
                    raise QuoteAdmissionError(f"row {line}: unequal bid/ask size precision")
                bid, ask = (_decimal(x, "price") for x in prices)
                bid_size, ask_size = (_decimal(x, "size") for x in sizes)
                if bid >= ask:
                    raise QuoteAdmissionError(f"row {line}: crossed/locked top-of-book")
                if bid % tick or ask % tick or bid_size % lot or ask_size % lot:
                    raise QuoteAdmissionError(f"row {line}: off declared tick/lot grid")
                last_sequence, last_event, last_arrival = sequence, event, arrival
                yield {
                    "sequence": sequence, "instrument_id": instrument,
                    "ts_event": event, "ts_init": arrival,
                    "bid_price": prices[0], "ask_price": prices[1],
                    "bid_size": sizes[0], "ask_size": sizes[1],
                }
        except csv.Error as exc:
            raise QuoteAdmissionError("invalid CSV quoting") from exc


def _validate_identifiers(instrument: str, source_id: str, revision: str) -> None:
    if not ID.fullmatch(instrument):
        raise QuoteAdmissionError("actual physical contract.VENUE identifier required")
    if not SOURCE_ID.fullmatch(source_id):
        raise QuoteAdmissionError("source_id must be an explicit provenance label")
    if not REVISION.fullmatch(revision):
        raise QuoteAdmissionError("40-character producer revision required")


def _json_unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise QuoteAdmissionError("duplicate JSON key")
        value[key] = item
    return value


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stage_quotes(source: Path, output_dir: Path, *, instrument_id: str,
                 source_id: str, producer_revision: str,
                 tick_size: str, lot_size: str) -> dict:
    """Write new, quarantined quote JSONL and SHA-bound denial manifest."""
    _validate_identifiers(instrument_id, source_id, producer_revision)
    tick = _decimal(tick_size, "tick_size")
    lot = _decimal(lot_size, "lot_size")
    source = _require_source(source)
    output_dir = Path(output_dir)
    if output_dir.is_symlink() or output_dir.exists():
        raise QuoteAdmissionError("output already exists")
    if not output_dir.parent.is_dir() or output_dir.parent.is_symlink():
        raise QuoteAdmissionError("output parent must be an existing non-symlink directory")
    scratch = Path(tempfile.mkdtemp(prefix=".icarus-nautilus-", dir=output_dir.parent))
    source_digest, export_digest = hashlib.sha256(), hashlib.sha256()
    count = 0
    first_event = last_event = first_arrival = last_arrival = None
    try:
        with (scratch / "quotes.jsonl").open("wb") as outgoing:
            for row in _source_rows(source, instrument_id, tick, lot, source_digest):
                data = (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode()
                outgoing.write(data)
                export_digest.update(data)
                first_event = row["ts_event"] if first_event is None else first_event
                first_arrival = row["ts_init"] if first_arrival is None else first_arrival
                last_event, last_arrival = row["ts_event"], row["ts_init"]
                count += 1
        if count == 0:
            raise QuoteAdmissionError("empty quote source is not evidence")
        manifest = {
            "schema_version": SCHEMA, "format": "nautilus_quote_jsonl_staging_not_catalog",
            "nautilus_version_required": VERSION, "instrument_id": instrument_id,
            "source_id": source_id, "producer_revision": producer_revision,
            "tick_size": tick_size, "lot_size": lot_size,
            "source_sha256": source_digest.hexdigest(),
            "export_sha256": export_digest.hexdigest(), "rows": count,
            "first_event_ns": first_event, "last_event_ns": last_event,
            "first_arrival_ns": first_arrival, "last_arrival_ns": last_arrival,
            **{name: False for name in DENIED},
        }
        (scratch / "manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        manifest_hash = _file_hash(scratch / "manifest.json")
        if output_dir.exists() or output_dir.is_symlink():
            raise QuoteAdmissionError("output appeared during staging")
        scratch.rename(output_dir)
        return {"manifest": manifest, "manifest_sha256": manifest_hash}
    finally:
        if scratch.exists():
            shutil.rmtree(scratch)


def verify_native(source: Path, staging: Path, *, instrument_id: str,
                  source_id: str, producer_revision: str,
                  expected_source_sha256: str, expected_export_sha256: str,
                  expected_manifest_sha256: str) -> dict:
    """Read-only source-to-staging parity and pinned native QuoteTick roundtrip."""
    _validate_identifiers(instrument_id, source_id, producer_revision)
    for value in (expected_source_sha256, expected_export_sha256, expected_manifest_sha256):
        if not HASH.fullmatch(value):
            raise QuoteAdmissionError("independent 64-character SHA-256 pins required")
    source = _require_source(source)
    staging = Path(staging)
    if staging.is_symlink() or not staging.is_dir():
        raise QuoteAdmissionError("staging must be an existing non-symlink directory")
    files = list(staging.iterdir())
    if {x.name for x in files} != {"manifest.json", "quotes.jsonl"} or any(
        not x.is_file() or x.is_symlink() for x in files
    ):
        raise QuoteAdmissionError("unexpected or symlinked staging entries")
    manifest_path, export_path = staging / "manifest.json", staging / "quotes.jsonl"
    if manifest_path.stat().st_size > 16_384:
        raise QuoteAdmissionError("oversized manifest")
    if _file_hash(manifest_path) != expected_manifest_sha256:
        raise QuoteAdmissionError("manifest digest mismatch")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"),
                              object_pairs_hook=_json_unique)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise QuoteAdmissionError("invalid manifest JSON") from exc
    if not isinstance(manifest, dict):
        raise QuoteAdmissionError("manifest must be a JSON object")
    expected_keys = {
        "schema_version", "format", "nautilus_version_required", "instrument_id",
        "source_id", "producer_revision", "tick_size", "lot_size",
        "source_sha256", "export_sha256", "rows",
        "first_event_ns", "last_event_ns", "first_arrival_ns", "last_arrival_ns",
        *DENIED,
    }
    if set(manifest) != expected_keys:
        raise QuoteAdmissionError("unexpected manifest fields")
    for field, expected in {
        "schema_version": SCHEMA, "format": "nautilus_quote_jsonl_staging_not_catalog",
        "nautilus_version_required": VERSION, "instrument_id": instrument_id,
        "source_id": source_id, "producer_revision": producer_revision,
        "source_sha256": expected_source_sha256,
        "export_sha256": expected_export_sha256,
    }.items():
        if manifest[field] != expected:
            raise QuoteAdmissionError(f"manifest mismatch: {field}")
    if any(manifest[name] is not False for name in DENIED):
        raise QuoteAdmissionError("unapproved research/trading authority claim")
    if _file_hash(source) != expected_source_sha256:
        raise QuoteAdmissionError("source SHA-256 mismatch")
    if _file_hash(export_path) != expected_export_sha256:
        raise QuoteAdmissionError("export SHA-256 mismatch")
    tick = _decimal(manifest["tick_size"], "tick_size")
    lot = _decimal(manifest["lot_size"], "lot_size")
    if importlib.metadata.version("nautilus_trader") != VERSION:
        raise QuoteAdmissionError("native NautilusTrader version mismatch")
    from nautilus_trader.model import InstrumentId, Price, Quantity, QuoteTick

    native_id = InstrumentId.from_str(instrument_id)
    source_digest = hashlib.sha256()
    count = 0
    first_event = last_event = first_arrival = last_arrival = None
    with export_path.open("r", encoding="utf-8") as exported:
        for original, raw in zip_longest(
            _source_rows(source, instrument_id, tick, lot, source_digest), exported
        ):
            if original is None or raw is None:
                raise QuoteAdmissionError("source/export record count mismatch")
            if len(raw) > 4096:
                raise QuoteAdmissionError("oversized quote record")
            try:
                row = json.loads(raw, object_pairs_hook=_json_unique)
            except json.JSONDecodeError as exc:
                raise QuoteAdmissionError("invalid quote JSON") from exc
            if not isinstance(row, dict) or set(row) != set(RECORD_KEYS) or row != original:
                raise QuoteAdmissionError("source/export record mismatch")
            quote = QuoteTick(
                instrument_id=native_id,
                bid_price=Price.from_str(row["bid_price"]),
                ask_price=Price.from_str(row["ask_price"]),
                bid_size=Quantity.from_str(row["bid_size"]),
                ask_size=Quantity.from_str(row["ask_size"]),
                ts_event=row["ts_event"], ts_init=row["ts_init"],
            )
            native = QuoteTick.to_dict(quote)
            expected = {
                "type": "QuoteTick", "instrument_id": instrument_id,
                "bid_price": row["bid_price"], "ask_price": row["ask_price"],
                "bid_size": row["bid_size"], "ask_size": row["ask_size"],
                "ts_event": row["ts_event"], "ts_init": row["ts_init"],
            }
            if native != expected or QuoteTick.from_dict(native) != quote:
                raise QuoteAdmissionError("native QuoteTick precision/roundtrip mismatch")
            first_event = row["ts_event"] if first_event is None else first_event
            first_arrival = row["ts_init"] if first_arrival is None else first_arrival
            last_event, last_arrival = row["ts_event"], row["ts_init"]
            count += 1
    if source_digest.hexdigest() != expected_source_sha256:
        raise QuoteAdmissionError("source changed during verification")
    for field, value in {
        "rows": count, "first_event_ns": first_event, "last_event_ns": last_event,
        "first_arrival_ns": first_arrival, "last_arrival_ns": last_arrival,
    }.items():
        if manifest[field] != value:
            raise QuoteAdmissionError(f"manifest metadata mismatch: {field}")
    if count == 0:
        raise QuoteAdmissionError("no native quote records")
    return {
        "status": "NATIVE_QUOTE_ROUNDTRIP_STRUCTURAL_ONLY",
        "nautilus_version": VERSION, "rows_verified": count,
        "instrument_id": instrument_id,
        "source_sha256": expected_source_sha256,
        "export_sha256": expected_export_sha256,
        "manifest_sha256": expected_manifest_sha256,
        **{name: False for name in DENIED},
        "native_backtest_executed": False,
        "fills_verified": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    stage = commands.add_parser("stage")
    stage.add_argument("--input", required=True, type=Path)
    stage.add_argument("--output", required=True, type=Path)
    stage.add_argument("--tick-size", required=True)
    stage.add_argument("--lot-size", required=True)
    verify = commands.add_parser("verify-native")
    verify.add_argument("--source", required=True, type=Path)
    verify.add_argument("--staging", required=True, type=Path)
    for sub in (stage, verify):
        sub.add_argument("--instrument-id", required=True)
        sub.add_argument("--source-id", required=True)
        sub.add_argument("--producer-revision", required=True)
    for name in ("source", "export", "manifest"):
        verify.add_argument(f"--expected-{name}-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "stage":
            result = stage_quotes(
                args.input, args.output, instrument_id=args.instrument_id,
                source_id=args.source_id, producer_revision=args.producer_revision,
                tick_size=args.tick_size, lot_size=args.lot_size,
            )
        else:
            result = verify_native(
                args.source, args.staging, instrument_id=args.instrument_id,
                source_id=args.source_id, producer_revision=args.producer_revision,
                expected_source_sha256=args.expected_source_sha256,
                expected_export_sha256=args.expected_export_sha256,
                expected_manifest_sha256=args.expected_manifest_sha256,
            )
    except (QuoteAdmissionError, OSError, importlib.metadata.PackageNotFoundError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
