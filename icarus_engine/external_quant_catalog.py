"""Read-only, quarantine-only external research artifact catalog audit.

This module verifies caller-supplied bytes and provenance *claims*, not their
real-world authenticity, license entitlement, data freshness or trading value.
No third-party modules, network, broker, model or collector are invoked.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

SCHEMA = "icarus-external-quant-catalog-v1"
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z")
SEGMENT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\Z")
DENIED = ("rights_verified", "source_authenticity_verified", "holdout_approved", "execution_authorized")
ARTIFACT_KEYS = frozenset({
    "artifact_id", "path", "sha256", "size_bytes", "source_repository",
    "source_revision", "license_id", *DENIED,
})


class CatalogRejected(ValueError):
    """The candidate fails the quarantine-only integrity contract."""


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise CatalogRejected(message)


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _nonfinite(value: str):
    raise CatalogRejected("nonfinite JSON number")


def _is_real_directory(path: Path) -> bool:
    return path.is_dir() and not path.is_symlink()


def _safe_file(root: Path, relative: str) -> Path:
    _require(isinstance(relative, str) and relative and "\\" not in relative,
             "artifact path must be relative POSIX text")
    pure = PurePosixPath(relative)
    parts = relative.split("/")
    _require(not pure.is_absolute() and all(SEGMENT.fullmatch(part) for part in parts),
             "artifact path contains unsafe component")
    _require(all(part not in (".", "..") and not part.startswith(".") for part in parts),
             "artifact path is hidden or traverses directories")
    cursor = root
    for part in parts[:-1]:
        cursor = cursor / part
        _require(_is_real_directory(cursor), "artifact ancestor is not a real directory")
    result = cursor / parts[-1]
    _require(result.is_file() and not result.is_symlink(), "artifact is missing or a symlink")
    return result


def _sha256_and_size(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    count = 0
    try:
        with path.open("rb") as source:
            _require(stat.S_ISREG(os.fstat(source.fileno()).st_mode),
                     "artifact must be regular")
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
                count += len(chunk)
    except OSError as exc:
        raise CatalogRejected("artifact cannot be read") from exc
    return digest.hexdigest(), count


def verify_catalog(root: Path, *, expected_producer_repository: str,
                   expected_producer_revision: str) -> dict[str, object]:
    """Verify every declared artifact without writing or admitting it to ICARUS.

    Expected producer identity must come from an independently trusted record;
    matching caller-provided strings does not authenticate a GitHub commit.
    """
    _require(isinstance(expected_producer_repository, str)
             and REPOSITORY.fullmatch(expected_producer_repository) is not None,
             "invalid expected producer repository")
    _require(isinstance(expected_producer_revision, str)
             and HEX40.fullmatch(expected_producer_revision) is not None,
             "expected producer revision must be a lowercase full commit SHA")
    root = Path(root)
    _require(_is_real_directory(root), "catalog root must be a real directory")
    manifest_path = _safe_file(root, "catalog.json")
    try:
        raw_bytes = manifest_path.read_bytes()
        manifest = json.loads(raw_bytes.decode("utf-8"), object_pairs_hook=_unique,
                              parse_constant=_nonfinite)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CatalogRejected("invalid catalog JSON") from exc
    _require(isinstance(manifest, dict) and set(manifest) == {
        "schema_version", "producer_repository", "producer_revision", "artifacts"
    }, "catalog top-level fields mismatch")
    _require(manifest["schema_version"] == SCHEMA, "catalog schema mismatch")
    _require(manifest["producer_repository"] == expected_producer_repository
             and manifest["producer_revision"] == expected_producer_revision,
             "catalog producer identity mismatch")
    artifacts = manifest["artifacts"]
    _require(isinstance(artifacts, list) and len(artifacts) > 0,
             "catalog requires at least one artifact")
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    sources: set[tuple[str, str]] = set()
    bytes_verified = 0
    for artifact in artifacts:
        _require(isinstance(artifact, dict) and set(artifact) == ARTIFACT_KEYS,
                 "artifact fields mismatch")
        identifier = artifact["artifact_id"]
        _require(isinstance(identifier, str) and IDENTIFIER.fullmatch(identifier) is not None
                 and identifier not in seen_ids, "invalid or duplicate artifact id")
        seen_ids.add(identifier)
        path_text = artifact["path"]
        _require(isinstance(path_text, str) and path_text not in seen_paths,
                 "duplicate artifact path")
        seen_paths.add(path_text)
        _require(path_text.casefold() != "catalog.json", "manifest cannot be its own artifact")
        _require(isinstance(artifact["sha256"], str)
                 and HEX64.fullmatch(artifact["sha256"]) is not None,
                 "invalid SHA-256")
        _require(type(artifact["size_bytes"]) is int and artifact["size_bytes"] >= 0,
                 "invalid artifact size")
        repo = artifact["source_repository"]
        revision = artifact["source_revision"]
        license_id = artifact["license_id"]
        _require(isinstance(repo, str) and REPOSITORY.fullmatch(repo) is not None
                 and isinstance(revision, str) and HEX40.fullmatch(revision) is not None,
                 "source requires repository and full revision")
        _require(isinstance(license_id, str) and IDENTIFIER.fullmatch(license_id) is not None,
                 "source license must be explicitly identified")
        for flag in DENIED:
            _require(artifact[flag] is False, f"{flag} must remain false in quarantine")
        file_path = _safe_file(root, path_text)
        actual_sha, actual_size = _sha256_and_size(file_path)
        _require(actual_sha == artifact["sha256"] and actual_size == artifact["size_bytes"],
                 f"artifact integrity mismatch: {identifier}")
        bytes_verified += actual_size
        sources.add((repo, revision))
    return {
        "schema_version": "icarus-external-quant-catalog-receipt-v1",
        "manifest_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "producer_repository": expected_producer_repository,
        "producer_revision": expected_producer_revision,
        "artifacts_rechecked": len(seen_ids),
        "bytes_rechecked": bytes_verified,
        "distinct_source_revisions": len(sources),
        "source_authenticity_verified": False,
        "entitlement_verified": False,
        "training_approved": False,
        "execution_authorized": False,
        "authority_granted": "NONE",
        "research_admission": "QUARANTINED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--producer-repository", required=True)
    parser.add_argument("--producer-revision", required=True)
    args = parser.parse_args(argv)
    try:
        receipt = verify_catalog(args.root,
            expected_producer_repository=args.producer_repository,
            expected_producer_revision=args.producer_revision)
    except CatalogRejected as exc:
        parser.exit(2, f"REJECTED: {exc}\n")
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
