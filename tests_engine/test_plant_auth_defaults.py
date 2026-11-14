from __future__ import annotations

import pytest


def test_engine_service_requires_token_and_keeps_it_out_of_argv(monkeypatch, tmp_path):
    from icarus_plant.supervisor import default_engine_service

    monkeypatch.delenv("ICARUS_TOKEN", raising=False)
    monkeypatch.delenv("ICARUS_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    with pytest.raises(ValueError, match="ICARUS_TOKEN"):
        default_engine_service(str(tmp_path), "/repo", offline=True)

    service = default_engine_service(str(tmp_path), "/repo", offline=True, token="private-test-token")
    assert service.env["ICARUS_TOKEN"] == "private-test-token"
    assert "private-test-token" not in service.argv
    assert "--token" not in service.argv


def test_legacy_owner_token_environment_is_accepted_but_placeholders_are_rejected(monkeypatch):
    from icarus_engine.access_control import configured_owner_token, resolve_owner_token

    monkeypatch.setenv("ICARUS_TOKEN", "icarus")
    monkeypatch.setenv("ICARUS_ADMIN_TOKEN", "legacy-explicit-test-secret")
    assert configured_owner_token() == "legacy-explicit-test-secret"
    monkeypatch.setenv("ICARUS_TOKEN", "replace-me-too")
    monkeypatch.delenv("ICARUS_ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("ADMIN_TOKEN", "change-me-too")
    assert configured_owner_token() == ""
    with pytest.raises(ValueError, match="non-placeholder"):
        resolve_owner_token("icarus")


def test_plant_start_refuses_missing_token_before_health_or_service(monkeypatch, tmp_path):
    import icarus_plant.cli as cli

    monkeypatch.delenv("ICARUS_TOKEN", raising=False)
    monkeypatch.delenv("ICARUS_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    monkeypatch.setattr(cli, "health_ok", lambda *_args, **_kwargs: pytest.fail("health must not be probed"))
    monkeypatch.setattr(cli, "default_engine_service", lambda *_args, **_kwargs: pytest.fail("service must not start"))
    with pytest.raises(SystemExit, match="ICARUS_TOKEN"):
        cli.main(["start", "--root", str(tmp_path), "--no-downloads"])


def test_active_plant_launchers_do_not_advertise_or_forward_fixed_token():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    paths = ("icarus_plant/guide.py", "icarus_plant/cli.py", "icarus_plant/supervisor.py",
             "start-plant.sh", "start-plant.ps1", "start-yahoo.ps1", "scripts/start-as-is.sh")
    for relative in paths:
        source = (root / relative).read_text(encoding="utf-8")
        assert "token: icarus" not in source.lower(), relative
        assert "${ICARUS_TOKEN:-icarus}" not in source, relative
        assert "--token" not in source, relative
