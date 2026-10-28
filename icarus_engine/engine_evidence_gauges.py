"""Meaningful infrastructure gauges derived only from real committed Engine evidence.

These gauges describe evidence-pipeline readiness, not market edge, trade confidence,
strategy quality, profitability, execution readiness or production authorization.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from icarus_engine.engine_evidence_catalog import build_real_engine_evidence_catalog


def _pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((100.0 * numerator) / denominator, 2)


def _gauge(
    *,
    key: str,
    numerator: int,
    denominator: int,
    direction: str,
    meaning: str,
    interpretation: str,
) -> dict:
    return {
        "key": key,
        "value_pct": _pct(numerator, denominator),
        "numerator": numerator,
        "denominator": denominator,
        "direction": direction,
        "meaning": meaning,
        "interpretation": interpretation,
        "trading_edge_metric": False,
        "execution_authorized": False,
    }


def build_real_engine_evidence_gauges(peer_root: Path, *, expected_commit: str) -> dict:
    catalog = build_real_engine_evidence_catalog(peer_root, expected_commit=expected_commit)

    sentinel = catalog["sentinel_counts"]
    sentinel_total = sum(sentinel.values())
    sentinel_ok = sentinel.get("OK", 0)
    sentinel_bad = sentinel.get("BLOCKED", 0) + sentinel.get("FAILING", 0)

    providers = catalog["provider_snapshot"]["providers"]
    substantive = sum(
        1
        for value in providers.values()
        if value["substantive_work_performed"] and value["collected_rows"] > 0
    )

    lanes = catalog["native_research"]["lanes"]
    verified_lanes = sum(1 for value in lanes.values() if value.get("status") == "VERIFIED")

    sources = catalog["source_states"]
    consumption_visible = sum(
        1
        for value in sources.values()
        if value.get("consumption_state") not in (None, "BLOCKED")
    )

    sec = catalog["sec_edgar"]
    sec_integrity = int(
        sec["fact_rows"] > 0
        and sec["filing_rows"] > 0
        and len(sec["facts_sha256"]) == 64
        and len(sec["filing_sha256"]) == 64
    )

    interrepo = catalog["interrepo_acceptance"]
    peer_verified = int(str(interrepo.get("status", "")).startswith("VERIFIED"))

    gauges = {
        "sentinel_health_ok": _gauge(
            key="sentinel_health_ok",
            numerator=sentinel_ok,
            denominator=sentinel_total,
            direction="higher_is_better",
            meaning="Share of currently classified Sentinel checks that are OK.",
            interpretation="Pipeline/monitoring health only; blocked or failing sources remain visible.",
        ),
        "sentinel_blocked_or_failing": _gauge(
            key="sentinel_blocked_or_failing",
            numerator=sentinel_bad,
            denominator=sentinel_total,
            direction="lower_is_better",
            meaning="Share of Sentinel checks currently BLOCKED or FAILING.",
            interpretation="Operational debt/risk visibility, not a market-risk or trade-risk estimate.",
        ),
        "provider_substantive_delivery": _gauge(
            key="provider_substantive_delivery",
            numerator=substantive,
            denominator=len(providers),
            direction="higher_is_better",
            meaning="Share of provider receipts with real persisted rows and substantive work in the current provider context.",
            interpretation="Measures current evidence delivery coverage, not completeness of each provider catalog.",
        ),
        "native_lane_verified": _gauge(
            key="native_lane_verified",
            numerator=verified_lanes,
            denominator=len(lanes),
            direction="higher_is_better",
            meaning="Share of Native Five research lanes whose committed status is VERIFIED.",
            interpretation="Verifies lane evidence state only; local models, profitability and execution remain separate.",
        ),
        "source_consumption_not_blocked": _gauge(
            key="source_consumption_not_blocked",
            numerator=consumption_visible,
            denominator=len(sources),
            direction="higher_is_better",
            meaning="Share of canonical ingestion-manifest sources whose consumption state is not explicitly BLOCKED.",
            interpretation="Includes partial/evidence-only/dedicated states; it is not a full-data-coverage percentage.",
        ),
        "sec_edgar_manifest_integrity": _gauge(
            key="sec_edgar_manifest_integrity",
            numerator=sec_integrity,
            denominator=1,
            direction="binary_required",
            meaning="Whether committed SEC/EDGAR evidence has nonzero fact/filing rows and bound SHA-256 digests.",
            interpretation="Manifest integrity/presence only; it does not certify every filing fact semantically.",
        ),
        "interrepo_acceptance_verified": _gauge(
            key="interrepo_acceptance_verified",
            numerator=peer_verified,
            denominator=1,
            direction="binary_required",
            meaning="Whether the committed Engine peer packet is represented by a verified prior Icarus acceptance record.",
            interpretation="Cross-repository research observability only; acceptance is not execution authority.",
        ),
    }

    return {
        "schema_version": "icarus-real-engine-evidence-gauges-v1",
        "producer_repository": catalog["producer_repository"],
        "producer_commit": catalog["producer_commit"],
        "provider_current_collected_rows": catalog["provider_snapshot"]["current_collected_rows"],
        "sec_fact_rows": sec["fact_rows"],
        "sec_filing_rows": sec["filing_rows"],
        "native_run_id": catalog["native_research"]["run_id"],
        "gauges": gauges,
        "aggregate_edge_score": None,
        "edge_claim_allowed": False,
        "automatic_model_promotion": False,
        "production_decision_authorized": False,
        "execution_authorized": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine-root", required=True, type=Path)
    parser.add_argument("--engine-commit", required=True)
    args = parser.parse_args(argv)
    result = build_real_engine_evidence_gauges(
        args.engine_root,
        expected_commit=args.engine_commit,
    )
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
