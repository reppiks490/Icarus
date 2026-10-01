from pathlib import Path

import pytest

from icarus_engine.engine_control import ControlAction, EngineControlPlane
from icarus_engine.system_audit import load_repository_audit


def test_control_plane_status_isolated_and_truthful(tmp_path: Path):
    cp = EngineControlPlane(
        tmp_path,
        snapshotters={
            "ok": lambda: {"status": "green"},
            "warn": lambda: {"status": "unverified"},
            "reported_bad": lambda: {"status": "degraded"},
            "bad": lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        },
        actions={
            "noop": ControlAction(
                "noop", "No-op", "Test", "test action", lambda payload: {"payload": payload}
            )
        },
    )
    status = cp.status()
    assert status["schema_version"] == "icarus-engine-control-v2"
    assert status["authority"]["application_control"] is True
    assert status["authority"]["arbitrary_shell"] is False
    assert status["authority"]["broker_arming"] is False
    assert status["summary"]["registered_actions"] == 1
    assert status["summary"]["action_groups"] == {"Test": 1}
    assert status["summary"]["subsystem_errors"] == 2
    assert status["summary"]["subsystem_warnings"] == 1
    assert status["subsystems"]["ok"]["status"] == "ok"
    assert status["subsystems"]["warn"]["status"] == "warn"
    assert status["subsystems"]["reported_bad"]["status"] == "error"
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


def test_intent_is_durable_before_handler_mutates(tmp_path: Path):
    observed = {}

    def handler(_payload):
        audit = load_repository_audit(tmp_path)
        observed["event"] = audit["events"][0]
        return {"done": True}

    cp = EngineControlPlane(
        tmp_path,
        snapshotters={},
        actions={"mutate": ControlAction("mutate", "Mutate", "Test", "mutate", handler)},
    )
    out = cp.run({"action": "mutate"})
    assert out["ok"] is True
    assert observed["event"]["severity"] == "info"
    assert "requested" in observed["event"]["title"].lower()
    assert "status=REQUESTED" in observed["event"]["detail"]


def test_failed_intent_write_prevents_mutation(tmp_path: Path, monkeypatch):
    import icarus_engine.engine_control as mod

    called = {"handler": False}

    def handler(_payload):
        called["handler"] = True
        return {}

    def fail_write(*_args, **_kwargs):
        raise OSError("audit unavailable")

    monkeypatch.setattr(mod, "append_system_event", fail_write)
    cp = EngineControlPlane(
        tmp_path,
        snapshotters={},
        actions={"mutate": ControlAction("mutate", "Mutate", "Test", "mutate", handler)},
    )
    with pytest.raises(OSError, match="audit unavailable"):
        cp.run({"action": "mutate"})
    assert called["handler"] is False


def test_final_audit_failure_reports_partial_audit_without_repeating_mutation(tmp_path: Path, monkeypatch):
    import icarus_engine.engine_control as mod

    real_append = mod.append_system_event
    calls = {"append": 0, "handler": 0}

    def flaky_append(*args, **kwargs):
        calls["append"] += 1
        if calls["append"] == 2:
            raise OSError("final audit unavailable")
        return real_append(*args, **kwargs)

    def handler(_payload):
        calls["handler"] += 1
        return {"changed": True}

    monkeypatch.setattr(mod, "append_system_event", flaky_append)
    cp = EngineControlPlane(
        tmp_path,
        snapshotters={},
        actions={"mutate": ControlAction("mutate", "Mutate", "Test", "mutate", handler)},
    )
    out = cp.run({"action": "mutate"})
    assert calls["handler"] == 1
    assert out["ok"] is True
    assert out["audit_recorded"] is False
    assert "final audit unavailable" in out["audit_error"]
    audit = load_repository_audit(tmp_path)
    assert "requested" in audit["events"][0]["title"].lower()


def test_control_request_rejects_nonfinite_json(tmp_path: Path):
    cp = EngineControlPlane(
        tmp_path,
        snapshotters={},
        actions={"noop": ControlAction("noop", "No-op", "Test", "noop", lambda _: {})},
    )
    with pytest.raises(ValueError, match="finite JSON"):
        cp.run({"action": "noop", "args": {"x": float("nan")}})


def test_control_action_identity_and_handler_are_validated():
    with pytest.raises(ValueError, match="canonical lowercase"):
        ControlAction("Bad Action", "Bad", "Test", "x", lambda _: None)
    with pytest.raises(TypeError, match="handler"):
        ControlAction("bad.handler", "Bad", "Test", "x", None)  # type: ignore[arg-type]


def test_control_request_rejects_falsey_non_object_args(tmp_path: Path):
    cp = EngineControlPlane(
        tmp_path,
        snapshotters={},
        actions={"noop": ControlAction("noop", "No-op", "Test", "noop", lambda _: {})},
    )
    with pytest.raises(ValueError, match="args must be an object"):
        cp.run({"action": "noop", "args": []})
    with pytest.raises(ValueError, match="args must be an object"):
        cp.run({"action": "noop", "args": ""})
    assert cp.run({"action": "noop", "args": None})["ok"] is True


def test_control_action_publishes_argument_template_and_extended_target_types():
    for target in ("candidate", "proposal", "source"):
        action = ControlAction(
            f"test.{target}", "Test", "Test", "x", lambda _: None,
            target=target, args_example={"x": 1},
        )
        public = action.public()
        assert public["target"] == target
        assert public["args_example"] == {"x": 1}

    with pytest.raises(ValueError, match="unsupported target"):
        ControlAction("test.bad", "Bad", "Test", "x", lambda _: None, target="shell")


def test_control_action_rejects_nonfinite_argument_template():
    with pytest.raises(ValueError, match="args_example"):
        ControlAction(
            "test.nan", "Bad", "Test", "x", lambda _: None,
            args_example={"x": float("nan")},
        )
