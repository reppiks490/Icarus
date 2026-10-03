from __future__ import annotations

import json

import pytest

from icarus_engine.federation_acceptance import (
    ACCEPTANCE_SCHEMA,
    build_acceptance,
    persist_acceptance,
)


def _receipt(**overrides):
    payload = {
        "schema_version": "icarus-live-bilateral-federation-receipt-v1",
        "icarus_commit": "a" * 40,
        "icarus_engine_commit": "b" * 40,
        "peer_event_file_count": 10,
        "ingested_total": 10,
        "rejected_total": 0,
        "federation_schema": "icarus-engine-brain-federation-v1",
        "peer_packet_status": "green",
        "peer_packet_id": "c" * 64,
        "peer_packet_blob_sha": "d" * 40,
        "peer_source_commit": "e" * 40,
        "peer_source_commit_verified": True,
        "peer_source_commit_relation": "AHEAD",
        "peer_packet_fresh": True,
        "peer_packet_age_seconds": 22.0,
        "peer_lane_count": 5,
        "peer_substantive_lane_count": 2,
        "peer_durability_only_lane_count": 2,
        "peer_lane_witness_verified_count": 4,
        "peer_lane_witness_unavailable_count": 0,
        "peer_lane_contract_binding_verified_count": 5,
        "peer_lane_source_witnesses_required": True,
        "peer_source_contract_witness_status": "green",
        "peer_source_contract_witness_count": 3,
        "peer_source_contract_blob_witnesses_required": True,
        "strict_event_contract": True,
        "event_records": "RESEARCH_OBSERVABILITY_ONLY",
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
    payload.update(overrides)
    return payload


def test_acceptance_is_research_only_and_provenance_bound():
    acceptance = build_acceptance(_receipt())
    assert acceptance["schema_version"] == ACCEPTANCE_SCHEMA
    assert acceptance["peer_packet_id"] == "c" * 64
    assert acceptance["peer_packet_blob_sha"] == "d" * 40
    assert acceptance["peer_source_commit"] == "e" * 40
    assert acceptance["peer_source_contract_witness_count"] == 3
    assert acceptance["peer_lane_contract_binding_verified_count"] == 5
    assert acceptance["authority"] == "RESEARCH"
    assert acceptance["execution_authorized"] is False
    assert acceptance["production_decision_authorized"] is False
    assert acceptance["automatic_model_promotion"] is False


def test_same_peer_packet_is_idempotent_even_if_validator_head_advances(tmp_path):
    output = tmp_path / "acceptance.json"
    assert persist_acceptance(_receipt(), output) is True
    original = json.loads(output.read_text(encoding="utf-8"))

    assert persist_acceptance(_receipt(icarus_commit="f" * 40), output) is False
    again = json.loads(output.read_text(encoding="utf-8"))
    assert again == original
    assert again["accepted_by_icarus_commit"] == "a" * 40


def test_new_peer_packet_replaces_acceptance(tmp_path):
    output = tmp_path / "acceptance.json"
    assert persist_acceptance(_receipt(), output) is True
    next_receipt = _receipt(
        peer_packet_id="1" * 64,
        peer_packet_blob_sha="2" * 40,
        peer_source_commit="3" * 40,
    )
    assert persist_acceptance(next_receipt, output) is True
    acceptance = json.loads(output.read_text(encoding="utf-8"))
    assert acceptance["peer_packet_id"] == "1" * 64
    assert acceptance["peer_source_commit"] == "3" * 40


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"peer_packet_fresh": False}, "peer packet is stale"),
        ({"peer_source_contract_witness_status": "degraded"}, "source-contract witnesses"),
        ({"peer_lane_contract_binding_verified_count": 4}, "not every peer lane"),
        ({"strict_event_contract": False}, "strict remote event contract"),
        ({"execution_authorized": True}, "execution authority"),
        ({"production_decision_authorized": True}, "production-decision authority"),
    ],
)
def test_invalid_or_escalated_receipt_fails_closed(override, message):
    with pytest.raises(ValueError, match=message):
        build_acceptance(_receipt(**override))
