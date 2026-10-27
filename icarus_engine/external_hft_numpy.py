"""Quarantined HFTBacktest L2 Event NumPy NPY v1.0 writer (offline, research only).

Consumes only source-to-staging independently verified MBP L2 data. Does not
import or execute HFTBacktest, infer MBO, create book snapshots, or run orders.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import stat
import struct
import tempfile

from .external_hft_verify import (
    EXPORT, L2VerificationError, verify_hft_l2,
)

# Upstream Event (repr(C, align(64))) fields, pinned at revision below.
# The NPY header is a standard structured dtype with eight 8-byte fields.
UPSTREAM_HFTBACKTEST_REVISION = "5f3ec40b2afb764e0fea112f941ed85523ef4e88"
DTYPE = (
    ("ev", "<u8"), ("exch_ts", "<i8"), ("local_ts", "<i8"),
    ("px", "<f8"), ("qty", "<f8"), ("order_id", "<u8"),
    ("ival", "<i8"), ("fval", "<f8"),
)
RECORD = struct.Struct("<QqqddQqd")
MAGIC = b"\x93NUMPY\x01\x00"
LIMIT = 65535
CHUNK = 1024 * 1024


class L2NpyError(ValueError):
    """A source, staging or binary contract could not be verified."""


def _safe_directory(path: Path) -> Path:
    path = Path(path).absolute()
    for item in (path, *path.parents):
        if item.is_symlink():
            raise L2NpyError("symlink output path refused")
    if path.exists():
        raise L2NpyError("output directory already exists")
    if not path.parent.is_dir():
        raise L2NpyError("output parent must exist")
    return path


def _npy_header(rows: int) -> bytes:
    if type(rows) is not int or rows < 1 or rows > 2**63 - 1:
        raise L2NpyError("invalid NumPy shape")
    header = repr({
        "descr": list(DTYPE), "fortran_order": False, "shape": (rows,),
    }).encode("ascii")
    pad = (-(len(MAGIC) + 2 + len(header) + 1)) % 16
    header += b" " * pad + b"\n"
    if len(header) > LIMIT:
        raise L2NpyError("NumPy header exceeds v1.0 bound")
    return MAGIC + struct.pack("<H", len(header)) + header


def _decode_lines(source, digest):
    for index, line in enumerate(source):
        digest.update(line)
        try:
            yield line.decode("utf-8-sig" if index == 0 else "utf-8")
        except UnicodeError as exc:
            raise L2NpyError("non-UTF-8 staged CSV") from exc


def _recheck_row(row, index, previous):
    if None in row or any(value is None for value in row.values()):
        raise L2NpyError(f"row {index}: missing/extra event columns")
    try:
        ev = int(row["ev"])
        exch = int(row["exch_ts"])
        local = int(row["local_ts"])
        px = float(row["px"])
        qty = float(row["qty"])
        order = int(row["order_id"])
        ival = int(row["ival"])
        fval = float(row["fval"])
        if (str(ev) != row["ev"] or str(exch) != row["exch_ts"]
                or str(local) != row["local_ts"]
                or str(order) != row["order_id"]
                or str(ival) != row["ival"] or row["fval"] != "0.0"):
            raise ValueError("noncanonical field")
        if ev not in (
            1 | (1 << 29) | (1 << 30) | (1 << 31),
            1 | (1 << 28) | (1 << 30) | (1 << 31),
            2 | (1 << 29) | (1 << 30) | (1 << 31),
            2 | (1 << 28) | (1 << 30) | (1 << 31),
        ):
            raise ValueError("unsupported event")
        if (exch < 0 or local < exch or order != 0 or ival != 0 or fval != 0.0
                or not (0 < px < float("inf")) or not (0 <= qty < float("inf"))
                or (ev & 0xff) == 2 and qty == 0):
            raise ValueError("invalid event values")
        if previous is not None and (exch < previous[0] or local < previous[1]):
            raise ValueError("nonmonotonic clocks")
        return RECORD.pack(ev, exch, local, px, qty, order, ival, fval), (exch, local)
    except (ValueError, OverflowError, struct.error, TypeError) as exc:
        raise L2NpyError(f"row {index}: malformed or out-of-range event") from exc


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def pack_verified_l2(
    source: Path,
    staging: Path,
    output: Path,
    *,
    expected_contract_id: str,
    expected_source_id: str,
    expected_input_sha256: str,
    expected_tick_size: str,
    expected_lot_size: str,
) -> dict:
    """Write a native NumPy structured-array file after independent admission.

    Source hash must be obtained from an independently trusted original receipt.
    No arbitrary row ceiling. The file is not a HFTBacktest replay receipt.
    """
    # Run the *independent* original-source verifier before touching output.
    receipt = verify_hft_l2(
        source, staging,
        expected_contract_id=expected_contract_id,
        expected_source_id=expected_source_id,
        expected_input_sha256=expected_input_sha256,
        expected_tick_size=expected_tick_size,
        expected_lot_size=expected_lot_size,
    )
    output = _safe_directory(output)
    staged_file = Path(staging).absolute() / "hft-events.csv"
    if not stat.S_ISREG(staged_file.stat().st_mode) or staged_file.is_symlink():
        raise L2NpyError("staged event file must be regular")
    scratch = Path(tempfile.mkdtemp(prefix=".icarus-hft-npy-", dir=output.parent))
    try:
        digest_csv = hashlib.sha256()
        digest_npy = hashlib.sha256()
        rows = 0
        previous = None
        with staged_file.open("rb") as incoming, (scratch / "hft-events.npy").open("wb") as binary:
            header = _npy_header(receipt["rows"])
            binary.write(header)
            digest_npy.update(header)
            reader = csv.DictReader(_decode_lines(incoming, digest_csv), strict=True)
            if reader.fieldnames != list(EXPORT):
                raise L2NpyError("staged CSV header changed")
            try:
                for index, event in enumerate(reader, 2):
                    packed, previous = _recheck_row(event, index, previous)
                    binary.write(packed)
                    digest_npy.update(packed)
                    rows += 1
            except csv.Error as exc:
                raise L2NpyError("malformed staged CSV") from exc
        if rows != receipt["rows"] or digest_csv.hexdigest() != receipt["export_sha256"]:
            raise L2NpyError("staged CSV changed after independent verification")
        if _sha256_file(Path(source)) != expected_input_sha256:
            raise L2NpyError("original source changed during conversion")
        npy_path = scratch / "hft-events.npy"
        if npy_path.stat().st_size != len(header) + rows * RECORD.size:
            raise L2NpyError("native binary size mismatch")
        if _sha256_file(npy_path) != digest_npy.hexdigest():
            raise L2NpyError("native binary digest mismatch")
        manifest = {
            "schema_version": "icarus-hftbacktest-npy-quarantine-v1",
            "format": "numpy_npy_v1_structured_events",
            "upstream_hftbacktest_revision": UPSTREAM_HFTBACKTEST_REVISION,
            "actual_contract_id": expected_contract_id,
            "source_id": expected_source_id,
            "source_sha256": expected_input_sha256,
            "staged_csv_sha256": receipt["export_sha256"],
            "npy_sha256": digest_npy.hexdigest(),
            "rows": rows, "depth_updates": receipt["depth_updates"],
            "trades": receipt["trades"], "dtype": [list(item) for item in DTYPE],
            "record_size_bytes": RECORD.size,
            "source_authenticity_verified": False,
            "entitlement_verified": False,
            "clock_sync_verified": False,
            "complete_book_verified": False,
            "mbo_order_ids_available": False,
            "numpy_independent_readback_verified": False,
            "hftbacktest_runtime_verified": False,
            "queue_and_latency_calibrated": False,
            "empirical_fill_quality_verified": False,
            "training_approved": False,
            "execution_authorized": False,
            "authority_granted": "NONE",
            "status": "QUARANTINED",
        }
        (scratch / "native_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        _safe_directory(output)  # Fail if another worker created it.
        scratch.rename(output)
        return manifest
    finally:
        if scratch.exists():
            shutil.rmtree(scratch)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--contract-id", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--expected-input-sha256", required=True)
    parser.add_argument("--tick-size", required=True)
    parser.add_argument("--lot-size", required=True)
    args = parser.parse_args(argv)
    try:
        report = pack_verified_l2(
            args.source, args.staging, args.output,
            expected_contract_id=args.contract_id,
            expected_source_id=args.source_id,
            expected_input_sha256=args.expected_input_sha256,
            expected_tick_size=args.tick_size, expected_lot_size=args.lot_size,
        )
    except (L2VerificationError, L2NpyError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
