"""Explicit trading reads for one paper workspace; never select the parent."""
from __future__ import annotations

import copy
from contextlib import contextmanager
import math
import time

from .assets import chart_capabilities
from .paper_pnl import validate_paper_pnl
from .paper_workspaces import _available_assets
from .runtime import FlattenUnavailableError
from .workspace_config import WorkspaceRevisionConflict


class WorkspaceAPIError(ValueError):
    def __init__(self, status: int, detail: str, reason=None):
        super().__init__(detail)
        self.status = status
        self.reason = reason or ("RUNTIME_UNAVAILABLE" if status == 503 else "RESOURCE_UNAVAILABLE")
        self.receipt = {}

    def as_dict(self, profile_id):
        return {"detail": str(self), "workspace_id": profile_id, "available": False,
                "reason": self.reason, "execution_authorized": False, **self.receipt}


class WorkspaceAPI:
    def __init__(self, manager):
        self.manager = manager

    def _selected(self, profile_id, symbol=None):
        profile = self.manager.profiles.get(profile_id)
        if profile is None:
            raise WorkspaceAPIError(404, "unknown command center")
        power = getattr(self.manager, 'runtime_power', None)
        if power is not None and not power.is_on(profile_id):
            raise WorkspaceAPIError(503, "selected dashboard runtime is off or changing state", "WORKSPACE_RUNTIME_OFF")
        portfolio = self.manager.portfolios.get(profile_id)
        if portfolio is None:
            raise WorkspaceAPIError(503, "selected paper runtime is unavailable")
        runner = None
        if symbol is not None:
            if symbol not in profile["assets"] or symbol not in portfolio.runners:
                raise WorkspaceAPIError(404, "asset is not running in this workspace")
            runner = portfolio.runners[symbol]
        return profile, portfolio, runner

    @contextmanager
    def runtime_lock(self, profile_id):
        self._selected(profile_id)
        lock = self.manager.configuration_lock(profile_id)
        if not lock.acquire(blocking=False):
            raise WorkspaceAPIError(409, "selected workspace is busy; retry after its current operation")
        try:
            self._selected(profile_id)
            yield
        finally:
            lock.release()

    @staticmethod
    def _identity(profile):
        return {"workspace_id": profile["id"], "config_revision": profile["config_revision"],
                "paper_only": True, "execution_authorized": False}

    def _selected_snapshot(self, profile_id):
        """Validate one workspace without reading sibling runtime/journal state."""
        now = int(time.time())
        selected, ledger = self.manager._profile_snapshot(profile_id, now)
        ledgers = []
        for candidate_id in self.manager.profiles:
            if candidate_id == profile_id:
                ledgers.append(ledger)
            else:
                ledgers.append({"id": candidate_id, "currency": "USD", "runtime_available": False,
                                "snapshot_ts": now, "realized_pnl": 0.0, "open_pnl": 0.0,
                                "open_positions": 0, "oldest_open_mark_ts": None})
        accounting = validate_paper_pnl(ledgers, as_of_ts=now)
        validated = next(row for row in accounting["profiles"] if row["id"] == profile_id)
        for field in ("realized_pnl", "open_pnl", "total_pnl"):
            selected["pnl"][field] = validated[field]
        selected["pnl"]["paper_pnl"] = validated["realized_pnl"]
        selected["status"]["paper_pnl"] = validated["realized_pnl"]
        selected["valuation_complete"] = validated["accounting_complete"]
        return selected, validated

    def _status(self, profile_id):
        self._selected(profile_id)
        try:
            selected, accounting = self._selected_snapshot(profile_id)
        except RuntimeError as ex:
            raise WorkspaceAPIError(503, "paper snapshot is not ready", "SNAPSHOT_UNAVAILABLE") from ex
        if not selected["runtime_available"]:
            raise WorkspaceAPIError(503, "selected paper runtime is unavailable")
        if selected["status"].get("snapshot_unavailable"):
            raise WorkspaceAPIError(503, "paper snapshot is not ready", "SNAPSHOT_UNAVAILABLE")
        return {**selected["status"], **self._identity(selected), "accounting": accounting,
                "pnl_basis": selected["pnl"]["basis"]}

    def read(self, profile_id, resource, symbol=None, *, limit=100):
        if resource == "status" and symbol is None:
            return self._status(profile_id)
        with self.runtime_lock(profile_id):
            profile, portfolio, runner = self._selected(profile_id, symbol)
            identity = self._identity(profile)
            if resource == "performance" and symbol is None:
                from .workspace_performance import snapshot
                capitals = [getattr(r.spec, "capital", None) for r in portfolio.runner_list()]
                capital = (sum(capitals) if capitals and all(type(v) in (int, float)
                           and math.isfinite(v) and v > 0 for v in capitals) else None)
                if capital is not None and not math.isfinite(capital):
                    capital = None
                return {**snapshot(portfolio.journal, capital=capital), **identity}
            if resource == "assets" and symbol is None:
                return {**identity, "registry": _available_assets(), "registry_scope": "shared",
                        "running": list(portfolio.order), "chart_capabilities": chart_capabilities()}
            if resource == "inputs" and runner is not None:
                with runner.lock:
                    override = profile["asset_overrides"].get(symbol, {})
                    return {**identity, "asset": symbol, "effective": runner.inputs.to_dict(),
                            "base": runner.inputs_base.to_dict(), "sources": list(runner.cfg.sources or []),
                            "overrides": copy.deepcopy(override.get("inputs", {})),
                            "workspace_inputs": copy.deepcopy(profile["inputs"]),
                            "preset": portfolio.preset_for(runner), "pts_scale": runner.pts_scale,
                            "instrument": {"kind": runner.spec.kind,
                                           "continuous_symbol": runner.spec.tv_symbol if runner.spec.kind == "futures" else None,
                                           "provider_symbol": runner.spec.ticker,
                                           "contract_policy": "continuous_only" if runner.spec.kind == "futures" else "not_applicable"},
                            "chart": {"timeframe": runner.spec.chart_tf, "chart_type": runner.spec.chart_type,
                                      "fill_on": runner.spec.fill_on, "security_source": runner.spec.security_source},
                            "chart_capabilities": runner.chart_capability_view()}
            if resource == "trades" and runner is not None:
                with runner.lock:
                    trades = runner.trades(limit)
                return {**identity, "asset": symbol, "trades": trades,
                        "history_basis": "Current runner replay and paper trades; persisted paper results are available separately in Performance."}
            raise WorkspaceAPIError(404, "unknown command center resource")

    def market_data(self, profile_id, symbol, resource, *, schema="mbp-10", limit=200):
        from .workspace_market_data import snapshot
        with self.runtime_lock(profile_id):
            profile, _, runner = self._selected(profile_id, symbol)
            return {**snapshot(runner, resource, schema=schema, limit=limit), **self._identity(profile)}

    def chart(self, profile_id, symbol, *, n=240, offset=0):
        with self.runtime_lock(profile_id):
            profile, _, runner = self._selected(profile_id, symbol)
            try:
                chart = runner.chart(n, offset=offset, nonblocking=True)
            except RuntimeError as ex:
                raise WorkspaceAPIError(503, "paper chart is not ready", "SNAPSHOT_UNAVAILABLE") from ex
            return {**chart, **self._identity(profile)}

    def export(self, profile_id, symbol):
        with self.runtime_lock(profile_id):
            profile, _, runner = self._selected(profile_id, symbol)
            return runner.export_csv(), self._identity(profile)

    def control(self, profile_id, symbol, action, body):
        with self.runtime_lock(profile_id):
            _, portfolio, runner = self._selected(profile_id, symbol)
            scope = "workspace" if symbol is None else "asset"
            try:
                if action == "config":
                    result = (self.manager.update(profile_id, body) if symbol is None
                              else self.manager.update_asset(profile_id, symbol, body))
                elif action == "pause":
                    if set(body) != {"paused"} or type(body["paused"]) is not bool:
                        raise ValueError("pause accepts only paused: true or false; use the asset route for an asset control")
                    result = self.manager.pause(profile_id, body["paused"], asset=symbol)
                elif action == "flatten":
                    if set(body) != {"confirm"} or body["confirm"] is not True:
                        raise ValueError("flatten accepts only confirm: true; use the asset route for an asset control")
                    result = self.manager.flatten(profile_id, asset=symbol)
                else:
                    raise WorkspaceAPIError(404, "unknown workspace control")
            except FlattenUnavailableError as ex:
                targets = portfolio.runner_list() if runner is None else [runner]
                open_assets = [r.symbol for r in targets if r.em.open or getattr(getattr(r.em, "shadow", None), "open", ())]
                error = WorkspaceAPIError(409, str(ex), "FLATTEN_UNAVAILABLE")
                error.receipt = {**self._identity(self.manager.profiles[profile_id]),
                    "error": "flatten_unavailable",
                    "profile_id": profile_id, "asset": symbol, "scope": scope,
                    "flattened_positions": int(getattr(ex, "flattened_positions", 0) or 0),
                    "shadow_censored_positions": int(getattr(ex, "shadow_censored_positions", 0) or 0),
                    "failed_assets": list(getattr(ex, "failed_assets", [])),
                    "partial": bool(getattr(ex, "partial", False)), "open_assets": open_assets,
                    "positions_remain_open": bool(open_assets),
                    "paused": bool(portfolio.paused) if runner is None else bool(runner.paused)}
                raise error from ex
            except WorkspaceRevisionConflict as ex:
                raise WorkspaceAPIError(409, str(ex), "REVISION_CONFLICT") from ex
            except WorkspaceAPIError:
                raise
            except (ValueError, TypeError, KeyError) as ex:
                raise WorkspaceAPIError(400, str(ex), "INVALID_CONTROL") from ex
            return {**result, **self._identity(self.manager.profiles[profile_id]),
                    "asset": symbol, "scope": scope}
