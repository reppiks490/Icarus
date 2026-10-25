"""Native research readers attached to one selected workspace's private state.

Construction may initialize the native SQLite schema. Reads do not collect,
record observations, refresh candidates, run research, or start workers.
"""
from __future__ import annotations

from contextvars import ContextVar
from functools import cached_property
from pathlib import Path

from .apex import ApexKernel
from .brain import brain_snapshot
from .dreamstate import DreamstateLab
from .pantheon import PantheonKernel
from .parallax import ParallaxStore
from .sibyl import SibylEngine
from .workspace_api import WorkspaceAPIError


def private_root(root):
    """Reject linked native databases, journals and directories before opening."""
    root = Path(root)
    if any(path.is_symlink() for path in (root, *root.parents)):
        raise WorkspaceAPIError(409, "workspace subsystem state must not use symlinks")
    if root.exists() and any(path.is_symlink() for path in root.rglob("*")):
        raise WorkspaceAPIError(409, "workspace subsystem state must not use symlinks")
    return root


def validate_query(path, query, selectors, port):
    allowed = selectors.get(path)
    if allowed is None:
        raise WorkspaceAPIError(503, "this panel has no selected-workspace reader", "WORKSPACE_PANEL_UNAVAILABLE")
    if set(query) - allowed or any(not isinstance(v, list) or len(v) != 1 for v in query.values()):
        raise WorkspaceAPIError(400, "unknown or repeated panel selectors")
    asset = query.get("asset", [None])[0] or None
    if asset is not None and asset not in port.runners:
        raise WorkspaceAPIError(404, "asset is not running in the selected workspace")
    return asset


class WorkspaceResearchEngines:
    APEX_PARTS = frozenset(("participants", "crowdhunt", "forces", "cascades", "causality",
                            "worlds", "epistemics", "self", "conscience"))
    READ_SELECTORS = {
        "parallax": frozenset(("asset", "limit")),
        "dreamstate": frozenset(("asset", "limit")),
        "pantheon": frozenset(("asset", "limit")),
        "sibyl": frozenset(("asset",)),
        "apex": frozenset(("asset", "as_of")),
        **{f"apex/{part}": frozenset(("asset", "as_of")) for part in APEX_PARTS},
    }

    def __init__(self, runtime):
        self.runtime = runtime
        self.root = private_root(runtime.root)
        self.port = runtime.port
        self.learning_snapshot = None
        self._asset_context = ContextVar(f"workspace_research_asset_{id(self)}", default=None)

    @cached_property
    def parallax(self):
        return ParallaxStore(private_root(self.root))

    @cached_property
    def dreamstate(self):
        return DreamstateLab(private_root(self.root), parallax=self.parallax)

    @cached_property
    def pantheon(self):
        return PantheonKernel(private_root(self.root))

    @cached_property
    def sibyl(self):
        return SibylEngine(private_root(self.root))

    def sibyl_snapshot(self, asset=None):
        # The native no-context default is NQ; select a real workspace runner
        # explicitly so an empty or non-NQ workspace cannot acquire that default.
        if asset is None:
            asset = next(iter(self.port.runners), None)
        if asset is None or asset not in self.port.runners:
            raise WorkspaceAPIError(503, "SIBYL requires a selected running asset", "WORKSPACE_PANEL_UNAVAILABLE")
        market = self.port.status()
        return self.sibyl.snapshot(asset, market_status=market,
            parallax_state=self.parallax.snapshot(), dreamstate_state=self.dreamstate.snapshot(),
            brain_state=brain_snapshot(self.root, market_status=market))

    @cached_property
    def apex(self):
        return ApexKernel(private_root(self.root),
            possibility=lambda: self.runtime.possibility.snapshot(self._asset_context.get()),
            chronofold=lambda: self.runtime.chronofold.snapshot(self._asset_context.get() or ""),
            pantheon=self.pantheon.snapshot, parallax=self.parallax.snapshot,
            dreamstate=self.dreamstate.snapshot,
            sibyl=lambda: self.sibyl_snapshot(self._asset_context.get()),
            learning=self.learning_snapshot)

    def read(self, path, query):
        asset = validate_query(path, query, self.READ_SELECTORS, self.port)
        private_root(self.root)
        if path in {"parallax", "dreamstate", "pantheon"}:
            default = {"parallax": 100, "dreamstate": 200, "pantheon": 50}[path]
            return getattr(self, path).snapshot(limit=int(query.get("limit", [str(default)])[0]))
        if path == "sibyl":
            return self.sibyl_snapshot(asset)
        token = self._asset_context.set(asset)
        try:
            state = self.apex.snapshot(asset=asset, as_of=query.get("as_of", [None])[0])
            return state if path == "apex" else state[path.split("/", 1)[1]]
        finally:
            self._asset_context.reset(token)

    def close(self):
        if "apex" in self.__dict__:
            self.apex.close()
