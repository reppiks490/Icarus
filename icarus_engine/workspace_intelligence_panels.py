"""Read native private intelligence state without starting autonomous services."""
from __future__ import annotations

from functools import cached_property

from .ascendancy.archive import GenomeArchive
from .ascendancy.autopilot import GovernorAutopilot
from .ascendancy.capabilities import capability_snapshot
from .ascendancy.contribution import ContributionLab
from .ascendancy.evaluator import EvaluatorCascade
from .ascendancy.executor import GovernorExecutor
from .ascendancy.foundry import CandidateFoundry
from .ascendancy.frontier import build_frontier
from .ascendancy.governor import EvolutionGovernor
from .ascendancy.invention import InventionLab
from .ascendancy.mechanisms import MechanismLab
from .ascendancy.native_validation import NativeContractValidator
from .ascendancy.unknowns import UnknownUnknownLab
from .ascendancy.work_orders import ResearchWorkOrderBoard
from .autopilot import TacticalAutopilot
from .brain import brain_snapshot
from .research_service import ResearchWorkspace
from .workspace_api import WorkspaceAPIError
from .workspace_research_engines import private_root, validate_query


def _disabled(*_args, **_kwargs):
    raise RuntimeError("selected-workspace intelligence panels are read-only")


class WorkspaceIntelligencePanels:
    ASCENDANCY_TYPES = {
        "genomes": GenomeArchive, "candidates": CandidateFoundry,
        "unknowns": UnknownUnknownLab, "mechanisms": MechanismLab,
        "inventions": InventionLab, "contributions": ContributionLab,
        "evaluator": EvaluatorCascade, "governor": EvolutionGovernor,
        "executor": GovernorExecutor,
    }
    READ_SELECTORS = {
        **{path: frozenset(("asset",)) for path in (
            "research", "research/adaptation", "research/source-watch", "research/events",
            "research/analysis", "research/activation", "research/sources", "brain", "autopilot",
            "learning", "learning/health", "learning/experience", "learning/scorecards", "learning/datasets",
            "ascendancy/capabilities", "ascendancy/autopilot", "ascendancy/work-orders", "ascendancy/native-validation")},
        **{f"ascendancy/{part}": frozenset(("asset",)) for part in ASCENDANCY_TYPES},
        "ascendancy/intelligence": frozenset(("asset", "as_of", "limit")),
        "research/records": frozenset(("asset", "kind", "cik", "limit")),
    }

    def __init__(self, runtime, research_engines):
        self.runtime, self.engines = runtime, research_engines
        self.root, self.port = private_root(runtime.root), runtime.port
        self._ascendancy = {}
        # Deferred lookup keeps LearningFabric lazy until an actual read. APEX
        # receives the same selected native learning store as this panel.
        self.engines.learning_snapshot = lambda: self.learning.snapshot()
        if "apex" in self.engines.__dict__:
            self.engines.apex._learning = self.engines.learning_snapshot

    @cached_property
    def research(self):
        private_root(self.root)
        return ResearchWorkspace(self.port)

    @property
    def learning(self):
        private_root(self.root)
        return self.research.learning

    @cached_property
    def autopilot(self):
        private_root(self.root)
        return TacticalAutopilot(self.port, possibility_snapshot=self.runtime.possibility.snapshot)

    @cached_property
    def governor_autopilot(self):
        return GovernorAutopilot(private_root(self.root), plan_callback=_disabled,
                                 execute_callback=_disabled, enabled=False)

    def _native(self, part):
        if part not in self._ascendancy:
            self._ascendancy[part] = self.ASCENDANCY_TYPES[part](private_root(self.root))
        return self._ascendancy[part]

    @cached_property
    def work_orders(self):
        return ResearchWorkOrderBoard(private_root(self.root), evaluator=self._native("evaluator"))

    @cached_property
    def native_validation(self):
        return NativeContractValidator(private_root(self.root), evaluator=self._native("evaluator"), enabled=False)

    def _research_status(self):
        # Native ResearchWorkspace.status uses reentrant runner locks without a
        # timeout. Hold those selected locks with a bounded wait before entering
        # the native reader so a busy runner produces an explicit unavailable
        # response instead of blocking an HTTP worker indefinitely.
        acquired = []
        try:
            for runner in self.port.runner_list():
                if not runner.lock.acquire(timeout=0.05):
                    raise WorkspaceAPIError(503, "selected research runtime is busy", "WORKSPACE_PANEL_UNAVAILABLE")
                acquired.append(runner.lock)
            return self.research.status()
        finally:
            for lock in reversed(acquired):
                lock.release()

    def read(self, path, query):
        asset = validate_query(path, query, self.READ_SELECTORS, self.port)
        private_root(self.root)
        if path == "research":
            return self._research_status()
        research_parts = {"research/adaptation": "adaptation", "research/source-watch": "source_watch",
                          "research/analysis": "analysis", "research/activation": "activation",
                          "research/sources": "market_sources"}
        if path in research_parts:
            return getattr(self.research, research_parts[path]).status()
        if path == "research/events":
            if asset is None:
                raise WorkspaceAPIError(400, "research events require an asset")
            return self.research.events(asset)
        if path == "research/records":
            return self.research.market_sources.records(kind=query.get("kind", ["asset"])[0],
                asset=asset, cik=query.get("cik", [None])[0], limit=int(query.get("limit", ["100"])[0]))
        if path == "brain":
            return brain_snapshot(self.root, market_status=self.port.status(),
                                  research_status=self._research_status())
        if path == "autopilot":
            return self.autopilot.status()
        if path == "learning":
            return {**self.learning.snapshot(), "storage_scope": {
                "native_state": "selected_workspace_private",
                "shared_history_admission": "UNAVAILABLE",
                "automatic_history_scan": False,
                "note": "This read uses existing private learning state; shared historical training is not admitted by this adapter.",
            }}
        if path == "learning/health":
            return self.learning.health()
        if path == "learning/experience":
            return self.learning.experience_state()
        if path == "learning/scorecards":
            return {"scorecards": self.learning.scorecards(), "execution_authorized": False,
                    "production_decision_authorized": False}
        if path == "learning/datasets":
            return {"datasets": self.learning.datasets(), "training_runs": self.learning.training_runs(),
                    "execution_authorized": False, "production_decision_authorized": False}
        part = path.split("/", 1)[1]
        if part == "capabilities":
            return capability_snapshot()
        if part == "intelligence":
            return self.learning.intelligence_snapshot(as_of=query.get("as_of", [None])[0],
                limit=int(query.get("limit", ["200"])[0]))
        if part == "autopilot":
            return self.governor_autopilot.status()
        if part == "work-orders":
            return self.work_orders.snapshot()
        if part == "native-validation":
            return self.native_validation.snapshot()
        state = self._native(part).snapshot()
        if part == "genomes":
            return {"archive": state, "frontier": build_frontier(state),
                    "execution_authorized": False, "production_decision_authorized": False}
        return state

    def close(self):
        # ResearchWorkspace.close only stops already-instantiated services. No
        # panel method enables or starts them, including saved enabled configs.
        if "research" in self.__dict__:
            self.research.close()
