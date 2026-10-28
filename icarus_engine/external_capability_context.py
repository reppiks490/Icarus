"""Read-only, fail-closed external repository capability context for ICARUS.

The owner-actions source inventory is not an installed-tool inventory, and
neither a source snapshot nor an apparent call site establishes runtime usage.
This module never imports/executes external repositories, contacts GitHub,
collects market data, or grants research, training or execution authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA = "icarus-external-capability-context-v1"
MAX_INPUT_BYTES = 8 * 1024 * 1024
REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")

# Review candidates, not verified imports, integrations or licenses.
CANDIDATE_SUBSYSTEMS: dict[str, tuple[str, ...]] = {
    "microsoft/rd-agent": ("research_agent", "model_isolation"),
    "microsoft/qlib": ("research_workspace", "experiment_tracking"),
    "morluto/rea": ("source_inspection", "sandboxing"),
    "polakowo/vectorbt": ("quant_research", "validation"),
    "nautechsystems/nautilus_trader": ("paper_execution", "market_replay"),
    "NVIDIA/OpenShell": ("sandboxing", "model_isolation"),
    "NationalSecurityAgency/ghidra": ("static_analysis", "supply_chain"),
    "K-Dense-AI/scientific-agent-skills": ("research_agent", "evaluation"),
    "Comfy-Org/ComfyUI": ("visualization", "ui_research"),
    "agent-substrate/substrate": ("agent_orchestration",),
    "cporter202/API-mega-list": ("api_discovery",),
    "ar51an/unbound-dashboard": ("ui_research",),
    "cvxpy/cvxpy": ("quant_research", "optimization"),
}


class ContextError(ValueError):
    """Invalid, incomplete, unsafe or unproven source context."""


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContextError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise ContextError("nonfinite JSON constant")


def _read_json(path: str | Path) -> tuple[dict[str, Any], str]:
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ContextError("input must be a regular non-symlink file")
    size = source.stat().st_size
    if size == 0 or size > MAX_INPUT_BYTES:
        raise ContextError("input file size outside bounded range")
    payload = source.read_bytes()
    if len(payload) != size:
        raise ContextError("input changed while being read")
    try:
        parsed = json.loads(payload.decode("utf-8"), object_pairs_hook=_no_duplicates,
                            parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContextError("input is not strict UTF-8 JSON") from exc
    if not isinstance(parsed, dict):
        raise ContextError("input JSON must be an object")
    return parsed, hashlib.sha256(payload).hexdigest()


def _revision(value: str) -> str:
    if not isinstance(value, str) or not SHA_PATTERN.fullmatch(value):
        raise ContextError("a pinned 40-character repository commit is required")
    return value.lower()


def _repo_name(value: Any) -> str:
    if not isinstance(value, str) or not REPO_PATTERN.fullmatch(value):
        raise ContextError("invalid repository identity")
    if any(part in (".", "..") for part in value.split("/")):
        raise ContextError("invalid repository path component")
    return value


def _archive_dir(value: Any) -> str:
    if not isinstance(value, str) or "\\" in value:
        raise ContextError("invalid archive directory")
    path = PurePosixPath(value)
    if (path.is_absolute() or len(path.parts) != 2 or path.parts[0] != "source-repos"
            or path.parts[1] in (".", "..") or ".." in value.split("/")):
        raise ContextError("archive directory escapes source-repos")
    return value


def build_context(owner_inventory_path: str | Path, engine_federation_path: str | Path,
                  *, owner_revision: str, engine_revision: str) -> dict[str, Any]:
    """Join pinned real repository ledgers; never promote usage by assertion.

    Revisions identify checkout provenance supplied by the caller. This offline
    function does not independently attest remote GitHub revision or source
    archive contents; exact-checkout CI is a separate required gate.
    """
    owner_revision = _revision(owner_revision)
    engine_revision = _revision(engine_revision)
    inventory, inventory_sha = _read_json(owner_inventory_path)
    federation, federation_sha = _read_json(engine_federation_path)
    if inventory.get("schema_version") != "icarus-external-source-inventory-v1":
        raise ContextError("unknown owner inventory schema")
    if federation.get("schema_version") != "icarus-federated-repo-evidence-v1":
        raise ContextError("unknown Engine federation schema")
    archive = inventory.get("source_archive")
    counts = inventory.get("counts")
    rows = inventory.get("repo_entries")
    if not isinstance(archive, dict) or not isinstance(counts, dict) or not isinstance(rows, list):
        raise ContextError("missing source inventory fields")
    if (archive.get("filename") != "ICARUS-GitHub-source-snapshots.tar.zst"
            or archive.get("verified_actual_archive_sha256") is not True
            or not isinstance(archive.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", archive["sha256"])):
        raise ContextError("source archive verification checkpoint absent")
    if not isinstance(counts.get("distinct_identity_union"), int) or isinstance(counts.get("distinct_identity_union"), bool):
        raise ContextError("invalid inventory count")
    if len(rows) != counts["distinct_identity_union"] or len(rows) > 10000:
        raise ContextError("inventory identity count mismatch")
    if not isinstance(federation.get("repositories"), list):
        raise ContextError("missing Engine federation repositories")
    if federation.get("authority") != "RESEARCH_EVIDENCE_ONLY":
        raise ContextError("unexpected Engine evidence authority")

    federation_roles: dict[str, dict[str, Any]] = {}
    for item in federation["repositories"]:
        if not isinstance(item, dict):
            raise ContextError("invalid Engine federation row")
        name = _repo_name(item.get("repository"))
        key = name.casefold()
        if key in federation_roles:
            raise ContextError("duplicate Engine federation repository")
        evidence = item.get("evidence_paths")
        if not isinstance(evidence, list) or any(not isinstance(p, str) for p in evidence):
            raise ContextError("invalid Engine evidence paths")
        federation_roles[key] = {
            "repository": name,
            "role": str(item.get("role", "")),
            "data_authority": str(item.get("data_authority", "")),
            "evidence_path_count": len(evidence),
        }

    seen: set[str] = set()
    source_commit_groups: dict[str, list[str]] = {}
    output_rows: list[dict[str, Any]] = []
    verified_snapshots = 0
    named_only = 0
    for item in rows:
        if not isinstance(item, dict):
            raise ContextError("invalid external inventory row")
        name = _repo_name(item.get("repository"))
        key = name.casefold()
        if key in seen:
            raise ContextError("duplicate external repository identity")
        seen.add(key)
        snapshot = item.get("snapshot_verified")
        if type(snapshot) is not bool:
            raise ContextError("snapshot_verified must be boolean")
        commit = item.get("source_commit")
        directory = item.get("archive_directory")
        if snapshot:
            verified_snapshots += 1
            commit = _revision(commit)
            directory = _archive_dir(directory)
            if item.get("source_archive") != archive["filename"]:
                raise ContextError("snapshot archive mismatch")
            source_commit_groups.setdefault(commit, []).append(name)
        else:
            named_only += 1
            if commit is not None or directory is not None:
                raise ContextError("unverified snapshot claims pinned archive content")
        if item.get("installed") not in ("unverified", "missing", "downloaded_unverified"):
            raise ContextError("installed claim requires independent runtime verification")
        if item.get("actually_used_by_icarus") != "unverified":
            raise ContextError("runtime usage claim requires independent invocation proof")
        if item.get("exact_head_integration_ci") != "unverified":
            raise ContextError("exact-head CI claim requires independent workflow verification")
        licenses = item.get("source_license_filenames")
        if not isinstance(licenses, list) or any(not isinstance(x, str) for x in licenses):
            raise ContextError("invalid license filename list")
        members = item.get("source_list_membership")
        if not isinstance(members, list) or any(x not in ("all", "starred", "forked") for x in members):
            raise ContextError("invalid source list membership")
        output_rows.append({
            "repository": name,
            "source_url": f"https://github.com/{name}",
            "source_commit": commit,
            "source_archive": archive["filename"] if snapshot else None,
            "archive_directory": directory,
            "source_list_membership": sorted(set(members)),
            "source_license_filenames": licenses,
            "license_review_required": True,
            "snapshot_verified_by_source_audit": snapshot,
            "installation_status": item["installed"],
            "integration_stage": "inspected-source-snapshot" if snapshot else "discovered-name-only",
            "candidate_subsystems_not_verified": list(CANDIDATE_SUBSYSTEMS.get(name, ())),
            "engine_federation_role": federation_roles.get(key),
            "usage_status": "NOT_VERIFIED",
            "actually_invoked_by_icarus": False,
            "tested_exact_head": False,
            "training_authorized": False,
            "execution_authorized": False,
            "next_action": "independent license/API, pinned adapter, runtime invocation and exact-head CI evidence" if snapshot else "obtain authorized source checkout, license/API and runtime evidence",
        })
    if verified_snapshots != counts.get("verified_snapshot_repositories"):
        raise ContextError("snapshot count mismatch")
    if counts.get("installed_verified") != 0 or counts.get("actually_invoked_verified") != 0 or counts.get("exact_head_integration_verified") != 0:
        raise ContextError("source-only inventory cannot independently attest runtime usage")
    if counts.get("named_without_snapshot") != named_only:
        raise ContextError("named-only inventory count mismatch")
    if all(key in counts for key in ("distinct_named", "snapshot_not_named", "intersection_named_and_snapshot", "unique_pinned_source_commits")):
        if (counts["distinct_named"] != counts["named_without_snapshot"] + counts["intersection_named_and_snapshot"]
                or verified_snapshots != counts["intersection_named_and_snapshot"] + counts["snapshot_not_named"]
                or len(rows) != counts["distinct_named"] + counts["snapshot_not_named"]
                or len(source_commit_groups) != counts["unique_pinned_source_commits"]):
            raise ContextError("source-list/archive crosswalk counts inconsistent")
    for row in output_rows:
        commit = row["source_commit"]
        row["same_commit_identity_group"] = sorted(source_commit_groups[commit]) if commit else []
    return {
        "schema_version": SCHEMA,
        "authority": "READ_ONLY_SOURCE_CONTEXT_NO_TRAINING_NO_EXECUTION",
        "owner_inventory": {"repository": "reppiks490/icarus-owner-actions", "commit": owner_revision,
                            "file_sha256": inventory_sha, "archive_checkpoint_sha256": archive["sha256"],
                            "archive_reverified_by_this_consumer": False},
        "engine_federation": {"repository": "reppiks490/Icarus-engine", "commit": engine_revision,
                              "file_sha256": federation_sha, "roles": sorted(federation_roles.values(), key=lambda x: x["repository"])},
        "counts": {"discovered": len(output_rows), "accessible_source_snapshots": verified_snapshots,
                   "inspected_source_snapshots": verified_snapshots, "installed_verified": 0,
                   "eligible_license_cleared": 0, "adapter_integrated_verified": 0,
                   "actually_invoked_verified": 0, "tested_exact_head_verified": 0,
                   "blocked_for_verified_usage": len(output_rows),
                   "distinct_source_commits": len(source_commit_groups),
                   "candidate_mapped_not_integrated": sum(bool(r["candidate_subsystems_not_verified"]) for r in output_rows)},
        "external_repositories": sorted(output_rows, key=lambda x: x["repository"].casefold()),
        "policy": {"runtime_usage_requires": ["pinned source", "license and dependency review",
                   "actual ICARUS callsite", "real invocation receipt", "independent exact-head CI"],
                   "forks_same_commit_not_independent_capability": True,
                   "market_edge_claim_allowed": False,
                   "execution_authorized": False},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ICARUS read-only external capability context")
    parser.add_argument("--owner-inventory", required=True)
    parser.add_argument("--engine-federation", required=True)
    parser.add_argument("--owner-revision", required=True)
    parser.add_argument("--engine-revision", required=True)
    parser.add_argument("--expect-discovered", type=int)
    parser.add_argument("--expect-snapshots", type=int)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)
    try:
        context = build_context(args.owner_inventory, args.engine_federation,
                                owner_revision=args.owner_revision, engine_revision=args.engine_revision)
        if args.expect_discovered is not None and context["counts"]["discovered"] != args.expect_discovered:
            raise ContextError("expected discovered count mismatch")
        if args.expect_snapshots is not None and context["counts"]["accessible_source_snapshots"] != args.expect_snapshots:
            raise ContextError("expected snapshot count mismatch")
    except (ContextError, OSError) as exc:
        parser.exit(2, f"capability context BLOCKED: {exc}\n")
    print(json.dumps(context["counts"] if args.summary else context, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
