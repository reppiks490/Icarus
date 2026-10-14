from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import zipfile

import pytest

from icarus_engine.brain_sync import (
    _normalize_historical_context_contract,
    _normalize_historical_document,
    _normalize_peer_packet,
    _validate_historical_source_semantics,
)
from tests_engine.test_brain_sync import _consumer_contract, _peer_packet, _rehash_peer_packet

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "federation_v2"
_FIXTURE_TMP = Path(tempfile.mkdtemp(prefix="icarus-federation-v2-"))
with zipfile.ZipFile(FIXTURE_ROOT / "cases.zip") as archive:
    archive.extractall(_FIXTURE_TMP)
FIXTURES = _FIXTURE_TMP / "cases"


def _case(name):
    root = FIXTURES / name
    contract = json.loads((root / "contract_historical_context.json").read_text())
    block = json.loads((root / "packet_block.json").read_text()) if (root / "packet_block.json").exists() else None
    return root, contract, block


def _consumer(block):
    return _consumer_contract(historical_context=block)


def test_pinned_federation_fixture_bundle_matches_its_manifest():
    manifest = json.loads((FIXTURE_ROOT / "MANIFEST.json").read_text())
    assert manifest["execution_authorized"] is False
    with zipfile.ZipFile(FIXTURE_ROOT / "cases.zip") as archive:
        assert set(archive.namelist()) == set(manifest["files"])
        for path, digest in manifest["files"].items():
            assert hashlib.sha256(archive.read(path)).hexdigest() == digest
    assert hashlib.sha256((FIXTURE_ROOT / "build_fixtures.py").read_bytes()).hexdigest() == manifest["generator_sha256"]


@pytest.mark.parametrize("name", [
    "contract_head_authority", "contract_source_field_changed", "contract_source_set_mismatch",
    "contract_source_widened", "contract_truth_invariant", "contract_witness_weakened",
    "contract_eligibility_removed", "undeclared_modern_contract", "contract_version_bool",
    "contract_version_float", "unsupported_contract_version",
])
def test_contract_fixtures_fail_with_their_frozen_reason(name):
    _, contract, _ = _case(name)
    expected = json.loads((FIXTURES / name / "expected.json").read_text())["expect"]
    with pytest.raises(ValueError, match=expected):
        _normalize_historical_context_contract(_consumer(contract))


@pytest.mark.parametrize("name", [
    "document_authority_expansion", "document_kind_confusion", "document_run_prefixed_key",
    "invalid_source_clock_missing", "invalid_source_clock_naive", "raw_payloads_included",
    "schema_mismatch", "source_not_eligible", "summary_too_large",
])
def test_document_fixtures_fail_closed_with_their_frozen_reason(name):
    _, contract, _ = _case("accept_modern6")
    sources = {row["id"]: row for row in _normalize_historical_context_contract(_consumer(contract))}
    case_root = FIXTURES / name
    expected = json.loads((case_root / "expected.json").read_text())["expect"]
    observed = []
    for source_id in ("provider_collection", "sec_edgar"):
        source = sources[source_id]
        payload_path = case_root / "sources" / source["path"]
        payload = json.loads(payload_path.read_text())
        try:
            _normalize_historical_document(source, payload, blob_sha="a" * 40)
        except ValueError as exc:
            observed.append(str(exc))
    assert any(expected in error for error in observed), observed


def test_exact_six_source_contract_is_accepted():
    _, block, _ = _case("accept_modern6")
    sources = _normalize_historical_context_contract(_consumer(block))
    assert len(sources) == 6
    assert {row["kind"] for row in sources} == {"RUN_LATEST", "RESEARCH_CONTEXT_DOCUMENT"}
    assert {row["id"] for row in sources if row["kind"] == "RESEARCH_CONTEXT_DOCUMENT"} == {
        "provider_collection", "sec_edgar"
    }


def test_undeclared_six_source_contract_does_not_downgrade_to_legacy():
    _, block, _ = _case("undeclared_modern_contract")
    with pytest.raises(ValueError, match="UNDECLARED_MODERN_CONTRACT"):
        _normalize_historical_context_contract(_consumer(block))


@pytest.mark.parametrize("name", ["contract_version_bool", "contract_version_float", "unsupported_contract_version"])
def test_contract_version_requires_exact_json_integer_two(name):
    _, block, _ = _case(name)
    with pytest.raises(ValueError, match="UNSUPPORTED_CONTRACT_VERSION"):
        _normalize_historical_context_contract(_consumer(block))


def test_modern_packet_shape_is_bound_to_all_six_sources():
    root, contract, block = _case("accept_modern6")
    consumer = _consumer(contract)
    packet = _peer_packet()
    packet["source_commit"] = block["source_commit"]
    packet["observed_at"] = block["observed_at"]
    packet["historical_context_version"] = 2
    packet["historical_artifacts"] = block["historical_artifacts"]
    _rehash_peer_packet(packet)
    normalized = _normalize_peer_packet(packet, blob_sha="a" * 40, consumer_contract=consumer)
    assert normalized["historical_packet_witness_count"] == 6
    assert {row["kind"] for row in normalized["historical_packet_witnesses"]} == {
        "RUN_LATEST", "RESEARCH_CONTEXT_DOCUMENT"
    }
    assert not any(row["candidate_evidence_eligible"] for row in normalized["historical_packet_witnesses"])
    assert all(row["execution_authorized"] is False for row in normalized["historical_packet_witnesses"])
    document_witnesses = {
        row["id"]: row for row in normalized["historical_packet_witnesses"]
        if row["kind"] == "RESEARCH_CONTEXT_DOCUMENT"
    }
    for source_id in ("provider_collection", "sec_edgar"):
        witness = document_witnesses[source_id]
        assert witness["schema_key"]
        assert witness["raw_exclusion_field"]
        assert witness["collection_clock_field"]
        source_payload = json.loads((root / "sources" / witness["path"]).read_text())
        _validate_historical_source_semantics(witness, source_payload)
        projection = _normalize_historical_document(
            witness, source_payload, blob_sha="a" * 40
        )
        assert projection["summary"] == witness["packet_summary"]
        assert projection["clocks"] == witness["packet_clocks"]


def test_modern_packet_rejects_unversioned_or_wrong_typed_version():
    _, contract, block = _case("accept_modern6")
    for bad in (None, True, 2.0, "2", 3):
        packet = _peer_packet()
        packet["source_commit"] = block["source_commit"]
        packet["observed_at"] = block["observed_at"]
        packet["historical_artifacts"] = block["historical_artifacts"]
        if bad is not None:
            packet["historical_context_version"] = bad
        _rehash_peer_packet(packet)
        with pytest.raises(ValueError, match="PACKET_VERSION_MISMATCH"):
            _normalize_peer_packet(packet, blob_sha="a" * 40, consumer_contract=_consumer(contract))


def test_research_context_live_projection_contains_digest_not_source_fields():
    root, contract, _ = _case("accept_modern6")
    sources = {row["id"]: row for row in _normalize_historical_context_contract(_consumer(contract))}
    for source_id in ("provider_collection", "sec_edgar"):
        source = sources[source_id]
        raw_path = root / "sources" / source["path"]
        payload = json.loads(raw_path.read_text())
        raw = raw_path.read_bytes()
        blob = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
        row = _normalize_historical_document(source, payload, blob_sha=blob)
        assert row["run_id"] is None and row["run_status"] is None
        assert row["summary"]["fields_sha256"]
        assert row["summary"]["fields_bytes"] > 0
        assert "tickers" not in row["summary"]
        assert row["execution_authorized"] is False


def test_research_context_live_projection_rejects_bad_clock_authority_and_kind_confusion():
    root, contract, _ = _case("accept_modern6")
    sources = {row["id"]: row for row in _normalize_historical_context_contract(_consumer(contract))}
    for source_id, field, value, reason in (
        ("provider_collection", "snapshot_at_utc", "yesterday", "INVALID_SOURCE_CLOCK"),
        ("provider_collection", "execution_authorized", True, "AUTHORITY_EXPANSION"),
        ("provider_collection", "RUN_STATUS", "RUN_PERSISTED", "KIND_CONFUSION"),
        ("sec_edgar", "status", "error", "SOURCE_NOT_ELIGIBLE"),
    ):
        source = sources[source_id]
        payload = json.loads((root / "sources" / source["path"]).read_text())
        payload[field] = value
        with pytest.raises(ValueError, match=reason):
            _normalize_historical_document(source, payload, blob_sha="a" * 40)
