"""Fail-closed, read-only audit of pinned external source snapshots.

This module NEVER imports, executes, extracts or installs repository code. It
checks source-archive integrity and produces evidence for later integration.
Source presence is not installation, invocation, or a validated integration.

Usage:
    python tools/external_execution_archive_audit.py \
        --manifest ICARUS_GitHub_snapshot_manifest.json \
        --archive ICARUS-GitHub-source-snapshots.tar.zst \
        --output external_execution_archive_audit.json

Only the Python standard library is required, except the installed zstd
executable for streaming a .tar.zst. The archive is never extracted.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import posixpath
import re
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_EXECUTION_SIGNALS = {
    "market_microstructure": ("orderbook", "order-book", "mbo", "mbp", "mdp", "depth", "dbn", "tick"),
    "execution_research": ("backtest", "nautilus", "kungfu", "quantopian", "vectorbt", "simulat"),
    "numerical_optimization": ("cvxpy", "optimizer", "optimization", "risk", "portfolio"),
    "data_client_or_parser": ("databento", "secdef", "datamine", "cme"),
}


class AuditError(ValueError):
    """Invalid or untrusted source evidence; never silently downgrade to success."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_archive_path(name: str) -> bool:
    """Reject absolute, Windows-style and traversal paths before normalization."""
    if not name or name.startswith(("/", "\\")) or "\\" in name or "\x00" in name:
        return False
    parts = name.rstrip("/").split("/")
    return all(part not in ("", ".", "..") for part in parts)


def _safe_repo_dir(directory: str) -> bool:
    return (
        isinstance(directory, str)
        and _safe_archive_path(directory)
        and directory.startswith("source-repos/")
        and len(directory.split("/")) == 2
    )


def _safe_link(member: tarfile.TarInfo, repo_root: str) -> bool:
    """Symlinks may be internal; links escaping their own repo are unsafe."""
    if not member.issym() and not member.islnk():
        return True
    target = member.linkname
    if not target or target.startswith(("/", "\\")) or "\\" in target or "\x00" in target:
        return False
    # Tar hard links use archive-root paths; symlinks use parent-relative paths.
    resolved = posixpath.normpath(
        target if member.islnk() else posixpath.join(posixpath.dirname(member.name), target)
    )
    return resolved == repo_root or resolved.startswith(repo_root + "/")


def load_manifest(path: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuditError(f"Cannot parse source manifest: {exc}") from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("repositories"), list):
        raise AuditError("Manifest requires a repositories array")
    archive = manifest.get("archive")
    if not isinstance(archive, dict) or not _SHA256.fullmatch(str(archive.get("sha256", ""))):
        raise AuditError("Manifest requires a pinned archive SHA-256")
    if not isinstance(archive.get("bytes"), int) or archive["bytes"] <= 0:
        raise AuditError("Manifest requires positive archive byte length")
    if not isinstance(archive.get("entries"), int) or archive["entries"] < 1:
        raise AuditError("Manifest requires positive snapshot repository count")
    repos: dict[str, dict[str, Any]] = {}
    identities: set[str] = set()
    for entry in manifest["repositories"]:
        if not isinstance(entry, dict):
            raise AuditError("Repository entry is not an object")
        repo = entry.get("repository")
        directory = entry.get("directory")
        commit = entry.get("commit")
        if not isinstance(repo, str) or not _REPO.fullmatch(repo):
            raise AuditError(f"Invalid repository identity: {repo!r}")
        if not _safe_repo_dir(directory):
            raise AuditError(f"Unsafe or non-canonical repository directory: {directory!r}")
        if not isinstance(commit, str) or not _COMMIT.fullmatch(commit):
            raise AuditError(f"Repository {repo} lacks a pinned full commit SHA")
        if repo in identities or directory in repos:
            raise AuditError(f"Duplicate repository identity or archive directory: {repo}")
        identities.add(repo)
        if not isinstance(entry.get("license_files_at_root"), list):
            raise AuditError(f"Repository {repo} missing license-file inventory")
        if entry.get("snapshot_included") is not True:
            raise AuditError(f"Repository {repo} listed without included snapshot")
        repos[directory] = entry
    if len(repos) != archive["entries"]:
        raise AuditError("Snapshot count differs from manifest archive.entries")
    return manifest, repos


def _repo_signals(repository: str) -> list[str]:
    name = repository.lower()
    return sorted(
        label for label, needles in _EXECUTION_SIGNALS.items() if any(n in name for n in needles)
    )


def audit_archive(
    manifest_path: Path, archive_path: Path, *, max_members: int = 2_000_000
) -> dict[str, Any]:
    """Verify a local archive against its pinned manifest without extraction.

    Fail closed for corrupt/truncated archives, unsafe paths, escaping symlinks,
    missing/unlisted repositories, and unsupported TAR member types.
    """
    manifest, repos = load_manifest(manifest_path)
    if archive_path.suffixes[-2:] != [".tar", ".zst"]:
        raise AuditError("Only .tar.zst archives are supported")
    try:
        actual_bytes = archive_path.stat().st_size
    except OSError as exc:
        raise AuditError(f"Archive unavailable: {exc}") from exc
    if actual_bytes != manifest["archive"]["bytes"]:
        raise AuditError(f"Archive size mismatch: expected {manifest['archive']['bytes']}, got {actual_bytes}")
    actual_sha = _sha256_file(archive_path)
    if actual_sha != manifest["archive"]["sha256"]:
        raise AuditError("Archive SHA-256 does not match pinned manifest")

    per_repo: dict[str, dict[str, int]] = {
        directory: {"members": 0, "files": 0, "file_bytes": 0, "symlinks": 0}
        for directory in repos
    }
    errors: list[str] = []
    member_count = 0
    zstd = subprocess.Popen(
        ["zstd", "-dc", "--", str(archive_path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        assert zstd.stdout is not None
        with tarfile.open(fileobj=zstd.stdout, mode="r|") as tar:
            for member in tar:
                member_count += 1
                if member_count > max_members:
                    raise AuditError("Archive member limit exceeded")
                name = member.name.rstrip("/")
                if not _safe_archive_path(name):
                    errors.append(f"Unsafe archive member: {member.name[:200]}")
                    continue
                if name == "source-repos":
                    if not member.isdir():
                        errors.append("Source root is not a directory")
                    continue
                parts = name.split("/")
                if len(parts) < 2 or parts[0] != "source-repos":
                    errors.append(f"Unexpected archive member: {name[:200]}")
                    continue
                root = "/".join(parts[:2])
                if root not in repos:
                    errors.append(f"Unmanifested repository directory: {root[:200]}")
                    continue
                counts = per_repo[root]
                counts["members"] += 1
                if member.isfile():
                    counts["files"] += 1
                    counts["file_bytes"] += member.size
                elif member.isdir():
                    pass
                elif member.issym() or member.islnk():
                    counts["symlinks"] += 1
                    if not _safe_link(member, root):
                        errors.append(f"Repository-escaping link: {name[:200]}")
                else:
                    errors.append(f"Unsupported archive member type: {name[:200]}")
        zstd.stdout.close()
        stderr = zstd.stderr.read(2000) if zstd.stderr else b""
        code = zstd.wait()
        if code != 0:
            raise AuditError(f"zstd failed (exit {code}): {stderr.decode('utf-8', 'replace')[:200]}")
    except (tarfile.TarError, OSError, EOFError) as exc:
        raise AuditError(f"Cannot safely parse TAR stream: {exc}") from exc
    finally:
        if zstd.poll() is None:
            zstd.kill()
            zstd.wait()
        if zstd.stdout:
            zstd.stdout.close()
        if zstd.stderr:
            zstd.stderr.close()
    for root, counts in per_repo.items():
        if counts["members"] == 0 or counts["files"] == 0:
            errors.append(f"Repository snapshot missing/empty: {root}")
    if errors:
        raise AuditError("Archive member validation failed: " + "; ".join(errors[:8]))

    commit_groups: dict[str, list[str]] = collections.defaultdict(list)
    rows: list[dict[str, Any]] = []
    for directory, entry in sorted(repos.items()):
        commit_groups[entry["commit"]].append(entry["repository"])
        counts = per_repo[directory]
        rows.append({
            "repository": entry["repository"],
            "archive_directory": directory,
            "source_commit": entry["commit"],
            "source_snapshot_verified": True,
            "root_license_file_present": bool(entry["license_files_at_root"]),
            "license_review_required": True,
            "capability_candidates_from_name_only": _repo_signals(entry["repository"]),
            "members": counts["members"],
            "regular_files": counts["files"],
            "regular_file_bytes": counts["file_bytes"],
            "symlinks_confined_to_repository": counts["symlinks"],
            "installed": "unverified",
            "integration_stage": "source-snapshot-verified",
            "icarus_runtime_invocation_verified": False,
            "exact_head_integration_test_verified": False,
        })
    return {
        "schema_version": "icarus-external-source-audit-v1",
        "evidence_kind": "source-integrity-only-not-market-or-integration-evidence",
        "archive": {
            "filename": archive_path.name,
            "bytes": actual_bytes,
            "sha256": actual_sha,
            "tar_members": member_count,
            "snapshot_repositories": len(repos),
            "unique_pinned_source_commits": len(commit_groups),
            "duplicate_commit_groups": [sorted(names) for names in commit_groups.values() if len(names) > 1],
            "repositories_missing_root_license_file": sum(
                not row["root_license_file_present"] for row in rows
            ),
            "confined_symlinks": sum(row["symlinks_confined_to_repository"] for row in rows),
        },
        "acceptance_counts": {
            "source_snapshots_verified": len(repos),
            "source_commits_distinct": len(commit_groups),
            "installed_verified": 0,
            "actually_invoked_by_icarus_verified": 0,
            "exact_head_integrations_verified": 0,
            "target_distinct_verified_used": 80,
        },
        "repositories": rows,
        "limitations": [
            "This checks archive/manifest integrity only; no source code was executed or installed.",
            "A root license filename is not legal clearance; every license needs review.",
            "A fork and its upstream sharing one commit are not two independent capabilities.",
            "No local owner Windows/WSL 100+GB repository locations are asserted accessible.",
            "No market data or empirical execution/fill performance is validated.",
        ],
    }



def attach_repository_lists(report: dict[str, Any], paths: list[Path]) -> dict[str, Any]:
    """Crosswalk operator's named repos against pinned snapshots, without usage claims.

    Lists are plain UTF-8 lines containing owner/repo. Blank lines and # comments
    are ignored. The source lists remain unmodified, and duplicate names are
    deduplicated across all lists. The result is not installation evidence.
    """
    named: set[str] = set()
    sources: list[dict[str, Any]] = []
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            raise AuditError(f"Cannot read repository list {path.name}: {exc}") from exc
        items: set[str] = set()
        for line_number, raw in enumerate(lines, 1):
            value = raw.strip()
            if not value or value.startswith("#"):
                continue
            if not _REPO.fullmatch(value):
                raise AuditError(f"Invalid repository identity in {path.name} line {line_number}")
            items.add(value)
        sources.append({"filename": path.name, "distinct_repositories": len(items)})
        named.update(items)
    archived = {row["repository"] for row in report["repositories"]}
    report["repository_list_sources"] = sources
    report["named_repository_crosswalk"] = {
        "distinct_named": len(named),
        "distinct_snapshot_only": len(archived - named),
        "distinct_union": len(archived | named),
        "named_with_verified_snapshot": len(named & archived),
        "named_without_verified_snapshot": sorted(named - archived),
        "snapshot_not_in_named_lists": sorted(archived - named),
        "unverified_names_are_not_installed_or_used": True,
    }
    report["acceptance_counts"]["named_or_snapshotted_distinct"] = len(archived | named)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Write machine-readable audit report; stdout otherwise")
    parser.add_argument("--repository-list", type=Path, action="append", default=[], help="Additional owner/repo text inventory; repeatable")
    args = parser.parse_args(argv)
    try:
        report = audit_archive(args.manifest, args.archive)
        if args.repository_list:
            attach_repository_lists(report, args.repository_list)
    except (AuditError, FileNotFoundError) as exc:
        print(f"SOURCE_AUDIT_BLOCKED: {exc}", file=sys.stderr)
        return 2
    content = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        # Explicit caller-chosen output; never write into source archive.
        if args.output.resolve() in (args.manifest.resolve(), args.archive.resolve()):
            print("SOURCE_AUDIT_BLOCKED: output would overwrite source evidence", file=sys.stderr)
            return 2
        args.output.write_text(content, encoding="utf-8")
    else:
        sys.stdout.write(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
