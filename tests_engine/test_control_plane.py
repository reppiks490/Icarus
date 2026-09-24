from __future__ import annotations

import copy
import math
from pathlib import Path

import pytest

from icarus_control.canonical import (
    CanonicalizationError,
    canonical_json,
    load_json,
    loads_strict,
    receipt_digest,
    sha256_digest,
)
from icarus_control.validation import validate_cycle, validate_receipt


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "docs/icarus-control-plane/contracts/icarus-control-v1.json"
SCHEMA_PATH = ROOT / "docs/icarus-control-plane/contracts/icarus-pipeline-v1.json"


@pytest.fixture()
def contracts():
    return load_json(POLICY_PATH), load_json(SCHEMA_PATH)


def _payload(stage: str):
    if stage == "S4":
        return {
            "test_oracle_origin": "independent property + mutation harness",
            "test_oracle_derived_from": [],
            "oracle_independence_status": "INDEPENDENT",
            "golden_vector_provenance": "NONE_REQUIRED_FOR_THIS_STRUCTURAL_TEST",
            "negative_controls": ["missing predecessor", "mixed policy", "tamper"],
            "mutation_or_fault_injection_plan": ["flip prior_stage_digest"],
        }
    if stage == "S5":
        return {
            "verification_oracle_status": "INDEPENDENT",
            "promotion_path_valid": True,
            "release_status": "STRUCTURAL_TEST_ONLY",
            "cycle_outcome": "STRUCTURAL_TEST_ONLY",
        }
    return {}


def _receipt(
    stage: str,
    policy,
    schema,
    *,
    prior=None,
    cycle="20260924-16",
    epoch="20260924-16",
    baseline="0123456789abcdef0123456789abcdef01234567",
    independence=None,
):
    independence = independence or ("PRIMARY" if stage == "S1" else "DERIVED")
    receipt = {
        "handoff_schema_version": "icarus-pipeline-v1",
        "pipeline_policy_version": "icarus-control-v1",
        "pipeline_policy_epoch": epoch,
        "cycle_id": cycle,
        "execution_instance_id": f"{cycle}-{stage}",
        "stage": stage,
        "producer": {"id": f"test-{stage}", "kind": "pytest"},
        "repo_baseline_revision": baseline,
        "repo_snapshot_set": [
            {"repo": "reppiks490/Icarus", "revision": baseline},
            {"repo": "example/evidence", "revision": "feedface"},
        ],
        "policy_contract_digest": sha256_digest(policy),
        "handoff_schema_digest": sha256_digest(schema),
        "prior_stage_digest": prior,
        "claims": [],
        "dependencies": [],
        "conflicts": [],
        "evidence_lineage": [
            {
                "evidence_id": f"E-{stage}",
                "origin": {"kind": "repo", "subject": "Icarus@baseline"},
                "independence": independence,
                "derived_from": [] if stage == "S1" else ["E-S1"],
            }
        ],
        "stage_payload": _payload(stage),
        "execution_authorized": False,
    }
    receipt["receipt_digest"] = receipt_digest(receipt)
    return receipt


def _chain(policy, schema):
    receipts = {}
    prior = None
    for stage in ("S1", "S2", "S3", "S4", "S5"):
        receipt = _receipt(stage, policy, schema, prior=prior)
        receipts[stage] = receipt
        prior = receipt["receipt_digest"]
    return receipts


def _redigest(receipt):
    receipt["receipt_digest"] = receipt_digest(receipt)


def test_canonical_json_is_deterministic_and_preserves_array_order():
    left = {"b": 2, "a": {"z": 3, "y": [2, 1]}}
    right = {"a": {"y": [2, 1], "z": 3}, "b": 2}
    assert canonical_json(left) == canonical_json(right)
    assert canonical_json({"x": [1, 2]}) != canonical_json({"x": [2, 1]})


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_nonfinite_numbers_are_rejected(bad):
    with pytest.raises(CanonicalizationError):
        canonical_json({"x": bad})


def test_duplicate_json_keys_are_rejected():
    with pytest.raises(CanonicalizationError):
        loads_strict('{"x":1,"x":2}')


def test_receipt_digest_excludes_only_the_digest_field():
    receipt = {"a": 1, "receipt_digest": "sha256:old"}
    first = receipt_digest(receipt)
    receipt["receipt_digest"] = "sha256:anything"
    assert receipt_digest(receipt) == first
    receipt["a"] = 2
    assert receipt_digest(receipt) != first


def test_valid_s1_to_s5_chain_is_structurally_eligible(contracts):
    policy, schema = contracts
    result = validate_cycle(_chain(policy, schema), policy, schema)
    assert result["status"] == "VALID"
    assert result["policy_chain_status"] == "CONSISTENT"
    assert result["snapshot_chain_status"] == "CONSISTENT"
    assert result["handoff_chain_status"] == "CONSISTENT"
    assert result["evidence_lineage_status"] == "VALID"
    assert result["independent_evidence_origin_count"] == 1
    assert result["promotion_path_valid"] is True
    assert result["execution_authorized"] is False


def test_missing_required_stage_fails_closed_and_marks_policy_chain_mixed(contracts):
    policy, schema = contracts
    receipts = _chain(policy, schema)
    del receipts["S3"]
    result = validate_cycle(receipts, policy, schema)
    assert result["status"] != "VALID"
    assert result["policy_chain_status"] == "MIXED_POLICY"
    assert result["promotion_path_valid"] is False
    assert "S3" in result["missing_stages"]


def test_different_policy_epoch_is_mixed_policy(contracts):
    policy, schema = contracts
    receipts = _chain(policy, schema)
    receipts["S3"]["pipeline_policy_epoch"] = "20260924-17"
    _redigest(receipts["S3"])
    # Repair later digest links so the policy check is isolated.
    receipts["S4"]["prior_stage_digest"] = receipts["S3"]["receipt_digest"]
    _redigest(receipts["S4"])
    receipts["S5"]["prior_stage_digest"] = receipts["S4"]["receipt_digest"]
    _redigest(receipts["S5"])
    result = validate_cycle(receipts, policy, schema)
    assert result["policy_chain_status"] == "MIXED_POLICY"
    assert result["promotion_path_valid"] is False


def test_mixed_baseline_revision_is_detected_even_with_valid_digests(contracts):
    policy, schema = contracts
    receipts = _chain(policy, schema)
    receipts["S4"]["repo_baseline_revision"] = "b" * 40
    receipts["S4"]["repo_snapshot_set"][0]["revision"] = "b" * 40
    _redigest(receipts["S4"])
    receipts["S5"]["prior_stage_digest"] = receipts["S4"]["receipt_digest"]
    _redigest(receipts["S5"])
    result = validate_cycle(receipts, policy, schema)
    assert result["snapshot_chain_status"] == "MIXED_REVISION"
    assert result["promotion_path_valid"] is False


def test_broken_predecessor_digest_invalidates_handoff_chain(contracts):
    policy, schema = contracts
    receipts = _chain(policy, schema)
    receipts["S3"]["prior_stage_digest"] = "sha256:" + "0" * 64
    _redigest(receipts["S3"])
    result = validate_cycle(receipts, policy, schema)
    assert result["handoff_chain_status"] == "INVALID"
    assert result["status"] == "INVALID"
    assert result["promotion_path_valid"] is False


def test_post_creation_tamper_breaks_receipt_digest(contracts):
    policy, schema = contracts
    receipt = _receipt("S1", policy, schema)
    assert validate_receipt(receipt, policy, schema)["status"] == "VALID"
    receipt["repo_baseline_revision"] = "tampered"
    result = validate_receipt(receipt, policy, schema)
    assert result["status"] == "INVALID"
    assert "receipt_digest mismatch" in result["errors"]


def test_execution_authority_cannot_be_enabled(contracts):
    policy, schema = contracts
    receipt = _receipt("S1", policy, schema)
    receipt["execution_authorized"] = True
    _redigest(receipt)
    result = validate_receipt(receipt, policy, schema)
    assert result["status"] == "INVALID"
    assert result["authority_violations"]


def test_s4_oracle_provenance_is_mandatory(contracts):
    policy, schema = contracts
    receipt = _receipt("S4", policy, schema, prior="sha256:" + "1" * 64)
    del receipt["stage_payload"]["test_oracle_origin"]
    _redigest(receipt)
    result = validate_receipt(receipt, policy, schema)
    assert result["status"] == "INVALID"
    assert any("test_oracle_origin" in error for error in result["errors"])


def test_partially_independent_oracle_blocks_full_structural_promotion(contracts):
    policy, schema = contracts
    receipts = _chain(policy, schema)
    receipts["S4"]["stage_payload"]["oracle_independence_status"] = "PARTIALLY_INDEPENDENT"
    _redigest(receipts["S4"])
    receipts["S5"]["prior_stage_digest"] = receipts["S4"]["receipt_digest"]
    _redigest(receipts["S5"])
    result = validate_cycle(receipts, policy, schema)
    assert result["status"] == "VALID"
    assert result["promotion_path_valid"] is False


def test_stage_cannot_claim_maturity_above_its_ceiling(contracts):
    policy, schema = contracts
    receipt = _receipt("S1", policy, schema)
    receipt["claims"] = [
        {
            "claim_id": "C-1",
            "maturity": "VERIFIED_FOR_INTEGRATION",
            "dependencies": [],
            "evidence_ids": ["E-S1"],
        }
    ]
    _redigest(receipt)
    result = validate_receipt(receipt, policy, schema)
    assert result["status"] == "INVALID"
    assert result["authority_violations"]


def test_duplicate_independent_origin_is_not_counted_as_corroboration(contracts):
    policy, schema = contracts
    receipts = _chain(policy, schema)
    receipts["S2"]["evidence_lineage"][0]["independence"] = "INDEPENDENT_REPLICATION"
    _redigest(receipts["S2"])
    receipts["S3"]["prior_stage_digest"] = receipts["S2"]["receipt_digest"]
    _redigest(receipts["S3"])
    receipts["S4"]["prior_stage_digest"] = receipts["S3"]["receipt_digest"]
    _redigest(receipts["S4"])
    receipts["S5"]["prior_stage_digest"] = receipts["S4"]["receipt_digest"]
    _redigest(receipts["S5"])
    result = validate_cycle(receipts, policy, schema)
    assert result["evidence_lineage_status"] == "DUPLICATE_INFLATED"
    assert result["independent_evidence_origin_count"] == 1
    assert result["promotion_path_valid"] is False


def test_unknown_oracle_enum_fails_closed(contracts):
    policy, schema = contracts
    receipt = _receipt("S4", policy, schema, prior="sha256:" + "1" * 64)
    receipt["stage_payload"]["oracle_independence_status"] = "FUTURE_MAGIC"
    _redigest(receipt)
    result = validate_receipt(receipt, policy, schema)
    assert result["status"] == "INVALID"
    assert any("unknown S4 oracle" in error for error in result["errors"])
