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


def _candidate(**overrides):
    body = {
        "origin": "generated_math",
        "source_repo": "reppiks490/Icarus",
        "source_commit": "d" * 40,
        "title": "Residual phase candidate",
        "hypothesis": "A residual-conditioned phase representation adds protected information.",
        "mechanism": {
            "type": "representation_mutation",
            "inputs": ["price", "information_time"],
            "transform": "residual_phase",
            "outputs": ["phase_state"],
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
            "max_evaluations": 32,
            "max_wall_seconds": 900,
            "max_cost_units": 10.0,
        },
        "metadata": {"fixture": True},
    }
    body.update(overrides)
    return body


def _unknown_event(**overrides):
    body = {
        "source_engine": "apex-omega",
        "source_kind": "native",
        "source_repo": "reppiks490/Icarus",
        "source_commit": "e" * 40,
        "asset": "NQ",
        "horizon_seconds": 300,
        "observed_at": "2026-10-02T06:00:00Z",
        "received_at": "2026-10-02T06:00:01Z",
        "episode_id": "ep-http-001",
        "regime": "RTH_HIGH_VOL",
        "residual_family": "synchronized_reversal_underprediction",
        "residual_magnitude": 0.82,
        "evidence_class": "derived",
        "evidence_ids": ["evidence:http:unknown:1"],
        "failed_systems": ["chronofold", "psi", "apex-omega"],
        "phenomenon_descriptors": {"session": "RTH", "volatility_band": "HIGH"},
        "context": {"reality_gap_state": "DEGRADED", "nullspace_route": "unresolved"},
        "cause": None,
    }
    body.update(overrides)
    return body


def _invention_seed(**overrides):
    body = {
        "source_repo": "reppiks490/Icarus",
        "source_commit": "9" * 40,
        "research_question": "Can an information-time phase state add protected information?",
        "target_outcome": "incremental_information",
        "observations": [
            {"role": "price_series", "name": "price", "evidence_class": "observed"},
            {"role": "returns", "name": "returns", "evidence_class": "derived"},
            {"role": "volatility", "name": "realized_volatility", "evidence_class": "derived"},
            {"role": "information_rate", "name": "information_rate", "evidence_class": "derived"},
        ],
        "target_roles": ["phase_state"],
        "parent_candidate_ids": [],
        "constraints": {"max_depth": 3, "max_candidates": 16, "max_cost_units": 7.0},
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
            "max_cost_units": 50.0,
        },
        "context": {"asset": "NQ", "session": "RTH"},
    }
    body.update(overrides)
    return body


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


def test_candidate_foundry_api_is_authenticated_and_research_only(ascendancy_genome_http):
    port, srv, request = ascendancy_genome_http
    paused_before = port.paused
    runners_before = list(port.runners)

    code, body = request("GET", "/api/ascendancy/candidates", auth=False)
    assert code == 401
    assert "admin token" in body["detail"]

    code, body = request("POST", "/admin/ascendancy/candidate", body=_candidate(), auth=False)
    assert code == 401
    assert "admin token" in body["detail"]

    code, registered = request("POST", "/admin/ascendancy/candidate", body=_candidate())
    assert code == 200, registered
    candidate = registered["candidate"]
    assert candidate["stage"] == "PROPOSED"
    assert registered["trading_state_unchanged"] is True
    assert registered["execution_authorized"] is False
    assert registered["production_decision_authorized"] is False

    code, snapshot = request("GET", "/api/ascendancy/candidates")
    assert code == 200
    assert snapshot["candidate_count"] == 1
    assert snapshot["candidates"][0]["candidate_id"] == candidate["candidate_id"]
    assert snapshot["contracts"]["qualified_shadow_reserved_for_protected_qualification"] is True

    code, advanced = request("POST", "/admin/ascendancy/candidate-stage", body={
        "candidate_id": candidate["candidate_id"],
        "stage": "INCUBATING",
        "reason": "mechanism review passed",
    })
    assert code == 200, advanced
    assert advanced["stage"] == "INCUBATING"
    assert advanced["trading_state_unchanged"] is True

    code, blocked = request("POST", "/admin/ascendancy/candidate-stage", body={
        "candidate_id": candidate["candidate_id"],
        "stage": "QUALIFIED_SHADOW",
        "reason": "must not be allowed by foundry",
    })
    assert code == 400
    assert "terminal" in blocked["detail"].lower()

    code, rejected = request("POST", "/admin/ascendancy/candidate-reject", body={
        "candidate_id": candidate["candidate_id"],
        "reason": "falsifier triggered",
    })
    assert code == 200, rejected
    assert rejected["stage"] == "REJECTED"
    assert rejected["trading_state_unchanged"] is True

    assert port.paused is paused_before
    assert list(port.runners) == runners_before
    assert srv.ascendancy_foundry.snapshot()["candidate_count"] == 1


def test_invalid_foundry_candidate_fails_before_mutation(ascendancy_genome_http):
    _, srv, request = ascendancy_genome_http
    before = srv.ascendancy_foundry.snapshot()["candidate_count"]
    invalid = _candidate(falsifiers=[])
    code, body = request("POST", "/admin/ascendancy/candidate", body=invalid)
    assert code == 400
    assert "falsifier" in body["detail"].lower()
    assert srv.ascendancy_foundry.snapshot()["candidate_count"] == before


def test_unknown_unknown_api_is_authenticated_and_research_only(ascendancy_genome_http):
    port, srv, request = ascendancy_genome_http
    paused_before = port.paused
    runners_before = list(port.runners)

    code, body = request("GET", "/api/ascendancy/unknowns", auth=False)
    assert code == 401
    assert "admin token" in body["detail"]

    code, saved = request("POST", "/admin/ascendancy/unknown-event", body=_unknown_event())
    assert code == 200, saved
    signature = saved["event"]["phenomenon_signature"]
    assert saved["trading_state_unchanged"] is True
    assert saved["event"]["cause"] is None

    code, snapshot = request("GET", "/api/ascendancy/unknowns")
    assert code == 200
    assert snapshot["phenomenon_count"] == 1
    assert snapshot["phenomena"][0]["cause"] is None
    assert snapshot["phenomena"][0]["status"] == "EARLY"

    code, explained = request("POST", "/admin/ascendancy/unknown-explanation", body={
        "phenomenon_signature": signature,
        "explanation": "A volatility scaling artifact explains the residual.",
        "status": "FAILED",
        "evidence": ["ablation:http:volatility"],
        "source_repo": "reppiks490/Icarus",
        "source_commit": "f" * 40,
    })
    assert code == 200, explained
    assert explained["trading_state_unchanged"] is True

    candidate_id = "a" * 64
    code, linked = request("POST", "/admin/ascendancy/unknown-link-candidate", body={
        "phenomenon_signature": signature,
        "candidate_id": candidate_id,
        "rationale": "candidate generated from unexplained residual",
    })
    assert code == 200, linked
    assert linked["candidate_id"] == candidate_id
    assert linked["trading_state_unchanged"] is True

    code, snapshot = request("GET", "/api/ascendancy/unknowns")
    assert code == 200
    phenomenon = snapshot["phenomena"][0]
    assert phenomenon["failed_explanations"] == [
        "A volatility scaling artifact explains the residual."
    ]
    assert phenomenon["candidate_ids"] == [candidate_id]
    assert phenomenon["cause"] is None

    assert port.paused is paused_before
    assert list(port.runners) == runners_before
    assert srv.ascendancy_unknowns.snapshot()["event_count"] == 1


def test_unknown_event_with_assigned_cause_fails_before_mutation(ascendancy_genome_http):
    _, srv, request = ascendancy_genome_http
    before = srv.ascendancy_unknowns.snapshot()["event_count"]
    invalid = _unknown_event(cause="invented hidden force")
    code, body = request("POST", "/admin/ascendancy/unknown-event", body=invalid)
    assert code == 400
    assert "cause must remain null" in body["detail"]
    assert srv.ascendancy_unknowns.snapshot()["event_count"] == before


def test_mechanism_lab_api_is_authenticated_candidate_bound_and_research_only(ascendancy_genome_http):
    port, srv, request = ascendancy_genome_http
    paused_before = port.paused
    runners_before = list(port.runners)

    code, body = request("GET", "/api/ascendancy/mechanisms", auth=False)
    assert code == 401
    assert "admin token" in body["detail"]

    unbound = {
        "candidate_id": "a" * 64,
        "source_repo": "reppiks490/Icarus",
        "source_commit": "c" * 40,
        "evaluation_contract_hash": "b" * 64,
        "mechanism_key": "time_price_phase",
        "experiment_kind": "ablation",
        "target_metric": "incremental_information",
        "direction": "max",
        "baseline_value": 0.20,
        "perturbed_value": 0.10,
        "context": {"asset": "NQ", "regime": "RTH_HIGH_VOL"},
        "episode_id": "http-unbound",
        "related_mechanisms": [],
        "evidence": ["paired-replay:http"],
        "observed_at": "2026-10-02T06:30:00Z",
    }
    code, body = request("POST", "/admin/ascendancy/mechanism-experiment", body=unbound)
    assert code == 400
    assert "unknown candidate" in body["detail"].lower()

    code, registered = request("POST", "/admin/ascendancy/candidate", body=_candidate())
    assert code == 200, registered
    candidate = registered["candidate"]

    experiment = dict(unbound)
    experiment["candidate_id"] = candidate["candidate_id"]
    experiment["source_repo"] = candidate["source_repo"]
    experiment["source_commit"] = candidate["source_commit"]
    experiment["evaluation_contract_hash"] = candidate["evaluation_contract"]["contract_hash"]
    experiment["episode_id"] = "http-bound"
    code, saved = request("POST", "/admin/ascendancy/mechanism-experiment", body=experiment)
    assert code == 200, saved
    assert saved["trading_state_unchanged"] is True
    assert saved["experiment"]["causal_proof"] is False
    assert saved["execution_authorized"] is False
    assert saved["production_decision_authorized"] is False

    code, snapshot = request("GET", "/api/ascendancy/mechanisms")
    assert code == 200
    assert snapshot["experiment_count"] == 1
    assert snapshot["mechanisms"][0]["classification"] == "UNRESOLVED"
    assert snapshot["truth_contract"]["mechanism_attribution_is_not_causal_proof"] is True

    assert port.paused is paused_before
    assert list(port.runners) == runners_before
    assert srv.ascendancy_mechanisms.snapshot()["experiment_count"] == 1


def test_invention_api_generates_blueprints_and_feeds_foundry_research_only(ascendancy_genome_http):
    port, srv, request = ascendancy_genome_http
    paused_before = port.paused
    runners_before = list(port.runners)

    code, body = request("GET", "/api/ascendancy/inventions", auth=False)
    assert code == 401
    assert "admin token" in body["detail"]

    code, generated = request(
        "POST", "/admin/ascendancy/invention-generate", body=_invention_seed()
    )
    assert code == 200, generated
    assert generated["generated_count"] > 0
    assert generated["trading_state_unchanged"] is True
    blueprint = next(
        row for row in generated["blueprints"]
        if row["primitive_ids"] == ["information_clock", "phase_embedding"]
    )
    assert blueprint["status"] == "UNTESTED_HYPOTHESIS"
    assert blueprint["edge_claim_established"] is False

    code, snapshot = request("GET", "/api/ascendancy/inventions")
    assert code == 200
    assert snapshot["blueprint_count"] == generated["generated_count"]
    assert snapshot["truth_contract"]["generated_blueprint_is_not_validated_edge"] is True

    code, promoted = request(
        "POST",
        "/admin/ascendancy/invention-to-candidate",
        body={"blueprint_id": blueprint["blueprint_id"]},
    )
    assert code == 200, promoted
    assert promoted["candidate"]["origin"] == "generated_math"
    assert promoted["candidate"]["stage"] == "PROPOSED"
    assert promoted["candidate"]["metadata"]["blueprint_id"] == blueprint["blueprint_id"]
    assert promoted["trading_state_unchanged"] is True
    assert promoted["execution_authorized"] is False
    assert promoted["production_decision_authorized"] is False

    assert port.paused is paused_before
    assert list(port.runners) == runners_before
    assert srv.ascendancy_inventions.snapshot()["blueprint_count"] > 0
    assert srv.ascendancy_foundry.snapshot()["candidate_count"] == 1
