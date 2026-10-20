"""Explicit trading reads for one paper workspace; never select the parent."""
from __future__ import annotations

import copy
import math

from .assets import chart_capabilities
from .paper_workspaces import _available_assets


class WorkspaceAPIError(ValueError):
    def __init__(self, status: int, detail: str, reason=None):
        super().__init__(detail)
        self.status = status
        self.reason = reason or ("RUNTIME_UNAVAILABLE" if status == 503 else "RESOURCE_UNAVAILABLE")

    def as_dict(self, profile_id):
        return {"detail": str(self), "workspace_id": profile_id, "available": False,
                "reason": self.reason, "execution_authorized": False}


class WorkspaceAPI:
    def __init__(self, manager):
        self.manager = manager

    def _selected(self, profile_id, symbol=None):
        profile = self.manager.profiles.get(profile_id)
        if profile is None:
            raise WorkspaceAPIError(404, "unknown command center")
        portfolio = self.manager.portfolios.get(profile_id)
        if portfolio is None:
            raise WorkspaceAPIError(503, "selected paper runtime is unavailable")
        runner = None
        if symbol is not None:
            if symbol not in profile["assets"] or symbol not in portfolio.runners:
                raise WorkspaceAPIError(404, "asset is not running in this workspace")
            runner = portfolio.runners[symbol]
        return profile, portfolio, runner

    @staticmethod
    def _identity(profile):
        return {"workspace_id": profile["id"], "config_revision": profile["config_revision"],
                "paper_only": True, "execution_authorized": False}

    def read(self, profile_id, resource, symbol=None, *, limit=100):
        with self.manager._lock:
            profile, portfolio, runner = self._selected(profile_id, symbol)
            identity = self._identity(profile)
            if resource == "status" and symbol is None:
                try:
                    state = self.manager.snapshot()
                except RuntimeError as ex:
                    raise WorkspaceAPIError(503, "paper snapshot is not ready", "SNAPSHOT_UNAVAILABLE") from ex
                selected = next(row for row in state["profiles"] if row["id"] == profile_id)
                if selected["status"].get("snapshot_unavailable"):
                    raise WorkspaceAPIError(503, "paper snapshot is not ready", "SNAPSHOT_UNAVAILABLE")
                accounting = next(row for row in state["paper_pnl"]["profiles"] if row["id"] == profile_id)
                return {**selected["status"], **identity, "accounting": accounting,
                        "pnl_basis": selected["pnl"]["basis"]}
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

    def chart(self, profile_id, symbol, *, n=240, offset=0):
        with self.manager._lock:
            profile, _, runner = self._selected(profile_id, symbol)
            try:
                chart = runner.chart(n, offset=offset, nonblocking=True)
            except RuntimeError as ex:
                raise WorkspaceAPIError(503, "paper chart is not ready", "SNAPSHOT_UNAVAILABLE") from ex
            return {**chart, **self._identity(profile)}

    def export(self, profile_id, symbol):
        with self.manager._lock:
            profile, _, runner = self._selected(profile_id, symbol)
            return runner.export_csv(), self._identity(profile)
