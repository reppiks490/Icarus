from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from icarus_engine.runtime import Journal, Portfolio
from icarus_engine.server import serve


def _candidate():
    return {
        "origin": "generated_math",
        "source_repo": "reppiks490/Icarus",
        "source_commit": "c" * 40,
        "title": "Rebased ASCENDANCY candidate",
        "hypothesis": "A bounded representation mutation adds conditional information.",
        "mechanism": {
            "type": "representation_mutation",
            "inputs": ["price", "information_time"],
            "transform": "phase_compression",
            "outputs": ["compressed_phase"],
        },
        "expected_advantage": {
            "target": "incremental_information",
            "direction": "increase",
            "scope": "NQ:RTH",
        },
        "required_observations": [
            {"name": "price", "evidence_class": "observed"},
            {"name": "information_time", "evidence_class": "derived"},
        ],
        "falsifiers": [
            "protected OOS incremental information is nonpositive",
            "effect disappears under regime-stratified replay",
        ],
        "parent_candidate_ids": [],
        "parent_genome_ids": [],
        "evaluation_contract": {
            "objectives": [
                {"name": "incremental_information", "direction": "max"},
                {"name": "instability", "direction": "min"},
            ],
            "descriptor_keys": ["regime", "complexity_band"],
            "protected_holdout_required": True,
        },
        "resource_budget": {
            "max_evaluations": 64,
            "max_wall_seconds": 1800,
            "max_cost_units": 25.0,
        },
        "metadata": {"research_question": "fixture"},
    }


def _genome():
    return {
        "source_repo": "reppiks490/Icarus",
        "source_commit": "d" * 40,
        "parent_genome_ids": [],
        "nodes": [
            {
                "id": "capabilities",
                "subsystem": "capability-orchestrator",
                "kind": "native",
                "tier": "research",
                "config": {},
            }
        ],
        "edges": [],
        "mutation": {
            "operator": "seed",
            "target": "architecture",
            "rationale": "runtime integration fixture",
        },
        "falsifiers": ["protected OOS contribution is nonpositive"],
        "resource_budget": {
            "max_evaluations": 16,
            "max_wall_seconds": 600,
            "max_cost_units": 10.0,
        },
        "evaluation_contract": {
            "objectives": [
                {"name": "incremental_information", "direction": "max"},
                {"name": "instability", "direction": "min"},
            ],
            "descriptor_keys": ["regime"],
            "protected_holdout_required": True,
        },
    }


@pytest.fixture
def ascendancy_runtime_http(tmp_path):
    port = Portfolio(Journal(":memory:"), str(tmp_path))
    srv = serve(port, 0, token="ascendancy-token", start=False)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def request(method: str, route: str, *, body=None, auth=True):
        headers = {}
        if auth:
            headers["Authorization"] = "Bearer ascendancy-token"
        data = None
        if body is not None:
            data = json.dumps(body, allow_nan=False).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(base + route, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as reply:
                return reply.status, json.load(reply)
        except urllib.error.HTTPError as ex:
            return ex.code, json.load(ex)

    yield port, srv, request
    srv.shutdown()
    srv.server_close()
    thread.join(5)
    port.journal.con.close()


def test_rebased_ascendancy_read_surface_is_authenticated_and_research_only(ascendancy_runtime_http):
    _, _, request = ascendancy_runtime_http
    routes = (
        "/api/ascendancy/capabilities",
        "/api/ascendancy/genomes",
        "/api/ascendancy/candidates",
        "/api/ascendancy/unknowns",
        "/api/ascendancy/mechanisms",
        "/api/ascendancy/inventions",
        "/api/ascendancy/contributions",
        "/api/ascendancy/evaluator",
        "/api/ascendancy/federation",
    )
    for route in routes:
        code, body = request("GET", route, auth=False)
        assert code == 401, route
        assert "admin token" in body["detail"]

        code, body = request("GET", route)
        assert code == 200, (route, body)
        assert body["execution_authorized"] is False
        assert body["production_decision_authorized"] is False


def test_candidate_and_evaluator_runtime_preserve_trading_control_state(ascendancy_runtime_http):
    port, srv, request = ascendancy_runtime_http
    paused_before = port.paused
    runners_before = list(port.runners)

    code, saved = request("POST", "/admin/ascendancy/candidate", body=_candidate())
    assert code == 200, saved
    assert saved["trading_state_unchanged"] is True
    candidate = saved["candidate"]
    assert candidate["execution_authorized"] is False

    code, enrolled = request(
        "POST",
        "/admin/ascendancy/evaluator-register",
        body={"candidate_id": candidate["candidate_id"]},
    )
    assert code == 200, enrolled
    assert enrolled["trading_state_unchanged"] is True
    assert enrolled["execution_authorized"] is False

    code, state = request("GET", "/api/ascendancy/evaluator")
    assert code == 200
    assert state["candidate_count"] == 1

    assert port.paused is paused_before
    assert list(port.runners) == runners_before
    assert srv.ascendancy_foundry.snapshot()["candidate_count"] == 1


def test_genome_runtime_compiles_before_persistence_and_preserves_authority(ascendancy_runtime_http):
    port, srv, request = ascendancy_runtime_http
    paused_before = port.paused
    runners_before = list(port.runners)

    code, saved = request("POST", "/admin/ascendancy/genome", body=_genome())
    assert code == 200, saved
    assert saved["trading_state_unchanged"] is True
    assert saved["execution_authorized"] is False
    assert saved["genome"]["source_commit"] == "d" * 40
    assert saved["compile_receipt"]["execution_authorized"] is False

    code, state = request("GET", "/api/ascendancy/genomes")
    assert code == 200
    assert state["archive"]["genome_count"] == 1
    assert state["frontier"]["execution_authorized"] is False

    assert port.paused is paused_before
    assert list(port.runners) == runners_before
    assert srv.ascendancy_archive.snapshot()["genome_count"] == 1


def test_federation_route_reuses_canonical_brain_remote_sync_not_parallel_peer_store(ascendancy_runtime_http):
    _, srv, request = ascendancy_runtime_http
    code, state = request("GET", "/api/ascendancy/federation")
    assert code == 200
    assert state == srv.brain_remote_sync.status()
    assert state["execution_authorized"] is False
    assert state["production_decision_authorized"] is False
    assert not hasattr(srv, "ascendancy_peers")
