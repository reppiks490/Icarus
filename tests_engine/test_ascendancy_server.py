from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from icarus_engine.runtime import Journal, Portfolio
from icarus_engine.server import serve


def _genome(*, subsystem="chronofold"):
    return {
        "source_repo": "reppiks490/Icarus",
        "source_commit": "c" * 40,
        "parent_genome_ids": [],
        "nodes": [
            {"id": "time", "subsystem": subsystem, "kind": "native", "tier": "research", "config": {"mode": "shadow"}},
        ],
        "edges": [],
        "mutation": {
            "operator": "seed",
            "target": "architecture",
            "rationale": "HTTP genome fixture",
        },
        "falsifiers": ["protected OOS contribution is nonpositive"],
        "resource_budget": {
            "max_evaluations": 32,
            "max_wall_seconds": 900,
            "max_cost_units": 25.0,
        },
        "evaluation_contract": {
            "objectives": [
                {"name": "incremental_information", "direction": "max"},
                {"name": "instability", "direction": "min"},
            ],
            "descriptor_keys": ["regime", "complexity_band"],
            "protected_holdout_required": True,
        },
    }


@pytest.fixture
def ascendancy_genome_http(tmp_path):
    port = Portfolio(Journal(":memory:"), str(tmp_path))
    srv = serve(port, 0, token="ascendancy-genome-token", start=False)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def request(method: str, route: str, *, body=None, raw: bytes | None = None, auth: bool = True):
        headers = {}
        if auth:
            headers["Authorization"] = "Bearer ascendancy-genome-token"
        data = raw
        if body is not None:
            data = json.dumps(body, allow_nan=False).encode()
        if data is not None:
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


def test_genome_api_requires_authentication(ascendancy_genome_http):
    _, _, request = ascendancy_genome_http
    code, body = request("GET", "/api/ascendancy/genomes", auth=False)
    assert code == 401
    assert "admin token" in body["detail"]

    code, body = request("POST", "/admin/ascendancy/genome", body=_genome(), auth=False)
    assert code == 401
    assert "admin token" in body["detail"]


def test_register_compile_evaluate_and_retire_are_research_only(ascendancy_genome_http):
    port, srv, request = ascendancy_genome_http
    paused_before = port.paused
    runners_before = list(port.runners)

    code, registered = request("POST", "/admin/ascendancy/genome", body=_genome())
    assert code == 200, registered
    assert registered["genome"]["state"] == "REGISTERED_RESEARCH"
    assert registered["compile_receipt"]["status"] == "COMPILED_RESEARCH_ONLY"
    assert registered["compile_receipt"]["production_bindings"] == []
    assert registered["trading_state_unchanged"] is True
    assert registered["execution_authorized"] is False
    assert registered["production_decision_authorized"] is False
    genome = registered["genome"]

    code, snapshot = request("GET", "/api/ascendancy/genomes")
    assert code == 200
    assert snapshot["archive"]["genome_count"] == 1
    assert snapshot["archive"]["compile_count"] == 1
    assert snapshot["frontier"]["contract_count"] == 0
    assert snapshot["execution_authorized"] is False
    assert snapshot["production_decision_authorized"] is False

    evaluation = {
        "genome_id": genome["genome_id"],
        "evaluation_contract_hash": genome["evaluation_contract"]["contract_hash"],
        "metrics": {"incremental_information": 0.19, "instability": 0.06},
        "descriptors": {"regime": "RTH", "complexity_band": "LOW"},
        "evidence": ["protected-holdout:http-fixture"],
        "observed_at": "2026-10-02T04:00:00Z",
        "status": "VALIDATED_RESEARCH",
    }
    code, evaluated = request("POST", "/admin/ascendancy/genome-evaluation", body=evaluation)
    assert code == 200, evaluated
    assert evaluated["trading_state_unchanged"] is True
    assert evaluated["execution_authorized"] is False
    assert evaluated["production_decision_authorized"] is False

    code, snapshot = request("GET", "/api/ascendancy/genomes")
    assert code == 200
    assert snapshot["archive"]["evaluation_count"] == 1
    group = snapshot["frontier"]["contracts"][0]
    assert group["pareto_genome_ids"] == [genome["genome_id"]]

    code, retired = request("POST", "/admin/ascendancy/genome-retire", body={
        "genome_id": genome["genome_id"],
        "reason": "HTTP retirement fixture",
    })
    assert code == 200, retired
    assert retired["state"] == "RETIRED"
    assert retired["trading_state_unchanged"] is True
    assert retired["execution_authorized"] is False
    assert retired["production_decision_authorized"] is False

    assert port.paused is paused_before
    assert list(port.runners) == runners_before
    assert srv.ascendancy_archive.snapshot()["evaluation_count"] == 1


def test_invalid_genome_compile_fails_before_archive_mutation(ascendancy_genome_http):
    _, srv, request = ascendancy_genome_http
    before = srv.ascendancy_archive.snapshot()["genome_count"]
    code, body = request("POST", "/admin/ascendancy/genome", body=_genome(subsystem="definitely-not-native"))
    assert code == 400
    assert "unknown native subsystem" in body["detail"]
    assert srv.ascendancy_archive.snapshot()["genome_count"] == before


def test_ascendancy_bad_json_is_strict_and_unauthenticated_body_is_not_parsed(ascendancy_genome_http):
    _, srv, request = ascendancy_genome_http
    before = srv.ascendancy_archive.snapshot()["genome_count"]

    code, body = request("POST", "/admin/ascendancy/genome", raw=b'{"broken":')
    assert code == 400
    assert "bad JSON body" in body["detail"]

    code, body = request("POST", "/admin/ascendancy/genome", raw=b'{"broken":', auth=False)
    assert code == 401
    assert "bad admin token" in body["detail"]
    assert srv.ascendancy_archive.snapshot()["genome_count"] == before
