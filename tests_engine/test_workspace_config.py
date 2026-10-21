"""Persisted workspace settings stay scoped, recoverable and revisioned."""
import copy
import json
from types import SimpleNamespace

import pytest

from icarus_engine import paper_workspaces
from icarus_engine.pine.timeframe import Bar


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


def _track_replays(monkeypatch, portfolio):
    calls = []
    for symbol, runner in portfolio.runners.items():
        original = runner.rewarm
        def recorded(*args, _symbol=symbol, _original=original, **kwargs):
            calls.append(_symbol)
            return _original(*args, **kwargs)
        monkeypatch.setattr(runner, "rewarm", recorded)
    return calls


def test_asset_edit_preserves_unrelated_runner_engine_cutover_and_cached_views(manager_factory, monkeypatch):
    manager = manager_factory(start=True)
    portfolio = manager.portfolios["cc1"]
    es = portfolio.runners["ES"]
    es.live_from_ts = 1234
    es.publish_read_views()
    prior = (es.em, es.strat, es.inputs_base, es.live_from_ts, copy.deepcopy(es._public_views))
    calls = _track_replays(monkeypatch, portfolio)
    manager.update_asset("cc1", "NQ", {"expected_revision": 0, "inputs": {"tp1_pts": 17}})
    assert calls == ["NQ"], "one asset edit must not replay its unrelated sibling"
    assert es.em is prior[0] and es.strat is prior[1] and es.inputs_base is prior[2]
    assert es.live_from_ts == prior[3] and es._public_views == prior[4]


def test_batch_override_edit_replays_only_changed_admitted_symbols(manager_factory, monkeypatch):
    manager = manager_factory(start=True)
    manager.update_asset("cc1", "ES", {"expected_revision": 0, "inputs": {"tp1_pts": 33}})
    portfolio = manager.portfolios["cc1"]
    calls = _track_replays(monkeypatch, portfolio)
    overrides = copy.deepcopy(manager.profiles["cc1"]["asset_overrides"])
    overrides["NQ"] = {"inputs": {"tp1_pts": 17}}
    manager.update("cc1", {"expected_revision": 1, "asset_overrides": overrides})
    assert calls == ["NQ"]


def test_workspace_default_edit_replays_all_existing_runners(manager_factory, monkeypatch):
    manager = manager_factory(start=True)
    calls = _track_replays(monkeypatch, manager.portfolios["cc1"])
    manager.update("cc1", {"expected_revision": 0, "inputs": {"tp1_pts": 17}})
    assert calls == ["NQ", "ES"]


def test_unselected_open_sibling_still_blocks_asset_configuration(manager_factory, monkeypatch):
    manager = manager_factory(start=True)
    portfolio = manager.portfolios["cc1"]
    es = portfolio.runners["ES"]
    es.em.entry("guard", 1, 1)
    es.em.process_bar(Bar(0, 100, 100, 100, 100, 1), 0)
    assert es.em.open
    calls = _track_replays(monkeypatch, portfolio)
    before = manager._path("cc1").read_bytes()
    with pytest.raises(ValueError, match="flat|open|pending"):
        manager.update_asset("cc1", "NQ", {"expected_revision": 0, "inputs": {"tp1_pts": 17}})
    assert not calls and manager._path("cc1").read_bytes() == before
    assert manager.profiles["cc1"]["config_revision"] == 0


@pytest.mark.parametrize("asset,expected", [("NQ", ["NQ"]), (None, ["NQ", "ES"])])
def test_explicit_rewarm_replays_unchanged_selected_settings_once(manager_factory, monkeypatch, asset, expected):
    manager = manager_factory(start=True)
    portfolio = manager.portfolios["cc1"]
    before = copy.deepcopy(manager.profiles["cc1"])
    engines = {key: runner.em for key, runner in portfolio.runners.items()}
    calls = _track_replays(monkeypatch, portfolio)
    result = manager.rewarm("cc1", asset, {"expected_revision": 0})
    assert calls == expected and result["rewarmed_assets"] == expected
    assert result["config_revision"] == 1
    after = manager.profiles["cc1"]
    assert {k: v for k, v in after.items() if k != "config_revision"} == {k: v for k, v in before.items() if k != "config_revision"}
    assert json.loads(manager._path("cc1").read_text())["config_revision"] == 1
    for key, runner in portfolio.runners.items():
        assert (runner.em is not engines[key]) == (key in expected)


@pytest.mark.parametrize("body", [{}, {"expected_revision": True}, {"expected_revision": 9},
                                 {"expected_revision": 0, "asset": "ES"}, {"expected_revision": 0, "inputs": {}}])
def test_rewarm_rejects_revision_and_scope_before_replay(manager_factory, monkeypatch, body):
    manager = manager_factory(start=True)
    calls = _track_replays(monkeypatch, manager.portfolios["cc1"])
    saved = manager._path("cc1").read_bytes()
    with pytest.raises(ValueError):
        manager.rewarm("cc1", "NQ", body)
    assert not calls and manager._path("cc1").read_bytes() == saved
    assert manager.profiles["cc1"]["config_revision"] == 0


def test_explicit_rewarm_restores_selected_state_and_exact_file_after_replace_failure(manager_factory, monkeypatch):
    manager = manager_factory(start=True)
    portfolio = manager.portfolios["cc1"]
    before = {symbol: runner.em for symbol, runner in portfolio.runners.items()}
    saved = manager._path("cc1").read_bytes()
    save = manager._save
    def replace_then_fail(candidate):
        save(candidate)
        raise OSError("injected post-replace failure")
    monkeypatch.setattr(manager, "_save", replace_then_fail)
    with pytest.raises(OSError, match="post-replace"):
        manager.rewarm("cc1", "NQ", {"expected_revision": 0})
    assert manager._path("cc1").read_bytes() == saved
    assert manager.profiles["cc1"]["config_revision"] == 0
    assert all(runner.em is before[symbol] for symbol, runner in portfolio.runners.items())


@pytest.mark.parametrize("cost,value", [("commission", -7), ("capital", 0),
                                       ("slippage_ticks", -1), ("slippage_ticks", 1.5)])
def test_invalid_preset_costs_cannot_commit_configuration(manager_factory, cost, value):
    manager = manager_factory(start=True)
    runner = manager.portfolios["cc1"].runners["NQ"]
    before = (manager._path("cc1").read_bytes(), copy.deepcopy(manager.profiles["cc1"]),
              copy.deepcopy(runner.spec), runner.inputs_base)
    preset = manager.root.parent / "presets" / "invalid-costs.json"
    preset.parent.mkdir(exist_ok=True)
    preset.write_text(json.dumps({"_meta": {cost: value}}))
    with pytest.raises(ValueError, match=cost):
        manager.update_asset("cc1", "NQ", {"expected_revision": 0, "preset": "invalid-costs"})
    assert manager._path("cc1").read_bytes() == before[0]
    assert manager.profiles["cc1"] == before[1]
    assert runner.spec == before[2]
    assert runner.inputs_base == before[3]


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
    manager.update("cc1", {"expected_revision": 0, "asset_overrides": {"NQ": {"inputs": {"tp1_pts": 17}}}})
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
        manager.update("cc1", {"expected_revision": 0, "asset_overrides": {"NQ": {"inputs": {"tp1_pts": 17}}}})
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
    manager.update("cc1", {"expected_revision": 0, "asset_overrides": {"NQ": {"preset": "commission-example"}}})
    assert nq.cfg.preset == "commission-example"
    assert nq.spec.commission == 77
    manager.update("cc1", {"expected_revision": 1, "asset_overrides": {}})
    assert nq.cfg.preset is None
    assert nq.spec.commission == commission


def test_revision_is_persisted_and_stale_edit_does_not_mutate(manager_factory):
    manager = manager_factory(start=True)
    result = manager.update("cc1", {"expected_revision": 0, "inputs": {"tp1_pts": 17}})
    assert result.get("config_revision") == 1
    before = manager._path("cc1").read_bytes()
    with pytest.raises(ValueError, match="revision") as rejected:
        manager.update("cc1", {"expected_revision": 0, "inputs": {"tp1_pts": 19}})
    assert type(rejected.value).__name__ == "WorkspaceRevisionConflict"
    assert manager._path("cc1").read_bytes() == before
    assert manager.portfolios["cc1"].runners["NQ"].inputs_base.tp1_pts == 17
    assert manager_factory().profiles["cc1"]["config_revision"] == 1
    profile = next(p for p in manager.snapshot()["profiles"] if p["id"] == "cc1")
    assert profile["config_revision"] == 1


@pytest.mark.parametrize("revision", [True, False, -1, 0.5, "0", None])
def test_malformed_revision_rejected_before_mutation(manager_factory, revision):
    manager = manager_factory(start=True)
    before = manager._path("cc1").read_bytes()
    with pytest.raises(ValueError, match="revision"):
        manager.update("cc1", {"expected_revision": revision, "inputs": {"tp1_pts": 17}})
    assert manager._path("cc1").read_bytes() == before


def test_concurrent_writers_with_same_revision_cannot_lose_an_edit(manager_factory):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    manager = manager_factory(start=True)
    barrier = Barrier(2)

    def edit(value):
        barrier.wait(timeout=5)
        try:
            return manager.update("cc1", {"expected_revision": 0, "inputs": {"tp1_pts": value}})
        except ValueError as ex:
            return ex

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(edit, (17, 19)))
    accepted = [r for r in results if isinstance(r, dict)]
    rejected = [r for r in results if isinstance(r, ValueError)]
    assert len(accepted) == len(rejected) == 1
    assert type(rejected[0]).__name__ == "WorkspaceRevisionConflict"
    assert accepted[0]["config_revision"] == 1
    saved = json.loads(manager._path("cc1").read_text())
    assert saved["config_revision"] == 1
    assert saved["inputs"]["tp1_pts"] == accepted[0]["inputs"]["tp1_pts"]


def test_explicit_asset_edit_and_reset_are_revisioned_and_local(manager_factory):
    manager = manager_factory(start=True)
    portfolio = manager.portfolios["cc1"]
    before_es = portfolio.runners["ES"].inputs_base.to_dict()
    result = manager.update_asset("cc1", "NQ", {"expected_revision": 0, "inputs": {"tp1_pts": 17}})
    assert result["id"] == "cc1" and result["asset"] == "NQ" and result["config_revision"] == 1
    assert portfolio.runners["NQ"].inputs_base.tp1_pts == 17
    assert portfolio.runners["ES"].inputs_base.to_dict() == before_es
    before = manager._path("cc1").read_bytes()
    with pytest.raises(ValueError, match="revision"):
        manager.update("cc1", {"inputs": {"tp1_pts": 19}})
    assert manager._path("cc1").read_bytes() == before
    result = manager.update_asset("cc1", "NQ", {"expected_revision": 1, "reset": True})
    assert result["config_revision"] == 2
    assert portfolio.runners["NQ"].inputs_base.tp1_pts == before_es["tp1_pts"]
    assert manager_factory().profiles["cc1"]["asset_overrides"] == {}


@pytest.mark.parametrize("symbol,body", [
    ("NQ", {"inputs": {"tp1_pts": 17}}),
    ("CL", {"expected_revision": 0, "inputs": {"tp1_pts": 17}}),
    ("nq", {"expected_revision": 0, "inputs": {"tp1_pts": 17}}),
    ("NQ", {"expected_revision": 0, "asset": "ES", "inputs": {"tp1_pts": 17}}),
    ("NQ", {"expected_revision": 0, "reset": "yes"}),
    ("NQ", {"expected_revision": 0, "reset": True, "inputs": {"tp1_pts": 17}}),
    ("NQ", {"expected_revision": 0, "inputs": {"invented": 17}}),
    ("NQ", {"expected_revision": 0, "chart": {"made_up": True}}),
])
def test_asset_edit_rejects_ambiguous_or_invalid_request_without_mutation(manager_factory, symbol, body):
    manager = manager_factory(start=True)
    before = manager._path("cc1").read_bytes()
    with pytest.raises(ValueError):
        manager.update_asset("cc1", symbol, body)
    assert manager._path("cc1").read_bytes() == before


@pytest.mark.parametrize("body", [
    {"asset": "NQ", "inputs": {"tp1_pts": 17}},
    {"schema_version": 999, "inputs": {"tp1_pts": 17}},
    {"config_revision": 0, "inputs": {"tp1_pts": 17}},
    {"unknown": 17},
    {"asset_overrides": {"NQ": {"inputs": {"tp1_pts": 17}}}},
])
def test_workspace_update_rejects_unsupported_writers_and_selectors(manager_factory, body):
    manager = manager_factory(start=True)
    before = manager._path("cc1").read_bytes()
    with pytest.raises(ValueError):
        manager.update("cc1", body)
    assert manager._path("cc1").read_bytes() == before


def test_uncommitted_and_failed_edit_never_leaks_into_cached_public_views(manager_factory, monkeypatch):
    manager = manager_factory(start=True)
    nq = manager.portfolios["cc1"].runners["NQ"]
    nq.publish_read_views()
    original = nq._busy_read_view(0)
    preset = manager.root.parent / "presets" / "rejected-example.json"
    preset.parent.mkdir(exist_ok=True)
    preset.write_text('{"_meta":{"slippage_ticks":77}}')
    observed = []
    save = manager._save

    def fail_after_replace(profile):
        observed.append(nq._busy_read_view(0))
        save(profile)
        raise OSError("injected reviewed persistence failure")

    monkeypatch.setattr(manager, "_save", fail_after_replace)
    with pytest.raises(OSError, match="reviewed persistence"):
        manager.update_asset("cc1", "NQ", {"expected_revision": 0, "preset": "rejected-example"})
    observed.append(nq._busy_read_view(0))
    assert nq.spec.slippage_ticks == original["slippage_ticks"]
    assert all(row["slippage_ticks"] == original["slippage_ticks"] for row in observed)
    assert all(row["preset"] == original["preset"] for row in observed)


def test_failed_timeframe_edit_restores_chart_routing_and_event_state(manager_factory, monkeypatch):
    from icarus_engine.pine.timeframe import Bar
    manager = manager_factory(start=True)
    nq = manager.portfolios["cc1"].runners["NQ"]
    nq.subbars.append((Bar(1789506000, 100, 101, 99, 100, 1), 1))
    original = (nq.spec.chart_tf, nq.chart_minutes, nq.chart_mode, nq.chart_value, nq.chart_seconds)
    nq.event_minute_agg = minute_state = object()
    nq.event_chart_agg = chart_state = object()
    nq._event_chart_session = "prior-observed-session"
    save = manager._save

    def fail_after_replace(profile):
        save(profile)
        raise OSError("injected timeframe persistence failure")

    monkeypatch.setattr(manager, "_save", fail_after_replace)
    with pytest.raises(OSError, match="timeframe persistence"):
        manager.update_asset("cc1", "NQ", {"expected_revision": 0, "chart": {"timeframe": "10"}})
    assert (nq.spec.chart_tf, nq.chart_minutes, nq.chart_mode, nq.chart_value, nq.chart_seconds) == original
    assert nq.event_minute_agg is minute_state
    assert nq.event_chart_agg is chart_state
    assert nq._event_chart_session == "prior-observed-session"
    assert manager.profiles["cc1"]["config_revision"] == 0


@pytest.mark.parametrize("override", [{"inputs": {"tp1_pts": 17}}, {"preset": "missing-example"}])
def test_whole_workspace_writer_cannot_configure_unselected_asset(manager_factory, override):
    manager = manager_factory(start=True)
    before = manager._path("cc1").read_bytes()
    with pytest.raises(ValueError, match="selected|admitted"):
        manager.update("cc1", {"expected_revision": 0, "asset_overrides": {"CL": override}})
    assert manager._path("cc1").read_bytes() == before
    assert manager.profiles["cc1"]["config_revision"] == 0


def test_removing_configured_asset_requires_explicit_override_disposition(manager_factory):
    manager = manager_factory(start=True)
    manager.update_asset("cc1", "NQ", {"expected_revision": 0, "inputs": {"tp1_pts": 17}})
    before = manager._path("cc1").read_bytes()
    with pytest.raises(ValueError, match="selected|admitted"):
        manager.update("cc1", {"expected_revision": 1, "assets": ["ES"]})
    assert manager._path("cc1").read_bytes() == before
    manager.update("cc1", {"expected_revision": 1, "assets": ["ES"], "asset_overrides": {}})
    assert manager.profiles["cc1"]["assets"] == ["ES"]


def test_snapshot_cannot_pair_new_runtime_with_old_configuration_revision(manager_factory, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    manager = manager_factory(start=True)
    entered, release, reader_entered, reader_done = (Event() for _ in range(4))
    save = manager._save

    def blocked_save(profile):
        save(profile)
        entered.set()
        assert release.wait(5)

    def read():
        reader_entered.set()
        snapshot = manager.snapshot()
        reader_done.set()
        return next(p for p in snapshot["profiles"] if p["id"] == "cc1")

    monkeypatch.setattr(manager, "_save", blocked_save)
    with ThreadPoolExecutor(max_workers=2) as executor:
        writer = executor.submit(manager.update, "cc1", {"expected_revision": 0, "inputs": {"tp1_pts": 17}})
        assert entered.wait(3)
        reader = executor.submit(read)
        assert reader_entered.wait(3)
        try:
            assert reader_done.wait(1), "one replay must not stall the complete workspace overview"
            row = reader.result(timeout=1)
            assert row["status"]["snapshot_unavailable"] is True
            assert row["effective_inputs"] == {}
        finally:
            release.set()
        writer.result(timeout=5)
    row = next(p for p in manager.snapshot()["profiles"] if p["id"] == "cc1")
    assert row["config_revision"] == 1
    assert row["effective_inputs"]["tp1_pts"] == 17


def test_explicit_null_preset_and_reset_have_distinct_replay_identity(manager_factory):
    from icarus_engine.backtest import freeze_replay_port
    manager = manager_factory()
    preset = manager.root.parent / "presets" / "baseline-example.json"
    preset.parent.mkdir(exist_ok=True)
    preset.write_text('{"tp1_pts":123}')
    manager.parent.preset = "baseline-example"
    manager = manager_factory(start=True)
    portfolio = manager.portfolios["cc1"]
    nq = portfolio.runners["NQ"]
    assert nq.inputs_base.tp1_pts == 123
    manager.update_asset("cc1", "NQ", {"expected_revision": 0, "preset": None})
    assert nq.inputs_base.tp1_pts != 123
    assert nq.cfg.preset is None
    assert portfolio.preset_for(nq) is None
    frozen = freeze_replay_port(portfolio, "NQ")
    assert frozen.preset_for(frozen.runners["NQ"]) is None
    manager.update_asset("cc1", "NQ", {"expected_revision": 1, "reset": True})
    assert nq.inputs_base.tp1_pts == 123
    assert portfolio.preset_for(nq) == "baseline-example"


def test_partial_workspace_chart_edit_preserves_other_saved_chart_choices(manager_factory):
    manager = manager_factory(start=True)
    before = copy.deepcopy(manager.profiles["cc1"]["chart"])
    manager.update("cc1", {"expected_revision": 0, "chart": {"fill_on": "chart"}})
    expected = {**before, "fill_on": "chart"}
    assert manager.profiles["cc1"]["chart"] == expected
    assert manager.portfolios["cc1"].runners["NQ"].spec.chart_tf == before["timeframe"]
    assert manager_factory().profiles["cc1"]["chart"] == expected


def test_configuration_transactions_in_other_workspaces_do_not_wait_for_replay(manager_factory, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError
    from threading import Event
    manager = manager_factory(start=True)
    nq = manager.portfolios["cc1"].runners["NQ"]
    entered, release = Event(), Event()
    rewarm = nq.rewarm

    def blocked(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return rewarm(*args, **kwargs)

    monkeypatch.setattr(nq, "rewarm", blocked)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(manager.update_asset, "cc1", "NQ", {"expected_revision": 0, "inputs": {"tp1_pts": 17}})
        assert entered.wait(3)
        second = executor.submit(manager.update_asset, "cc2", "NQ", {"expected_revision": 0, "inputs": {"tp1_pts": 19}})
        try:
            try:
                result = second.result(timeout=1)
            except TimeoutError:
                result = None
            assert result is not None, "CC2 configuration stalled behind unrelated CC1 replay"
            assert result["config_revision"] == 1
        finally:
            release.set()
        first.result(timeout=5)
        second.result(timeout=5)
