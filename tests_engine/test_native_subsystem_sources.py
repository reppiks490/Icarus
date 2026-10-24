from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "icarus_engine" / "native_subsystems"
PREFIX = "icarus_engine.native_subsystems._divine"
SOURCE_REVISION = "27ae69c593ede3019957100cd401625bd2424f43"
EXPECTED = {
    "_divine/nexus/contracts.py": (
        "systems/nexus/src/nexus/contracts.py",
        "e9fac11f0d205571e18930813693c6fb0f378d67",
        "3d9918e9a8fa658ae1ef6290efcab5dc287c8bd07c421a47274d6efa6c2e6877",
    ),
    "_divine/nexus/source_health.py": (
        "systems/nexus/src/nexus/source_health.py",
        "f884e9d911f3933d4a26b430ae033458adf3a1ce",
        "84a5f0ea2f1906779c51acc44f7ed67597c2f0780846a3d7fac3b8348f81db77",
    ),
    "_divine/aion/contracts.py": (
        "systems/aion/aion/contracts.py",
        "a3c4cd6d74577d9ff94e148cecd698c6b425f4cb",
        "3de1b91c4bcbc70b1730ee735fe3a1031c4ff8a777e030757e9c2e87e13e649a",
    ),
    "_divine/aion/store.py": (
        "systems/aion/aion/store.py",
        "a0fa57cdbfa0ef77f053bcfeeb7c92074f2a2714",
        "f2c816215e3a4d45aa5419c857fffd9693a67fd83f03f4ea53eea5c73ad374b6",
    ),
}


def test_native_sources_match_canonical_git_blobs_and_manifest():
    manifest = json.loads((NATIVE / "source_manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_repository"] == "reppiks490/divine-providence"
    assert manifest["source_revision"] == SOURCE_REVISION
    assert manifest["source_tree"] == "bde186e028d14f79a70b4408e3d94a79d3bc32c7"
    assert manifest["upstream_python_requires"] == ">=3.11"
    assert manifest["embedded_python_requires"] == ">=3.10"
    assert manifest["upstream_license_file"] is None
    assert manifest["upstream_license_status"] == "not_declared_in_pinned_tree"
    assert {row["path"] for row in manifest["files"]} == set(EXPECTED)
    for row in manifest["files"]:
        source_path, blob, sha256 = EXPECTED[row["path"]]
        raw = (NATIVE / row["path"]).read_bytes()
        actual_blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
        assert row["source_path"] == source_path
        assert actual_blob == row["git_blob_sha"] == blob
        assert hashlib.sha256(raw).hexdigest() == row["sha256"] == sha256
        assert row["size_bytes"] == len(raw)
    assert (NATIVE / "ATTRIBUTION.md").is_file()


SMOKE = r"""
import json
from pathlib import Path
import sys
from icarus_engine.native_subsystems._divine.nexus.contracts import VectorEvent
from icarus_engine.native_subsystems._divine.nexus.source_health import SourceHealthRegistry
from icarus_engine.native_subsystems._divine.aion.contracts import EvidenceTier, Observation, SourceSpec
from icarus_engine.native_subsystems._divine.aion.store import EventStore

assert 'numpy' not in sys.modules and 'pandas' not in sys.modules
event = VectorEvent('runtime:main:BTC', 100, 0, (('observed', 1.0),),
                    'icarus:cached-summary', available_ns=120,
                    availability_basis='observed_receipt')
registry = SourceHealthRegistry()
registry.observe(event, received_ns=120)
plane = registry.snapshot(120)
assert plane.verify()
assert plane.healthy_fraction is None
assert plane.unknown_slo_streams == ('runtime:main:BTC',)
path = Path(sys.argv[1]) / 'native.sqlite3'
store = EventStore(path)
source = SourceSpec('runtime:main:BTC', 'icarus.runtime-health.v1', 'BTC',
                    ('context',), EvidenceTier.CANDLE_PROXY, 'a' * 64,
                    origin='icarus_runtime_monitor')
store.register(source)
observation = Observation(source.source_id, 'health:one', 1, 'context', 100,
                          120, 120, EvidenceTier.CANDLE_PROXY, plane.to_dict())
receipt = store.append(observation)
del store
reopened = EventStore(path)
assert reopened.verify_chain()['verified']
assert reopened.verify_chain()['events'] == 1
assert reopened.asof(119) == []
assert reopened.asof(120)[0]['event_hash'] == receipt['event_hash']
print(json.dumps({'python': list(sys.version_info[:3]), 'native_chain_verified': True,
                  'receipt_time_gated': True, 'stdlib_only': True}))
"""


def _smoke(python: str, directory: Path) -> dict:
    environment = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(
        [python, "-S", "-c", SMOKE, str(directory)],
        cwd=directory,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_native_import_and_persistence_need_only_the_standard_library(tmp_path):
    assert _smoke(sys.executable, tmp_path)["stdlib_only"] is True


def test_windows_autocrlf_checkout_preserves_pinned_native_bytes(tmp_path):
    original = tmp_path / "original"
    original.mkdir()
    environment = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)

    def git(*args, cwd=original):
        result = subprocess.run(
            ["git", *args], cwd=cwd, env=environment, capture_output=True,
            text=True, timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    git("init", "-q")
    git("config", "user.name", "Native checkout verification")
    git("config", "user.email", "native-checkout@example.invalid")
    git("config", "core.autocrlf", "false")
    shutil.copyfile(ROOT / ".gitattributes", original / ".gitattributes")
    for relative in EXPECTED:
        target = original / "icarus_engine" / "native_subsystems" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((NATIVE / relative).read_bytes())
    git("add", ".")
    git("commit", "-qm", "canonical source bytes")
    checkout = tmp_path / "windows-checkout"
    git("clone", "-q", "--no-local", "--no-checkout", str(original), str(checkout))
    git("config", "core.autocrlf", "true", cwd=checkout)
    git("checkout", "-q", "HEAD", cwd=checkout)
    for relative, (_, _, sha256) in EXPECTED.items():
        raw = (checkout / "icarus_engine" / "native_subsystems" / relative).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == sha256


def test_native_cores_run_on_actual_python310(tmp_path):
    python = os.environ.get("ICARUS_NATIVE_PYTHON310")
    if python is None:
        python = sys.executable if sys.version_info[:2] == (3, 10) else shutil.which("python3.10")
    if not python:
        pytest.skip("set ICARUS_NATIVE_PYTHON310 to exercise the actual Python 3.10 runtime")
    result = _smoke(python, tmp_path)
    assert result["python"][:2] == [3, 10]
    assert result["native_chain_verified"] is True


def test_native_health_and_aion_reopen_preserve_receipt_time_and_revisions(tmp_path):
    nexus = importlib.import_module(PREFIX + ".nexus.contracts")
    health = importlib.import_module(PREFIX + ".nexus.source_health")
    aion = importlib.import_module(PREFIX + ".aion.contracts")
    stores = importlib.import_module(PREFIX + ".aion.store")
    registry = health.SourceHealthRegistry()
    event = nexus.VectorEvent("runtime:main:BTC", 100, 0, (("observed", 1.0),),
                              "icarus:cached-summary", available_ns=120,
                              availability_basis="observed_receipt")
    registry.observe(event, received_ns=120)
    plane = registry.snapshot(120)
    assert plane.verify()
    assert plane.healthy_fraction is None
    assert plane.unknown_slo_streams == (event.stream_id,)
    tampered = plane.to_dict()
    tampered["stream_count"] = 99
    assert not health.SourceHealthPlane.from_dict(tampered).verify()

    path = tmp_path / "aion.sqlite3"
    store = stores.EventStore(path)
    spec = aion.SourceSpec(event.stream_id, "icarus.runtime-health.v1", "BTC",
                           ("context",), aion.EvidenceTier.CANDLE_PROXY, "a" * 64,
                           origin="icarus_runtime_monitor")
    store.register(spec)
    observation = aion.Observation(spec.source_id, "health:one", 1, "context", 100,
                                   120, 120, aion.EvidenceTier.CANDLE_PROXY, plane.to_dict())
    original = store.append(observation)
    original_chain = store.verify_chain()
    del store
    reopened = stores.EventStore(path)
    assert reopened.verify_chain() == original_chain
    assert reopened.asof(119) == []
    assert reopened.asof(120)[0]["event_hash"] == original["event_hash"]
    assert reopened.append(observation)["idempotent"] is True
    assert reopened.verify_chain()["events"] == 1

    revised = aion.Observation(spec.source_id, "health:one", 2, "context", 100,
                               150, 150, aion.EvidenceTier.CANDLE_PROXY, {"revised": True})
    reopened.append(revised)
    assert reopened.verify_chain()["events"] == 2
    assert reopened.asof(120)[0]["event"]["revision"] == 1
    assert reopened.asof(150)[0]["event"]["revision"] == 2
    with pytest.raises(ValueError, match="observed receipt"):
        aion.Observation(spec.source_id, "backdated", 1, "context", 100,
                         120, 150, aion.EvidenceTier.CANDLE_PROXY, {})
