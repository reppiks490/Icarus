"""Selected-workspace read-only projection of real Icarus-engine evidence.

No network calls are made here. The peer checkout must be explicitly configured by
path and exact commit. Missing configuration is reported, never replaced with fake data.
"""
from __future__ import annotations

import os
from pathlib import Path

from .engine_evidence_catalog import EvidenceCatalogError, build_real_engine_evidence_catalog
from .engine_evidence_gauges import build_real_engine_evidence_gauges


def _base(status: str) -> dict:
    return {
        "schema_version": "icarus-workspace-engine-evidence-v1",
        "status": status,
        "source_repository": "reppiks490/Icarus-engine",
        "synthetic_market_evidence_used": False,
        "provider_requests_made": 0,
        "new_collection_performed": False,
        "automatic_model_promotion": False,
        "production_decision_authorized": False,
        "execution_authorized": False,
    }


def workspace_engine_evidence_snapshot() -> dict:
    root = os.environ.get("ICARUS_ENGINE_EVIDENCE_ROOT", "").strip()
    commit = os.environ.get("ICARUS_ENGINE_EVIDENCE_COMMIT", "").strip()
    if not root or not commit:
        return {
            **_base("UNAVAILABLE"),
            "reason": "ENGINE_EVIDENCE_CHECKOUT_NOT_CONFIGURED",
            "configured": False,
        }

    try:
        catalog = build_real_engine_evidence_catalog(Path(root), expected_commit=commit)
        gauges = build_real_engine_evidence_gauges(Path(root), expected_commit=commit)
    except (EvidenceCatalogError, OSError, ValueError) as exc:
        # Do not expose the machine-local checkout path in an operator response.
        detail = str(exc).replace(root, "<engine-peer>")
        return {
            **_base("BLOCKED"),
            "reason": "ENGINE_EVIDENCE_VALIDATION_FAILED",
            "detail": detail[:500],
            "configured": True,
            "expected_commit": commit,
        }

    provider_blockers = sorted(
        name
        for name, value in catalog["provider_snapshot"]["providers"].items()
        if str(value.get("status", "")).startswith("BLOCKED")
    )
    source_blockers = sorted(
        name
        for name, value in catalog["source_states"].items()
        if value.get("consumption_state") == "BLOCKED"
    )

    return {
        **_base("AVAILABLE"),
        "configured": True,
        "producer_commit": catalog["producer_commit"],
        "evidence_files": catalog["evidence_files"],
        "provider": {
            "snapshot_at_utc": catalog["provider_snapshot"]["snapshot_at_utc"],
            "current_collected_rows": catalog["provider_snapshot"]["current_collected_rows"],
            "substantive_providers": catalog["provider_snapshot"]["substantive_providers"],
            "providers": catalog["provider_snapshot"]["providers"],
        },
        "sec_edgar": catalog["sec_edgar"],
        "native_research": catalog["native_research"],
        "interrepo_acceptance": catalog["interrepo_acceptance"],
        "sentinel_counts": catalog["sentinel_counts"],
        "blockers": {
            "provider_blocked": provider_blockers,
            "source_consumption_blocked": source_blockers,
        },
        "gauges": gauges["gauges"],
        "aggregate_edge_score": None,
        "edge_claim_allowed": False,
    }
