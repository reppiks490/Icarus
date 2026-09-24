"""Fail-closed validation for ICARUS pipeline receipts and S1->S5 chains."""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from .canonical import canonical_json, receipt_digest, sha256_digest

PIPELINE_POLICY_VERSION = "icarus-control-v1"
HANDOFF_SCHEMA_VERSION = "icarus-pipeline-v1"
STAGES = ("S1", "S2", "S3", "S4", "S5")

DEFAULT_MATURITY_ORDER = (
    "OBSERVED",
    "SPECIFIED",
    "EMPIRICALLY_SUPPORTED",
    "IMPLEMENTATION_READY",
    "VERIFIED_FOR_INTEGRATION",
)

DEFAULT_STAGE_CEILINGS = {
    "S1": "OBSERVED",
    "S2": "SPECIFIED",
    "S3": "EMPIRICALLY_SUPPORTED",
    "S4": "IMPLEMENTATION_READY",
    "S5": "VERIFIED_FOR_INTEGRATION",
}

DEFAULT_EVIDENCE_INDEPENDENCE = {
    "PRIMARY",
    "INDEPENDENT_REPLICATION",
    "DERIVED",
    "DUPLICATE",
    "UNKNOWN",
}

DEFAULT_ORACLE_STATUSES = {
    "INDEPENDENT",
    "PARTIALLY_INDEPENDENT",
    "TAUTOLOGICAL",
    "UNVERIFIED",
    "INVALID",
}


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _append_missing(errors: list[str], obj: Mapping[str, Any], fields: list[str], prefix: str = "") -> None:
    for field in fields:
        if field not in obj:
            errors.append(f"{prefix}missing required field: {field}")


def _contract_view(policy: Mapping[str, Any], schema: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "policy_digest": sha256_digest(policy),
        "schema_digest": sha256_digest(schema),
        "stage_order": tuple(policy.get("stage_order") or STAGES),
        "maturity_order": tuple(policy.get("maturity_order") or DEFAULT_MATURITY_ORDER),
        "stage_ceilings": dict(policy.get("stage_maturity_ceiling") or DEFAULT_STAGE_CEILINGS),
        "common_fields": list(schema.get("required_common_fields") or []),
        "producer_fields": list(schema.get("producer_required_fields") or ["id", "kind"]),
        "snapshot_fields": list(schema.get("snapshot_required_fields") or ["repo", "revision"]),
        "claim_fields": list(
            schema.get("claim_required_fields")
            or ["claim_id", "maturity", "dependencies", "evidence_ids"]
        ),
        "evidence_fields": list(
            schema.get("evidence_required_fields")
            or ["evidence_id", "origin", "independence", "derived_from"]
        ),
        "evidence_values": set(
            schema.get("evidence_independence_values") or DEFAULT_EVIDENCE_INDEPENDENCE
        ),
        "s4_fields": list(schema.get("s4_stage_payload_required_fields") or []),
        "oracle_values": set(schema.get("oracle_independence_values") or DEFAULT_ORACLE_STATUSES),
        "s5_fields": list(schema.get("s5_stage_payload_required_fields") or []),
        "verification_oracle_values": set(
            schema.get("verification_oracle_values") or DEFAULT_ORACLE_STATUSES
        ),
    }


def validate_contracts(policy: Mapping[str, Any], schema: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if policy.get("policy_version") != PIPELINE_POLICY_VERSION:
        errors.append(
            f"policy contract version must be {PIPELINE_POLICY_VERSION!r}, "
            f"got {policy.get('policy_version')!r}"
        )
    if policy.get("handoff_schema_version") != HANDOFF_SCHEMA_VERSION:
        errors.append("policy contract binds a different handoff schema version")
    if schema.get("handoff_schema_version") != HANDOFF_SCHEMA_VERSION:
        errors.append(
            f"handoff contract version must be {HANDOFF_SCHEMA_VERSION!r}, "
            f"got {schema.get('handoff_schema_version')!r}"
        )
    if tuple(policy.get("stage_order") or ()) != STAGES:
        errors.append(f"policy stage order must be exactly {','.join(STAGES)}")
    return errors


def validate_receipt(
    receipt: Mapping[str, Any],
    policy: Mapping[str, Any],
    schema: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate one receipt without assuming its predecessor exists."""
    errors = validate_contracts(policy, schema)
    warnings: list[str] = []
    authority_violations: list[str] = []
    cv = _contract_view(policy, schema)

    if not isinstance(receipt, Mapping):
        return {
            "status": "INVALID",
            "errors": ["receipt must be an object"],
            "warnings": [],
            "authority_violations": [],
            "computed_receipt_digest": None,
        }

    _append_missing(errors, receipt, cv["common_fields"])

    stage = receipt.get("stage")
    if stage not in cv["stage_order"]:
        errors.append(f"unknown or invalid stage: {stage!r}")

    if receipt.get("handoff_schema_version") != HANDOFF_SCHEMA_VERSION:
        errors.append("receipt handoff_schema_version is incompatible")
    if receipt.get("pipeline_policy_version") != PIPELINE_POLICY_VERSION:
        errors.append("receipt pipeline_policy_version is incompatible")

    if receipt.get("policy_contract_digest") != cv["policy_digest"]:
        errors.append("policy_contract_digest does not match the supplied policy contract")
    if receipt.get("handoff_schema_digest") != cv["schema_digest"]:
        errors.append("handoff_schema_digest does not match the supplied handoff contract")

    cycle_id = receipt.get("cycle_id")
    epoch = receipt.get("pipeline_policy_epoch")
    instance = receipt.get("execution_instance_id")
    if not _is_nonempty_string(cycle_id):
        errors.append("cycle_id must be a non-empty string")
    if not _is_nonempty_string(epoch):
        errors.append("pipeline_policy_epoch must be a non-empty string")
    if stage in cv["stage_order"] and _is_nonempty_string(cycle_id):
        expected_instance = f"{cycle_id}-{stage}"
        if instance != expected_instance:
            errors.append(
                f"execution_instance_id must be {expected_instance!r}, got {instance!r}"
            )

    producer = receipt.get("producer")
    if not isinstance(producer, Mapping):
        errors.append("producer must be an object")
    else:
        _append_missing(errors, producer, cv["producer_fields"], "producer.")
        for field in cv["producer_fields"]:
            if field in producer and not _is_nonempty_string(producer[field]):
                errors.append(f"producer.{field} must be a non-empty string")

    if not _is_nonempty_string(receipt.get("repo_baseline_revision")):
        errors.append("repo_baseline_revision must be a non-empty string")

    snapshots = receipt.get("repo_snapshot_set")
    if not isinstance(snapshots, list) or not snapshots:
        errors.append("repo_snapshot_set must be a non-empty array")
    else:
        seen_repos: set[str] = set()
        for i, snapshot in enumerate(snapshots):
            if not isinstance(snapshot, Mapping):
                errors.append(f"repo_snapshot_set[{i}] must be an object")
                continue
            _append_missing(errors, snapshot, cv["snapshot_fields"], f"repo_snapshot_set[{i}].")
            repo = snapshot.get("repo")
            revision = snapshot.get("revision")
            if not _is_nonempty_string(repo) or not _is_nonempty_string(revision):
                errors.append(f"repo_snapshot_set[{i}] repo/revision must be non-empty strings")
            elif repo in seen_repos:
                errors.append(f"duplicate repo_snapshot_set repo: {repo}")
            else:
                seen_repos.add(repo)

    prior = receipt.get("prior_stage_digest")
    if stage == "S1":
        if prior is not None:
            errors.append("S1 prior_stage_digest must be null")
    elif stage in cv["stage_order"]:
        if not (
            isinstance(prior, str)
            and prior.startswith("sha256:")
            and len(prior) == len("sha256:") + 64
        ):
            errors.append(f"{stage} prior_stage_digest must be a sha256 digest")

    if receipt.get("execution_authorized") is not False:
        authority_violations.append("execution_authorized must be exactly false")
        errors.append("execution_authorized must be exactly false")

    for name in ("claims", "dependencies", "conflicts", "evidence_lineage"):
        if not isinstance(receipt.get(name), list):
            errors.append(f"{name} must be an array")

    maturity_order = cv["maturity_order"]
    maturity_rank = {name: i for i, name in enumerate(maturity_order)}
    ceiling = cv["stage_ceilings"].get(stage)
    ceiling_rank = maturity_rank.get(ceiling)
    claims = receipt.get("claims")
    if isinstance(claims, list):
        seen_claims: set[str] = set()
        for i, claim in enumerate(claims):
            if not isinstance(claim, Mapping):
                errors.append(f"claims[{i}] must be an object")
                continue
            _append_missing(errors, claim, cv["claim_fields"], f"claims[{i}].")
            claim_id = claim.get("claim_id")
            maturity = claim.get("maturity")
            if not _is_nonempty_string(claim_id):
                errors.append(f"claims[{i}].claim_id must be a non-empty string")
            elif claim_id in seen_claims:
                errors.append(f"duplicate claim_id in receipt: {claim_id}")
            else:
                seen_claims.add(claim_id)
            if maturity not in maturity_rank:
                errors.append(f"claims[{i}].maturity is unknown: {maturity!r}")
            elif ceiling_rank is not None and maturity_rank[maturity] > ceiling_rank:
                msg = f"{stage} claim {claim_id!r} exceeds maturity ceiling {ceiling}"
                authority_violations.append(msg)
                errors.append(msg)
            if not isinstance(claim.get("dependencies"), list):
                errors.append(f"claims[{i}].dependencies must be an array")
            if not isinstance(claim.get("evidence_ids"), list):
                errors.append(f"claims[{i}].evidence_ids must be an array")

    evidence = receipt.get("evidence_lineage")
    if isinstance(evidence, list):
        seen_evidence: set[str] = set()
        for i, item in enumerate(evidence):
            if not isinstance(item, Mapping):
                errors.append(f"evidence_lineage[{i}] must be an object")
                continue
            _append_missing(errors, item, cv["evidence_fields"], f"evidence_lineage[{i}].")
            evidence_id = item.get("evidence_id")
            if not _is_nonempty_string(evidence_id):
                errors.append(f"evidence_lineage[{i}].evidence_id must be a non-empty string")
            elif evidence_id in seen_evidence:
                errors.append(f"duplicate evidence_id in receipt: {evidence_id}")
            else:
                seen_evidence.add(evidence_id)
            if item.get("independence") not in cv["evidence_values"]:
                errors.append(
                    f"evidence_lineage[{i}].independence is unknown: "
                    f"{item.get('independence')!r}"
                )
            if not isinstance(item.get("derived_from"), list):
                errors.append(f"evidence_lineage[{i}].derived_from must be an array")

    payload = receipt.get("stage_payload")
    if not isinstance(payload, Mapping):
        errors.append("stage_payload must be an object")
        payload = {}

    if stage == "S4":
        _append_missing(errors, payload, cv["s4_fields"], "stage_payload.")
        oracle_status = payload.get("oracle_independence_status")
        if oracle_status not in cv["oracle_values"]:
            errors.append(f"unknown S4 oracle_independence_status: {oracle_status!r}")
    if stage == "S5":
        _append_missing(errors, payload, cv["s5_fields"], "stage_payload.")
        verification_status = payload.get("verification_oracle_status")
        if verification_status not in cv["verification_oracle_values"]:
            errors.append(f"unknown S5 verification_oracle_status: {verification_status!r}")
        if "promotion_path_valid" in payload and not isinstance(
            payload.get("promotion_path_valid"), bool
        ):
            errors.append("stage_payload.promotion_path_valid must be boolean")

    computed_digest = None
    try:
        computed_digest = receipt_digest(dict(receipt))
    except Exception as exc:
        errors.append(f"receipt cannot be canonicalized: {exc}")
    claimed_digest = receipt.get("receipt_digest")
    if computed_digest is not None and claimed_digest != computed_digest:
        errors.append("receipt_digest mismatch")

    return {
        "status": "VALID" if not errors else "INVALID",
        "stage": stage,
        "errors": errors,
        "warnings": warnings,
        "authority_violations": authority_violations,
        "computed_receipt_digest": computed_digest,
    }


def _origin_key(origin: Any) -> str:
    try:
        return canonical_json(origin)
    except Exception:
        return repr(origin)


def _lineage_summary(receipts: Mapping[str, Mapping[str, Any]]) -> tuple[str, int, list[str]]:
    origins: list[str] = []
    independent_origins: set[str] = set()
    unknown = False
    claimed_independent_by_origin: Counter[str] = Counter()
    breaks: list[str] = []

    for stage in STAGES:
        receipt = receipts.get(stage)
        if not isinstance(receipt, Mapping):
            continue
        for item in receipt.get("evidence_lineage") or []:
            if not isinstance(item, Mapping):
                continue
            origin = _origin_key(item.get("origin"))
            origins.append(origin)
            independence = item.get("independence")
            if independence in {"PRIMARY", "INDEPENDENT_REPLICATION"}:
                independent_origins.add(origin)
                claimed_independent_by_origin[origin] += 1
            elif independence == "UNKNOWN":
                unknown = True

    inflated = [origin for origin, count in claimed_independent_by_origin.items() if count > 1]
    if inflated:
        breaks.append(
            "multiple evidence entries claim independent authority from the same origin"
        )
        return "DUPLICATE_INFLATED", len(independent_origins), breaks
    if unknown:
        return "PARTIALLY_VERIFIED", len(independent_origins), breaks
    if origins:
        return "VALID", len(independent_origins), breaks
    return "UNKNOWN", 0, breaks


def validate_cycle(
    receipts: Mapping[str, Mapping[str, Any]],
    policy: Mapping[str, Any],
    schema: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the structural S1->S5 chain.

    A valid result proves only structural handoff coherence. It does not prove any
    scientific, trading, release, merge, deployment, or publication claim.
    """
    contract_errors = validate_contracts(policy, schema)
    cv = _contract_view(policy, schema)
    missing = [stage for stage in STAGES if stage not in receipts]
    per_stage = {
        stage: validate_receipt(receipts[stage], policy, schema)
        for stage in STAGES
        if stage in receipts
    }

    policy_breaks: list[str] = []
    epochs: set[str] = set()
    for stage in STAGES:
        receipt = receipts.get(stage)
        if receipt is None:
            policy_breaks.append(f"{stage}: missing required stage/policy evidence")
            continue
        if receipt.get("pipeline_policy_version") != PIPELINE_POLICY_VERSION:
            policy_breaks.append(f"{stage}: incompatible pipeline_policy_version")
        epoch = receipt.get("pipeline_policy_epoch")
        if _is_nonempty_string(epoch):
            epochs.add(epoch)
        else:
            policy_breaks.append(f"{stage}: missing pipeline_policy_epoch")
        if receipt.get("policy_contract_digest") != cv["policy_digest"]:
            policy_breaks.append(f"{stage}: policy contract digest mismatch")
        if receipt.get("handoff_schema_digest") != cv["schema_digest"]:
            policy_breaks.append(f"{stage}: handoff schema digest mismatch")
    if len(epochs) > 1:
        policy_breaks.append("pipeline_policy_epoch differs across stages")
    policy_chain_status = "CONSISTENT" if not policy_breaks else "MIXED_POLICY"

    snapshot_breaks: list[str] = []
    baselines: set[str] = set()
    snapshots: set[str] = set()
    for stage in STAGES:
        receipt = receipts.get(stage)
        if receipt is None:
            continue
        baseline = receipt.get("repo_baseline_revision")
        if _is_nonempty_string(baseline):
            baselines.add(baseline)
        try:
            snapshots.add(canonical_json(receipt.get("repo_snapshot_set")))
        except Exception:
            snapshot_breaks.append(f"{stage}: repo_snapshot_set is not canonicalizable")
    if len(baselines) > 1 or len(snapshots) > 1:
        snapshot_breaks.append("pinned repository subject differs across stages")
        snapshot_chain_status = "MIXED_REVISION"
    elif missing:
        snapshot_chain_status = "UNVERIFIED"
    elif baselines and snapshots and not snapshot_breaks:
        snapshot_chain_status = "CONSISTENT"
    else:
        snapshot_chain_status = "INVALID"

    handoff_breaks: list[str] = []
    if missing:
        handoff_chain_status = "INCOMPLETE"
    else:
        previous_digest = None
        for i, stage in enumerate(STAGES):
            receipt = receipts[stage]
            result = per_stage[stage]
            if result["status"] != "VALID":
                handoff_breaks.append(f"{stage}: receipt validation failed")
            if i == 0:
                if receipt.get("prior_stage_digest") is not None:
                    handoff_breaks.append("S1: prior_stage_digest must be null")
            elif receipt.get("prior_stage_digest") != previous_digest:
                handoff_breaks.append(
                    f"{stage}: prior_stage_digest does not match {STAGES[i - 1]} receipt"
                )
            previous_digest = result.get("computed_receipt_digest")
        handoff_chain_status = "CONSISTENT" if not handoff_breaks else "INVALID"

    authority_violations: list[str] = []
    for stage, result in per_stage.items():
        authority_violations.extend(
            f"{stage}: {item}" for item in result.get("authority_violations", [])
        )

    lineage_status, independent_origins, lineage_breaks = _lineage_summary(receipts)

    s4_payload = receipts.get("S4", {}).get("stage_payload", {}) if "S4" in receipts else {}
    s5_payload = receipts.get("S5", {}).get("stage_payload", {}) if "S5" in receipts else {}
    s4_oracle = s4_payload.get("oracle_independence_status")
    s5_oracle = s5_payload.get("verification_oracle_status")

    structurally_eligible = (
        not contract_errors
        and not missing
        and policy_chain_status == "CONSISTENT"
        and snapshot_chain_status == "CONSISTENT"
        and handoff_chain_status == "CONSISTENT"
        and not authority_violations
        and lineage_status not in {"DUPLICATE_INFLATED", "INVALID"}
        and s4_oracle == "INDEPENDENT"
        and s5_oracle == "INDEPENDENT"
    )

    reported_promotion = s5_payload.get("promotion_path_valid")
    if reported_promotion is True and not structurally_eligible:
        authority_violations.append(
            "S5 reports promotion_path_valid=true while structural prerequisites are not met"
        )
        structurally_eligible = False

    if contract_errors or any(
        result["status"] == "INVALID" for result in per_stage.values()
    ) or handoff_chain_status == "INVALID":
        status = "INVALID"
    elif policy_chain_status == "MIXED_POLICY":
        status = "MIXED_POLICY"
    elif snapshot_chain_status == "MIXED_REVISION":
        status = "MIXED_REVISION"
    elif missing:
        status = "INCOMPLETE"
    else:
        status = "VALID"

    return {
        "status": status,
        "pipeline_policy_version": PIPELINE_POLICY_VERSION,
        "handoff_schema_version": HANDOFF_SCHEMA_VERSION,
        "policy_chain_status": policy_chain_status,
        "policy_chain_breaks": policy_breaks,
        "snapshot_chain_status": snapshot_chain_status,
        "snapshot_chain_breaks": snapshot_breaks,
        "handoff_chain_status": handoff_chain_status,
        "handoff_chain_breaks": handoff_breaks,
        "evidence_lineage_status": lineage_status,
        "evidence_lineage_breaks": lineage_breaks,
        "independent_evidence_origin_count": independent_origins,
        "verification_oracle_status": s5_oracle or "UNVERIFIED",
        "s4_oracle_independence_status": s4_oracle or "UNVERIFIED",
        "promotion_path_valid": structurally_eligible,
        "authority_violations": authority_violations,
        "missing_stages": missing,
        "contract_errors": contract_errors,
        "stages": per_stage,
        "execution_authorized": False,
        "note": (
            "Structural validation only; a valid chain does not authorize execution "
            "or prove scientific/release claims."
        ),
    }
