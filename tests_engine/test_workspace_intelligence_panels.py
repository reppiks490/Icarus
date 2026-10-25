"""Native intelligence polling stays private and never starts active services."""
import json
from pathlib import Path

import pytest

from tests_engine.test_workspace_api import workspace_http  # noqa: F401


@pytest.mark.parametrize("panel", ["research", "brain", "learning", "learning/health", "learning/experience",
    "learning/scorecards", "learning/datasets", "autopilot", "ascendancy/genomes", "ascendancy/candidates",
    "ascendancy/unknowns", "ascendancy/mechanisms", "ascendancy/inventions", "ascendancy/contributions",
    "ascendancy/evaluator", "ascendancy/governor", "ascendancy/executor", "ascendancy/autopilot",
    "ascendancy/work-orders", "ascendancy/intelligence", "ascendancy/capabilities", "ascendancy/native-validation",
    "intuition-omega"])
def test_intelligence_status_uses_native_selected_state(workspace_http, monkeypatch, panel):
    _, parent, request = workspace_http
    monkeypatch.setattr(parent, "status", lambda *a, **k: pytest.fail("parent fallback"))
    selectors = "" if panel == "intuition-omega" else "?asset=NQ"
    code, data, _ = request(f"/api/command-centers/cc1/panels/{panel}{selectors}")
    assert code == 200, data
    assert data["workspace_id"] == "cc1" and data["execution_authorized"] is False
    if panel == "learning":
        assert data["training"]["run_count"] == 0
        assert data["predictions"]["count"] == 0
        assert data["storage_scope"]["shared_history_admission"] == "UNAVAILABLE"
    if panel == "intuition-omega":
        assert data["learning_source"]["state"] == "NOT_INITIALIZED"
        assert data["ledger"]["state"] == "NOT_INITIALIZED"
        assert data["execution_authorized"] is False
    if panel == "autopilot":
        assert data["running"] is False
    if panel == "ascendancy/autopilot":
        assert data["worker_running"] is False and data["enabled"] is False
    if panel == "brain":
        assert data["remote_sync"]["status"] == "not_configured"


def test_intelligence_reads_never_start_saved_enabled_workers(workspace_http, monkeypatch):
    from icarus_engine.learning_fabric import LearningFabric
    from icarus_engine.research_service import ResearchWorkspace
    from icarus_engine.autopilot import TacticalAutopilot
    from icarus_engine.ascendancy.autopilot import GovernorAutopilot
    from icarus_engine.source_watch import SourceWatch
    from icarus_engine.adaptation import AdaptationScheduler
    from icarus_engine.market_sources import MarketSources
    server, _, request = workspace_http
    def forbidden(*a, **k):
        pytest.fail("intelligence read started a worker, training, or collection")
    for cls, methods in ((LearningFabric, ("start_background", "run_cycle", "scan_history", "harvest_native", "backfill_dataset")),
                         (ResearchWorkspace, ("start_background", "start")),
                         (TacticalAutopilot, ("start_background", "start", "cycle_once")),
                         (GovernorAutopilot, ("start", "run_cycle")),
                         (SourceWatch, ("start", "tick")), (AdaptationScheduler, ("start", "tick")),
                         (MarketSources, ("collect",))):
        for method in methods:
            monkeypatch.setattr(cls, method, forbidden)
    root = server.command_centers.root / "cc1" / "subsystems" / "research"
    root.mkdir(parents=True, exist_ok=True)
    (root / "learning.json").write_text(json.dumps({"enabled": True}))
    for panel in ("research", "research/source-watch", "research/adaptation", "brain", "learning", "autopilot", "ascendancy/autopilot"):
        code, data, _ = request(f"/api/command-centers/cc1/panels/{panel}")
        assert code == 200, data
    assert request("/api/command-centers/cc1/panels/learning/health")[1]["background_running"] is False


def test_selected_learning_persists_without_shared_training_admission(tmp_path):
    from types import SimpleNamespace
    from icarus_engine.workspace_research_engines import WorkspaceResearchEngines
    from icarus_engine.workspace_intelligence_panels import WorkspaceIntelligencePanels
    from icarus_engine.learning_fabric import LearningFabric
    from tests_engine.test_learning_fabric import _prediction
    shared = LearningFabric(tmp_path)
    shared.record_prediction(_prediction(producer="parent-only"))
    shared.close()

    def make(name):
        root = tmp_path / name
        runtime = SimpleNamespace(root=root, port=SimpleNamespace(base_dir=str(root), runners={}),
                                  possibility=SimpleNamespace(snapshot=lambda: {}))
        return WorkspaceIntelligencePanels(runtime, WorkspaceResearchEngines(runtime))
    one = make("cc1")
    assert one.read("learning", {})["predictions"]["count"] == 0
    one.learning.record_prediction(_prediction(producer="selected-only"))
    one.close()
    reopened, other = make("cc1"), make("cc2")
    try:
        assert reopened.read("learning", {})["predictions"]["count"] == 1
        assert other.read("learning", {})["predictions"]["count"] == 0
        assert reopened.learning.path == tmp_path / "cc1" / "research" / "learning.sqlite3"
        assert reopened.learning._thread is None
    finally:
        reopened.close()
        other.close()


def test_apex_learning_binding_is_stable_before_and_after_learning_panel(workspace_http, monkeypatch):
    from icarus_engine.learning_fabric import LearningFabric
    from tests_engine.test_learning_fabric import _prediction
    server, _, request = workspace_http
    def forbidden(*a, **k):
        pytest.fail("APEX Learning context started acquisition or a worker")
    monkeypatch.setattr(LearningFabric, "start_background", forbidden)
    monkeypatch.setattr(LearningFabric, "run_cycle", forbidden)
    before = request("/api/command-centers/cc1/panels/apex?asset=NQ")[1]
    assert before["learning"]["status"] == "AVAILABLE"
    assert before["learning"]["snapshot"]["predictions"]["count"] == 0
    runtime = server.workspace_panels._runtimes["cc1"]
    runtime.intelligence.learning.record_prediction(_prediction())
    assert request("/api/command-centers/cc1/panels/learning")[1]["predictions"]["count"] == 1
    after = request("/api/command-centers/cc1/panels/apex?asset=NQ")[1]
    assert after["learning"]["status"] == "AVAILABLE"
    assert after["learning"]["snapshot"]["predictions"]["count"] == 1
    assert runtime.intelligence.learning._thread is None
    assert runtime.intelligence.learning.path == runtime.root / "research" / "learning.sqlite3"


def test_busy_research_runner_returns_unavailable_without_constructing_services(tmp_path):
    import threading
    from types import SimpleNamespace
    from icarus_engine.workspace_api import WorkspaceAPIError
    from icarus_engine.workspace_research_engines import WorkspaceResearchEngines
    from icarus_engine.workspace_intelligence_panels import WorkspaceIntelligencePanels
    lock = threading.Lock()
    port = SimpleNamespace(base_dir=str(tmp_path), runners={"NQ": object()},
                           runner_list=lambda: [SimpleNamespace(lock=lock)])
    runtime = SimpleNamespace(root=tmp_path, port=port)
    panels = WorkspaceIntelligencePanels(runtime, WorkspaceResearchEngines(runtime))
    lock.acquire()
    try:
        with pytest.raises(WorkspaceAPIError, match="busy"):
            panels.read("research", {})
        assert "research" not in panels.__dict__
    finally:
        lock.release()


def test_intuition_status_read_does_not_create_or_open_learning_state(workspace_http):
    server, parent, request = workspace_http
    selected_root = server.command_centers.root / "cc1" / "subsystems"
    parent_learning = parent.base_dir
    code, data, _ = request("/api/command-centers/cc1/panels/intuition-omega")
    assert code == 200, data
    assert data["workspace_id"] == "cc1"
    assert data["learning_source"]["state"] == "NOT_INITIALIZED"
    assert data["ledger"]["state"] == "NOT_INITIALIZED"
    assert not (selected_root / "research" / "learning.sqlite3").exists()
    assert not (selected_root / "intuition-omega" / "forecasts.sqlite3").exists()
    assert not (Path(parent_learning) / "intuition-omega" / "forecasts.sqlite3").exists()
