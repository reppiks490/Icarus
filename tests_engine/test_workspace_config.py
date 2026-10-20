"""Persisted workspace settings stay scoped, recoverable and revisioned."""
import copy
import json
from types import SimpleNamespace

import pytest

from icarus_engine import paper_workspaces


@pytest.fixture
def manager_factory(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_FEED", "file")
    monkeypatch.setattr(paper_workspaces, "_PROFILE_DEFAULTS", tuple(
        {**p, "assets": ["NQ", "ES"]} for p in paper_workspaces._PROFILE_DEFAULTS))
    monkeypatch.setattr(paper_workspaces.WorkspacePortfolio, "start", lambda self: None)
    feed = SimpleNamespace(ticker=lambda _s: 100.0)
    parent = SimpleNamespace(base_dir=str(tmp_path), poll_sec=5, profile="nq", preset=None,
                             warmup_bars=1200, pts_ref_symbol="NQ", pts_ref_price=100.0,
                             feeds={"yahoo": feed, "coinbase": feed})
    created = []

    def make(*, start=False):
        manager = paper_workspaces.PaperWorkspaceManager(parent)
        created.append(manager)
        if start:
            manager.start()
            for portfolio in manager.portfolios.values():
                for runner in portfolio.runner_list():
                    runner._init_strategy(100)
                    runner.warm = True
        return manager

    yield make
    for manager in reversed(created):
        manager.stop()


def _legacy(manager):
    value = copy.deepcopy(manager.profiles["cc1"])
    for key in ("schema_version", "config_revision", "asset_overrides"):
        value.pop(key, None)
    value["inputs"] = {"tp1_pts": 9.0}
    raw = (json.dumps(value, separators=(",", ":")) + "\n\n").encode()
    manager._path("cc1").write_bytes(raw)
    return value, raw


def test_legacy_record_migrates_without_changing_values_or_bytes(manager_factory):
    first = manager_factory()
    legacy, original = _legacy(first)
    manager = manager_factory(start=True)
    migrated = manager.profiles["cc1"]
    assert {k: migrated[k] for k in legacy} == legacy
    assert migrated.get("schema_version") == 2
    assert migrated.get("config_revision") == 0
    assert migrated.get("asset_overrides") == {}
    assert manager._path("cc1").read_bytes() == original
    manager.update("cc1", {"inputs": {"tp2_pts": 30.0}})
    backup = manager.root / "cc1.pre-v2.json"
    assert backup.read_bytes() == original
    manager.update("cc1", {"inputs": {"tp2_pts": 40.0}})
    assert backup.read_bytes() == original
    reloaded = manager_factory()
    assert reloaded.profiles["cc1"]["inputs"] == {"tp1_pts": 9.0, "tp2_pts": 40.0}


def test_new_record_has_explicit_schema_and_independent_override_maps(manager_factory):
    manager = manager_factory()
    for profile in manager.profiles.values():
        saved = json.loads(manager._path(profile["id"]).read_text())
        assert saved.get("schema_version") == 2
        assert saved.get("config_revision") == 0
        assert saved.get("asset_overrides") == {}
    manager.profiles["cc1"]["asset_overrides"]["NQ"] = {"inputs": {"tp1_pts": 7}}
    assert manager.profiles["cc2"]["asset_overrides"] == {}


@pytest.mark.parametrize("patch", [
    {"schema_version": 999}, {"schema_version": True}, {"schema_version": "2"},
    {"config_revision": -1}, {"config_revision": True}, {"config_revision": 1.5},
    {"unexpected_setting": 4}, {"inputs": {"unknown_input": 4}},
    {"asset_overrides": []}, {"asset_overrides": {"UNKNOWN": {"inputs": {}}}},
    {"asset_overrides": {"NQ": {"unknown_setting": True}}},
    {"asset_overrides": {"NQ": {"inputs": {"tp1_pts": float("nan")}}}},
    {"asset_overrides": {"NQ": {"inputs": {"use_tide": "yes"}}}},
    {"asset_overrides": {"NQ": {"inputs": {"unknown_input": 2}}}},
    {"asset_overrides": {"NQ": {"chart": {"timeframe": "banana"}}}},
    {"asset_overrides": {"NQ": {"chart": {"fill_on": "invented"}}}},
    {"asset_overrides": {"NQ": {"preset": "../outside"}}},
])
def test_future_schema_and_unknown_fields_fail_closed(manager_factory, patch):
    manager = manager_factory()
    saved = copy.deepcopy(manager.profiles["cc1"])
    saved.update(patch)
    raw = json.dumps(saved).encode()
    manager._path("cc1").write_bytes(raw)
    with pytest.raises(ValueError):
        manager_factory()
    assert manager._path("cc1").read_bytes() == raw
