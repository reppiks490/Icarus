"""Independent, concurrent paper-only strategy workspaces for the dashboard."""
from __future__ import annotations

from contextlib import ExitStack
import copy
import json
import math
import os
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from .assets import REGISTRY, apply_chart_config, validate_chart_config
from .workspace_universe import dashboard_assets
from .futures_catalog import FUTURES_PRODUCTS
from .paper_pnl import validate_paper_pnl
from .workspace_config import WorkspaceRevisionConflict, normalize_workspace
from .runtime import (
    AssetRunner,
    FlattenUnavailableError,
    Journal,
    Portfolio,
    RunnerConfig,
    apply_spec_meta,
    resolve_inputs,
    validate_values,
    preset_path,
)


# Owner-requested expansion is a research selection, separate from the default
# active portfolios and from dated-contract/broker execution qualification.
REQUESTED_FUTURES_FAMILIES = ("CL", "NG", "HG", "6E", "6J", "6B", "6A", "ZN", "ZB", "BTCF")
REQUESTED_FUTURES_MICROS = tuple(
    product.root for root in REQUESTED_FUTURES_FAMILIES
    for product in FUTURES_PRODUCTS.values() if product.full_root == root and product.root != root
)
REQUESTED_FUTURES_SYMBOLS = REQUESTED_FUTURES_FAMILIES + REQUESTED_FUTURES_MICROS


def requested_futures_metadata():
    return {
        "family_count": len(REQUESTED_FUTURES_FAMILIES),
        "full_roots": list(REQUESTED_FUTURES_FAMILIES),
        "micro_roots": list(REQUESTED_FUTURES_MICROS),
        "symbols": list(REQUESTED_FUTURES_SYMBOLS),
        "families": [{"root": root, "micro_roots": [micro for micro in REQUESTED_FUTURES_MICROS
                                                       if FUTURES_PRODUCTS[micro].full_root == root]}
                     for root in REQUESTED_FUTURES_FAMILIES],
        "purpose": "CORPUS_RESEARCH_AND_PAPER_CONFIGURATION",
        "profitability_verified": False,
        "fresh_feed_access_verified": False,
        "execution_authorized": False,
    }


_MINI_MICRO_FUTURES = (
    "NQ", "MNQ", "ES", "MES", "YM", "MYM", "RTY", "M2K",
    "GC", "MGC", "SI", "SIL",
)
_PROFILE_DEFAULTS = (
    {"id": "cc1", "name": "20m Full Asset Universe", "description": "Heikin Ashi · 20 minute · original assets + ten futures families and micros",
     "assets": dashboard_assets(), "chart": {"timeframe": "20", "chart_type": "heikin_ashi", "fill_on": "real", "security_source": "chart"}, "inputs": {}},
    {"id": "cc2", "name": "Short Target + ETH", "description": "5 minute starting profile · lower targets · larger size · includes ETH",
     "assets": dashboard_assets(), "chart": {"timeframe": "5", "chart_type": "heikin_ashi", "fill_on": "real", "security_source": "chart"},
     "inputs": {"tp1_pts": 7.5, "tp2_pts": 15.0, "qty_contracts": 10}},
    {"id": "cc3", "name": "Workspace 3", "description": "Independent paper workspace · editable starting profile",
     "assets": dashboard_assets(), "chart": {"timeframe": "20", "chart_type": "heikin_ashi", "fill_on": "real", "security_source": "chart"}, "inputs": {}},
    {"id": "cc4", "name": "5m Full Asset Universe", "description": "Heikin Ashi · 5 minute · original assets + ten futures families and micros",
     "assets": dashboard_assets(), "chart": {"timeframe": "5", "chart_type": "heikin_ashi", "fill_on": "real", "security_source": "chart"}, "inputs": {}},
)
_IDS = {row["id"] for row in _PROFILE_DEFAULTS}


def _validate_assets(value):
    if not isinstance(value, list) or not 1 <= len(value) <= len(REGISTRY):
        raise ValueError("assets must be a nonempty bounded list of canonical symbols")
    if any(type(symbol) is not str or symbol not in REGISTRY for symbol in value):
        raise ValueError("assets contain an unknown or noncanonical symbol")
    if len(set(value)) != len(value):
        raise ValueError("assets must not contain duplicate symbols")
    for symbol in value:
        product = FUTURES_PRODUCTS.get(symbol)
        if product is not None and product.runtime_qualified is not True:
            raise ValueError(f"assets: {symbol} is not runtime-qualified")
    return list(value)


def _available_assets():
    rows = []
    for symbol, spec in REGISTRY.items():
        product = FUTURES_PRODUCTS.get(symbol)
        rows.append({
            "symbol": symbol, "name": getattr(spec, "name", symbol),
            "requested_expansion": symbol in REQUESTED_FUTURES_SYMBOLS,
            "kind": getattr(spec, "kind", "futures"),
            "full_root": product.full_root if product else symbol,
            "exchange": getattr(spec, "exchange", ""),
            "provider_symbol": getattr(spec, "ticker", ""),
            "feed_mode": getattr(spec, "feed_mode", "unknown"),
            "selectable": product.runtime_qualified is True if product else True,
            "runtime_qualified": product.runtime_qualified is True if product else True,
            "execution_qualified": product.execution_qualified is True if product else False,
            "execution_blocker": product.execution_blocker if product else "no broker execution qualification",
            "data_access_verified": False,
            "data_access_note": "Configured public research route; actual availability and freshness require feed observations",
            "execution_authorized": False,
        })
    return rows


class SharedFeed:
    """Share feed sessions and collapse overlapping history requests across workspaces."""
    def __init__(self, feed: Any):
        self._feed = feed
        self._lock = threading.RLock()
        self._candles: Dict[Tuple[str, int], List[Tuple[int, int, Dict[int, Any]]]] = {}
        self._short_cache: Dict[Tuple[Any, ...], Tuple[float, Any]] = {}

    @property
    def native_interval_seconds(self) -> int:
        return getattr(self._feed, "native_interval_seconds", 60)

    @property
    def provider_name(self) -> str:
        return type(self._feed).__name__.lower()

    def cached_meta(self, symbol: str) -> Dict[str, Any]:
        """Expose only already observed health; Yahoo.meta can perform network I/O."""
        if self.provider_name == "databento":
            return self._feed.meta(symbol)
        cached = getattr(self._feed, "_meta", None)
        value = cached.get(symbol, {}) if isinstance(cached, dict) else {}
        return dict(value) if isinstance(value, dict) else {}

    def candles(self, symbol: str, granularity: int, start_ts: int, end_ts: int):
        key = (str(symbol), int(granularity))
        start, end = int(start_ts), int(end_ts)
        with self._lock:
            segments = self._candles.setdefault(key, [])
            cursor = start
            holes = []
            for left, right, _rows in sorted(segments, key=lambda item:item[0]):
                if right <= cursor or left >= end:
                    continue
                if left > cursor:
                    holes.append((cursor, min(left, end)))
                cursor = max(cursor, min(right, end))
                if cursor >= end:
                    break
            if cursor < end:
                holes.append((cursor, end))
            for left, right in holes:
                rows = self._feed.candles(symbol, granularity, left, right)
                # Providers promise a half-open range, but a shared cache must
                # enforce it itself: one stray row would otherwise be served
                # to every workspace and could mask a later correct fetch.
                cached_rows = {}
                for row in rows:
                    ts = int(row.ts)
                    if left <= ts < right:
                        cached_rows[ts] = row
                segments.append((left, right, cached_rows))
            merged = {}
            for left, right, rows in segments:
                if left < end and right > start:
                    merged.update((ts,row) for ts,row in rows.items() if start <= ts < end)
            return [merged[ts] for ts in sorted(merged)]

    def recent_ex(self, symbol: str, granularity: int = 60, since_ts: Optional[int] = None):
        key = ("recent_ex", str(symbol), int(granularity), since_ts)
        return self._short(key, lambda: self._feed.recent_ex(symbol, granularity, since_ts=since_ts))

    def recent(self, symbol: str, granularity: int = 60):
        key = ("recent", str(symbol), int(granularity))
        return self._short(key, lambda: self._feed.recent(symbol, granularity))

    def _short(self, key, load, ttl=0.5):
        now = time.monotonic()
        with self._lock:
            cached = self._short_cache.get(key)
            if cached and cached[0] > now:
                return copy.deepcopy(cached[1])
            value = load()
            self._short_cache[key] = (now + ttl, copy.deepcopy(value))
            return value

    def daily_volume(self, symbol: str, days: int = 5):
        key = ("daily_volume", str(symbol), int(days))
        return self._short(key, lambda: self._feed.daily_volume(symbol, days), ttl=300.0)

    def ticker(self, symbol: str):
        key = ("ticker", str(symbol))
        return self._short(key, lambda: self._feed.ticker(symbol), ttl=1.0)

    def close(self):
        # The original engine owns the shared provider transports.
        return None

    def stop_live(self, *_args, **_kwargs):
        return None

    def __getattr__(self, name):
        return getattr(self._feed, name)


class WorkspacePortfolio(Portfolio):
    def __init__(self, *args, workspace: Dict[str, Any], **kwargs):
        self.workspace = workspace
        super().__init__(*args, **kwargs)

    def _resolved(self, spec, workspace=None):
        workspace = self.workspace if workspace is None else workspace
        override = workspace.get("asset_overrides", {}).get(spec.symbol, {})
        chart = validate_chart_config({**workspace["chart"], **override.get("chart", {})})
        values = {**workspace["inputs"], **override.get("inputs", {})}
        preset = override.get("preset", self.preset)
        if override.get("preset") and not Path(preset_path(self.base_dir, preset)).is_file():
            raise ValueError(f"workspace preset {preset!r} not found")
        spec = apply_chart_config(spec, chart, pin=True)
        inputs, meta, sources = resolve_inputs(
            spec, self.base_dir, self.profile, preset, values,
            skip_asset_overrides=True, extra_label=f"command-center:{workspace['id']}"
        )
        spec = apply_spec_meta(spec, meta)
        spec = apply_chart_config(spec, chart, pin=True)
        return spec, inputs, sources

    def make_runner(self, spec, *, workspace=None):
        base_spec = copy.deepcopy(spec)
        spec, inputs, sources = self._resolved(spec, workspace)
        selected = self.workspace if workspace is None else workspace
        preset = selected.get("asset_overrides", {}).get(spec.symbol, {}).get("preset", self.preset)
        scale = self._ref_price() if spec.symbol != self.pts_ref_symbol else 0.0
        cfg = RunnerConfig(spec=spec, inputs=inputs, warmup_bars=self.warmup_bars,
                           sources=sources, profile=self.profile, preset=preset or spec.preset,
                           pts_ref_price=scale, base_dir=self.base_dir, base_spec=base_spec)
        runner = AssetRunner(cfg, self.journal, self.feeds)
        runner.latency_telemetry = self.latency_telemetry
        return runner

    def rewarm_asset(self, *_args, **_kwargs):
        raise ValueError("workspace settings require the revisioned workspace configuration transaction")

    def preset_for(self, runner):
        override = self.workspace.get("asset_overrides", {}).get(runner.symbol, {})
        if "preset" in override:
            return override["preset"]
        return super().preset_for(runner)

    def _refresh_continuous_feeds(self, now=None):
        if self.workspace["id"] != "cc1":
            return False
        return super()._refresh_continuous_feeds(now)

    def _run(self, runner):
        # Transaction-created workers may exist before every sibling thread has
        # started. They cannot warm up, poll or write the ledger until committed.
        gate = getattr(runner, "_workspace_start_gate", None)
        if gate is not None:
            while not gate.wait(0.1):
                if self._stop.is_set():
                    return
            if runner._removed or self._stop.is_set():
                return
        return super()._run(runner)

    def reconfigure(self, candidate: Dict[str, Any], *, persist=None) -> Dict[str, Any]:
        requested = _validate_assets(candidate["assets"])
        chart = validate_chart_config(candidate["chart"])
        values = dict(candidate["inputs"])
        validate_values(values)
        configuration_changed = any(candidate.get(key) != self.workspace.get(key)
                                    for key in ("chart", "inputs", "asset_overrides"))
        with self._lock, ExitStack() as locks:
            if self._stop.is_set():
                raise ValueError("command center paper runtime is stopped")
            previous = dict(self.runners)
            previous_order = list(self.order)
            removed = [runner for symbol, runner in previous.items() if symbol not in requested]
            # Stage construction and provider preparation without publishing maps.
            additions = []
            gate = threading.Event()
            previous_threads = dict(self._threads)
            snapshots = []
            old_workspace = copy.deepcopy(self.workspace)
            started = self._sampler_thread is not None and not self._stop.is_set()
            try:
                for symbol in requested:
                    if symbol in previous:
                        continue
                    runner = self.make_runner(copy.deepcopy(REGISTRY[symbol]), workspace=candidate)
                    if self.paused:
                        runner.paused = True
                    runner._workspace_start_gate = gate
                    additions.append(runner)
                    if started:
                        prepare = getattr(runner.feed, "prepare_live", None)
                        if runner.spec.kind == "futures" and callable(prepare):
                            prepare([runner.spec.ticker])
                            self._prepare_depth_context(runner.feed, [runner.spec.ticker])
                # Source preparation can block; keep existing runners free to
                # process their own bars, then validate removal under locks.
                for runner in sorted(previous.values(), key=lambda r: r.symbol):
                    locks.enter_context(runner.lock)
                for runner in removed:
                    if runner.em.open or runner.em._pending_entries or runner.em._pending_closes:
                        raise ValueError(f"{runner.symbol}: flatten open positions and cancel pending orders before removing the asset")
                    runner.ensure_configurable()
                if configuration_changed:
                    snapshots = [(r, r.configuration_snapshot(), copy.deepcopy(r.cfg.base_spec))
                                 for r in previous.values()]
                    # Existing transactional replay also validates all old runners.
                    self._reconfigure_existing(candidate)
                if persist is not None:
                    persist()
                if started:
                    for runner in additions:
                        self._spawn(runner)
                # Removing a flat runner is terminal for its worker. Keep its
                # handle under a unique key so shutdown still joins it even if
                # this symbol is subsequently re-added.
                for runner in removed:
                    runner.paused = True
                    runner._removed = True
                    worker = self._threads.pop(runner.symbol, None)
                    if worker is not None:
                        self._threads[f"retired:{runner.symbol}:{id(worker)}"] = worker
                staged = {runner.symbol: runner for runner in additions}
                self.runners = {symbol: previous.get(symbol, staged.get(symbol)) for symbol in requested}
                self.order = requested
                self.workspace = copy.deepcopy(candidate)
            except Exception:
                for runner in additions:
                    runner._removed = True
                gate.set()
                # Gated workers have performed no feed reads or journal writes.
                for key, worker in list(self._threads.items()):
                    if previous_threads.get(key) is not worker:
                        worker.join(5)
                self._threads = previous_threads
                self.runners, self.order = previous, previous_order
                for runner, snapshot, base_spec in reversed(snapshots):
                    runner.restore_configuration_snapshot(snapshot)
                    runner.cfg.base_spec = base_spec
                self.workspace = old_workspace
                raise
            gate.set()
        return {"ok": True, "id": self.workspace["id"], "assets": requested,
                "chart": chart, "inputs": values, "paper_only": True, "execution_authorized": False}

    def _reconfigure_existing(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        chart = validate_chart_config(candidate["chart"])
        values = dict(candidate["inputs"])
        validate_values(values)
        runners = self.runner_list()
        plans = []
        for runner in runners:
            runner.ensure_configurable()
            spec, inputs, sources = self._resolved(
                copy.deepcopy(runner.cfg.base_spec or runner.spec), candidate)
            runner.ensure_cached_timeframes(inputs)
            spec.chart_tf = runner.ensure_cached_chart_timeframe(spec.chart_tf)
            plans.append((runner, spec, inputs, sources))

        with ExitStack() as locks:
            for runner, *_ in sorted(plans, key=lambda item: item[0].symbol):
                locks.enter_context(runner.lock)
            for runner, *_ in plans:
                runner.ensure_configurable()
            snapshots = [(runner, runner.configuration_snapshot(), copy.deepcopy(runner.cfg.base_spec)) for runner, *_ in plans]
            try:
                for runner, *_ in plans:
                    runner.publish_read_views()
                for runner, spec, inputs, sources in plans:
                    runner.spec = spec
                    runner.cfg.spec = spec
                    runner.cfg.sources = list(sources)
                    override = candidate.get("asset_overrides", {}).get(runner.symbol, {})
                    runner.cfg.preset = override.get("preset", self.preset) or spec.preset
                    runner.rewarm(inputs, sources, reset_live_boundary=True, _publish_views=False)
            except Exception:
                for runner, snapshot, base_spec in reversed(snapshots):
                    runner.restore_configuration_snapshot(snapshot)
                    runner.cfg.base_spec = base_spec
                raise
        return {"ok": True, "id": self.workspace["id"], "assets": [r.symbol for r in runners],
                "chart": chart, "inputs": values, "paper_only": True, "execution_authorized": False}


class PaperWorkspaceManager:
    """Four isolated paper ledgers and runner maps, sharing the parent feed sessions."""
    def __init__(self, parent: Portfolio):
        self.parent = parent
        self.root = Path(parent.base_dir or os.getcwd()) / "command_centers"
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._closing_journals: set[int] = set()
        self._feeds = {name: SharedFeed(feed) for name, feed in parent.feeds.items()}
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.portfolios: Dict[str, WorkspacePortfolio] = {}
        self._load_profiles()

    def _path(self, profile_id):
        if profile_id not in _IDS:
            raise ValueError("unknown command center profile")
        return self.root / f"{profile_id}.json"

    def _load_profiles(self):
        for default in _PROFILE_DEFAULTS:
            path = self._path(default["id"])
            profile = copy.deepcopy(default)
            if path.exists():
                with path.open("r", encoding="utf-8") as fh:
                    saved = json.load(fh)
                if not isinstance(saved, dict) or saved.get("id") != default["id"]:
                    raise ValueError(f"invalid command center profile: {path.name}")
                profile.update(saved)
            if path.exists() and "assets" in saved:
                profile["assets"] = _validate_assets(saved["assets"])
            profile = normalize_workspace(profile)
            self.profiles[profile["id"]] = profile
            if not path.exists():
                self._save(profile)

    def _save(self, profile):
        path = self._path(profile["id"])
        if path.exists():
            original = path.read_bytes()
            saved = json.loads(original)
            if saved.get("schema_version", 1) == 1:
                backup = path.with_name(f"{profile['id']}.pre-v2.json")
                try:
                    with backup.open("xb") as fh:
                        fh.write(original)
                        fh.flush()
                        os.fsync(fh.fileno())
                except FileExistsError:
                    if backup.read_bytes() != original:
                        raise ValueError("workspace migration backup conflicts with the original record")
        tmp = path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(profile, fh, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)

    def start(self):
        try:
            for profile_id, profile in self.profiles.items():
                journal = Journal(str(self.root / f"{profile_id}.sqlite3"))
                try:
                    portfolio = WorkspacePortfolio(
                        journal, str(self.parent.base_dir), poll_sec=self.parent.poll_sec,
                        profile=self.parent.profile, preset=self.parent.preset,
                        warmup_bars=self.parent.warmup_bars, pts_ref_symbol=self.parent.pts_ref_symbol,
                        feeds=self._feeds, workspace=profile,
                    )
                except Exception as constructor_error:
                    try:
                        journal.close()
                    except Exception as cleanup_error:
                        raise constructor_error from cleanup_error
                    raise
                portfolio.pts_ref_price = self.parent.pts_ref_price
                self.portfolios[profile_id] = portfolio
                for symbol in profile["assets"]:
                    spec = copy.deepcopy(REGISTRY[symbol])
                    portfolio.add_asset(spec, start=False)
                portfolio.start()
        except Exception as start_error:
            try:
                self.stop()
            except Exception as cleanup_error:
                raise start_error from cleanup_error
            raise

    def stop(self):
        first_error = None
        for portfolio in reversed(list(self.portfolios.values())):
            try:
                portfolio.stop()
            except Exception as ex:
                first_error = first_error or ex
            try:
                self._close_journal_when_workers_stop(portfolio)
            except Exception as ex:
                first_error = first_error or ex
        if first_error is not None:
            raise first_error

    def _close_journal_when_workers_stop(self, portfolio):
        workers = list(getattr(portfolio, "_threads", {}).values())
        sampler = getattr(portfolio, "_sampler_thread", None)
        if sampler is not None:
            workers.append(sampler)
        pending = [worker for worker in workers if worker.is_alive()]
        if not pending:
            portfolio.journal.close()
            return

        journal_key = id(portfolio.journal)
        with self._lock:
            if journal_key in self._closing_journals:
                return
            self._closing_journals.add(journal_key)

        def close_after_workers_exit():
            try:
                for worker in pending:
                    worker.join()
                portfolio.journal.close()
            finally:
                with self._lock:
                    self._closing_journals.discard(journal_key)

        closer = threading.Thread(
            target=close_after_workers_exit,
            daemon=True,
            name=f"journal-close-{portfolio.workspace['id']}",
        )
        closer.start()

    @staticmethod
    def _asset_feed_state(asset: Dict[str, Any], poll_sec: float, feed_mode: str) -> str:
        if asset.get("last_error"):
            return "error"
        if not asset.get("warm"):
            return "warming"
        if feed_mode == "file":
            return "offline_file" if asset.get("last_bar_ts") is not None else "waiting_for_file"
        health = asset.get("feed_health") or {}
        if health.get("core_session_ok") is False or health.get("live_error"):
            return "error"
        if asset.get("feed_provider") == "databento" and health.get("mapping_active") is False:
            return "unmapped"
        age = asset.get("poll_age")
        if age is None:
            return "unobserved"
        if not isinstance(age, (int, float)) or not math.isfinite(age) or age > max(90.0, poll_sec * 3):
            return "stale"
        if not (asset.get("market") or {}).get("open"):
            return "market_closed"
        if asset.get("feed_provider") == "yahoo" and (asset.get("feed_delay") or 0) >= 120:
            return "delayed"
        return "observed"

    def _feed_summary(self, status: Dict[str, Any], portfolio: Optional[WorkspacePortfolio]) -> Dict[str, Any]:
        assets = status.get("assets") or []
        mode = getattr(portfolio, "feed_mode", getattr(self.parent, "feed_mode", "live"))
        poll_sec = getattr(portfolio, "poll_sec", self.parent.poll_sec)
        counts: Dict[str, int] = {}
        for asset in assets:
            state = self._asset_feed_state(asset, poll_sec, mode)
            counts[state] = counts.get(state, 0) + 1
        healthy = sum(counts.get(key, 0) for key in ("observed", "delayed", "market_closed", "offline_file"))
        if not assets:
            overall = "unobserved"
        elif counts.get("error"):
            overall = "error" if counts["error"] == len(assets) else "degraded"
        elif counts.get("stale"):
            overall = "stale" if counts["stale"] == len(assets) else "degraded"
        elif mode == "file":
            overall = "offline_file" if healthy == len(assets) else "waiting_for_file"
        elif counts.get("warming") or counts.get("unobserved") or counts.get("unmapped"):
            overall = "degraded" if healthy else ("warming" if counts.get("warming") else "unobserved")
        elif counts.get("delayed"):
            overall = "delayed"
        elif counts.get("market_closed") == len(assets):
            overall = "market_closed"
        else:
            overall = "observed"
        providers = sorted({str(asset.get("feed_provider") or asset.get("feed") or "unknown") for asset in assets})
        detail = f"{healthy}/{len(assets)} paper runners have a recent successful feed observation"
        if mode == "file":
            detail = f"{healthy}/{len(assets)} runners have local history; network feed disabled"
        elif counts.get("delayed"):
            detail += "; Yahoo futures quotes are delayed"
        if counts.get("error") or counts.get("stale"):
            detail += f"; {counts.get('error', 0)} error, {counts.get('stale', 0)} stale"
        return {"status": overall, "detail": detail, "providers": providers,
                "healthy_assets": healthy, "total_assets": len(assets), "state_counts": counts}

    def _connections(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        grouped: Dict[str, List[Tuple[Dict[str, Any], str]]] = {}
        for profile in rows:
            portfolio = self.portfolios.get(profile["id"])
            mode = getattr(portfolio, "feed_mode", getattr(self.parent, "feed_mode", "live"))
            interval = getattr(portfolio, "poll_sec", self.parent.poll_sec)
            for asset in profile["status"].get("assets") or []:
                provider = str(asset.get("feed_provider") or asset.get("feed") or "unknown")
                grouped.setdefault(provider, []).append((asset, self._asset_feed_state(asset, interval, mode)))
        feeds = []
        now = time.time()
        for provider, entries in sorted(grouped.items()):
            counts: Dict[str, int] = {}
            observed_at = []
            for asset, state in entries:
                counts[state] = counts.get(state, 0) + 1
                age = asset.get("poll_age")
                if isinstance(age, (int, float)) and math.isfinite(age) and age >= 0:
                    observed_at.append(now - age)
            if counts.get("error") or counts.get("stale"):
                state = "degraded"
            elif counts.get("waiting_for_file"):
                state = "waiting_for_file"
            elif counts.get("offline_file"):
                state = "offline_file"
            elif counts.get("warming"):
                state = "warming"
            elif counts.get("unobserved") or counts.get("unmapped"):
                state = "unobserved"
            elif counts.get("delayed"):
                state = "delayed"
            elif counts.get("market_closed") == len(entries):
                state = "market_closed"
            else:
                state = "observed"
            detail = f"{len(entries)} paper asset runners; " + ", ".join(f"{count} {key}" for key, count in sorted(counts.items()))
            if provider == "yahoo":
                detail += "; Yahoo futures data is delayed"
            feeds.append({"id": provider, "label": provider.title(), "status": state,
                          "detail": detail, "last_observed_at": max(observed_at) if observed_at else None})
        if not feeds:
            mode = getattr(self.parent, "feed_mode", "live")
            feeds.append({"id": mode, "label": mode.title(),
                          "status": "unobserved", "detail": "No paper runner has produced a feed observation",
                          "last_observed_at": None})
        alpaca_configured = bool(os.environ.get("ALPACA_API_KEY") and os.environ.get("ALPACA_SECRET_KEY"))
        adapters = [
            {"id": "local-paper", "label": "ICARUS local paper emulator", "kind": "paper_simulator",
             "configured": True, "connected": len(self.portfolios) == len(_IDS),
             "execution_authorized": False, "detail": "Isolated local simulation; no broker orders"},
            {"id": "alpaca-bridge", "label": "Alpaca bridge", "kind": "separate_paper_bridge",
             "configured": alpaca_configured, "connected": False, "execution_authorized": False,
             "detail": "Separate bridge adapter; not connected to command center workspaces"},
            {"id": "futures-broker", "label": "Futures broker", "kind": "broker",
             "configured": False, "connected": False, "execution_authorized": False,
             "detail": "No futures broker adapter is installed in these workspaces"},
            {"id": "prop-firm", "label": "Prop firm account", "kind": "prop_firm",
             "configured": False, "connected": False, "execution_authorized": False,
             "detail": "No prop firm account adapter or verified balance is available"},
        ]
        return {"feeds": feeds, "adapters": adapters, "execution_authorized": False}

    def snapshot(self):
        # Keep settings, effective runner inputs and revision in one committed view.
        # Runner locks alone cannot protect the manager's configuration identity.
        with self._lock:
            return self._snapshot()

    def _snapshot(self):
        now = int(time.time())
        rows = []
        ledgers = []
        for profile_id, profile in self.profiles.items():
            portfolio = self.portfolios.get(profile_id)
            status = portfolio.status(nonblocking=True) if portfolio else {"assets": [], "all_warm": False}
            runners = portfolio.runner_list() if portfolio else []
            effective = runners[0].inputs_base.to_dict() if runners else {}
            closed = portfolio.journal.closed_paper_profit() if portfolio else {"realized_pnl": 0.0, "closed_pieces": 0, "last_close_ts": None}
            missing_marks = []
            for asset in status.get("assets", []):
                if asset.get("position"):
                    mark = asset.get("price")
                    if type(mark) not in (int, float) or not math.isfinite(mark) or mark <= 0:
                        missing_marks.append(str(asset.get("symbol") or "unknown"))
            valuation_complete = portfolio is not None and not status.get("view_stale", False) and not missing_marks
            if status.get("positions") and not any(asset.get("position") for asset in status.get("assets", [])):
                valuation_complete = False
            open_pnl = float(status.get("open_profit") or 0.0)
            # Journals and catalog point values use explicit USD simulation units.
            # This currency never describes any broker account or FX conversion.
            open_assets = [asset for asset in status.get("assets", []) if asset.get("position")]
            position_count = status.get("positions", len(open_assets))
            marks = []
            for asset in open_assets:
                age, price = asset.get("price_age"), asset.get("price")
                if (type(age) not in (int, float) or not 0 <= age <= 1e9
                        or type(price) not in (int, float) or not 0 < price < 1e18):
                    break
                marks.append(now - int(math.ceil(age)))
            marks_complete = (len(marks) == len(open_assets) == position_count
                              and not status.get("view_stale", False))
            ledgers.append({"id": profile_id, "currency": "USD", "runtime_available": portfolio is not None,
                            "snapshot_ts": now, "realized_pnl": closed["realized_pnl"] if portfolio else None,
                            "open_pnl": status.get("open_profit", 0.0) if portfolio and not status.get("view_stale", False) else None,
                            "open_positions": position_count,
                            "oldest_open_mark_ts": min(marks) if marks and marks_complete else None})
            pnl = {**closed, "open_pnl": open_pnl, "paper_pnl": closed["realized_pnl"],
                   "replay_inclusive_net": float(status.get("net") or 0.0),
                   "basis": "persisted closures after paper cutover; open mark and replay-inclusive net shown separately"}
            status["paper_pnl"] = pnl["paper_pnl"]
            rows.append({**copy.deepcopy(profile), "status": status, "effective_inputs": effective, "paper_only": True,
                         "execution_authorized": False, "runtime_available": portfolio is not None,
                         "valuation_complete": valuation_complete, "missing_mark_symbols": missing_marks,
                         "pnl": pnl, "feed": self._feed_summary(status, portfolio)})
        accounting = validate_paper_pnl(ledgers, as_of_ts=now)
        for row, validated in zip(rows, accounting["profiles"]):
            for field in ("realized_pnl", "open_pnl", "total_pnl"):
                row["pnl"][field] = validated[field]
            row["pnl"]["paper_pnl"] = validated["realized_pnl"]
            row["status"]["paper_pnl"] = validated["realized_pnl"]
            row["valuation_complete"] = validated["accounting_complete"]
        aggregate = {"workspace_count": len(rows), "capital": sum(float(row["status"].get("capital") or 0.0) for row in rows),
                     "equity": sum(float(row["status"].get("equity") or 0.0) for row in rows),
                     "net": sum(float(row["status"].get("net") or 0.0) for row in rows),
                     "open_positions": sum(int(row["status"].get("positions") or 0) for row in rows),
                     "all_warm": all(bool(row["status"].get("all_warm")) for row in rows),
                     "pnl_basis": "persisted closures after paper cutover; open mark and replay-inclusive synthetic equity are separate"}
        # Every API consumer must receive the same four-ledger valuation. The
        # legacy projection must not claim completeness for stale/missing marks
        # or substitute partial sums when one of the runtimes is unavailable.
        aggregate.update(accounting["aggregate"])
        aggregate["paper_pnl"] = aggregate["realized_pnl"]
        aggregate["runtime_count"] = sum(row["runtime_available"] for row in rows)
        aggregate["missing_runtime_ids"] = [row["id"] for row in rows if not row["runtime_available"]]
        if not aggregate["accounting_complete"]:
            for field in ("capital", "equity", "net"):
                aggregate[field] = None
        aggregate["fees_status"] = "SIMULATOR_CONFIGURED_NOT_BROKER_RECONCILED"
        aggregate["valuation_status"] = ("PAPER_VALUATION_COMPLETE" if aggregate["accounting_complete"]
                                         else "PAPER_VALUATION_INCOMPLETE")
        aggregate["reconciliation_status"] = "NO_BROKER_RECONCILIATION"
        return {"mode": "concurrent_paper", "paper_only": True, "profiles": rows, "aggregate": aggregate,
                "paper_pnl": accounting,
                "connections": self._connections(rows), "available_assets": _available_assets(),
                "runtime_feed_mode": getattr(self.parent, "feed_mode", "unknown"),
                "requested_futures": requested_futures_metadata(),
                "execution_authorized": False}

    def update(self, profile_id: str, body: Dict[str, Any]):
        if profile_id not in self.profiles:
            raise ValueError("unknown command center profile")
        with self._lock:
            old = self.profiles[profile_id]
            candidate = copy.deepcopy(old)
            if not isinstance(body, dict):
                raise ValueError("workspace update must be an object")
            if set(body) - {"assets", "chart", "inputs", "asset_overrides", "expected_revision"}:
                raise ValueError("unknown workspace update fields or conflicting asset selector")
            if "expected_revision" not in body:
                if old.get("asset_overrides") or "asset_overrides" in body:
                    raise ValueError("expected_revision is required for per-asset workspace settings")
            else:
                expected = body["expected_revision"]
                if type(expected) is not int or expected < 0:
                    raise ValueError("expected_revision must be a nonnegative integer")
                if expected != old["config_revision"]:
                    raise WorkspaceRevisionConflict("workspace configuration revision changed; reload before editing")
            if "assets" in body:
                candidate["assets"] = _validate_assets(body["assets"])
            if "chart" in body:
                candidate["chart"] = {**old["chart"], **validate_chart_config(body["chart"])}
            if "inputs" in body:
                if not isinstance(body["inputs"], dict):
                    raise ValueError("inputs must be an object")
                values = dict(old["inputs"])
                values.update(body["inputs"])
                validate_values(values)
                candidate["inputs"] = values
            if "asset_overrides" in body:
                candidate["asset_overrides"] = copy.deepcopy(body["asset_overrides"])
            candidate = normalize_workspace(candidate)
            for override in candidate["asset_overrides"].values():
                if override.get("preset") and not Path(preset_path(self.parent.base_dir, override["preset"])).is_file():
                    raise ValueError("workspace preset not found")
            candidate["config_revision"] = old["config_revision"] + 1
            portfolio = self.portfolios.get(profile_id)
            if portfolio is None:
                raise ValueError("command center paper runtime is not running")
            old_bytes = self._path(profile_id).read_bytes()
            # reconfigure all runners while holding one workspace boundary; each runtime
            # replays its cached bars and restores exact state if any replay fails.
            try:
                result = portfolio.reconfigure(candidate, persist=lambda: self._save(candidate))
            except Exception:
                path = self._path(profile_id)
                if not path.exists() or path.read_bytes() != old_bytes:
                    tmp = path.with_suffix(".json.rollback.tmp")
                    with tmp.open("wb") as fh:
                        fh.write(old_bytes)
                        fh.flush()
                        os.fsync(fh.fileno())
                    os.replace(tmp, path)
                raise
            self.profiles[profile_id] = candidate
            portfolio.workspace = candidate
            result.update(schema_version=candidate["schema_version"], config_revision=candidate["config_revision"])
            return result

    def update_asset(self, profile_id: str, symbol: str, body: Dict[str, Any]):
        """Apply a revisioned edit to one admitted asset, never a parent writer."""
        if not isinstance(body, dict) or set(body) - {"expected_revision", "inputs", "chart", "preset", "reset"}:
            raise ValueError("unknown asset configuration fields or conflicting asset selector")
        if "expected_revision" not in body:
            raise ValueError("expected_revision is required for asset configuration")
        if "reset" in body and type(body["reset"]) is not bool:
            raise ValueError("reset must be true or false")
        if body.get("reset") and set(body) - {"expected_revision", "reset"}:
            raise ValueError("reset cannot be combined with other asset settings")
        if not body.get("reset") and not set(body) & {"inputs", "chart", "preset"}:
            raise ValueError("asset configuration needs inputs, chart, preset or reset")
        with self._lock:
            profile = self.profiles.get(profile_id)
            portfolio = self.portfolios.get(profile_id)
            if (profile is None or portfolio is None or symbol not in profile["assets"]
                    or symbol not in portfolio.runners):
                raise ValueError("selected workspace asset is unavailable")
            overrides = copy.deepcopy(profile["asset_overrides"])
            if body.get("reset"):
                overrides.pop(symbol, None)
            else:
                entry = overrides.setdefault(symbol, {})
                for key in ("inputs", "chart"):
                    if key in body:
                        if not isinstance(body[key], dict):
                            raise ValueError(f"asset {key} must be an object")
                        entry[key] = {**entry.get(key, {}), **body[key]}
                if "preset" in body:
                    entry["preset"] = body["preset"]
            result = self.update(profile_id, {"expected_revision": body["expected_revision"],
                                              "asset_overrides": overrides})
            result["asset"] = symbol
            return result

    def pause(self, profile_id: str, paused: bool):
        if profile_id not in self.portfolios:
            raise ValueError("unknown command center profile")
        portfolio = self.portfolios[profile_id]
        with portfolio._lock:
            previous = portfolio.paused
            cancelled = 0
            changed = []
            try:
                for runner in portfolio.runner_list():
                    old = runner.paused
                    cancelled += runner.set_paused(bool(paused))
                    changed.append((runner, old))
            except Exception:
                for runner, old in reversed(changed):
                    runner.set_paused(old)
                portfolio.paused = previous
                raise
            portfolio.paused = bool(paused)
        return {"ok": True, "id": profile_id, "paused": bool(paused),
                "cancelled_pending_entries": cancelled, "paper_only": True}

    def flatten(self, profile_id: str):
        if profile_id not in self.portfolios:
            raise ValueError("unknown command center profile")
        portfolio = self.portfolios[profile_id]
        with portfolio._lock:
            runners = portfolio.runner_list()
            portfolio.paused = True
            pause_errors = []
            for runner in runners:
                try:
                    runner.set_paused(True)
                except Exception as ex:
                    pause_errors.append({"asset": runner.symbol, "detail": f"{type(ex).__name__}: {ex}"})
            if pause_errors:
                error = FlattenUnavailableError(
                    "Could not pause every paper runner; flattening was not attempted")
                error.flattened_positions = 0
                error.failed_assets = pause_errors
                error.partial = False
                raise error

            for runner in runners:
                emulator = getattr(runner, "em", None)
                shadow = getattr(emulator, "shadow", None)
                has_open = bool(getattr(emulator, "open", ())) or bool(getattr(shadow, "open", ()))
                mark = getattr(runner, "last_price", None)
                try:
                    valid_mark = mark is not None and math.isfinite(float(mark)) and float(mark) > 0
                except (TypeError, ValueError, OverflowError):
                    valid_mark = False
                if has_open and not valid_mark:
                    error = FlattenUnavailableError(
                        f"{runner.symbol}: cannot flatten a paper position without a valid observed mark")
                    error.flattened_positions = 0
                    error.failed_assets = [{"asset": runner.symbol, "detail": str(error)}]
                    error.partial = False
                    raise error

            count = 0
            shadow_censored = 0
            failures = []
            for runner in runners:
                emulator = getattr(runner, "em", None)
                primary_before = list(getattr(emulator, "open", ()) or ())
                shadow_before = list(getattr(getattr(emulator, "shadow", None), "open", ()) or ())
                primary_ids_before = {getattr(trade, "entry_id", id(trade)) for trade in primary_before}
                shadow_ids_before = {getattr(trade, "entry_id", id(trade)) for trade in shadow_before}
                try:
                    reported = int(runner.flatten("workspace") or 0)
                except Exception as ex:
                    primary_after = list(getattr(emulator, "open", ()) or ())
                    shadow_after = list(getattr(getattr(emulator, "shadow", None), "open", ()) or ())
                    primary_ids_after = {getattr(trade, "entry_id", id(trade)) for trade in primary_after}
                    shadow_ids_after = {getattr(trade, "entry_id", id(trade)) for trade in shadow_after}
                    # A runner can close/censor state and then fail while
                    # recording its execution receipt. Reconcile state changes
                    # even when no return value was produced.
                    count += len(primary_ids_before - primary_ids_after)
                    shadow_censored += len(shadow_ids_before - shadow_ids_after)
                    failures.append({"asset": runner.symbol, "detail": f"{type(ex).__name__}: {ex}"})
                else:
                    if emulator is None:
                        # Keep small injected/test runners compatible; production
                        # AssetRunner instances always expose their emulator.
                        count += reported
                    else:
                        primary_after = list(getattr(emulator, "open", ()) or ())
                        shadow_after = list(getattr(getattr(emulator, "shadow", None), "open", ()) or ())
                        primary_ids_after = {getattr(trade, "entry_id", id(trade)) for trade in primary_after}
                        shadow_ids_after = {getattr(trade, "entry_id", id(trade)) for trade in shadow_after}
                        count += len(primary_ids_before - primary_ids_after)
                        shadow_censored += len(shadow_ids_before - shadow_ids_after)
            if failures:
                error = FlattenUnavailableError(
                    f"Flatten completed with {count} position(s) closed and {len(failures)} runner failure(s)")
                error.flattened_positions = count
                error.shadow_censored_positions = shadow_censored
                error.failed_assets = failures
                error.partial = count > 0
                raise error
        return {"ok": True, "id": profile_id, "flattened_positions": count,
                "shadow_censored_positions": shadow_censored,
                "paused": True, "paper_only": True}
