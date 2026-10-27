"""Read-only proof of structural parity for an independently produced Qlib dump_bin dataset.

The verifier does NOT run Qlib, load ML models, access network/data providers or
authorize an execution decision. Binary layout is inspected against the official
microsoft/qlib scripts/dump_bin.py writer (little-endian float32, calendar index
then factor/price observations).
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import struct

from .external_research_verify import VerificationRejected, _sha256, _require

FIELDS = ("open", "high", "low", "close", "volume", "factor")
PREPARED_COLUMNS = ("date", "open", "high", "low", "close", "volume", "factor")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
FREQS = frozenset({"1min", "2min", "5min", "10min", "15min", "30min", "60min"})
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\Z")


def _regular_file(path: Path) -> None:
    _require(not path.is_symlink() and path.is_file(), f"missing/linked file: {path.name}")


def _regular_dir(path: Path) -> None:
    _require(not path.is_symlink() and path.is_dir(), f"missing/linked directory: {path.name}")


def _read_json(path: Path) -> dict:
    _regular_file(path)
    try:
        def unique(pairs):
            data = {}
            for key, value in pairs:
                _require(key not in data, "duplicate manifest key")
                data[key] = value
            return data
        obj = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationRejected("invalid preparation manifest") from exc
    _require(isinstance(obj, dict), "preparation manifest is not an object")
    return obj


def _utc_naive(text: object) -> str:
    _require(isinstance(text, str) and DATE_RE.fullmatch(text) is not None,
             "invalid Qlib UTC-naive timestamp")
    from datetime import datetime
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError as exc:
        raise VerificationRejected("invalid Qlib UTC-naive timestamp") from exc
    _require(parsed.strftime("%Y-%m-%d %H:%M:%S") == text,
             "noncanonical date field")
    return text


def _expect_f32(raw: object) -> bytes:
    _require(isinstance(raw, str), "invalid CSV numeric string")
    try:
        value = Decimal(raw)
        _require(value.is_finite(), "nonfinite CSV numeric field")
        return struct.pack("<f", float(value))
    except (ValueError, TypeError, InvalidOperation, OverflowError) as exc:
        raise VerificationRejected("numeric value outside float32 encoding") from exc


def verify_qlib_binary(
    prepared_dir: Path,
    qlib_dir: Path,
    *,
    expected_contract_id: str,
    expected_producer_revision: str,
    expected_producer_repository: str,
    expected_handoff_id: str,
) -> dict[str, object]:
    """Compare every prepared raw observation to official Qlib binary layout.

    This is a structural integrity check only: the expected revision and input
    provenance must independently come from an authorized source.
    """
    prepared_dir = Path(prepared_dir)
    qlib_dir = Path(qlib_dir)
    _regular_dir(prepared_dir)
    _regular_dir(qlib_dir)
    prep = _read_json(prepared_dir / "prepare_manifest.json")
    _require(prep.get("schema_version") == "icarus-qlib-csv-input-v1"
             and prep.get("authority_granted") == "NONE"
             and prep.get("execution_authorized") is False
             and prep.get("native_qlib_binary_verified") is False
             and prep.get("model_trained") is False,
             "preparation authority or format mismatch")
    for flag in ("calendar_completeness_verified", "provider_authenticity_verified",
                 "entitlement_verified"):
        _require(prep.get(flag) is False, f"unverified flag elevated: {flag}")
    _require(isinstance(expected_producer_revision, str)
             and re.fullmatch(r"[0-9a-f]{40}", expected_producer_revision) is not None
             and prep.get("producer_revision") == expected_producer_revision,
             "producer revision mismatch")
    _require(isinstance(expected_producer_repository, str)
             and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", expected_producer_repository)
             is not None
             and prep.get("producer_repository") == expected_producer_repository,
             "producer repository mismatch")
    _require(isinstance(expected_handoff_id, str)
             and HEX64.fullmatch(expected_handoff_id) is not None
             and prep.get("handoff_id") == expected_handoff_id,
             "independent handoff identity mismatch")
    _require(isinstance(expected_contract_id, str)
             and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", expected_contract_id) is not None
             and prep.get("actual_contract_id") == expected_contract_id,
             "physical futures contract mismatch")
    _require(prep.get("price_basis") == "raw_unadjusted"
             and prep.get("factor") == "1"
             and prep.get("datetime_field") == "date"
             and prep.get("naive_datetime_interpretation") == "UTC",
             "Qlib factor/timezone conventions mismatch")
    frequency = prep.get("qlib_frequency")
    _require(isinstance(frequency, str) and frequency in FREQS,
             "unrecognized native Qlib frequency")
    count = prep.get("rows")
    _require(type(count) is int and count > 0, "invalid preparation row count")
    digest = prep.get("qlib_csv_sha256")
    _require(isinstance(digest, str) and HEX64.fullmatch(digest) is not None,
             "invalid preparation checksum")
    _require(prep.get("relative_csv_path") == f"qlib_input/{expected_contract_id}.csv",
             "unrecognized prepared CSV path")
    input_dir = prepared_dir / "qlib_input"
    _regular_dir(input_dir)
    csv_path = input_dir / f"{expected_contract_id}.csv"
    _require(_sha256(csv_path) == digest, "prepared CSV checksum mismatch")

    cal_dir = qlib_dir / "calendars"
    instruments_dir = qlib_dir / "instruments"
    features_root = qlib_dir / "features"
    contract_features = features_root / expected_contract_id.lower()
    for folder in (cal_dir, instruments_dir, features_root, contract_features):
        _regular_dir(folder)
    cal_path = cal_dir / f"{frequency}.txt"
    inst_path = instruments_dir / "all.txt"
    for path in (cal_path, inst_path):
        _regular_file(path)
    binary_paths = {
        field: contract_features / f"{field}.{frequency}.bin"
        for field in FIELDS
    }
    handles = {}
    observations = 0
    first = last = None
    calendar_hash = hashlib.sha256()
    try:
        with csv_path.open("r", newline="", encoding="utf-8") as csv_in, \
                cal_path.open("rb") as calendars:
            reader = csv.DictReader(csv_in, strict=True)
            _require(reader.fieldnames == list(PREPARED_COLUMNS),
                     "prepared CSV has unknown columns")
            for field, path in binary_paths.items():
                _regular_file(path)
                _require(path.stat().st_size == 4 * (count + 1),
                         f"Qlib float32 byte-length mismatch: {field}")
                handle = path.open("rb")
                handles[field] = handle
                _require(handle.read(4) == struct.pack("<f", 0.0),
                         f"Qlib calendar start index mismatch: {field}")
            try:
                for row in reader:
                    _require(None not in row and all(v is not None for v in row.values()),
                             "malformed prepared CSV row")
                    utc = _utc_naive(row["date"])
                    if last is not None:
                        _require(utc > last, "Qlib timestamps not strictly increasing")
                    if first is None:
                        first = utc
                    last = utc
                    calendar_line = calendars.readline()
                    _require(calendar_line == (utc + "\n").encode("ascii"),
                             "Qlib calendar does not equal raw timestamp")
                    calendar_hash.update(calendar_line)
                    for field, handle in handles.items():
                        observed = handle.read(4)
                        _require(observed == _expect_f32(row[field]),
                                 f"Qlib float32 data parity mismatch: {field}")
                    observations += 1
            except csv.Error as exc:
                raise VerificationRejected("invalid prepared CSV syntax") from exc
            _require(calendars.read(1) == b"", "Qlib calendar contains unexpected data")
        _require(observations == count, "Qlib observation count mismatch")
        _require(_sha256(csv_path) == digest, "prepared CSV changed during verification")
        with inst_path.open("r", encoding="utf-8", newline="") as instruments:
            entries = [line.rstrip("\r\n") for line in instruments]
        _require(entries == [f"{expected_contract_id.upper()}\t{first}\t{last}"],
                 "Qlib instrument range or physical contract mismatch")
        for field, handle in handles.items():
            _require(handle.read(1) == b"", f"unexpected trailing Qlib data: {field}")
        return {
            "schema_version": "icarus-qlib-native-structural-verify-v1",
            "producer_revision": expected_producer_revision,
            "producer_repository": expected_producer_repository,
            "handoff_id": expected_handoff_id,
            "actual_contract_id": expected_contract_id,
            "frequency": frequency,
            "rows_rechecked": observations,
            "prepared_csv_sha256": digest,
            "qlib_calendar_sha256": calendar_hash.hexdigest(),
            "qlib_feature_digests": {
                field: _sha256(path) for field, path in binary_paths.items()
            },
            "structural_binary_parity": True,
            "native_qlib_code_executed_by_this_tool": False,
            "vendor_authenticity_verified": False,
            "data_entitlement_verified": False,
            "market_calendar_completeness_verified": False,
            "real_price_execution_validated": False,
            "model_approved": False,
            "authority_granted": "NONE",
        }
    except (OSError, UnicodeError) as exc:
        raise VerificationRejected("unable to read Qlib native output") from exc
    finally:
        for handle in handles.values():
            handle.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--qlib-dir", type=Path, required=True)
    parser.add_argument("--contract-id", required=True)
    parser.add_argument("--producer-revision", required=True)
    parser.add_argument("--producer-repository", required=True)
    parser.add_argument("--handoff-id", required=True)
    args = parser.parse_args(argv)
    try:
        receipt = verify_qlib_binary(
            args.prepared, args.qlib_dir,
            expected_contract_id=args.contract_id,
            expected_producer_revision=args.producer_revision,
            expected_producer_repository=args.producer_repository,
            expected_handoff_id=args.handoff_id,
        )
    except (VerificationRejected, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(receipt, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
