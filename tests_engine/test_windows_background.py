"""Check Windows launch flags at the real worker-to-process boundary."""
import subprocess
import sys
from types import SimpleNamespace

import pytest

from icarus_engine import code_provenance, unzip_batches
from icarus_engine.trainers import xgb_slot
from icarus_plant import supervisor


NO_WINDOW = 0x08000000
NEW_PROCESS_GROUP = 0x00000200


@pytest.mark.parametrize("operation", ["provenance", "trainer", "csv_fetch"])
def test_background_git_launches_never_create_windows_console(monkeypatch, tmp_path, operation):
    monkeypatch.delenv("ICARUS_GIT_SHA", raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", NO_WINDOW, raising=False)

    def execute(command, **kwargs):
        assert kwargs.get("creationflags", 0) & NO_WINDOW, command
        assert command[0] == "git"
        out = "" if "status" in command else "a" * 40 + "\n"
        return subprocess.CompletedProcess(command, 0, out, "")

    monkeypatch.setattr(subprocess, "run", execute)
    if operation == "provenance":
        result = code_provenance.local_code_provenance(tmp_path)
        assert result["commit"] == "a" * 40 and result["clean"] is True
    elif operation == "trainer":
        assert xgb_slot.revision() == "a" * 40
    else:
        assert unzip_batches.fetch_repo(tmp_path / "csv-data") == tmp_path / "csv-data"


def test_supervised_windows_worker_keeps_group_and_hides_console(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", NO_WINDOW, raising=False)
    monkeypatch.setattr(subprocess, "CREATE_NEW_PROCESS_GROUP", NEW_PROCESS_GROUP, raising=False)
    # Keep filesystem behavior real while selecting the Windows process branch.
    import os
    monkeypatch.setattr(supervisor, "os", SimpleNamespace(name="nt", environ=os.environ, path=os.path))

    def launch(command, **kwargs):
        assert kwargs["creationflags"] & NO_WINDOW
        assert kwargs["creationflags"] & NEW_PROCESS_GROUP
        assert kwargs["stdout"].name == str(tmp_path / "logs" / "worker.log")
        assert kwargs["stderr"] == subprocess.STDOUT
        return SimpleNamespace(pid=404)

    monkeypatch.setattr(subprocess, "Popen", launch)
    plant = supervisor.Plant(str(tmp_path), repo=str(tmp_path))
    service = supervisor.Service(name="worker", argv=["python", "worker.py"], cwd=str(tmp_path), health_url="")
    plant.spawn(service)
    assert service.popen.pid == 404


def test_posix_background_git_has_no_windows_flags(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")

    def execute(command, **kwargs):
        assert kwargs.get("creationflags", 0) == 0
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", execute)
    assert unzip_batches.fetch_repo(tmp_path / "csv-data") == tmp_path / "csv-data"


@pytest.mark.skipif(sys.platform != "win32", reason="requires real Windows console API")
def test_real_background_child_has_no_console_window():
    from icarus_engine.process_launch import background_kwargs
    result = subprocess.run(
        [sys.executable, "-c", "import ctypes; print(ctypes.windll.kernel32.GetConsoleWindow())"],
        capture_output=True, text=True, check=True, timeout=10,
        **background_kwargs(),
    )
    assert result.stdout.strip() == "0"
