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
            if reader.fieldnames is None or set(reader.fieldnames) != set(FIELDS):
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
    args = parser.parse_args(argv)
    if args.command == "probe":
        print(json.dumps(installed_distributions(), sort_keys=True, indent=2))
        return 0
    try:
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
