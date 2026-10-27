"""Independent, read-only consumer verification for quarantined research exports.

This is a structural/file-integrity check, NOT provider authentication, native
Qlib ingestion, backtest validation, model approval, or order authorization.
No files are written; no plugins, brokers, or vendor APIs are imported/called.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re


BAR_FIELDS = ("instrument", "datetime", "open", "high", "low", "close", "volume")
METRICS = ("open", "high", "low", "close", "volume")
DENIED = (
    "source_authenticity_verified", "entitlement_verified",
    "roll_mapping_verified", "training_approved", "execution_authorized",
)
EVIDENCE_MISSING = frozenset({
    "vendor_authenticity_receipt", "entitlement_confirmation",
    "roll_calendar_validation", "training_holdout_validation",
})
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
IDENTIFIER = re.compile(r"[A-Za-z0-9_.!:-]{1,64}\Z")


class VerificationRejected(ValueError):
    """A candidate cannot be consumed even as verified structural evidence."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise VerificationRejected(reason)


def _identifier(value: object, name: str) -> str:
    _require(isinstance(value, str) and IDENTIFIER.fullmatch(value) is not None,
             f"invalid {name}")
    return value


def _utc(value: object) -> datetime:
    _require(isinstance(value, str), "timestamp must be a string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError) as exc:
        raise VerificationRejected("invalid timestamp") from exc
    _require(parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0),
             "timestamp must explicitly be UTC")
    return parsed.astimezone(timezone.utc)


def _decimal(value: object) -> Decimal:
    _require(isinstance(value, str), "numeric value must be a CSV string")
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise VerificationRejected("invalid numeric value") from exc
    _require(parsed.is_finite(), "nonfinite numeric value")
    return parsed


def _regular(path: Path) -> None:
    _require(not path.is_symlink() and path.is_file(), f"not a regular file: {path.name}")


def _sha256(path: Path) -> str:
    _regular(path)
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    output: dict[str, object] = {}
    for name, value in pairs:
        _require(name not in output, "duplicate JSON object key")
        output[name] = value
    return output


def _parse_constant(value: str):
    raise VerificationRejected(f"nonstandard JSON constant: {value}")


def _json(path: Path) -> dict[str, object]:
    _regular(path)
    try:
        obj = json.loads(path.read_text(encoding="utf-8"),
                         object_pairs_hook=_unique_pairs,
                         parse_constant=_parse_constant)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationRejected(f"invalid JSON: {path.name}") from exc
    _require(isinstance(obj, dict), "JSON object required")
    return obj


def _verify_rows(csv_path: Path, manifest: dict[str, object]) -> int:
    first = last = None
    previous = None
    count = 0
    instrument = _identifier(manifest.get("instrument"), "instrument")
    seconds = manifest.get("bar_seconds")
    _require(type(seconds) is int and 1 <= seconds <= 86400,
             "invalid bar duration")
    _regular(csv_path)
    try:
        with csv_path.open("r", encoding="utf-8", newline="") as infile:
            reader = csv.DictReader(infile, strict=True)
            _require(reader.fieldnames == list(BAR_FIELDS),
                     "CSV columns and ordering must match canonical export")
            for record in reader:
                _require(None not in record and all(v is not None for v in record.values()),
                         "malformed CSV row")
                _require(record["instrument"] == instrument,
                         "different instrument in staged row")
                instant = _utc(record["datetime"])
                if previous is not None:
                    delta = (instant - previous).total_seconds()
                    _require(delta >= seconds and delta % seconds == 0,
                             "duplicate, backwards, or overlapping bar timestamp")
                values = {name: _decimal(record[name]) for name in METRICS}
                _require(values["high"] >= max(values["open"], values["close"])
                         and values["low"] <= min(values["open"], values["close"])
                         and values["high"] >= values["low"]
                         and values["volume"] >= 0, "bad OHLCV geometry")
                first = instant if first is None else first
                previous = instant
                last = instant
                count += 1
    except (csv.Error, UnicodeError) as exc:
        raise VerificationRejected("malformed CSV") from exc
    _require(count > 0 and type(manifest.get("rows")) is int and count == manifest["rows"],
             "row count mismatch")
    _require(first == _utc(manifest.get("first_utc"))
             and last == _utc(manifest.get("last_utc")), "source/export timestamps mismatch")
    return count


def verify_candidate(
    staging_dir: Path,
    *,
    expected_producer_repository: str,
    expected_producer_revision: str,
) -> dict[str, object]:
    """Read-only fail-closed verification of a single quarantined candidate.

    Expected identity MUST come from an independently trusted GitHub/revision
    record; equality is not cryptographic signature/producer authorization.
    """
    _require(isinstance(expected_producer_repository, str)
             and REPOSITORY.fullmatch(expected_producer_repository) is not None,
             "invalid expected producer repository")
    _require(isinstance(expected_producer_revision, str)
             and HEX40.fullmatch(expected_producer_revision) is not None,
             "expected revision must be a complete lowercase commit SHA")

    folder = Path(staging_dir)
    _require(not folder.is_symlink() and folder.is_dir(),
             "staging directory must be real")
    candidate_dir = folder / "candidate_handoff"
    _require(not candidate_dir.is_symlink() and candidate_dir.is_dir(),
             "candidate directory must be real")
    manifest_file = folder / "manifest.json"
    csv_file = folder / "qlib-bars.csv"
    evidence_file = candidate_dir / "evidence_record.json"
    handoff_file = candidate_dir / "handoff.json"
    manifest = _json(manifest_file)
    evidence = _json(evidence_file)
    handoff = _json(handoff_file)

    _require(manifest.get("schema_version") == "icarus-external-research-v1"
             and manifest.get("target") == "qlib_csv_staging"
             and manifest.get("price_basis") == "raw_operator_attested",
             "invalid staging format/basis")
    _identifier(manifest.get("source_id"), "source_id")
    _identifier(manifest.get("actual_contract_id"), "contract_id")
    for key in DENIED:
        _require(manifest.get(key) is False,
                 f"candidate attempted authority elevation: {key}")
    source_hash = manifest.get("source_sha256")
    exported_hash = manifest.get("export_sha256")
    _require(isinstance(source_hash, str) and HEX64.fullmatch(source_hash) is not None,
             "invalid source checksum")
    _require(isinstance(exported_hash, str) and HEX64.fullmatch(exported_hash) is not None,
             "invalid export checksum")
    _require(_sha256(csv_file) == exported_hash, "export data checksum mismatch")
    count = _verify_rows(csv_file, manifest)

    _require(handoff.get("schema_version") == "1.0.0"
             and handoff.get("producer") == "external_quant_fabric"
             and handoff.get("producer_repository") == expected_producer_repository
             and handoff.get("producer_revision") == expected_producer_revision
             and handoff.get("target_repository") == "reppiks490/Icarus"
             and handoff.get("target_revision") is None,
             "unrecognized or unpinned research handoff")
    _require(handoff.get("authority_requested") == "RESEARCH"
             and handoff.get("authority_granted") == "NONE",
             "handoff authority elevation denied")
    _require(type(handoff.get("claims")) is list
             and type(handoff.get("limitations")) is list
             and len(handoff["limitations"]) > 0,
             "missing research limitations")

    artifacts = handoff.get("artifacts")
    _require(type(artifacts) is list and len(artifacts) == 3,
             "incomplete or unexpected handoff artifact set")
    expected_artifacts = {
        "qlib-bars.csv": exported_hash,
        "manifest.json": _sha256(manifest_file),
        "candidate_handoff/evidence_record.json": _sha256(evidence_file),
    }
    seen: set[str] = set()
    for entry in artifacts:
        _require(isinstance(entry, dict) and isinstance(entry.get("path"), str),
                 "invalid artifact descriptor")
        path = entry["path"]
        _require(path in expected_artifacts and path not in seen,
                 "unrecognized or duplicate artifact")
        _require(entry.get("hash") == expected_artifacts[path],
                 "artifact checksum mismatch")
        seen.add(path)
    _require(seen == set(expected_artifacts), "missing artifact")

    _require(evidence.get("schema_version") == "1.0.0"
             and evidence.get("source_revision") == expected_producer_revision
             and evidence.get("transform_revision") == expected_producer_revision
             and evidence.get("source_id") == manifest["source_id"]
             and evidence.get("instrument_id") == manifest["instrument"]
             and evidence.get("contract_id") == manifest["actual_contract_id"]
             and evidence.get("raw_artifact_hash") == source_hash
             and evidence.get("timezone") == "UTC",
             "evidence lineage mismatch")
    _require(evidence.get("decision_context_at") is None,
             "provisional research cannot have execution decision time")
    quality = evidence.get("quality")
    _require(isinstance(quality, dict) and quality.get("stale") is True
             and quality.get("confidence") is None
             and quality.get("conflicted") is False
             and isinstance(quality.get("missing_fields"), list)
             and EVIDENCE_MISSING.issubset(set(quality["missing_fields"])),
             "unverified research must remain explicitly stale and incomplete")
    payload = evidence.get("payload")
    _require(isinstance(payload, dict)
             and payload.get("kind") == "quarantined_qlib_csv_staging"
             and payload.get("authority") == "NONE"
             and payload.get("export_sha256") == exported_hash
             and type(payload.get("rows")) is int and payload["rows"] == count
             and payload.get("bar_seconds") == manifest["bar_seconds"],
             "evidence payload mismatch")

    observed = _utc(evidence.get("observed_at"))
    available = _utc(evidence.get("available_at"))
    _require(observed == _utc(manifest["last_utc"]) and available >= observed,
             "evidence availability/observation mismatch")
    identity = hashlib.sha256((
        f"{expected_producer_repository}|{expected_producer_revision}|"
        f"{source_hash}|{exported_hash}|{available.isoformat()}"
    ).encode("utf-8")).hexdigest()
    _require(handoff.get("handoff_id") == identity
             and evidence.get("evidence_id") == identity
             and handoff.get("evidence_ids") == [identity],
             "handoff identity mismatch")

    return {
        "schema_version": "icarus-consumer-verification-v1",
        "handoff_id": identity,
        "producer_repository": expected_producer_repository,
        "producer_revision": expected_producer_revision,
        "rows_rechecked": count,
        "artifact_hashes_rechecked": True,
        "timestamps_and_ohlcv_rechecked": True,
        "candidate_structurally_valid": True,
        "provider_authenticity_verified": False,
        "entitlement_verified": False,
        "roll_calendar_verified": False,
        "approved_for_training": False,
        "approved_for_execution": False,
        "authority_granted": "NONE",
        "status": "QUARANTINED_REQUIRES_INDEPENDENT_PROVENANCE",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", required=True, type=Path)
    parser.add_argument("--producer-repository", required=True)
    parser.add_argument("--producer-revision", required=True)
    args = parser.parse_args(argv)
    try:
        receipt = verify_candidate(
            args.staging,
            expected_producer_repository=args.producer_repository,
            expected_producer_revision=args.producer_revision,
        )
    except (VerificationRejected, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
