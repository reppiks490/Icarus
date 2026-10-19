"""Archive restoration checks using only temporary synthetic ciphertext."""
import base64
import errno
import json
import os
from pathlib import Path
import stat
import sys
import zlib

import pytest

pytest.importorskip("cryptography")
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from tools import provider_archive as archive
from tools import provider_exhaustive_collection as collection


@pytest.fixture
def restore_args(tmp_path, monkeypatch):
    key = bytes(range(32))
    nonce = bytes(range(12))
    data = {"synthetic": [1, 2, 3]}
    payload = zlib.compress(json.dumps(data).encode())
    encrypted = tmp_path / "fixture.enc"
    encrypted.write_bytes(nonce + AESGCM(key).encrypt(nonce, payload, b"test-run:fmp:fixture"))
    output = tmp_path / "private" / "restored.json"
    monkeypatch.setenv("ICARUS_DATA_ARCHIVE_KEY", base64.b64encode(key).decode())
    monkeypatch.setattr(sys, "argv", ["provider_archive", "--provider", "fmp", "--run-id", "test-run",
                                      "--archive", str(encrypted), "--output", str(output)])
    return encrypted, output, data


def test_restores_authenticated_json_without_printing_payload(restore_args, capsys):
    _, output, data = restore_args
    archive.main()
    assert json.loads(output.read_text(encoding="utf-8")) == data
    assert "synthetic" not in capsys.readouterr().out


@pytest.mark.skipif(os.name != "posix", reason="POSIX mode bits; Windows uses directory ACLs")
def test_plaintext_is_private_before_the_first_write(restore_args, monkeypatch):
    _, output, data = restore_args
    original_dump = json.dump
    observed = []

    def inspect_write(value, stream, **kwargs):
        observed.append(stat.S_IMODE(os.fstat(stream.fileno()).st_mode))
        assert observed[-1] == 0o600
        return original_dump(value, stream, **kwargs)

    monkeypatch.setattr(archive.json, "dump", inspect_write)
    previous_umask = os.umask(0)
    try:
        archive.main()
    finally:
        os.umask(previous_umask)
    assert observed == [0o600]
    assert json.loads(output.read_text()) == data
    assert stat.S_IMODE(output.stat().st_mode) == 0o600


@pytest.mark.parametrize("symlink", [False, True])
def test_existing_output_is_never_overwritten(restore_args, symlink):
    _, output, _ = restore_args
    output.parent.mkdir()
    existing = output
    if symlink:
        existing = output.parent / "existing.json"
        try:
            output.symlink_to(existing)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks unavailable")
    existing.write_text("preserve this file")
    with pytest.raises(FileExistsError):
        archive.main()
    assert existing.read_text() == "preserve this file"
    assert output.is_symlink() is symlink


@pytest.mark.parametrize("failure", ["ciphertext", "key", "aad"])
def test_decryption_failure_creates_no_output(restore_args, monkeypatch, failure):
    encrypted, output, _ = restore_args
    if failure == "ciphertext":
        payload = encrypted.read_bytes()
        encrypted.write_bytes(payload[:-1] + bytes([payload[-1] ^ 1]))
    elif failure == "key":
        monkeypatch.setenv("ICARUS_DATA_ARCHIVE_KEY", base64.b64encode(b"x" * 32).decode())
    else:
        monkeypatch.setattr(sys, "argv", [value if value != "test-run" else "other-run" for value in sys.argv])
    from cryptography.exceptions import InvalidTag
    with pytest.raises(InvalidTag):
        archive.main()
    assert not output.parent.exists()


@pytest.mark.parametrize("key_name", ["TWELVE_DATA_API_KEY", "TWELVEDATA_API_KEY", "TWELVE_API_KEY"])
def test_existing_provider_credential_aliases_remain_compatible(tmp_path, key_name):
    data = {"synthetic": [1, 2, 3]}
    assert collection.archive(tmp_path, "test-run", "twelve", "fixture", data, {}, "synthetic-key") == "ENCRYPTED_AES256_GCM"
    encrypted = next(tmp_path.rglob("*.enc"))
    assert archive.decrypt(encrypted.read_bytes(), "twelve", "test-run", "fixture",
                           {key_name: "synthetic-key"}) == data


def test_partial_write_failure_removes_plaintext_and_closes_stream(restore_args, monkeypatch):
    _, output, _ = restore_args
    streams = []

    def fail_write(value, stream, **kwargs):
        streams.append(stream)
        stream.write("partial synthetic plaintext")
        stream.flush()
        raise OSError("synthetic write failure")

    monkeypatch.setattr(archive.json, "dump", fail_write)
    with pytest.raises(OSError, match="synthetic write failure"):
        archive.main()
    assert streams[0].closed
    assert not output.exists()


def test_stream_construction_failure_closes_descriptor_and_removes_output(restore_args, monkeypatch):
    _, output, _ = restore_args
    descriptors = []

    def fail_fdopen(fd, *args, **kwargs):
        descriptors.append(fd)
        raise OSError("synthetic stream construction failure")

    original_unlink = Path.unlink

    def inspect_cleanup(path, *args, **kwargs):
        if path == output:
            # Windows cannot remove a file while its descriptor is still open.
            with pytest.raises(OSError) as closed:
                os.fstat(descriptors[0])
            assert closed.value.errno == errno.EBADF
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(archive.os, "fdopen", fail_fdopen)
    monkeypatch.setattr(Path, "unlink", inspect_cleanup)
    with pytest.raises(OSError, match="synthetic stream construction failure"):
        archive.main()
    assert len(descriptors) == 1
    with pytest.raises(OSError) as closed:
        os.fstat(descriptors[0])
    assert closed.value.errno == errno.EBADF
    assert not output.exists()
