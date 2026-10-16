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
from .runtime import (
    AssetRunner,
    FlattenUnavailableError,
    Journal,
    Portfolio,
    RunnerConfig,
    apply_spec_meta,
    resolve_inputs,
    validate_values,
)


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
        rows = []
        for profile_id, profile in self.profiles.items():
            portfolio = self.portfolios.get(profile_id)
            status = portfolio.status(nonblocking=True) if portfolio else {"assets": [], "all_warm": False}
            runners = portfolio.runner_list() if portfolio else []
            effective = runners[0].inputs_base.to_dict() if runners else {}
            closed = portfolio.journal.closed_paper_profit() if portfolio else {"realized_pnl": 0.0, "closed_pieces": 0, "last_close_ts": None}
            open_pnl = float(status.get("open_profit") or 0.0)
            pnl = {**closed, "open_pnl": open_pnl, "paper_pnl": closed["realized_pnl"],
                   "replay_inclusive_net": float(status.get("net") or 0.0),
                   "basis": "persisted closures after paper cutover; open mark and replay-inclusive net shown separately"}
            status["paper_pnl"] = pnl["paper_pnl"]
            rows.append({**copy.deepcopy(profile), "status": status, "effective_inputs": effective, "paper_only": True,
                         "execution_authorized": False, "pnl": pnl, "feed": self._feed_summary(status, portfolio)})
        aggregate = {"workspace_count": len(rows), "capital": sum(float(row["status"].get("capital") or 0.0) for row in rows),
                     "equity": sum(float(row["status"].get("equity") or 0.0) for row in rows),
                     "net": sum(float(row["status"].get("net") or 0.0) for row in rows),
                     "realized_pnl": sum(row["pnl"]["realized_pnl"] for row in rows),
                     "open_pnl": sum(row["pnl"]["open_pnl"] for row in rows),
                     "open_positions": sum(int(row["status"].get("positions") or 0) for row in rows),
                     "all_warm": all(bool(row["status"].get("all_warm")) for row in rows),
                     "pnl_basis": "persisted closures after paper cutover; open mark and replay-inclusive synthetic equity are separate"}
        aggregate["paper_pnl"] = aggregate["realized_pnl"]
        return {"mode": "concurrent_paper", "paper_only": True, "profiles": rows, "aggregate": aggregate,
                "connections": self._connections(rows), "execution_authorized": False}

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
            failures = []
            for runner in runners:
                try:
                    count += int(runner.flatten("workspace") or 0)
                except Exception as ex:
                    failures.append({"asset": runner.symbol, "detail": f"{type(ex).__name__}: {ex}"})
            if failures:
                error = FlattenUnavailableError(
                    f"Flatten completed with {count} position(s) closed and {len(failures)} runner failure(s)")
                error.flattened_positions = count
                error.failed_assets = failures
                error.partial = count > 0
                raise error
        return {"ok": True, "id": profile_id, "flattened_positions": count,
                "paused": True, "paper_only": True}
