"""Existing subsystem services bound to one explicit paper workspace."""
from __future__ import annotations

import copy
from functools import cached_property
import threading
import time

from .chronofold import ChronofoldEngine
from .commissioning import CommissioningEngine
from .engine_control import ControlAction, EngineControlPlane
from .possibility import PossibilityEngine
from .runtime import AssetRunner, Portfolio
from .workspace_api import WorkspaceAPIError
from .workspace_market_data import snapshot as cached_market_snapshot
from .workspace_research_engines import WorkspaceResearchEngines
from .workspace_intelligence_panels import WorkspaceIntelligencePanels
from .workspace_golive import snapshot as selected_golive_snapshot


class CachedPanelFeed:
    """Analytics may inspect existing buffers, never start provider sessions."""
    def __init__(self, runner):
        self.runner = runner

    @property
    def provider_name(self):
        return cached_market_snapshot(self.runner, "capabilities")["provider"]

    def trades(self, symbol, *, limit=500):
        return cached_market_snapshot(self.runner, "ticks", limit=limit)["ticks"]

    def depth_events(self, symbol, *, schema="mbp-10", limit=200):
        return cached_market_snapshot(self.runner, "depth", schema=schema, limit=limit)["events"]

    def meta(self, symbol):
        return cached_market_snapshot(self.runner, "capabilities")["metadata"]

    def capabilities(self):
        return cached_market_snapshot(self.runner, "capabilities")["capabilities"]


class PanelRunner:
    def __init__(self, runner):
        self._runner = runner
        self.feed = CachedPanelFeed(runner)

    def __getattr__(self, name):
        return getattr(self._runner, name)

    def _feed_health_view(self):
        return self.feed.meta(self.spec.ticker)

    def summary(self, *, nonblocking=False):
        if not self.lock.acquire(timeout=0.05):
            return self._runner._busy_read_view(0)
        try:
            return AssetRunner._summary(self)
        finally:
            self.lock.release()


class PanelPortfolio:
    """Read the selected portfolio; store subsystem files outside shared presets."""
    def __init__(self, portfolio, root):
        self._portfolio = portfolio
        self.base_dir = str(root)

    def __getattr__(self, name):
        return getattr(self._portfolio, name)

    def status(self, **kwargs):
        try:
            return Portfolio.status(self, nonblocking=True)
        except RuntimeError as ex:
            raise WorkspaceAPIError(503, "selected subsystem snapshot is not ready", "SNAPSHOT_UNAVAILABLE") from ex

    @property
    def runners(self):
        return {key: PanelRunner(value) for key, value in self._portfolio.runners.items()}

    def runner_list(self):
        return [PanelRunner(value) for value in self._portfolio.runner_list()]


class RuntimePanels:
    def __init__(self, manager, api, workspace_id, portfolio):
        self.manager, self.api, self.workspace_id = manager, api, workspace_id
        root = manager.root / workspace_id / "subsystems"
        if any(path.is_symlink() for path in (root.parent, root)):
            raise WorkspaceAPIError(409, "workspace subsystem directory must not be a symlink")
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.root = root
        self.port = PanelPortfolio(portfolio, root)

    @cached_property
    def possibility(self):
        return PossibilityEngine(self.port)

    @cached_property
    def chronofold(self):
        return ChronofoldEngine(self.port, possibility=self.possibility)

    @cached_property
    def commissioning(self):
        return CommissioningEngine(self.root, self.port, self.chronofold)

    @cached_property
    def research_engines(self):
        readers = WorkspaceResearchEngines(self)
        readers.learning_snapshot = lambda: self.intelligence.learning.snapshot()
        return readers

    @cached_property
    def intelligence(self):
        return WorkspaceIntelligencePanels(self, self.research_engines)

    def _control(self, action, target=None, **body):
        return self.api.control(self.workspace_id, target, action, body)

    @cached_property
    def control(self):
        actions = [
            ControlAction("engine.pause_all", "Pause workspace entries", "Engine", "Pause entries in this paper workspace; exits remain active.",
                          lambda p: self._control("pause", paused=True)),
            ControlAction("engine.resume_all", "Resume workspace entries", "Engine", "Resume entries in this paper workspace.",
                          lambda p: self._control("pause", paused=False)),
            ControlAction("engine.flatten_all", "Flatten workspace paper positions", "Engine", "Close only this workspace's paper positions.",
                          lambda p: self._control("flatten", confirm=True), danger=True, confirmation="FLATTEN ALL PAPER POSITIONS"),
            ControlAction("asset.pause", "Pause asset", "Assets", "Pause the selected workspace asset.",
                          lambda p: self._control("pause", p["target"], paused=True), target="asset"),
            ControlAction("asset.resume", "Resume asset", "Assets", "Resume the selected workspace asset.",
                          lambda p: self._control("pause", p["target"], paused=False), target="asset"),
            ControlAction("asset.flatten", "Flatten paper position", "Assets", "Close only the selected workspace asset's paper position.",
                          lambda p: self._control("flatten", p["target"], confirm=True), target="asset", danger=True,
                          confirmation="FLATTEN PAPER POSITION"),
            ControlAction("commissioning.capture", "Freeze Chronofold forecast", "Commissioning", "Append a selected-workspace research forecast before its outcome.",
                          lambda p: self.commissioning.capture(p["target"]), target="asset"),
            ControlAction("commissioning.settle_asset", "Settle ready asset forecasts", "Commissioning", "Settle this workspace's eligible selected-asset forecasts.",
                          lambda p: self.commissioning.settle_ready(p["target"]), target="asset"),
            ControlAction("commissioning.settle_all", "Settle ready workspace forecasts", "Commissioning", "Settle this workspace's eligible forecasts.",
                          lambda p: self.commissioning.settle_ready()),
            ControlAction("commissioning.tick", "Run commissioning cycle", "Commissioning", "Capture and settle selected-workspace research observations.",
                          lambda p: self.commissioning.tick()),
            ControlAction("commissioning.start", "Start commissioning sampler", "Commissioning", "Start only this workspace's research sampler.",
                          lambda p: self.commissioning.start_background() or self.commissioning.status()),
            ControlAction("commissioning.stop", "Stop commissioning sampler", "Commissioning", "Stop only this workspace's research sampler.",
                          lambda p: self.commissioning.close() or self.commissioning.status()),
            ControlAction("sync.all", "Refresh workspace diagnostics", "Observability", "Read this workspace's existing diagnostics without provider collection or parent synchronization.",
                          lambda p: {"possibility": self.possibility.status(), "chronofold": self.chronofold.status(),
                                     "commissioning": self.commissioning.status()}),
        ]
        return EngineControlPlane(self.root, snapshotters={
            "portfolio": self.port.status, "possibility": self.possibility.status,
            "chronofold": self.chronofold.status, "commissioning": self.commissioning.status,
        }, actions={a.action_id: a for a in actions})

    def read(self, path, query):
        asset = query.get("asset", [""])[0]
        if path in WorkspaceResearchEngines.READ_SELECTORS:
            return self.research_engines.read(path, query)
        if path in WorkspaceIntelligencePanels.READ_SELECTORS:
            return self.intelligence.read(path, query)
        if path == "golive":
            return selected_golive_snapshot(self.port)
        if path == "possibility":
            return self.possibility.snapshot(asset)
        if path == "possibility/evidence":
            return self.possibility.evidence_snapshot(asset, limit=int(query.get("limit", ["100"])[0]),
                include_expired=query.get("include_expired", ["false"])[0] in {"true", "1"},
                as_of=query.get("as_of", [None])[0])
        if path == "chronofold":
            return self.chronofold.snapshot(asset)
        if path == "commissioning":
            return self.commissioning.status(asset)
        if path == "engine-control":
            return self.control.status()
        raise WorkspaceAPIError(503, "this panel has no selected-workspace runtime adapter", "WORKSPACE_PANEL_UNAVAILABLE")

    def mutate(self, path, body):
        if path == "engine-control":
            if body.get("args") not in (None, {}):
                raise ValueError("selected-workspace controls do not accept action arguments")
            return self.control.run(body)
        if path == "possibility/evidence":
            allowed = {"asset", "values", "source", "observed_at", "ttl_seconds"}
            if set(body) - allowed or not {"asset", "values", "source"} <= set(body):
                raise ValueError("possibility evidence requires explicit asset, values and source")
            return self.possibility.ingest_external(**body)
        raise WorkspaceAPIError(501, "this action has no selected-workspace adapter", "WORKSPACE_ACTION_UNAVAILABLE")

    def close(self):
        errors = []
        for name in ("intelligence", "research_engines", "commissioning"):
            service = self.__dict__.get(name)
            if service is not None:
                try:
                    service.close()
                except Exception as error:
                    errors.append(error)
        service = self.__dict__.get('commissioning')
        if service is not None:
            service._stop.set()
            thread = service._thread
            if thread is not None and thread is not threading.current_thread():
                thread.join()
        if errors:
            raise RuntimeError("selected panel service failed to close") from errors[0]


class WorkspacePanels:
    READ_SELECTORS = {
        "possibility": frozenset(("asset",)),
        "possibility/evidence": frozenset(("asset", "limit", "include_expired", "as_of")),
        "chronofold": frozenset(("asset",)), "commissioning": frozenset(("asset",)),
        "engine-control": frozenset(("asset",)), "golive": frozenset(("asset",)),
        **WorkspaceResearchEngines.READ_SELECTORS, **WorkspaceIntelligencePanels.READ_SELECTORS,
    }
    READS = frozenset(READ_SELECTORS)
    WRITES = frozenset(("engine-control", "possibility/evidence"))

    def __init__(self, manager, api):
        self.manager, self.api = manager, api
        self._lock = threading.RLock()
        self._runtimes = {}
        self._background = False
        self._closed = False
        self._bundle_locks = {key: threading.RLock() for key in manager.profiles}

    def _bundle(self, profile_id, portfolio):
        # Constructors and first commissioning ticks may be slow. They belong
        # only to this workspace; the shared registry lock protects bookkeeping.
        with self._bundle_locks[profile_id]:
            power = getattr(self.manager, 'runtime_power', None)
            with self._lock:
                if (self._closed or self.manager.portfolios.get(profile_id) is not portfolio
                        or (power is not None and not power.is_on(profile_id))):
                    raise WorkspaceAPIError(503, "selected dashboard runtime is off or changing state")
                current = self._runtimes.get(profile_id)
                background = self._background
            if current is None or current.port._portfolio is not portfolio:
                if current is not None:
                    current.close()
                current = RuntimePanels(self.manager, self.api, profile_id, portfolio)
                with self._lock:
                    cancelled = (self._closed or self.manager.portfolios.get(profile_id) is not portfolio
                                 or (power is not None and not power.is_on(profile_id)))
                if cancelled:
                    current.close()
                    raise WorkspaceAPIError(503, "selected dashboard runtime changed during panel startup")
                with self._lock:
                    self._runtimes[profile_id] = current
            if background:
                current.commissioning.start_background()
            return current

    def activate(self, profile_id, portfolio):
        """Initialize one published runtime without delaying HTTP or siblings."""
        def initialize():
            try:
                with self._lock:
                    if self._closed or not self._background:
                        return
                if self.manager.portfolios.get(profile_id) is portfolio:
                    self._bundle(profile_id, portfolio)
            except Exception:
                # A selected diagnostic failure does not stop its paper workers.
                # A later explicit panel read reports/retries the local failure.
                return
        threading.Thread(target=initialize, daemon=True,
                         name=f"workspace-panels-{profile_id}").start()

    def read(self, profile_id, path, query):
        if path not in self.READS:
            raise WorkspaceAPIError(503, "this panel has no selected-workspace runtime adapter", "WORKSPACE_PANEL_UNAVAILABLE")
        allowed = self.READ_SELECTORS[path]
        if set(query) - allowed or any(len(values) != 1 for values in query.values()):
            raise WorkspaceAPIError(400, "unknown or repeated panel selectors")
        with self.api.runtime_lock(profile_id):
            profile, portfolio, _ = self.api._selected(profile_id, query.get("asset", [None])[0] or None)
            try:
                data = self._bundle(profile_id, portfolio).read(path, query)
            except (ValueError, TypeError) as ex:
                if isinstance(ex, WorkspaceAPIError):
                    raise
                raise WorkspaceAPIError(400, str(ex)) from ex
            return {**copy.deepcopy(data), **self.api._identity(profile)}

    def mutate(self, profile_id, path, body, expected_revision):
        if path not in self.WRITES:
            raise WorkspaceAPIError(501, "this action has no selected-workspace adapter", "WORKSPACE_ACTION_UNAVAILABLE")
        if not isinstance(expected_revision, str) or not 1 <= len(expected_revision) <= 16 or not expected_revision.isascii() or not expected_revision.isdecimal():
            raise WorkspaceAPIError(400, "a captured workspace configuration revision is required")
        if not isinstance(body, dict):
            raise WorkspaceAPIError(400, "panel action must be an object")
        with self.api.runtime_lock(profile_id):
            profile, portfolio, _ = self.api._selected(profile_id)
            if int(expected_revision) != profile["config_revision"]:
                raise WorkspaceAPIError(409, "workspace configuration changed", "REVISION_CONFLICT")
            # Reject a foreign asset before creating a service directory or audit.
            target = body.get("target")
            action = str(body.get("action") or "")
            if target and (action.startswith("asset.") or action.startswith("commissioning.")):
                self.api._selected(profile_id, target)
            if path == "possibility/evidence":
                self.api._selected(profile_id, body.get("asset"))
            try:
                data = self._bundle(profile_id, portfolio).mutate(path, body)
            except (ValueError, TypeError, KeyError) as ex:
                if isinstance(ex, WorkspaceAPIError):
                    raise
                raise WorkspaceAPIError(400, str(ex)) from ex
            return {**data, **self.api._identity(profile)}

    def start(self):
        with self._lock:
            if self._closed:
                return
            self._background = True
        for profile_id, portfolio in list(self.manager.portfolios.items()):
            self.activate(profile_id, portfolio)

    def close(self):
        with self._lock:
            self._background = False
            self._closed = True
        # Never wait for one blocked sampler on the HTTP shutdown thread.
        workers = [threading.Thread(target=self.suspend, args=(key,), daemon=True)
                   for key in self._bundle_locks]
        for worker in workers:
            worker.start()
        deadline = time.monotonic() + .1
        for worker in workers:
            worker.join(max(0, deadline - time.monotonic()))

    def suspend(self, profile_id):
        """Drain one dashboard before its lifecycle worker retires the journal."""
        with self._bundle_locks[profile_id]:
            with self._lock:
                bundle = self._runtimes.pop(profile_id, None)
            if bundle is not None:
                bundle.close()
                service = bundle.__dict__.get('commissioning')
                thread = getattr(service, '_thread', None)
                if thread is not None and thread is not threading.current_thread():
                    thread.join()
