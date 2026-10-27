"""Offline Qlib-compatible *CSV* preparation behind the ICARUS quarantine gate.

This deliberately DOES NOT run Qlib, train a model, or create Qlib .bin files.
Qlib's separately installed dump_bin.py can consume the isolated CSV directory
after operator approval. All timestamps are UTC (rendered without a suffix to
match Qlib's documented datetime parser), recorded explicitly in a manifest.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile

from .external_research_verify import VerificationRejected, verify_candidate


# Restrict to frequencies whose lossless UTC bar timestamps can be exported.
# This DOES NOT claim that the user's installed Qlib model/provider supports them.
FREQUENCIES = {
    60: "1min",
    120: "2min",
    300: "5min",
    600: "10min",
    900: "15min",
    1800: "30min",
    3600: "60min",
}
FIELDS = ("date", "open", "high", "low", "close", "volume", "factor")
CONTRACT_FILENAME = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


def _stream_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare_qlib_csv(
    staging_dir: Path,
    output_dir: Path,
    *,
    expected_producer_repository: str,
    expected_producer_revision: str,
) -> dict[str, object]:
    """Produce a Qlib dump_bin-compatible CSV in a NEW directory, never run it.

    Admission rechecks data and canonical handoff; no recovered/assumed
    entitlement or model authority is granted. The input is read twice and
    checked against its hash, so a changed staged source fails before publish.
    """
    verified = verify_candidate(
        staging_dir,
        expected_producer_repository=expected_producer_repository,
        expected_producer_revision=expected_producer_revision,
    )
    staging_dir = Path(staging_dir)
    source = staging_dir / "qlib-bars.csv"
    manifest_path = staging_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cadence = manifest["bar_seconds"]
    if cadence not in FREQUENCIES:
        raise VerificationRejected(
            "Qlib CSV preparation requires a supported fixed-minute bar cadence"
        )
    contract_id = manifest["actual_contract_id"]
    if not isinstance(contract_id, str) or CONTRACT_FILENAME.fullmatch(contract_id) is None:
        raise VerificationRejected(
            "Qlib filename requires a concrete safe actual contract identifier"
        )
    target = Path(output_dir)
    if target.is_symlink() or target.exists():
        raise VerificationRejected("target output directory must not exist")
    parent = target.parent
    if not parent.is_dir():
        raise VerificationRejected("output parent directory must already exist")
    if source.is_symlink() or manifest_path.is_symlink():
        raise VerificationRejected("staging source cannot be a symlink")

    scratch = Path(tempfile.mkdtemp(prefix=".icarus-qlib-csv-", dir=parent))
    try:
        input_dir = scratch / "qlib_input"
        input_dir.mkdir()
        converted = input_dir / f"{contract_id}.csv"
        count = 0
        digest = hashlib.sha256()
        with source.open("rb") as incoming, converted.open(
            "w", newline="", encoding="utf-8"
        ) as outgoing:
            def raw_lines():
                for data in incoming:
                    digest.update(data)
                    try:
                        yield data.decode("utf-8")
                    except UnicodeDecodeError as exc:
                        raise VerificationRejected("staged input is not UTF-8") from exc

            reader = csv.DictReader(raw_lines(), strict=True)
            if reader.fieldnames != [
                "instrument", "datetime", "open", "high", "low", "close", "volume"
            ]:
                raise VerificationRejected("unexpected staged CSV columns")
            writer = csv.DictWriter(outgoing, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            try:
                for row in reader:
                    if None in row or any(v is None for v in row.values()):
                        raise VerificationRejected("malformed staged CSV")
                    # Preserve raw price/volume strings exactly; the independent
                    # verifier has already checked Decimal geometry/finiteness.
                    utc = datetime.fromisoformat(row["datetime"].replace("Z", "+00:00"))
                    if utc.tzinfo is None or utc.utcoffset() is None or utc.utcoffset().total_seconds() != 0:
                        raise VerificationRejected("lost UTC timestamp identity")
                    utc = utc.astimezone(timezone.utc)
                    seconds_into_utc_day = utc.hour * 3600 + utc.minute * 60 + utc.second
                    if utc.microsecond != 0 or seconds_into_utc_day % cadence != 0:
                        raise VerificationRejected("unaligned/subsecond bars cannot be losslessly converted")
                    timestamp = utc.strftime("%Y-%m-%d %H:%M:%S")
                    writer.writerow({
                        "date": timestamp,
                        **{field: row[field] for field in ("open", "high", "low", "close", "volume")},
                        "factor": "1",
                    })
                    count += 1
            except csv.Error as exc:
                raise VerificationRejected("invalid staged CSV quoting") from exc

        if digest.hexdigest() != manifest["export_sha256"] or count != verified["rows_rechecked"]:
            raise VerificationRejected("source changed while preparing Qlib input")
        record: dict[str, object] = {
            "schema_version": "icarus-qlib-csv-input-v1",
            "handoff_id": verified["handoff_id"],
            "producer_repository": expected_producer_repository,
            "producer_revision": expected_producer_revision,
            "source_export_sha256": manifest["export_sha256"],
            "qlib_csv_sha256": _stream_hash(converted),
            "relative_csv_path": f"qlib_input/{contract_id}.csv",
            "actual_contract_id": contract_id,
            "qlib_frequency": FREQUENCIES[cadence],
            "bar_seconds": cadence,
            "datetime_field": "date",
            "naive_datetime_interpretation": "UTC",
            "factor": "1",
            "price_basis": "raw_unadjusted",
            "rows": count,
            "calendar_completeness_verified": False,
            "provider_authenticity_verified": False,
            "entitlement_verified": False,
            "native_qlib_binary_verified": False,
            "model_trained": False,
            "execution_authorized": False,
            "authority_granted": "NONE",
        }
        (scratch / "prepare_manifest.json").write_text(
            json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        if target.is_symlink() or target.exists():
            raise VerificationRejected("target output appeared during preparation")
        scratch.rename(target)
        return record
    finally:
        if scratch.exists():
            shutil.rmtree(scratch)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--producer-repository", required=True)
    parser.add_argument("--producer-revision", required=True)
    args = parser.parse_args(argv)
    try:
        result = prepare_qlib_csv(
            args.staging, args.output,
            expected_producer_repository=args.producer_repository,
            expected_producer_revision=args.producer_revision,
        )
    except (VerificationRejected, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
