"""Read-only CLI for ICARUS control-plane receipt verification."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .canonical import CanonicalizationError, load_json, receipt_digest, sha256_digest
from .validation import validate_cycle, validate_receipt


DEFAULT_POLICY = Path("docs/icarus-control-plane/contracts/icarus-control-v1.json")
DEFAULT_SCHEMA = Path("docs/icarus-control-plane/contracts/icarus-pipeline-v1.json")


def _load_object(path: Path, label: str) -> dict[str, Any]:
    value = load_json(path)
    if not isinstance(value, dict):
        raise CanonicalizationError(f"{label} must be a JSON object: {path}")
    return value


def _contracts(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    return _load_object(Path(args.policy), "policy"), _load_object(Path(args.schema), "schema")


def _print(value: Any) -> None:
    print(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False))


def cmd_digest(args: argparse.Namespace) -> int:
    value = load_json(Path(args.file))
    if isinstance(value, dict) and args.receipt:
        print(receipt_digest(value))
    else:
        print(sha256_digest(value))
    return 0


def cmd_validate_receipt(args: argparse.Namespace) -> int:
    receipt = _load_object(Path(args.file), "receipt")
    policy, schema = _contracts(args)
    result = validate_receipt(receipt, policy, schema)
    _print(result)
    return 0 if result["status"] == "VALID" else 1


def _load_cycle(directory: Path) -> dict[str, dict[str, Any]]:
    receipts: dict[str, dict[str, Any]] = {}
    for stage in ("S1", "S2", "S3", "S4", "S5"):
        path = directory / f"{stage}.json"
        if not path.exists():
            continue
        receipts[stage] = _load_object(path, f"{stage} receipt")
    return receipts


def cmd_validate_cycle(args: argparse.Namespace) -> int:
    policy, schema = _contracts(args)
    receipts = _load_cycle(Path(args.directory))
    result = validate_cycle(receipts, policy, schema)
    _print(result)
    return 0 if result["status"] == "VALID" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="icarus-control",
        description=(
            "Read-only verifier for ICARUS S1-S5 handoff receipts. "
            "Never authorizes execution or trading."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    digest = sub.add_parser("digest", help="canonical SHA-256 of a JSON document")
    digest.add_argument("file")
    digest.add_argument(
        "--receipt",
        action="store_true",
        help="exclude only receipt_digest before hashing",
    )
    digest.set_defaults(fn=cmd_digest)

    receipt = sub.add_parser("validate-receipt", help="validate one handoff receipt")
    receipt.add_argument("file")
    receipt.add_argument("--policy", default=str(DEFAULT_POLICY))
    receipt.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    receipt.set_defaults(fn=cmd_validate_receipt)

    cycle = sub.add_parser("validate-cycle", help="validate S1.json through S5.json")
    cycle.add_argument("directory")
    cycle.add_argument("--policy", default=str(DEFAULT_POLICY))
    cycle.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    cycle.set_defaults(fn=cmd_validate_cycle)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.fn(args) or 0)
    except (OSError, CanonicalizationError, ValueError) as exc:
        print(f"icarus-control: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
