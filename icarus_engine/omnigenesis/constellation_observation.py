"""Phase 25: verifiable, data-minimized Constellation observability evidence.

This module DOES NOT open GitHub, broker, market, database or network
connections. It independently recomputes the exact research tribunal
with the same source revision and emits an offline read-only projection.
GitHub source/run fields are caller declarations, NOT API attestations.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from .constellation import _valid_plan, arbitrate
from .constellation_recovery import _read, verify_checkpoint
from .contracts import identity

_SCHEMA = "icarus-omnigenesis-constellation-observation-v1"
_AUTHORITY = {
    "research_only": True,
    "execution_authorized": False,
    "production_decision_authorized": False,
    "auto_promote": False,
}


def observe_constellation(plan: Mapping[str, Any],
                          checkpoint: Mapping[str, Any],
                          tribunal: Mapping[str, Any],
                          *, predecessor: Mapping[str, Any] | None = None) -> dict:
    """Recompute evidence; no raw receipts or account data in the projection."""
    p = _valid_plan(plan)
    current = verify_checkpoint(p, checkpoint)
    if current["status"] != "COMPLETE_PENDING_TRIBUNAL":
        raise ValueError("cannot observe incomplete or failed Constellation")
    prior_id = None
    if current["retry_round"] == 1:
        if predecessor is None:
            raise ValueError("recovered checkpoint requires original predecessor")
        previous = verify_checkpoint(p, predecessor)
        if (previous["status"] != "RETRY_REQUIRED"
                or previous["context"] != current["context"]
                or current["previous_checkpoint_id"] != previous["checkpoint_id"]):
            raise ValueError("recovery predecessor mismatch")
        seen = {(r["lane"], r["shard"]): r
                for r in current["accepted_receipts"]}
        for old in previous["accepted_receipts"]:
            if seen.get((old["lane"], old["shard"])) != old:
                raise ValueError("recovery predecessor evidence not monotonic")
        prior_id = previous["checkpoint_id"]
    elif predecessor is not None:
        raise ValueError("unexpected previous checkpoint for first-pass success")
    official = arbitrate(p, current["accepted_receipts"])
    if not isinstance(tribunal, dict) or tribunal != official:
        raise ValueError("independent tribunal output does not match computed evidence")
    if (official["release_authorized"] is not False or
            official["broker_order_count"] != 0 or
            official["independent_scientific_validation"] is not False):
        raise ValueError("tribunal authority or external-science mismatch")
    receipt_by_worker = {(r["lane"], r["shard"]): r["receipt_id"]
                         for r in current["accepted_receipts"]}
    workers = [
        {"lane": job["lane"], "shard": job["shard"],
         "status": "COMPLETED_RESEARCH_ONLY",
         "receipt_id": receipt_by_worker[(job["lane"], job["shard"])]}
        for job in p["jobs"]
    ]
    report = {
        "schema_version": _SCHEMA,
        "authority": dict(_AUTHORITY),
        "evidence_kind": "SAME_SOURCE_REPLAYED_CONSTELLATION_WORKERS",
        "status": "VERIFIED_LOCAL_RESEARCH_RECEIPTS_PENDING_EXTERNAL_REVIEW",
        "plan_id": p["plan_id"],
        "checkpoint_id": current["checkpoint_id"],
        "predecessor_checkpoint_id": prior_id,
        "tribunal_id": official["tribunal_id"],
        "claimed_github_run": dict(current["context"]),
        "github_api_provenance_verified": False,
        "source_commit_attested": False,
        "active_workers_now": 0,
        "snapshot_is_live": False,
        "worker_count": len(workers),
        "completed_count": len(workers),
        "retry_round": current["retry_round"],
        "workers": workers,
        "source_authenticity_verified": False,
        "independent_scientific_validation": False,
        "real_profitability_verified": False,
        "broker_order_count": 0,
        "strategy_promoted": False,
        "release_authorized": False,
    }
    report["observation_id"] = identity(report)
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Read-only source-recomputed research observatory projection")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--tribunal", type=Path, required=True)
    parser.add_argument("--predecessor", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = observe_constellation(
        _read(args.plan), _read(args.checkpoint), _read(args.tribunal),
        predecessor=_read(args.predecessor) if args.predecessor else None,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as fp:
        json.dump(result, fp, indent=2, sort_keys=True)
        fp.write("\n")
    print(json.dumps({
        "observation_id": result["observation_id"],
        "status": result["status"],
        "worker_count": result["worker_count"],
        "broker_order_count": 0,
        "github_api_provenance_verified": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
