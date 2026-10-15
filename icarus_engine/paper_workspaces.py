"""Independent, concurrent paper-only strategy workspaces for the dashboard."""
from __future__ import annotations

from contextlib import ExitStack
import copy
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from .assets import REGISTRY, apply_chart_config, validate_chart_config
from .runtime import AssetRunner, Journal, Portfolio, RunnerConfig, apply_spec_meta, resolve_inputs, validate_values


_MINI_MICRO_FUTURES = (
    "NQ", "MNQ", "ES", "MES", "YM", "MYM", "RTY", "M2K",
    "GC", "MGC", "SI", "SIL",
)
_PROFILE_DEFAULTS = (
    {"id": "cc1", "name": "20m Minis + Micros", "description": "Heikin Ashi · 20 minute · registered mini/micro futures",
     "assets": list(_MINI_MICRO_FUTURES), "chart": {"timeframe": "20", "chart_type": "heikin_ashi", "fill_on": "real", "security_source": "chart"}, "inputs": {}},
    {"id": "cc2", "name": "Short Target + ETH", "description": "5 minute starting profile · lower targets · larger size · includes ETH",
     "assets": [*_MINI_MICRO_FUTURES, "ETH"], "chart": {"timeframe": "5", "chart_type": "heikin_ashi", "fill_on": "real", "security_source": "chart"},
     "inputs": {"tp1_pts": 7.5, "tp2_pts": 15.0, "qty_contracts": 10}},
    {"id": "cc3", "name": "Workspace 3", "description": "Independent paper workspace · editable starting profile",
     "assets": list(_MINI_MICRO_FUTURES), "chart": {"timeframe": "20", "chart_type": "heikin_ashi", "fill_on": "real", "security_source": "chart"}, "inputs": {}},
    {"id": "cc4", "name": "5m Minis + Micros", "description": "Heikin Ashi · 5 minute · registered mini/micro futures",
     "assets": list(_MINI_MICRO_FUTURES), "chart": {"timeframe": "5", "chart_type": "heikin_ashi", "fill_on": "real", "security_source": "chart"}, "inputs": {}},
)
_IDS = {row["id"] for row in _PROFILE_DEFAULTS}


class SharedFeed:
    """Share feed sessions and collapse overlapping history requests across workspaces."""
    def __init__(self, feed: Any):
        self._feed = feed
        self._lock = threading.RLock()
        self._candles: Dict[Tuple[str, int], List[Tuple[int, int, Dict[int, Any]]]] = {}
        self._short_cache: Dict[Tuple[Any, ...], Tuple[float, Any]] = {}

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
                segments.append((left, right, {int(row.ts):row for row in rows}))
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

    def _resolved(self, spec):
        chart = validate_chart_config(self.workspace["chart"])
        spec = apply_chart_config(spec, chart, pin=True)
        inputs, meta, sources = resolve_inputs(
            spec, self.base_dir, self.profile, self.preset, self.workspace["inputs"],
            skip_asset_overrides=True, extra_label=f"command-center:{self.workspace['id']}"
        )
        spec = apply_spec_meta(spec, meta)
        spec = apply_chart_config(spec, chart, pin=True)
        return spec, inputs, sources

    def make_runner(self, spec):
        spec, inputs, sources = self._resolved(spec)
        base_spec = copy.deepcopy(spec)
        scale = self._ref_price() if spec.symbol != self.pts_ref_symbol else 0.0
        cfg = RunnerConfig(spec=spec, inputs=inputs, warmup_bars=self.warmup_bars,
                           sources=sources, profile=self.profile, preset=self.preset or spec.preset,
                           pts_ref_price=scale, base_dir=self.base_dir, base_spec=base_spec)
        runner = AssetRunner(cfg, self.journal, self.feeds)
        runner.latency_telemetry = self.latency_telemetry
        return runner

    def _refresh_continuous_feeds(self, now=None):
        if self.workspace["id"] != "cc1":
            return False
        return super()._refresh_continuous_feeds(now)

    def reconfigure(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        chart = validate_chart_config(candidate["chart"])
        values = dict(candidate["inputs"])
        validate_values(values)
        runners = self.runner_list()
        plans = []
        for runner in runners:
            runner.ensure_configurable()
            spec = apply_chart_config(copy.deepcopy(runner.cfg.base_spec or runner.spec), chart, pin=True)
            inputs, meta, sources = resolve_inputs(
                spec, self.base_dir, self.profile, self.preset, values,
                skip_asset_overrides=True, extra_label=f"command-center:{self.workspace['id']}"
            )
            spec = apply_spec_meta(spec, meta)
            spec = apply_chart_config(spec, chart, pin=True)
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
                for runner, spec, inputs, sources in plans:
                    runner.spec = spec
                    runner.cfg.spec = spec
                    runner.cfg.base_spec = copy.deepcopy(spec)
                    runner.cfg.sources = list(sources)
                    runner.rewarm(inputs, sources, reset_live_boundary=True)
            except Exception:
                for runner, snapshot, base_spec in reversed(snapshots):
                    runner.restore_configuration_snapshot(snapshot)
                    runner.cfg.base_spec = base_spec
                raise
        self.workspace.update({"chart": chart, "inputs": values})
        return {"ok": True, "id": self.workspace["id"], "assets": [r.symbol for r in runners],
                "chart": chart, "inputs": values, "paper_only": True, "execution_authorized": False}


class PaperWorkspaceManager:
    """Four isolated paper ledgers and runner maps, sharing the parent feed sessions."""
    def __init__(self, parent: Portfolio):
        self.parent = parent
        self.root = Path(parent.base_dir or os.getcwd()) / "command_centers"
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
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
                profile.update({k: saved[k] for k in ("name", "description", "assets", "chart", "inputs") if k in saved})
            profile["assets"] = list(default["assets"])
            profile["chart"] = validate_chart_config(profile["chart"])
            values = dict(profile["inputs"])
            validate_values(values)
            profile["inputs"] = values
            self.profiles[profile["id"]] = profile
            if not path.exists():
                self._save(profile)

    def _save(self, profile):
        path = self._path(profile["id"])
        tmp = path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(profile, fh, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)

    def start(self):
        started = []
        try:
            for profile_id, profile in self.profiles.items():
                journal = Journal(str(self.root / f"{profile_id}.sqlite3"))
                portfolio = WorkspacePortfolio(
                    journal, str(self.parent.base_dir), poll_sec=self.parent.poll_sec,
                    profile=self.parent.profile, preset=self.parent.preset,
                    warmup_bars=self.parent.warmup_bars, pts_ref_symbol=self.parent.pts_ref_symbol,
                    feeds=self._feeds, workspace=profile,
                )
                portfolio.pts_ref_price = self.parent.pts_ref_price
                self.portfolios[profile_id] = portfolio
                for symbol in profile["assets"]:
                    spec = copy.deepcopy(REGISTRY[symbol])
                    portfolio.add_asset(spec, start=False)
                started.append(portfolio)
                portfolio.start()
        except Exception:
            for portfolio in reversed(started):
                portfolio.stop()
            raise

    def stop(self):
        for portfolio in reversed(list(self.portfolios.values())):
            portfolio.stop()

    def snapshot(self):
        rows = []
        for profile_id, profile in self.profiles.items():
            portfolio = self.portfolios.get(profile_id)
            status = portfolio.status(nonblocking=True) if portfolio else {"assets": [], "all_warm": False}
            runners = portfolio.runner_list() if portfolio else []
            effective = runners[0].inputs_base.to_dict() if runners else {}
            rows.append({**copy.deepcopy(profile), "status": status, "effective_inputs": effective, "paper_only": True,
                         "execution_authorized": False})
        return {"mode": "concurrent_paper", "profiles": rows, "execution_authorized": False}

    def update(self, profile_id: str, body: Dict[str, Any]):
        if profile_id not in self.profiles:
            raise ValueError("unknown command center profile")
        with self._lock:
            old = self.profiles[profile_id]
            candidate = copy.deepcopy(old)
            if "chart" in body:
                candidate["chart"] = validate_chart_config(body["chart"])
            if "inputs" in body:
                if not isinstance(body["inputs"], dict):
                    raise ValueError("inputs must be an object")
                values = dict(old["inputs"])
                values.update(body["inputs"])
                validate_values(values)
                candidate["inputs"] = values
            portfolio = self.portfolios.get(profile_id)
            if portfolio is None:
                raise ValueError("command center paper runtime is not running")
            old_profile = copy.deepcopy(old)
            self._save(candidate)
            # reconfigure all runners while holding one workspace boundary; each runtime
            # replays its cached bars and restores exact state if any replay fails.
            try:
                result = portfolio.reconfigure(candidate)
            except Exception:
                self._save(old_profile)
                raise
            self.profiles[profile_id] = candidate
            portfolio.workspace = candidate
            return result

    def pause(self, profile_id: str, paused: bool):
        if profile_id not in self.portfolios:
            raise ValueError("unknown command center profile")
        portfolio = self.portfolios[profile_id]
        with portfolio._lock:
            portfolio.paused = bool(paused)
            cancelled = 0
            for runner in portfolio.runner_list():
                cancelled += runner.set_paused(bool(paused))
        return {"ok": True, "id": profile_id, "paused": bool(paused),
                "cancelled_pending_entries": cancelled, "paper_only": True}

    def flatten(self, profile_id: str):
        if profile_id not in self.portfolios:
            raise ValueError("unknown command center profile")
        portfolio = self.portfolios[profile_id]
        with portfolio._lock:
            portfolio.paused = True
            runners = portfolio.runner_list()
            for runner in runners:
                runner.set_paused(True)
            count = sum(runner.flatten("workspace") for runner in runners)
        return {"ok": True, "id": profile_id, "flattened_positions": count,
                "paused": True, "paper_only": True}
