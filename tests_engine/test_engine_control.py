from pathlib import Path

import pytest

from icarus_engine.engine_control import ControlAction, EngineControlPlane
from icarus_engine.system_audit import load_repository_audit


def test_control_plane_status_isolated_and_truthful(tmp_path: Path):
    cp = EngineControlPlane(
        tmp_path,
        snapshotters={
            "ok": lambda: {"status": "green"},
            "bad": lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        },
        actions={
            "noop": ControlAction(
                "noop", "No-op", "Test", "test action", lambda payload: {"payload": payload}
            )
        },
    )
    status = cp.status()
    assert status["schema_version"] == "icarus-engine-control-v1"
    assert status["authority"]["application_control"] is True
    assert status["authority"]["arbitrary_shell"] is False
    assert status["authority"]["broker_arming"] is False
    assert status["summary"]["registered_actions"] == 1
    assert status["summary"]["subsystem_errors"] == 1
    assert status["subsystems"]["ok"]["status"] == "ok"
    assert status["subsystems"]["bad"]["status"] == "error"


def test_registered_action_runs_and_records_audit(tmp_path: Path):
    seen = []

    def handler(payload):
        seen.append(payload)
        return {"done": True}

    cp = EngineControlPlane(
        tmp_path,
        snapshotters={},
        actions={
            "asset.pause": ControlAction(
                "asset.pause", "Pause", "Assets", "pause asset", handler, target="asset"
            )
        },
    )
    out = cp.run({
        "action": "asset.pause",
        "target": "nq",
        "reason": "operator test",
    })
    assert out["ok"] is True
    assert out["target"] == "NQ"
    assert seen[0]["target"] == "NQ"
    audit = load_repository_audit(tmp_path)
    assert audit["events"][0]["kind"] == "integration"
    assert audit["events"][0]["severity"] == "success"
    assert "Engine Control" in audit["events"][0]["title"]


def test_job_target_identity_is_not_uppercased(tmp_path: Path):
    seen = []
    cp = EngineControlPlane(
        tmp_path,
        snapshotters={},
        actions={
            "research.cancel": ControlAction(
                "research.cancel", "Cancel", "Research", "cancel job",
                lambda payload: seen.append(payload) or {"ok": True},
                target="job",
            )
        },
    )
    cp.run({"action": "research.cancel", "target": "job-AbC-123"})
    assert seen[0]["target"] == "job-AbC-123"


def test_dangerous_action_requires_exact_confirmation(tmp_path: Path):
    cp = EngineControlPlane(
        tmp_path,
        snapshotters={},
        actions={
            "danger": ControlAction(
                "danger", "Danger", "Test", "dangerous", lambda _: {"ok": True},
                danger=True, confirmation="DO IT",
            )
        },
    )
    with pytest.raises(ValueError, match="requires exact confirmation"):
        cp.run({"action": "danger"})
    with pytest.raises(ValueError, match="requires exact confirmation"):
        cp.run({"action": "danger", "confirm": "do it"})
    assert cp.run({"action": "danger", "confirm": "DO IT"})["ok"] is True


def test_control_request_rejects_unknown_fields_and_bad_target_shape(tmp_path: Path):
    cp = EngineControlPlane(
        tmp_path,
        snapshotters={},
        actions={
            "noop": ControlAction("noop", "No-op", "Test", "noop", lambda _: None),
            "asset": ControlAction("asset", "Asset", "Test", "asset", lambda _: None, target="asset"),
        },
    )
    with pytest.raises(ValueError, match="unknown control fields"):
        cp.run({"action": "noop", "surprise": 1})
    with pytest.raises(ValueError, match="does not accept a target"):
        cp.run({"action": "noop", "target": "NQ"})
    with pytest.raises(ValueError, match="requires target"):
        cp.run({"action": "asset"})


def test_action_registry_key_must_match_action_id(tmp_path: Path):
    with pytest.raises(ValueError, match="registry keys"):
        EngineControlPlane(
            tmp_path,
            snapshotters={},
            actions={"wrong": ControlAction("right", "Right", "Test", "x", lambda _: None)},
        )


def test_failed_action_is_audited(tmp_path: Path):
    def fail(_):
        raise RuntimeError("expected")

    cp = EngineControlPlane(
        tmp_path,
        snapshotters={},
        actions={"fail": ControlAction("fail", "Fail", "Test", "fails", fail)},
    )
    with pytest.raises(RuntimeError, match="expected"):
        cp.run({"action": "fail"})
    audit = load_repository_audit(tmp_path)
    assert audit["events"][0]["severity"] == "error"
    assert "Engine Control failed" in audit["events"][0]["title"]
