"""Native research views read selected cached state and durable private ledgers."""
import json

import pytest

from tests_engine.test_workspace_api import workspace_http  # noqa: F401


@pytest.mark.parametrize("workspace,price", [("cc1", 100), ("cc2", 200), ("cc3", 300), ("cc4", 400)])
@pytest.mark.parametrize("panel", ["parallax", "dreamstate", "pantheon", "sibyl", "apex"])
def test_native_research_http_reads_selected_workspace(workspace_http, monkeypatch, workspace, price, panel):
    _, parent, request = workspace_http
    monkeypatch.setattr(parent, "status", lambda *a, **k: pytest.fail("parent fallback"))
    code, data, _ = request(f"/api/command-centers/{workspace}/panels/{panel}?asset=NQ")
    assert code == 200, data
    assert data["workspace_id"] == workspace and data["paper_only"] is True
    assert data["execution_authorized"] is False
    if panel == "sibyl":
        assert data["current_price"] == price
        assert data["evidence"]["count"] == 0
    elif panel == "apex":
        psi = next(row for row in data["siblings"] if row["subsystem"] == "psi")
        assert psi["snapshot"]["price"] == price
        assert data["epistemics"]["evidence_count"] == 0


@pytest.mark.parametrize("panel", ["parallax", "dreamstate", "pantheon", "sibyl", "apex"])
def test_research_rejects_foreign_assets_and_ambiguous_queries(workspace_http, panel):
    _, _, request = workspace_http
    for query, expected in [("asset=ES", 404), ("asset=NQ&asset=NQ", 400), ("workspace=cc2", 400)]:
        code, data, _ = request(f"/api/command-centers/cc1/panels/{panel}?{query}")
        assert code == expected, data


def test_native_readers_reopen_only_selected_persisted_records(tmp_path):
    from types import SimpleNamespace
    from icarus_engine.workspace_research_engines import WorkspaceResearchEngines
    from tests_engine.test_parallax_dreamstate import _record_pair
    from tests_engine.test_pantheon_aether import _payload
    from tests_engine.test_sibyl import _evidence
    from tests_engine.test_apex_store import _body

    def runtime(root, price):
        row = {"symbol": "NQ", "price": price}
        return SimpleNamespace(root=root, port=SimpleNamespace(runners={"NQ": object()}, status=lambda: {"assets": [row]}),
            possibility=SimpleNamespace(snapshot=lambda *a: {"price": price}),
            chronofold=SimpleNamespace(snapshot=lambda *a: {"price": price}))

    one, two = runtime(tmp_path / "cc1", 100), runtime(tmp_path / "cc2", 200)
    readers = WorkspaceResearchEngines(one)
    _record_pair(readers.parallax, 1)
    readers.pantheon.record_observation(_payload())
    _evidence(readers.sibyl, "macro")
    readers.apex.ingest_evidence(_body())
    readers.close()
    reopened, other = WorkspaceResearchEngines(one), WorkspaceResearchEngines(two)
    try:
        assert reopened.read("parallax", {})["counts"]["decisions"] == 1
        assert other.read("parallax", {})["counts"]["decisions"] == 0
        assert reopened.read("pantheon", {})["counts"]["observations"] == 1
        assert other.read("pantheon", {})["counts"]["observations"] == 0
        assert reopened.read("sibyl", {})["evidence"]["count"] == 1
        assert other.read("sibyl", {})["evidence"]["count"] == 0
        assert reopened.read("apex", {})["epistemics"]["evidence_count"] == 1
        assert other.read("apex", {})["epistemics"]["evidence_count"] == 0
        assert reopened.read("dreamstate", {})["candidates"] == []
        assert reopened.parallax.path.parent == one.root / "research"
        assert reopened.dreamstate.parallax is reopened.parallax
        assert reopened.sibyl.recent_forecasts("NQ") == []
    finally:
        reopened.close()
        other.close()


def test_research_cached_provider_reads_never_start_workers_or_acquisition(workspace_http, monkeypatch):
    from icarus_engine.learning_fabric import LearningFabric
    from tests_engine.test_workspace_market_data import owner
    server, _, request = workspace_http
    feed = owner()
    def forbidden(*a, **k):
        pytest.fail("research reader initiated provider acquisition or a worker")
    feed.trades = feed.depth_events = feed.meta = feed.capabilities = forbidden
    monkeypatch.setattr(LearningFabric, "start_background", forbidden)
    monkeypatch.setattr(LearningFabric, "run_cycle", forbidden)
    monkeypatch.setattr(LearningFabric, "scan_history", forbidden)
    monkeypatch.setattr(LearningFabric, "harvest_native", forbidden)
    server.command_centers.portfolios["cc1"].runners["NQ"].feed = feed
    for panel in ("parallax", "dreamstate", "pantheon", "sibyl", "apex", "apex/forces"):
        code, data, _ = request(f"/api/command-centers/cc1/panels/{panel}?asset=NQ")
        assert code == 200, data
    assert '"observed_outcomes": 0' in json.dumps(request("/api/command-centers/cc1/panels/parallax")[1])


def test_research_rejects_linked_private_state_before_native_open(tmp_path):
    from types import SimpleNamespace
    from icarus_engine.workspace_api import WorkspaceAPIError
    from icarus_engine.workspace_research_engines import WorkspaceResearchEngines
    outside = tmp_path / "outside"
    outside.mkdir()
    private = tmp_path / "cc1"
    private.mkdir()
    (private / "research").symlink_to(outside, target_is_directory=True)
    with pytest.raises(WorkspaceAPIError, match="symlink"):
        WorkspaceResearchEngines(SimpleNamespace(root=private, port=object()))
    assert list(outside.iterdir()) == []


def test_apex_siblings_use_explicit_selected_asset(tmp_path):
    from types import SimpleNamespace
    from icarus_engine.workspace_research_engines import WorkspaceResearchEngines
    rows = [{"symbol": "NQ", "price": 100}, {"symbol": "ES", "price": 200}]
    runtime = SimpleNamespace(root=tmp_path, port=SimpleNamespace(runners={"NQ": object(), "ES": object()},
        status=lambda: {"assets": rows}), possibility=SimpleNamespace(snapshot=lambda asset: {"asset": asset}),
        chronofold=SimpleNamespace(snapshot=lambda asset: {"asset": asset}))
    reader = WorkspaceResearchEngines(runtime)
    try:
        state = reader.read("apex", {"asset": ["ES"]})
        siblings = {row["subsystem"]: row for row in state["siblings"]}
        assert siblings["psi"]["snapshot"]["asset"] == "ES"
        assert siblings["chronofold"]["snapshot"]["asset"] == "ES"
        assert siblings["sibyl"]["snapshot"]["asset"] == "ES"
    finally:
        reader.close()
