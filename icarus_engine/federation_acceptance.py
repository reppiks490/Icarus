from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping


RECEIPT_SCHEMA = "icarus-live-bilateral-federation-receipt-v1"
ACCEPTANCE_SCHEMA = "icarus-engine-federation-acceptance-v1"
VALIDATION_CONTRACT_VERSION = 1


def _is_hex(value: Any, length: int) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == length and all(ch in "0123456789abcdef" for ch in text)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_receipt(receipt: Mapping[str, Any]) -> None:
    _require(receipt.get("schema_version") == RECEIPT_SCHEMA, "unsupported federation receipt schema")
    _require(receipt.get("peer_packet_status") == "green", "peer packet is not green")
    _require(_is_hex(receipt.get("peer_packet_id"), 64), "peer packet ID is invalid")
    _require(_is_hex(receipt.get("peer_packet_blob_sha"), 40), "peer packet Git blob SHA is invalid")
    _require(_is_hex(receipt.get("peer_source_commit"), 40), "peer source commit is invalid")
    _require(_is_hex(receipt.get("icarus_commit"), 40), "ICARUS validator commit is invalid")
    _require(receipt.get("peer_source_commit_verified") is True, "peer source commit is not verified")
    _require(
        receipt.get("peer_source_commit_relation") in {"AHEAD", "IDENTICAL"},
        "peer source commit relation is not mainline-valid",
    )
    _require(receipt.get("peer_packet_fresh") is True, "peer packet is stale")
    _require(
        receipt.get("peer_source_contract_witness_status") == "green",
        "peer source-contract witnesses are not green",
    )
    _require(
        receipt.get("peer_source_contract_witness_count") == 3,
        "peer source-contract witness count is incomplete",
    )
    _require(
        receipt.get("peer_source_contract_blob_witnesses_required") is True,
        "peer source-contract blob witnesses are not required",
    )
    lane_count = receipt.get("peer_lane_count")
    binding_count = receipt.get("peer_lane_contract_binding_verified_count")
    _require(type(lane_count) is int and lane_count >= 1, "peer lane count is invalid")
    _require(binding_count == lane_count, "not every peer lane is contract-bound")
    _require(
        type(receipt.get("peer_lane_witness_verified_count")) is int
        and receipt.get("peer_lane_witness_verified_count") >= 1,
        "peer lane source witnesses are incomplete",
    )
    _require(
        receipt.get("peer_lane_source_witnesses_required") is True,
        "peer lane source witnesses are not required",
    )
    _require(
        receipt.get("strict_event_contract") is True,
        "strict remote event contract is not verified",
    )
    _require(
        receipt.get("event_records") == "RESEARCH_OBSERVABILITY_ONLY",
        "remote event authority is not research-observability-only",
    )
    _require(receipt.get("execution_authorized") is False, "receipt attempts execution authority")
    _require(
        receipt.get("production_decision_authorized") is False,
        "receipt attempts production-decision authority",
    )


def build_acceptance(receipt: Mapping[str, Any]) -> dict[str, Any]:
    validate_receipt(receipt)
    return {
        "schema_version": ACCEPTANCE_SCHEMA,
        "validation_contract_version": VALIDATION_CONTRACT_VERSION,
        "source_receipt_schema": RECEIPT_SCHEMA,
        "accepted_by_repository": "reppiks490/Icarus",
        "producer_repository": "reppiks490/Icarus-engine",
        "accepted_by_icarus_commit": str(receipt["icarus_commit"]).lower(),
        "peer_packet_id": str(receipt["peer_packet_id"]).lower(),
        "peer_packet_blob_sha": str(receipt["peer_packet_blob_sha"]).lower(),
        "peer_source_commit": str(receipt["peer_source_commit"]).lower(),
        "peer_source_commit_relation": receipt["peer_source_commit_relation"],
        "peer_packet_fresh": True,
        "peer_packet_age_seconds_at_acceptance": receipt.get("peer_packet_age_seconds"),
        "peer_source_contract_witness_count": receipt["peer_source_contract_witness_count"],
        "peer_lane_count": receipt["peer_lane_count"],
        "peer_lane_witness_verified_count": receipt["peer_lane_witness_verified_count"],
        "peer_lane_contract_binding_verified_count": receipt[
            "peer_lane_contract_binding_verified_count"
        ],
        "peer_substantive_lane_count": receipt.get("peer_substantive_lane_count", 0),
        "peer_durability_only_lane_count": receipt.get("peer_durability_only_lane_count", 0),
        "event_records": "RESEARCH_OBSERVABILITY_ONLY",
        "authority": "RESEARCH",
        "execution_authorized": False,
        "production_decision_authorized": False,
        "automatic_model_promotion": False,
        "truth_contract": {
            "foreign_peer_state_is_evidence_not_native_truth": True,
            "durability_only_is_not_substantive_research_evidence": True,
            "acceptance_is_not_execution_authority": True,
            "acceptance_is_not_production_decision_authority": True,
            "same_packet_is_idempotent": True,
        },
    }


def persist_acceptance(receipt: Mapping[str, Any], output: Path) -> bool:
    acceptance = build_acceptance(receipt)
    if output.is_file():
        try:
            existing = json.loads(output.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = None
        if isinstance(existing, Mapping):
            same_identity = (
                existing.get("schema_version") == ACCEPTANCE_SCHEMA
                and existing.get("validation_contract_version") == VALIDATION_CONTRACT_VERSION
                and existing.get("peer_packet_id") == acceptance["peer_packet_id"]
                and existing.get("peer_packet_blob_sha") == acceptance["peer_packet_blob_sha"]
                and existing.get("peer_source_commit") == acceptance["peer_source_commit"]
            )
            if same_identity:
                return False

    output.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(acceptance, sort_keys=True, indent=2, allow_nan=False) + "\n"
    with NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=output.parent,
        prefix=".federation-acceptance-",
        delete=False,
    ) as handle:
        temp = Path(handle.name)
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, output)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and persist a research-only Icarus-engine federation acceptance."
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    receipt = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(receipt, Mapping):
        raise ValueError("federation receipt must be a JSON object")
    changed = persist_acceptance(receipt, Path(args.output))
    print(
        json.dumps(
            {
                "changed": changed,
                "output": args.output,
                "peer_packet_id": receipt.get("peer_packet_id"),
                "execution_authorized": False,
                "production_decision_authorized": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
