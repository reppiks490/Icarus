"""Bounded in-process jobs owned by one explicit paper-workspace identity."""
from __future__ import annotations

import copy
import json
import time
import uuid
from dataclasses import replace
from pathlib import Path
from threading import RLock, Thread

from .assets import REGISTRY, validate_chart_config
from .backtest import freeze_replay_port, run_backtest, validate_backtest_params
from .paper_workspaces import _validate_assets
from .parity import compare_lists, engine_trades_from_rows, read_tv_trades_text
from .pine.timeframe import tf_minutes
from .runtime import preset_path
from .workspace_config import WorkspaceRevisionConflict, normalize_workspace


class WorkspaceJobError(ValueError):
    """A scoped request failed with an HTTP-compatible status and safe detail."""

    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


class ScopedWorkspaceJobs:
    """Own jobs locally; never consult the parent backtest job registry.

    The workspace mutation lock protects acceptance against its transactions.
    Workers release the registry lock before entering any manager transaction.
    Replay workers receive only a frozen shim and a defensive request copy.
    """

    _LIMIT = 20
    _BACKTEST_FIELDS = {
        "preset", "inputs", "fill_on", "chart_type", "timeframe", "security_source",
        "slippage_ticks", "commission", "capital", "session", "window_start",
        "window_end", "leverage",
    }

    def __init__(self, manager):
        self.manager = manager
        self._lock = RLock()
        self._jobs = {}

    def _configuration_lock(self, workspace_id):
        if workspace_id not in self.manager.profiles:
            raise WorkspaceJobError(404, "unknown workspace")
        return self.manager.configuration_lock(workspace_id)

    def _source(self, workspace_id, symbol, *, whole=False):
        profile = self.manager.profiles.get(workspace_id)
        if profile is None:
            raise WorkspaceJobError(404, "unknown workspace")
        if not isinstance(symbol, str) or symbol != symbol.strip().upper() or (symbol == "*" and not whole):
            raise WorkspaceJobError(400, "asset must be a canonical symbol")
        if symbol != "*" and (symbol not in REGISTRY or symbol not in profile["assets"]):
            raise WorkspaceJobError(404, "selected workspace asset is unavailable")
        port = self.manager.portfolios.get(workspace_id)
        if port is None:
            raise WorkspaceJobError(503, "selected workspace runtime is unavailable")
        symbols = profile["assets"] if symbol == "*" else [symbol]
        for selected in symbols:
            runner = port.runners.get(selected)
            if runner is None:
                raise WorkspaceJobError(404, "selected workspace asset is unavailable")
            with runner.lock:
                if not runner.warm or getattr(runner, "rewarming", False):
                    raise WorkspaceJobError(409, f"{selected}: selected workspace asset is still warming")
        return profile, port, port.runners.get(symbol)

    @staticmethod
    def _revision(profile, body):
        if not isinstance(body, dict):
            raise WorkspaceJobError(400, "job request must be an object")
        expected = body.get("expected_revision")
        if type(expected) is not int or expected < 0:
            raise WorkspaceJobError(400, "expected_revision must be a nonnegative integer")
        if expected != profile["config_revision"]:
            raise WorkspaceJobError(409, "workspace configuration revision changed; reload before editing")
        return expected

    @staticmethod
    def _bad_request(error):
        if isinstance(error, WorkspaceJobError):
            return error
        status = 409 if isinstance(error, WorkspaceRevisionConflict) else 400
        return WorkspaceJobError(status, str(error))

    def _validate_config(self, profile, symbol, body):
        candidate = copy.deepcopy(profile)
        if symbol == "*":
            if set(body) - {"expected_revision", "assets", "inputs", "chart", "asset_overrides"}:
                raise ValueError("unknown workspace configuration fields or conflicting asset selector")
            if not set(body) & {"assets", "inputs", "chart", "asset_overrides"}:
                raise ValueError("workspace configuration needs assets, inputs, chart or asset_overrides")
            if "assets" in body:
                candidate["assets"] = _validate_assets(body["assets"])
            if "asset_overrides" in body:
                candidate["asset_overrides"] = copy.deepcopy(body["asset_overrides"])
            target = candidate
        else:
            if set(body) - {"expected_revision", "inputs", "chart", "preset", "reset"}:
                raise ValueError("unknown asset configuration fields or conflicting asset selector")
            if "reset" in body and type(body["reset"]) is not bool:
                raise ValueError("reset must be true or false")
            if body.get("reset"):
                if set(body) - {"expected_revision", "reset"}:
                    raise ValueError("reset cannot be combined with other asset settings")
                candidate["asset_overrides"].pop(symbol, None)
                return normalize_workspace(candidate)
            if not set(body) & {"inputs", "chart", "preset"}:
                raise ValueError("asset configuration needs inputs, chart, preset or reset")
            target = candidate["asset_overrides"].setdefault(symbol, {})
            if "preset" in body:
                target["preset"] = body["preset"]
        for key in ("inputs", "chart"):
            if key in body:
                if not isinstance(body[key], dict):
                    raise ValueError(f"{key} must be an object")
                values = validate_chart_config(body[key]) if key == "chart" else body[key]
                target[key] = {**target.get(key, {}), **values}
        candidate = normalize_workspace(candidate)
        for override in candidate["asset_overrides"].values():
            name = override.get("preset")
            if name and not Path(preset_path(self.manager.parent.base_dir, name)).is_file():
                raise WorkspaceJobError(404, "workspace preset not found")
        return candidate

    @staticmethod
    def _resolve_candidate(port, candidate, symbols=None):
        # Admission reads configuration only, without constructing runners or
        # fetching data. The committing transaction resolves/validates again.
        with port._lock:
            for selected in candidate["assets"] if symbols is None else symbols:
                runner = port.runners.get(selected)
                if runner is None:
                    spec = copy.deepcopy(REGISTRY[selected])
                else:
                    with runner.lock:
                        spec = copy.deepcopy(runner.cfg.base_spec or runner.spec)
                port._resolved(spec, candidate)

    def submit_config(self, workspace_id, symbol, body):
        try:
            if not isinstance(body, dict):
                raise ValueError("job request must be an object")
            params = copy.deepcopy(body)
            identity = json.dumps(params, sort_keys=True, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError, OverflowError) as error:
            raise self._bad_request(error) from error
        # Reusing accepted work must remain responsive while its transaction owns
        # the workspace lock. Identity includes the previously checked revision;
        # this path accepts no new edit and never changes configuration.
        existing = self._active_config(workspace_id, symbol, identity)
        if existing is not None:
            return existing
        with self._configuration_lock(workspace_id):
            profile, port, _runner = self._source(workspace_id, symbol, whole=True)
            revision = self._revision(profile, params)
            try:
                candidate = self._validate_config(profile, symbol, params)
                self._resolve_candidate(port, candidate)
            except OSError as error:
                raise WorkspaceJobError(503, "workspace configuration files are unavailable") from error
            except (TypeError, ValueError, OverflowError) as error:
                raise self._bad_request(error) from error

            def work(_progress):
                # The manager compares expected_revision again while committing.
                if symbol == "*":
                    return self.manager.update(workspace_id, copy.deepcopy(params))
                return self.manager.update_asset(workspace_id, symbol, copy.deepcopy(params))

            return self._accept("config", workspace_id, symbol, revision, params, work, identity)

    def submit_rewarm(self, workspace_id, symbol, body):
        if not isinstance(body, dict) or set(body) != {"expected_revision"}:
            raise WorkspaceJobError(400, "rewarm accepts only expected_revision; scope belongs in the route")
        params = copy.deepcopy(body)
        try:
            identity = "rewarm:" + json.dumps(params, sort_keys=True, allow_nan=False)
        except (TypeError, ValueError, OverflowError) as error:
            raise self._bad_request(error) from error
        existing = self._active_config(workspace_id, symbol, identity)
        if existing is not None:
            return existing
        with self._configuration_lock(workspace_id):
            profile, port, _runner = self._source(workspace_id, symbol, whole=True)
            revision = self._revision(profile, params)
            try:
                selected = profile["assets"] if symbol == "*" else [symbol]
                self._resolve_candidate(port, profile, selected)
            except OSError as error:
                raise WorkspaceJobError(503, "workspace configuration files are unavailable") from error
            except (TypeError, ValueError, OverflowError) as error:
                raise self._bad_request(error) from error

            def work(_progress):
                return self.manager.rewarm(workspace_id, None if symbol == "*" else symbol, copy.deepcopy(params))

            return self._accept("config", workspace_id, symbol, revision,
                                {"operation": "rewarm", **params}, work, identity)

    @staticmethod
    def _validate_cached(frozen, symbol, params):
        src = frozen.runners[symbol]
        effective = {key: getattr(src.spec, key) for key in
                     ("fill_on", "chart_type", "security_source", "slippage_ticks", "commission", "capital", "session")}
        effective["timeframe"] = src.spec.chart_tf
        validate_backtest_params({**effective, **params})
        inputs = replace(src.inputs_base, **params.get("inputs", {}))
        requested = {tf_minutes(getattr(inputs, f"htf_tf_{n}")) for n in range(1, 6)}
        available = set(src.chains) | {m for m, rows in src.deep.items() if rows}
        if requested - available:
            raise ValueError(f"{symbol}: cached history unavailable for requested HTF minutes {sorted(requested - available)}")
        chart = tf_minutes(params.get("timeframe", src.spec.chart_tf))
        if chart != tf_minutes(src.spec.chart_tf):
            if not any(int(sub) <= chart and chart % int(sub) == 0 for _bar, sub in src.subbars):
                raise ValueError(f"{symbol}: cached source bars cannot rebuild requested chart timeframe")

    def submit_backtest(self, workspace_id, symbol, body):
        with self._configuration_lock(workspace_id):
            profile, port, runner = self._source(workspace_id, symbol)
            revision = self._revision(profile, body)
            try:
                if set(body) - self._BACKTEST_FIELDS - {"expected_revision"}:
                    raise ValueError("unknown backtest fields or conflicting asset selector")
                params = validate_backtest_params({k: v for k, v in body.items() if k != "expected_revision"})
                with port._lock, runner.lock:
                    frozen = freeze_replay_port(port, symbol)
                    if "preset" in body:
                        candidate = copy.deepcopy(profile)
                        candidate["asset_overrides"].setdefault(symbol, {})["preset"] = body["preset"]
                        candidate = normalize_workspace(candidate)
                        name = candidate["asset_overrides"][symbol]["preset"]
                        if name and not Path(preset_path(port.base_dir, name)).is_file():
                            raise WorkspaceJobError(404, "workspace preset not found")
                        spec, inputs, sources = port._resolved(copy.deepcopy(runner.cfg.base_spec or runner.spec), candidate)
                        src = frozen.runners[symbol]
                        src.spec = spec
                        src.cfg.spec = copy.deepcopy(spec)
                        src.inputs_base = inputs
                        src.inputs = copy.deepcopy(inputs)
                        src.cfg.inputs = copy.deepcopy(inputs)
                        src.cfg.sources = list(sources)
                        src.cfg.preset = name
                        frozen.preset_for = lambda _runner: name
                    self._validate_cached(frozen, symbol, params)
                worker_params = copy.deepcopy(params)
                worker_params.pop("preset", None)
            except OSError as error:
                raise WorkspaceJobError(503, "workspace configuration files are unavailable") from error
            except (TypeError, ValueError, OverflowError) as error:
                raise self._bad_request(error) from error

            def work(progress):
                result = run_backtest(frozen, symbol, **worker_params, progress=progress)
                result.update(workspace_id=workspace_id, config_revision=revision,
                              paper_only=True, execution_authorized=False,
                              evidence_basis="Engineering replay evidence; no execution approval or accuracy proof")
                return result

            return self._accept("backtest", workspace_id, symbol, revision, {"asset": symbol, **params}, work)

    def _active_config(self, workspace_id, symbol, identity):
        with self._lock:
            for row in self._jobs.values():
                if (row["kind"] == "config" and row["workspace_id"] == workspace_id
                        and row["status"] == "running"
                        and (symbol == "*" or row["asset"] in ("*", symbol))):
                    if row["asset"] == symbol and row["_identity"] == identity:
                        return self._receipt(row, False)
                    raise WorkspaceJobError(409, "overlapping workspace configuration job is already running")
        return None

    def _accept(self, kind, workspace_id, symbol, revision, params, work, identity=None):
        with self._lock:
            if kind == "config":
                existing = self._active_config(workspace_id, symbol, identity)
                if existing is not None:
                    return existing
            if len(self._jobs) >= self._LIMIT:
                completed = [row for row in self._jobs.values() if row["status"] != "running"]
                if not completed:
                    raise WorkspaceJobError(409, "workspace job capacity is full; wait for an active job")
                oldest = min(completed, key=lambda row: (row["finished"], row["started"]))
                self._jobs.pop(oldest["id"])
            job_id = f"ws-{uuid.uuid4().hex}"
            row = {"id": job_id, "kind": kind, "workspace_id": workspace_id, "asset": symbol,
                   "config_revision": revision, "status": "running", "progress": 0,
                   "started": time.time(), "finished": None, "params": copy.deepcopy(params),
                   "error": None, "_identity": identity}
            self._jobs[job_id] = row

            def progress(value):
                with self._lock:
                    row["progress"] = value

            def run():
                try:
                    result = work(progress)
                    with self._lock:
                        row.update(result=result, status="done", finished=time.time())
                except Exception as error:
                    with self._lock:
                        row.update(status="error", error=f"{type(error).__name__}: {error}", finished=time.time())

            try:
                Thread(target=run, daemon=True, name=f"workspace-{kind}-{job_id}").start()
            except Exception as error:
                self._jobs.pop(job_id, None)
                raise WorkspaceJobError(503, f"workspace job worker could not start: {error}") from error
            return self._receipt(row, True)

    @staticmethod
    def _receipt(row, created):
        return {"job": row["id"], "workspace_id": row["workspace_id"],
                "config_revision": row["config_revision"], "created": created}

    def _owned(self, workspace_id, job_id):
        row = self._jobs.get(job_id)
        if row is None or row["workspace_id"] != workspace_id:
            raise WorkspaceJobError(404, "unknown workspace job")
        return row

    def get(self, workspace_id, job_id, *, full=True):
        with self._lock:
            row = self._owned(workspace_id, job_id)
            out = {k: copy.deepcopy(v) for k, v in row.items() if k not in ("_identity", "result")}
            if full and row["status"] == "done":
                out["result"] = {k: copy.deepcopy(v) for k, v in row["result"].items() if k != "csv"}
            return out

    def _completed_backtest(self, workspace_id, job_id):
        row = self._owned(workspace_id, job_id)
        if row["kind"] != "backtest" or row["status"] != "done":
            raise WorkspaceJobError(409, "workspace backtest is not completed")
        return row

    def export_csv(self, workspace_id, job_id):
        with self._lock:
            return self._completed_backtest(workspace_id, job_id)["result"]["csv"]

    def compare(self, workspace_id, job_id, csv_text, tolerance=1):
        with self._lock:
            row = self._completed_backtest(workspace_id, job_id)
            result = copy.deepcopy(row["result"])
            revision = row["config_revision"]
        if not isinstance(csv_text, str) or not csv_text.strip():
            raise WorkspaceJobError(400, "csv text required")
        if type(tolerance) is not int or not 0 <= tolerance <= 1000:
            raise WorkspaceJobError(400, "comparison tolerance must be an integer from 0 to 1000")
        try:
            tv = read_tv_trades_text(csv_text)
            eng = engine_trades_from_rows(result["trades"])
            report = compare_lists(eng, tv, int(result["config"]["tf"]) * 60, tolerance)
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            raise self._bad_request(error) from error
        return {"job": job_id, "workspace_id": workspace_id, "config_revision": revision,
                "report": report, "execution_authorized": False}
