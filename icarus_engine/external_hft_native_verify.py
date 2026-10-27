"""Independent, read-only native HFTBacktest Event NPY quarantine verifier.

No simulator, provider, model, broker, trading, or file writes. Structural
verification does not establish licensed source authenticity or executable fills.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
from pathlib import Path
import re
import stat
import struct

from .external_hft_verify import EXPORT, L2VerificationError, verify_hft_l2

MAGIC = b"\x93NUMPY\x01\x00"
EVENT = struct.Struct("<QqqddQqd")
FIELDS = [
    ["ev", "<u8"], ["exch_ts", "<i8"], ["local_ts", "<i8"],
    ["px", "<f8"], ["qty", "<f8"], ["order_id", "<u8"],
    ["ival", "<i8"], ["fval", "<f8"],
]
PINNED_UPSTREAM = "5f3ec40b2afb764e0fea112f941ed85523ef4e88"
DENIED = (
    "source_authenticity_verified", "entitlement_verified",
    "clock_sync_verified", "complete_book_verified",
    "mbo_order_ids_available", "numpy_independent_readback_verified",
    "hftbacktest_runtime_verified", "queue_and_latency_calibrated",
    "empirical_fill_quality_verified", "training_approved",
    "execution_authorized",
)
FIELDS_REQUIRED = {
    "schema_version", "format", "upstream_hftbacktest_revision",
    "actual_contract_id", "source_id", "source_sha256",
    "staged_csv_sha256", "npy_sha256", "rows", "depth_updates",
    "trades", "dtype", "record_size_bytes", "authority_granted", "status",
} | set(DENIED)
SHA = re.compile(r"[0-9a-f]{64}\Z")
BLOCK = 1024 * 1024


class NativeVerificationError(ValueError):
    """Native event quarantine failed independent structural verification."""


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise NativeVerificationError("duplicate JSON manifest key")
        result[key] = value
    return result


def _reject_constant(value):
    raise NativeVerificationError("nonstandard JSON constant")


def _safe(path, directory=False):
    path = Path(path).absolute()
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            raise NativeVerificationError("symlink path refused")
    try:
        mode = path.stat().st_mode
    except OSError as exc:
        raise NativeVerificationError("missing/unreadable quarantine path") from exc
    if directory and not stat.S_ISDIR(mode):
        raise NativeVerificationError("expected directory")
    if not directory and not stat.S_ISREG(mode):
        raise NativeVerificationError("expected regular file")
    return path


def _sha_file(path):
    digest = hashlib.sha256()
    with _safe(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(BLOCK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest(path, receipt, contract, source_id, source_sha):
    path = _safe(path)
    if path.stat().st_size > 65536:
        raise NativeVerificationError("manifest exceeds bounded size")
    try:
        data = json.loads(path.read_text(encoding="utf-8"),
                          object_pairs_hook=_unique_pairs,
                          parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise NativeVerificationError("invalid manifest encoding/JSON") from exc
    if not isinstance(data, dict) or set(data) != FIELDS_REQUIRED:
        raise NativeVerificationError("native manifest keys missing or unexpected")
    fixed = {
        "schema_version": "icarus-hftbacktest-npy-quarantine-v1",
        "format": "numpy_npy_v1_structured_events",
        "upstream_hftbacktest_revision": PINNED_UPSTREAM,
        "actual_contract_id": contract,
        "source_id": source_id,
        "source_sha256": source_sha,
        "staged_csv_sha256": receipt["export_sha256"],
        "dtype": FIELDS,
        "record_size_bytes": EVENT.size,
        "authority_granted": "NONE",
        "status": "QUARANTINED",
    }
    for key, value in fixed.items():
        if type(data[key]) is not type(value) or data[key] != value:
            raise NativeVerificationError(f"native manifest {key} mismatch")
    for key in DENIED:
        if data[key] is not False:
            raise NativeVerificationError(f"unsafe authority claim: {key}")
    for key in ("rows", "depth_updates", "trades"):
        if type(data[key]) is not int or data[key] != receipt[key]:
            raise NativeVerificationError(f"native manifest {key} count mismatch")
    if not isinstance(data["npy_sha256"], str) or not SHA.fullmatch(data["npy_sha256"]):
        raise NativeVerificationError("invalid native SHA-256")
    return data


def _header(handle, rows):
    prefix = handle.read(10)
    if len(prefix) != 10 or prefix[:8] != MAGIC:
        raise NativeVerificationError("unsupported NPY magic/version")
    header_len = struct.unpack("<H", prefix[8:10])[0]
    if not header_len or (10 + header_len) % 16:
        raise NativeVerificationError("invalid NPY header length/alignment")
    raw = handle.read(header_len)
    if len(raw) != header_len or not raw.endswith(b"\n"):
        raise NativeVerificationError("truncated NPY header")
    try:
        parsed = ast.parse(raw.decode("ascii"), mode="eval")
        if not isinstance(parsed.body, ast.Dict):
            raise NativeVerificationError("NPY header is not a dict")
        keys = [ast.literal_eval(node) for node in parsed.body.keys]
        if len(keys) != len(set(keys)):
            raise NativeVerificationError("duplicate NPY header keys")
        header = ast.literal_eval(parsed)
    except NativeVerificationError:
        raise
    except (UnicodeError, SyntaxError, ValueError, TypeError, MemoryError, RecursionError) as exc:
        raise NativeVerificationError("invalid NPY header") from exc
    if not isinstance(header, dict) or set(header) != {
        "descr", "fortran_order", "shape"
    }:
        raise NativeVerificationError("unexpected NPY header fields")
    expected = [tuple(item) for item in FIELDS]
    if (header["descr"] != expected or header["fortran_order"] is not False
            or header["shape"] != (rows,)):
        raise NativeVerificationError("NPY dtype/shape/byte-order mismatch")
    return prefix + raw


def verify_native_l2(source, staging, native_dir, *, expected_contract_id,
                     expected_source_id, expected_input_sha256,
                     expected_tick_size, expected_lot_size):
    """Read and compare every native record with independently checked source.

    The original SHA must come from a separate trusted receipt, never the
    staged/native manifests. Does not grant replay, research or trading authority.
    """
    original = verify_hft_l2(
        source, staging,
        expected_contract_id=expected_contract_id,
        expected_source_id=expected_source_id,
        expected_input_sha256=expected_input_sha256,
        expected_tick_size=expected_tick_size,
        expected_lot_size=expected_lot_size,
    )
    native_dir = _safe(native_dir, directory=True)
    if {entry.name for entry in native_dir.iterdir()} != {
        "hft-events.npy", "native_manifest.json"
    }:
        raise NativeVerificationError("unexpected/missing native artifacts")
    binary = _safe(native_dir / "hft-events.npy")
    manifest = _manifest(native_dir / "native_manifest.json", original,
                         expected_contract_id, expected_source_id,
                         expected_input_sha256)
    staged = _safe(Path(staging) / "hft-events.csv")
    count = 0
    digest = hashlib.sha256()
    try:
        with staged.open("r", encoding="utf-8-sig", newline="") as source_csv, binary.open("rb") as npy:
            header = _header(npy, original["rows"])
            digest.update(header)
            reader = csv.DictReader(source_csv, strict=True)
            if reader.fieldnames != list(EXPORT):
                raise NativeVerificationError("staged event columns changed")
            for row in reader:
                count += 1
                if count > original["rows"]:
                    raise NativeVerificationError("extra staged records")
                if None in row or any(value is None for value in row.values()):
                    raise NativeVerificationError("malformed staged event row")
                try:
                    expected = EVENT.pack(
                        int(row["ev"]), int(row["exch_ts"]), int(row["local_ts"]),
                        float(row["px"]), float(row["qty"]), int(row["order_id"]),
                        int(row["ival"]), float(row["fval"]),
                    )
                except (ValueError, OverflowError, struct.error, TypeError) as exc:
                    raise NativeVerificationError("staged event cannot be encoded") from exc
                actual = npy.read(EVENT.size)
                if actual != expected:
                    raise NativeVerificationError(f"native record {count} differs from source")
                digest.update(actual)
            if count != original["rows"]:
                raise NativeVerificationError("missing staged records")
            if npy.read(1):
                raise NativeVerificationError("trailing native binary bytes")
    except csv.Error as exc:
        raise NativeVerificationError("malformed staged CSV quoting") from exc
    if binary.stat().st_size != len(header) + count * EVENT.size:
        raise NativeVerificationError("native file size mismatch")
    if digest.hexdigest() != manifest["npy_sha256"] or _sha_file(binary) != digest.hexdigest():
        raise NativeVerificationError("native file hash mismatch")
    if _sha_file(source) != expected_input_sha256:
        raise NativeVerificationError("original source changed during verification")
    if _sha_file(staged) != original["export_sha256"]:
        raise NativeVerificationError("staging changed during verification")
    return {
        "status": "STRUCTURALLY_VERIFIED_QUARANTINED",
        "actual_contract_id": expected_contract_id,
        "source_id": expected_source_id,
        "source_sha256": expected_input_sha256,
        "staged_csv_sha256": original["export_sha256"],
        "native_sha256": digest.hexdigest(),
        "rows": count,
        "record_size_bytes": EVENT.size,
        "native_byte_parity_verified": True,
        "source_authenticity_verified": False,
        "entitlement_verified": False,
        "hftbacktest_runtime_verified": False,
        "queue_and_latency_calibrated": False,
        "empirical_fill_quality_verified": False,
        "training_approved": False,
        "execution_authorized": False,
        "authority_granted": "NONE",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "staging", "native-dir"):
        parser.add_argument("--" + name, required=True, type=Path)
    for name in ("contract-id", "source-id", "expected-input-sha256",
                 "tick-size", "lot-size"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    try:
        receipt = verify_native_l2(
            args.source, args.staging, args.native_dir,
            expected_contract_id=args.contract_id,
            expected_source_id=args.source_id,
            expected_input_sha256=args.expected_input_sha256,
            expected_tick_size=args.tick_size, expected_lot_size=args.lot_size,
        )
    except (NativeVerificationError, L2VerificationError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
