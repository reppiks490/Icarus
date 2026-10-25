"""Selected-workspace INTUITION import never crosses the research boundary."""
from __future__ import annotations

import hashlib
from pathlib import Path
from threading import Event
import time

import pytest

from tests_engine.test_workspace_api import workspace_http  # noqa: F401

def _seed_verified_pair(root, monkeypatch, producer):
    import icarus_engine.learning_fabric as fabric_module
    from icarus_engine.learning_fabric import LearningFabric
    from tests_engine.test_learning_fabric import _prediction

    receipts = iter(("2026-10-01T14:00:01Z", "2026-10-01T14:05:01Z"))
    monkeypatch.setattr(fabric_module, "_utc_now", lambda: next(receipts, "2026-10-25T12:00:00Z"))
    fabric = LearningFabric(root)
    body = _prediction(producer=producer)
    body.update({
        "prediction": "up",
        "metadata": {
            "venue": "CME", "timeframe_seconds": 60, "chart": "heikin_ashi",
            "execution_basis": "real_price", "feature_schema": "direction-v1",
            "session_id": producer + "-session",
            "intuition_target_contract": "direction",
        },
    })
    prediction = fabric.record_prediction(body)["prediction"]
    fabric.record_outcome({
        "prediction_id": prediction["prediction_id"],
        "observed_at": "2026-10-01T14:05:00Z",
        "actual_value": 102.0,
        "evidence": [producer + ":matured-outcome"],
    })
    path = fabric.path
    fabric.close()
    return path


def _wait(adapter, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = adapter.snapshot()
        if state["import_job"]["status"] not in {"RUNNING", "PENDING"}:
            return state
        time.sleep(0.01)
    raise AssertionError("INTUITION import job did not finish within the test deadline")


def test_import_is_explicit_selected_workspace_idempotent_and_source_read_only(tmp_path, monkeypatch):
    from icarus_engine.intuition_omega.workspace_adapter import IntuitionWorkspaceAdapter

    selected = tmp_path / "cc1" / "subsystems"
    sibling = tmp_path / "cc2" / "subsystems"
    source = _seed_verified_pair(selected, monkeypatch, "cc1-source")
    _seed_verified_pair(sibling, monkeypatch, "cc2-source")
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    adapter = IntuitionWorkspaceAdapter(selected, workspace_id="cc1")

    initial = adapter.snapshot()
    assert initial["learning_source"]["state"] == "AVAILABLE"
    assert initial["ledger"]["state"] == "NOT_INITIALIZED"
    assert initial["import_job"]["status"] == "NOT_STARTED"
    assert initial["execution_authorized"] is False
    assert not (selected / "intuition-omega" / "forecasts.sqlite3").exists()

    accepted = adapter.start_import()
    assert accepted["status"] == "RUNNING"
    finished = _wait(adapter)
    assert finished["import_job"]["status"] == "COMPLETED"
    assert finished["import_job"]["result"]["imported"] == 1, finished["import_job"]["result"].get("rejected_by_reason")
    assert finished["import_job"]["result"]["source_mutated"] is False
    assert finished["execution_authorized"] is False
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    assert (selected / "intuition-omega" / "forecasts.sqlite3").is_file()
    assert not (sibling / "intuition-omega" / "forecasts.sqlite3").exists()

    repeated = adapter.start_import()
    assert repeated["status"] == "RUNNING"
    second = _wait(adapter)
    assert second["import_job"]["result"]["imported"] == 0
    assert second["import_job"]["result"]["already_present"] == 1
    adapter.close()


def test_status_read_does_not_create_learning_or_intuition_databases(tmp_path):
    from icarus_engine.intuition_omega.workspace_adapter import IntuitionWorkspaceAdapter

    selected = tmp_path / "cc3" / "subsystems"
    adapter = IntuitionWorkspaceAdapter(selected, workspace_id="cc3")
    state = adapter.snapshot()
    assert state["status"] == "NOT_INITIALIZED"
    assert state["learning_source"]["state"] == "NOT_INITIALIZED"
    assert state["ledger"]["state"] == "NOT_INITIALIZED"
    assert state["source_mutated"] is False
    assert not (selected / "research" / "learning.sqlite3").exists()
    assert not (selected / "intuition-omega" / "forecasts.sqlite3").exists()


def test_closing_adapter_cancels_the_background_import(tmp_path, monkeypatch):
    from icarus_engine.learning_fabric import LearningFabric
    import icarus_engine.intuition_omega.workspace_adapter as adapter_module

    root = tmp_path / "cc1" / "subsystems"
    fabric = LearningFabric(root)
    fabric.close()
    started = Event()

    def waiting_import(source, destination, *, as_of, cancelled):
        started.set()
        while not cancelled():
            time.sleep(0.001)
        raise InterruptedError("cancelled by adapter close")

    monkeypatch.setattr(adapter_module, "import_verified_learning_pairs", waiting_import)
    adapter = adapter_module.IntuitionWorkspaceAdapter(root, workspace_id="cc1")
    adapter.start_import()
    assert started.wait(2)
    adapter.close()
    assert adapter.snapshot()["import_job"]["status"] == "CANCELLED"


def test_selected_import_action_is_owner_and_revision_gated(workspace_http):
    from icarus_engine.learning_fabric import LearningFabric

    server, parent, request = workspace_http
    selected_root = server.command_centers.root / "cc1" / "subsystems"
    source = LearningFabric(selected_root)
    source.close()

    action = "/admin/command-centers/cc1/panels/intuition-omega/import-learning"
    assert request(action, body={})[0] == 400
    viewer = request("/admin/access/add", body={"label": "intuition-viewer"})[1]["user"]["token"]
    headers = {"X-Icarus-Config-Revision": "0"}
    assert request(action, body={}, token=viewer, extra_headers=headers)[0] == 403

    code, accepted, _ = request(action, body={}, extra_headers=headers)
    assert code == 200, accepted
    assert accepted["workspace_id"] == "cc1"
    assert accepted["execution_authorized"] is False
    assert accepted["production_decision_authorized"] is False

    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        code, observed, _ = request("/api/command-centers/cc1/panels/intuition-omega")
        assert code == 200, observed
        if observed["import_job"]["status"] == "COMPLETED":
            break
        time.sleep(0.01)
    else:
        pytest.fail("selected workspace Learning import did not complete")

    assert observed["workspace_id"] == "cc1"
    assert observed["import_job"]["result"]["total_examined"] == 0
    assert source.path.is_file()
    assert (selected_root / "intuition-omega" / "forecasts.sqlite3").is_file()
    assert not (server.command_centers.root / "cc2" / "subsystems" / "intuition-omega" / "forecasts.sqlite3").exists()
    assert not (Path(parent.base_dir) / "intuition-omega" / "forecasts.sqlite3").exists()
