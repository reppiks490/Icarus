"""Phase 24: bounded recovery checkpoints for Constellation research shards.

A recovery checkpoint captures validated partial worker receipts for later
continuation, but does not make an unsigned GitHub artifact a trusted source,
establish exactly-once distributed execution, or grant broker permissions.
Each worker is recomputed using the *same source* for consistency; independent
scientific review remains required. The retry budget is ONE per missing shard.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import re
from pathlib import Path
from typing import Any, Mapping

from .constellation import _valid_plan, run_worker, arbitrate
from .contracts import identity

_SCHEMA = "icarus-omnigenesis-constellation-recovery-v1"
_SOURCE_SHA = re.compile(r"^[0-9a-f]{40}$")
_RUN_ID = re.compile(r"^[1-9][0-9]{0,19}$")
_EXPECTED_KEYS = {
    "schema_version", "plan_id", "context", "retry_round",
    "accepted_receipts", "accepted_count", "pending_jobs", "pending_count",
    "retry_jobs", "status", "previous_checkpoint_id",
    "same_source_recomputation", "broker_order_count",
    "independent_review_required", "checkpoint_id",
}
_AUTHORITY = {
    "research_only": True,
    "execution_authorized": False,
    "production_decision_authorized": False,
    "auto_promote": False,
}
_CONTEXT_FIELDS = {"github_run_id", "github_run_attempt", "source_sha"}


def context(run_id: str, attempt: int, source_sha: str) -> dict:
    """Caller-declared GitHub identity; only GitHub itself can attest origin."""
    if type(run_id) is not str or not _RUN_ID.fullmatch(run_id):
        raise ValueError("invalid GitHub run id")
    if type(attempt) is not int or not 1 <= attempt <= 100:
        raise ValueError("invalid GitHub run attempt")
    if type(source_sha) is not str or not _SOURCE_SHA.fullmatch(source_sha):
        raise ValueError("invalid source revision SHA")
    return {
        "github_run_id": run_id, "github_run_attempt": attempt,
        "source_sha": source_sha,
    }


def _validated_receipts(plan: dict, receipts: list[Any]) -> dict:
    if not isinstance(receipts, list) or len(receipts) > len(plan["jobs"]):
        raise ValueError("unexpected recovery receipt count")
    expected = {(j["lane"], j["shard"]) for j in plan["jobs"]}
    accepted = {}
    for receipt in receipts:
        if not isinstance(receipt, dict):
            raise ValueError("invalid recovery receipt")
        pair = (receipt.get("lane"), receipt.get("shard"))
        if pair not in expected or pair in accepted:
            raise ValueError("unregistered or duplicate recovery worker")
        if receipt != run_worker(plan, pair[0], pair[1]):
            raise ValueError("tampered or incompatible recovery worker receipt")
        accepted[pair] = deepcopy(receipt)
    return accepted


def _snapshot(plan: dict, where: dict, accepted: dict,
              retry_round: int, previous_id: str | None) -> dict:
    missing = [dict(j) for j in plan["jobs"]
               if (j["lane"], j["shard"]) not in accepted]
    completed = [accepted[(j["lane"], j["shard"])]
                 for j in plan["jobs"] if (j["lane"], j["shard"]) in accepted]
    if not missing:
        status, retry_jobs = "COMPLETE_PENDING_TRIBUNAL", []
    elif not completed:
        status, retry_jobs = "FAIL_CLOSED_NO_EVIDENCE", []
    elif retry_round == 0:
        status, retry_jobs = "RETRY_REQUIRED", missing
    else:
        status, retry_jobs = "FAIL_CLOSED_RETRY_EXHAUSTED", []
    obj = {
        "schema_version": _SCHEMA,
        "plan_id": plan["plan_id"],
        "context": dict(where),
        "retry_round": retry_round,
        "accepted_receipts": completed,
        "accepted_count": len(completed),
        "pending_jobs": missing,
        "pending_count": len(missing),
        "retry_jobs": retry_jobs,
        "status": status,
        "previous_checkpoint_id": previous_id,
        "same_source_recomputation": True,
        "broker_order_count": 0,
        "independent_review_required": True,
    }
    obj["checkpoint_id"] = identity(obj)
    return obj


def verify_checkpoint(plan: Mapping[str, Any],
                      checkpoint: Mapping[str, Any]) -> dict:
    """Validate an exported checkpoint rather than trusting its status field."""
    p = _valid_plan(plan)
    if not isinstance(checkpoint, dict) or set(checkpoint) != _EXPECTED_KEYS:
        raise ValueError("unexpected recovery checkpoint schema")
    if checkpoint.get("schema_version") != _SCHEMA:
        raise ValueError("unsupported recovery checkpoint version")
    c = checkpoint["context"]
    if not isinstance(c, dict) or set(c) != _CONTEXT_FIELDS:
        raise ValueError("invalid recovery source context")
    where = context(c["github_run_id"], c["github_run_attempt"],
                    c["source_sha"])
    round_ = checkpoint.get("retry_round")
    if type(round_) is not int or round_ not in (0, 1):
        raise ValueError("invalid recovery round")
    previous_id = checkpoint.get("previous_checkpoint_id")
    if round_ == 0 and previous_id is not None:
        raise ValueError("initial checkpoint has unexpected predecessor")
    if round_ == 1 and (not isinstance(previous_id, str) or
                        not re.fullmatch(r"[0-9a-f]{64}", previous_id)):
        raise ValueError("recovery continuation missing previous checkpoint id")
    accepted = _validated_receipts(p, checkpoint["accepted_receipts"])
    expected = _snapshot(p, where, accepted, round_, previous_id)
    if checkpoint != expected:
        raise ValueError("recovery checkpoint digest, identity or status mismatch")
    return expected


def checkpoint_recovery(plan: Mapping[str, Any],
                        current_receipts: list[Any], *,
                        run_id: str, attempt: int, source_sha: str,
                        previous: Mapping[str, Any] | None = None) -> dict:
    """Build a strict partial snapshot or finish one bounded recovery attempt.

    On a continuation, the previous checkpoint has to be an original
    RETRY_REQUIRED snapshot from the same plan/source/run. All prior
    receipt values are immutable and must remain present, and newer
    evidence must match the same deterministic source implementation.
    """
    p = _valid_plan(plan)
    where = context(run_id, attempt, source_sha)
    accepted = _validated_receipts(p, current_receipts)
    if previous is None:
        return _snapshot(p, where, accepted, 0, None)
    previous_valid = verify_checkpoint(p, previous)
    if previous_valid["context"] != where:
        raise ValueError("checkpoint source/run mismatch")
    if previous_valid["status"] != "RETRY_REQUIRED":
        raise ValueError("no eligible unfinished recovery to resume")
    for old in previous_valid["accepted_receipts"]:
        key = (old["lane"], old["shard"])
        if key not in accepted or accepted[key] != old:
            raise ValueError("checkpoint continuation removed or changed prior evidence")
    return _snapshot(p, where, accepted, 1,
                     previous_valid["checkpoint_id"])


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError("duplicate recovery JSON key")
        result[k] = v
    return result


def _read(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError("missing, symlinked or oversized recovery input")
    try:
        return json.loads(path.read_text(encoding="utf-8"),
                          object_pairs_hook=_unique_pairs)
    except (UnicodeError, OSError, json.JSONDecodeError) as exc:
        raise ValueError("malformed recovery input") from exc


def _collect(folder: Path) -> list[dict]:
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("missing or symlinked recovery worker directory")
    entries = list(folder.iterdir())
    if len(entries) > 12:
        raise ValueError("extra recovery artifacts are forbidden")
    out = []
    for entry in entries:
        if not entry.name.startswith("worker-") or not entry.name.endswith(".json"):
            raise ValueError("unrecognized recovery artifact")
        item = _read(entry)
        if entry.name != f"worker-{item.get('lane')}-{item.get('shard')}.json":
            raise ValueError("recovery artifact file identity mismatch")
        out.append(item)
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Offline Constellation missing-shard checkpoint; NO BROKER")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--worker-dir", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", type=int, required=True)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = checkpoint_recovery(
        _read(args.plan), _collect(args.worker_dir),
        run_id=args.run_id, attempt=args.run_attempt,
        source_sha=args.source_sha,
        previous=_read(args.previous) if args.previous else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({
        "checkpoint_id": report["checkpoint_id"],
        "status": report["status"],
        "accepted": report["accepted_count"],
        "missing": report["pending_count"],
        "retry_jobs": report["retry_jobs"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
