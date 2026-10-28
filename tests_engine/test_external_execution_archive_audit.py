"""Mechanics-only fixtures: these do not represent market data or integrations."""

import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from external_execution_archive_audit import (  # noqa: E402
    AuditError,
    _safe_archive_path,
    _safe_link,
    audit_archive,
    load_manifest,
    main,
)


def _fixture(tmp_path, *, files=None, links=None, manifest_sha=None):
    files = files if files is not None else {"source-repos/vendor__engine/engine.py": b"print('not executed')"}
    links = links or {}
    tar_path = tmp_path / "sources.tar"
    with tarfile.open(tar_path, "w") as archive:
        for name, data in files.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            archive.addfile(entry, io.BytesIO(data))
        for name, target in links.items():
            entry = tarfile.TarInfo(name)
            entry.type = tarfile.SYMTYPE
            entry.linkname = target
            archive.addfile(entry)
    zst_path = tmp_path / "sources.tar.zst"
    with zst_path.open("wb") as out:
        subprocess.run(["zstd", "-q", "-c", str(tar_path)], stdout=out, check=True)
    digest = hashlib.sha256(zst_path.read_bytes()).hexdigest()
    manifest = {
        "archive": {"filename": "sources.tar.zst", "bytes": zst_path.stat().st_size,
                    "sha256": manifest_sha or digest, "entries": 1},
        "repositories": [{"repository": "vendor/engine", "directory": "source-repos/vendor__engine",
                          "commit": "a" * 40, "license_files_at_root": ["LICENSE"],
                          "snapshot_included": True}],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path, zst_path


def test_realistic_snapshot_is_not_a_used_integration(tmp_path):
    manifest, archive = _fixture(tmp_path)
    result = audit_archive(manifest, archive)
    assert result["acceptance_counts"]["source_snapshots_verified"] == 1
    assert result["acceptance_counts"]["actually_invoked_by_icarus_verified"] == 0
    assert result["acceptance_counts"]["exact_head_integrations_verified"] == 0
    assert result["repositories"][0]["installed"] == "unverified"


def test_sha_mismatch_blocks(tmp_path):
    manifest, archive = _fixture(tmp_path, manifest_sha="0" * 64)
    with pytest.raises(AuditError, match="SHA-256"):
        audit_archive(manifest, archive)


def test_traversal_and_absolute_paths_block(tmp_path):
    for name in ("source-repos/vendor__engine/../../escape.py", "/tmp/escape.py", "C:\\escape.py"):
        manifest, archive = _fixture(tmp_path, files={name: b"no"})
        with pytest.raises(AuditError, match="validation failed"):
            audit_archive(manifest, archive)


def test_internal_symlink_allowed_and_escape_blocked(tmp_path):
    manifest, archive = _fixture(tmp_path, links={"source-repos/vendor__engine/README.md": "engine.py"})
    assert audit_archive(manifest, archive)["archive"]["confined_symlinks"] == 1
    manifest, archive = _fixture(tmp_path, links={"source-repos/vendor__engine/README.md": "../../outside"})
    with pytest.raises(AuditError, match="Repository-escaping"):
        audit_archive(manifest, archive)


def test_unmanifested_directory_blocks(tmp_path):
    manifest, archive = _fixture(tmp_path, files={"source-repos/other__repo/engine.py": b"no"})
    with pytest.raises(AuditError, match="Unmanifested"):
        audit_archive(manifest, archive)


def test_unsafe_manifest_directory_blocks(tmp_path):
    manifest, _ = _fixture(tmp_path)
    payload = json.loads(manifest.read_text())
    payload["repositories"][0]["directory"] = "source-repos/../outside"
    manifest.write_text(json.dumps(payload))
    with pytest.raises(AuditError, match="non-canonical"):
        load_manifest(manifest)


def test_output_cannot_overwrite_archive_or_manifest(tmp_path):
    manifest, archive = _fixture(tmp_path)
    assert main(["--manifest", str(manifest), "--archive", str(archive), "--output", str(manifest)]) == 2
    assert load_manifest(manifest)[0]["archive"]["entries"] == 1


def test_missing_archive_blocks(tmp_path):
    manifest, archive = _fixture(tmp_path)
    archive.unlink()
    assert main(["--manifest", str(manifest), "--archive", str(archive)]) == 2


def test_symlink_normalization():
    member = tarfile.TarInfo("source-repos/vendor__engine/lib/LICENSE")
    member.type = tarfile.SYMTYPE
    member.linkname = "../LICENSE"
    assert _safe_link(member, "source-repos/vendor__engine")
    member.linkname = "../../../LICENSE"
    assert not _safe_link(member, "source-repos/vendor__engine")
    assert not _safe_archive_path("source-repos/vendor__engine/../evil")
