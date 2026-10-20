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


def test_asset_resolution_uses_only_its_workspace_overrides_and_shared_preset(manager_factory):
    manager = manager_factory()
    parent_override = manager.root.parent / "inputs.NQ.json"
    parent_override.write_text('{"tp1_pts":999}')
    preset = manager.root.parent / "presets" / "workspace-example.json"
    preset.parent.mkdir(exist_ok=True)
    preset.write_text('{"tp1_pts":13,"tp2_pts":29}')
    profile = copy.deepcopy(manager.profiles["cc1"])
    profile["inputs"] = {"tp1_pts": 11}
    profile["asset_overrides"] = {
        "NQ": {"inputs": {"tp1_pts": 17}, "chart": {"timeframe": "10"},
               "preset": "workspace-example"}}
    manager._path("cc1").write_text(json.dumps(profile))
    running = manager_factory(start=True)
    nq = running.portfolios["cc1"].runners["NQ"]
    es = running.portfolios["cc1"].runners["ES"]
    assert nq.inputs_base.tp1_pts == 17
    assert nq.inputs_base.tp2_pts == 29
    assert nq.cfg.preset == "workspace-example"
    assert nq.spec.chart_tf == "10"
    assert nq.spec.chart_type == profile["chart"]["chart_type"]
    assert es.inputs_base.tp1_pts == 11
    assert es.spec.chart_tf == profile["chart"]["timeframe"]
    assert running.portfolios["cc3"].runners["NQ"].inputs_base.tp1_pts != 17
    assert parent_override.read_text() == '{"tp1_pts":999}'


def test_asset_edit_reconfigures_only_its_effective_values_and_survives_reload(manager_factory):
    manager = manager_factory(start=True)
    portfolio = manager.portfolios["cc1"]
    nq, es = (portfolio.runners[s] for s in ("NQ", "ES"))
    es_before = es.inputs_base.to_dict()
    sibling_file = manager._path("cc2").read_bytes()
    manager.update("cc1", {"asset_overrides": {"NQ": {"inputs": {"tp1_pts": 17}}}})
    assert nq.inputs_base.tp1_pts == 17
    assert es.inputs_base.to_dict() == es_before
    assert manager._path("cc2").read_bytes() == sibling_file
    assert not (manager.root.parent / "inputs.NQ.json").exists()
    reloaded = manager_factory(start=True)
    assert reloaded.portfolios["cc1"].runners["NQ"].inputs_base.tp1_pts == 17
    assert reloaded.portfolios["cc1"].runners["ES"].inputs_base.to_dict() == es_before


def _unusual_saved_bytes(manager):
    raw = (json.dumps(manager.profiles["cc1"], separators=(",", ":")) + "\n\n").encode()
    manager._path("cc1").write_bytes(raw)
    return raw


def test_replay_failure_restores_exact_saved_bytes_and_old_runners(manager_factory, monkeypatch):
    manager = manager_factory(start=True)
    original = _unusual_saved_bytes(manager)
    portfolio = manager.portfolios["cc1"]
    runners = dict(portfolio.runners)
    before = {s: r.inputs_base.to_dict() for s, r in runners.items()}
    sibling = manager._path("cc2").read_bytes()

    def reject_replay(*_args, **_kwargs):
        raise RuntimeError("injected replay failure")

    monkeypatch.setattr(runners["ES"], "rewarm", reject_replay)
    with pytest.raises(RuntimeError, match="injected replay"):
        manager.update("cc1", {"inputs": {"tp1_pts": 19}})
    assert manager._path("cc1").read_bytes() == original
    assert portfolio.runners == runners
    assert {s: r.inputs_base.to_dict() for s, r in runners.items()} == before
    assert manager._path("cc2").read_bytes() == sibling


def test_late_persistence_failure_restores_exact_file_and_runtime(manager_factory, monkeypatch):
    manager = manager_factory(start=True)
    original = _unusual_saved_bytes(manager)
    portfolio = manager.portfolios["cc1"]
    before = {s: r.inputs_base.to_dict() for s, r in portfolio.runners.items()}
    original_save = manager._save

    def save_then_fail(profile):
        original_save(profile)
        raise OSError("injected post-replace failure")

    monkeypatch.setattr(manager, "_save", save_then_fail)
    with pytest.raises(OSError, match="post-replace"):
        manager.update("cc1", {"inputs": {"tp1_pts": 19}})
    assert manager._path("cc1").read_bytes() == original
    assert {s: r.inputs_base.to_dict() for s, r in portfolio.runners.items()} == before


@pytest.mark.parametrize("pending", ["open", "_pending_entries", "_pending_closes"])
def test_asset_edit_retains_flat_workspace_guard(manager_factory, pending):
    manager = manager_factory(start=True)
    portfolio = manager.portfolios["cc1"]
    original = _unusual_saved_bytes(manager)
    getattr(portfolio.runners["ES"].em, pending).append(object())
    with pytest.raises(ValueError, match="flatten|pending"):
        manager.update("cc1", {"asset_overrides": {"NQ": {"inputs": {"tp1_pts": 17}}}})
    assert portfolio.runners["NQ"].inputs_base.tp1_pts != 17
    assert manager._path("cc1").read_bytes() == original


def test_workspace_rejects_inherited_parent_rewarm_writer(manager_factory):
    manager = manager_factory(start=True)
    parent_override = manager.root.parent / "inputs.NQ.json"
    with pytest.raises(ValueError, match="workspace"):
        manager.portfolios["cc1"].rewarm_asset("NQ", {"tp1_pts": 17}, persist=True)
    assert not parent_override.exists()


def test_preset_edit_and_reset_restore_original_asset_properties(manager_factory):
    manager = manager_factory(start=True)
    portfolio = manager.portfolios["cc1"]
    nq = portfolio.runners["NQ"]
    commission = nq.spec.commission
    preset = manager.root.parent / "presets" / "commission-example.json"
    preset.parent.mkdir(exist_ok=True)
    preset.write_text('{"tp1_pts":17,"_meta":{"commission":77}}')
    manager.update("cc1", {"asset_overrides": {"NQ": {"preset": "commission-example"}}})
    assert nq.cfg.preset == "commission-example"
    assert nq.spec.commission == 77
    manager.update("cc1", {"asset_overrides": {}})
    assert nq.cfg.preset is None
    assert nq.spec.commission == commission
