"""Fail-closed, research-only staging boundary for external quantitative tools.

This module NEVER imports or executes trading frameworks, connects to a provider,
trains a model, changes strategy state, or communicates with a broker.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
from importlib import metadata
import json
from pathlib import Path
import re
import shutil
import tempfile


DISTRIBUTIONS = {
    "qlib": ("pyqlib",),
    "rd_agent": ("rdagent", "rd-agent"),
    "hftbacktest": ("hftbacktest",),
    "nautilus_trader": ("nautilus_trader",),
    "duckdb": ("duckdb",),
    "polars": ("polars",),
    "pyarrow": ("pyarrow",),
}
FIELDS = ("timestamp", "contract_id", "open", "high", "low", "close", "volume")
OUTPUT_FIELDS = ("instrument", "datetime", "open", "high", "low", "close", "volume")
IDENTITY = re.compile(r"[A-Za-z0-9_.!:-]{1,64}\Z")


class ResearchAdmissionError(ValueError):
    """Research data refused without changing any ICARUS state."""


def installed_distributions() -> dict[str, dict[str, object]]:
    """Inspect installed package metadata only; this does not test functionality."""
    found: dict[str, dict[str, object]] = {}
    for name, candidates in DISTRIBUTIONS.items():
        version = None
        distribution = None
        for candidate in candidates:
            try:
                version = metadata.version(candidate)
                distribution = candidate
                break
            except metadata.PackageNotFoundError:
                continue
        found[name] = {
            "distribution": distribution,
            "version": version,
            "metadata_present": version is not None,
            "runtime_verified": False,
            "icarus_integrated": False,
        }
    return found


def _number(raw: str, name: str, line: int) -> Decimal:
    try:
        value = Decimal(raw)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ResearchAdmissionError(f"row {line}: invalid {name}") from exc
    if not value.is_finite():
        raise ResearchAdmissionError(f"row {line}: nonfinite {name}")
    return value


def _timestamp(raw: str, line: int) -> datetime:
    try:
        value = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise ResearchAdmissionError(f"row {line}: invalid ISO timestamp") from exc
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ResearchAdmissionError(f"row {line}: timestamp must explicitly be UTC")
    return value.astimezone(timezone.utc)


def _valid_id(raw: str, label: str) -> str:
    if not isinstance(raw, str) or IDENTITY.fullmatch(raw) is None:
        raise ResearchAdmissionError(f"invalid {label}; use a specific stable identifier")
    return raw


def export_qlib_staging(
    source: Path,
    output_dir: Path,
    *,
    instrument: str,
    contract_id: str,
    bar_seconds: int,
    source_id: str,
    price_basis: str,
) -> dict[str, object]:
    """Stream genuine *declared* raw bars to a research-only Qlib CSV staging file.

    This enforces internal consistency, not the external authenticity of a
    caller-provided file. The caller must separately prove feed entitlements,
    vendor provenance, and the contract calendar before scientific promotion.
    """
    instrument = _valid_id(instrument, "instrument")
    contract_id = _valid_id(contract_id, "contract_id")
    source_id = _valid_id(source_id, "source_id")
    if price_basis != "raw":
        raise ResearchAdmissionError("Heikin-Ashi/synthetic prices cannot be admitted")
    if type(bar_seconds) is not int or not 1 <= bar_seconds <= 86400:
        raise ResearchAdmissionError("bar_seconds must be 1..86400")
    original_source = Path(source)
    if original_source.is_symlink():
        raise ResearchAdmissionError("input must not be a symlink")
    source = original_source.resolve(strict=True)
    output_dir = Path(output_dir).resolve()
    if not source.is_file() or source.is_symlink():
        raise ResearchAdmissionError("input must be a regular non-symlinked file")
    if output_dir.exists():
        raise ResearchAdmissionError("output directory already exists; refusing overwrite")
    if not output_dir.parent.is_dir():
        raise ResearchAdmissionError("output parent must already exist")
    if source.parent == output_dir or source == output_dir:
        raise ResearchAdmissionError("cannot write over input")

    scratch = Path(tempfile.mkdtemp(prefix=".icarus-external-", dir=output_dir.parent))
    first = None
    previous = None
    rows = 0
    input_digest = hashlib.sha256()
    try:
        with source.open("rb") as binary, (scratch / "qlib-bars.csv").open(
            "w", encoding="utf-8", newline=""
        ) as destination:
            # The raw-byte wrapper preserves exactly the bytes included in the
            # source checksum. utf-8-sig accepts a BOM only on the header line.
            def decoded():
                for index, data in enumerate(binary):
                    input_digest.update(data)
                    try:
                        yield data.decode("utf-8-sig" if index == 0 else "utf-8")
                    except UnicodeDecodeError as exc:
                        raise ResearchAdmissionError("input must be UTF-8 CSV") from exc

            reader = csv.DictReader(decoded(), strict=True)
            if reader.fieldnames != list(FIELDS):
                raise ResearchAdmissionError(
                    "required exact CSV columns: " + ",".join(FIELDS)
                )
            writer = csv.DictWriter(
                destination, fieldnames=OUTPUT_FIELDS, lineterminator="\n"
            )
            writer.writeheader()
            try:
                for line, record in enumerate(reader, 2):
                    if None in record or any(v is None for v in record.values()):
                        raise ResearchAdmissionError(f"row {line}: malformed CSV record")
                    if record["contract_id"] != contract_id:
                        raise ResearchAdmissionError(
                            f"row {line}: mixed or mismatched actual contract"
                        )
                    instant = _timestamp(record["timestamp"], line)
                    if previous is not None:
                        delta = (instant - previous).total_seconds()
                        if delta < bar_seconds or delta % bar_seconds != 0:
                            raise ResearchAdmissionError(
                                f"row {line}: nonmonotonic/overlapping bar times"
                            )
                    values = {
                        key: _number(record[key], key, line)
                        for key in ("open", "high", "low", "close", "volume")
                    }
                    if (
                        values["high"] < max(values["open"], values["close"])
                        or values["low"] > min(values["open"], values["close"])
                        or values["low"] > values["high"]
                        or values["volume"] < 0
                    ):
                        raise ResearchAdmissionError(f"row {line}: invalid OHLCV")
                    writer.writerow(
                        {
                            "instrument": instrument,
                            "datetime": instant.isoformat().replace("+00:00", "Z"),
                            **{key: format(value, "f") for key, value in values.items()},
                        }
                    )
                    first = first or instant
                    previous = instant
                    rows += 1
            except csv.Error as exc:
                raise ResearchAdmissionError("invalid CSV quoting") from exc
        if rows == 0:
            raise ResearchAdmissionError("empty input is not research evidence")
        export_digest = hashlib.sha256()
        with (scratch / "qlib-bars.csv").open("rb") as staged:
            for block in iter(lambda: staged.read(1024 * 1024), b""):
                export_digest.update(block)
        manifest: dict[str, object] = {
            "schema_version": "icarus-external-research-v1",
            "target": "qlib_csv_staging",
            "instrument": instrument,
            "actual_contract_id": contract_id,
            "bar_seconds": bar_seconds,
            "price_basis": "raw_operator_attested",
            "source_id": source_id,
            "source_sha256": input_digest.hexdigest(),
            "export_sha256": export_digest.hexdigest(),
            "first_utc": first.isoformat(),
            "last_utc": previous.isoformat(),
            "rows": rows,
            "source_authenticity_verified": False,
            "entitlement_verified": False,
            "roll_mapping_verified": False,
            "training_approved": False,
            "execution_authorized": False,
            "note": "CSV staging only. NOT a Qlib binary dataset, model, backtest, "
                    "fill proof, or permission to ingest into ICARUS decisions.",
        }
        (scratch / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if output_dir.exists():
            raise ResearchAdmissionError("output directory appeared during export")
        scratch.rename(output_dir)
        return manifest
    finally:
        if scratch.exists():
            shutil.rmtree(scratch)



def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for block in iter(lambda: src.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def emit_quarantined_handoff(
    staging_dir: Path,
    *,
    producer_repository: str,
    producer_revision: str,
    available_at: str,
) -> dict[str, object]:
    """Generate canonical evidence + handoff only; NEVER promote to Brain state.

    Caller-provided availability and provenance are recorded but remain
    UNVERIFIED. This is a quarantine package for an independent validator.
    """
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", producer_repository):
        raise ResearchAdmissionError("invalid producer repository")
    if not re.fullmatch(r"[0-9a-f]{40}", producer_revision):
        raise ResearchAdmissionError("producer revision must be full lowercase SHA-1")
    available = _timestamp(available_at, 1)
    folder = Path(staging_dir)
    manifest_path, csv_path = folder / "manifest.json", folder / "qlib-bars.csv"
    if any(p.is_symlink() or not p.is_file() for p in (manifest_path, csv_path)):
        raise ResearchAdmissionError("staging inputs must be regular non-symlink files")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise ResearchAdmissionError("invalid staging manifest") from exc
    if not isinstance(manifest, dict) or (
        manifest.get("schema_version") != "icarus-external-research-v1"
        or manifest.get("target") != "qlib_csv_staging"
        or manifest.get("price_basis") != "raw_operator_attested"
    ):
        raise ResearchAdmissionError("unrecognized staging format or price basis")
    for denied in ("source_authenticity_verified", "entitlement_verified",
                   "roll_mapping_verified", "training_approved",
                   "execution_authorized"):
        if manifest.get(denied) is not False:
            raise ResearchAdmissionError("unexpected/raised research authority")
    if type(manifest.get("rows")) is not int or manifest["rows"] <= 0:
        raise ResearchAdmissionError("invalid staged row count")
    source_hash = manifest.get("source_sha256", "")
    output_hash = manifest.get("export_sha256", "")
    if (
        not isinstance(source_hash, str)
        or not re.fullmatch(r"[0-9a-f]{64}", source_hash)
        or not isinstance(output_hash, str)
        or not re.fullmatch(r"[0-9a-f]{64}", output_hash)
        or _file_hash(csv_path) != output_hash
    ):
        raise ResearchAdmissionError("staged data checksum mismatch")
    first = _timestamp(manifest.get("first_utc", ""), 1)
    seen = _timestamp(manifest.get("last_utc", ""), 1)
    if first > seen:
        raise ResearchAdmissionError("invalid staged time interval")
    bar_seconds = manifest.get("bar_seconds")
    if type(bar_seconds) is not int or not 1 <= bar_seconds <= 86400:
        raise ResearchAdmissionError("invalid staged bar interval")
    source_id = _valid_id(manifest.get("source_id"), "source_id")
    if available < seen:
        raise ResearchAdmissionError("source cannot be available before final bar")
    instrument = _valid_id(manifest.get("instrument"), "instrument")
    contract_id = _valid_id(manifest.get("actual_contract_id"), "contract_id")
    identity = hashlib.sha256(
        f"{producer_repository}|{producer_revision}|{source_hash}|{output_hash}|"
        f"{available.isoformat()}".encode("utf-8")
    ).hexdigest()
    evidence = {
        "schema_version": "1.0.0",
        "evidence_id": identity,
        "source_id": source_id,
        "source_revision": producer_revision,
        "instrument_id": instrument,
        "contract_id": contract_id,
        "session_id": None,
        "timezone": "UTC",
        "observed_at": seen.isoformat(),
        "available_at": available.isoformat(),
        "decision_context_at": None,
        "raw_artifact_hash": source_hash,
        "transform_id": "icarus-external-qlib-staging-v1",
        "transform_revision": producer_revision,
        "quality": {
            "stale": True,
            "conflicted": False,
            "missing_fields": [
                "vendor_authenticity_receipt", "entitlement_confirmation",
                "roll_calendar_validation", "training_holdout_validation",
            ],
            "confidence": None,
        },
        "payload": {
            "kind": "quarantined_qlib_csv_staging",
            "export_sha256": output_hash,
            "rows": manifest["rows"],
            "bar_seconds": bar_seconds,
            "authority": "NONE",
        },
    }
    scratch = Path(tempfile.mkdtemp(prefix=".icarus-handoff-", dir=folder))
    destination = folder / "candidate_handoff"
    try:
        if destination.exists():
            raise ResearchAdmissionError("candidate handoff already exists")
        evidence_path = scratch / "evidence_record.json"
        evidence_path.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n")
        handoff = {
            "schema_version": "1.0.0",
            "handoff_id": identity,
            "producer": "external_quant_fabric",
            "producer_repository": producer_repository,
            "producer_revision": producer_revision,
            "target_repository": "reppiks490/Icarus",
            "target_revision": None,
            "created_at": None,
            "expires_at": None,
            "artifacts": [
                {"path": "qlib-bars.csv", "hash": output_hash,
                 "media_type": "text/csv"},
                {"path": "manifest.json", "hash": _file_hash(manifest_path),
                 "media_type": "application/json"},
                {"path": "candidate_handoff/evidence_record.json",
                 "hash": _file_hash(evidence_path),
                 "media_type": "application/json"},
            ],
            "evidence_ids": [identity],
            "claims": ["Structurally validated Qlib CSV staging; no empirical market-edge claim"],
            "assumptions": ["Source authenticity and availability are caller-attested only"],
            "tests": [],
            "authority_requested": "RESEARCH",
            "authority_granted": "NONE",
            "limitations": [
                "Quarantined, stale by default; cannot enter Brain or trading state",
                "Vendor entitlements, contracts and fill assumptions unverified",
            ],
        }
        (scratch / "handoff.json").write_text(
            json.dumps(handoff, sort_keys=True, indent=2) + "\n"
        )
        scratch.rename(destination)
        return handoff
    finally:
        if scratch.exists():
            shutil.rmtree(scratch)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("probe", help="metadata-only local dependency discovery")
    export = commands.add_parser("export-qlib", help="validate/stream raw bars into staging")
    export.add_argument("--input", required=True, type=Path)
    export.add_argument("--output", required=True, type=Path)
    export.add_argument("--instrument", required=True)
    export.add_argument("--contract-id", required=True)
    export.add_argument("--source-id", required=True)
    export.add_argument("--bar-seconds", required=True, type=int)
    export.add_argument("--price-basis", required=True, choices=["raw"])
    handoff = commands.add_parser(
        "emit-handoff", help="make a quarantined canonical schema candidate"
    )
    handoff.add_argument("--staging", required=True, type=Path)
    handoff.add_argument("--producer-repository", required=True)
    handoff.add_argument("--producer-revision", required=True)
    handoff.add_argument("--available-at", required=True)
    args = parser.parse_args(argv)
    if args.command == "probe":
        print(json.dumps(installed_distributions(), sort_keys=True, indent=2))
        return 0
    try:
        if args.command == "emit-handoff":
            result = emit_quarantined_handoff(
                args.staging, producer_repository=args.producer_repository,
                producer_revision=args.producer_revision,
                available_at=args.available_at,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        report = export_qlib_staging(
            args.input, args.output, instrument=args.instrument,
            contract_id=args.contract_id, source_id=args.source_id,
            bar_seconds=args.bar_seconds, price_basis=args.price_basis,
        )
    except (ResearchAdmissionError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
