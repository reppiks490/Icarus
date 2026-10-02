from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from icarus_engine.runtime import Journal, Portfolio
from icarus_engine.server import serve


REPO = Path(__file__).resolve().parents[1]


def _federation_snapshot():
    return {
        "schema_version": "icarus-brain-remote-sync-v1",
        "repository": "reppiks490/Icarus-engine",
        "ref": "main",
        "status": "green",
        "peer_packet_status": "green",
        "peer_packet_id": "1" * 64,
        "peer_source_commit": "a" * 40,
        "peer_source_commit_verified": True,
        "peer_source_commit_relation": "HEAD_OR_ANCESTOR",
        "peer_packet_fresh": True,
        "peer_packet_age_seconds": 45.0,
        "historical_context_status": "green",
        "historical_context_source_count": 2,
        "historical_candidate_evidence_count": 0,
        "historical_context_sources": [
            {
                "id": "apex_council",
                "path": "automation_intelligence/agent_fabric/apex_council/latest.json",
                "remote_blob_sha": "b" * 40,
                "run_id": "apex-1",
                "run_status": "RUN_PERSISTED",
                "evidence_status": "HISTORICAL_RESEARCH_EVIDENCE",
                "collection_only": False,
                "research_context_eligible": True,
                "candidate_evidence_eligible": False,
                "foreign_evidence_only": True,
                "requires_foundry_and_evaluator": True,
                "summary": {
                    "RUN_CORE.disagreements_collisions": [
                        "Flow and macro disagree on persistence horizon."
                    ]
                },
                "subject": "Apex Council",
                "execution_authorized": False,
                "production_decision_authorized": False,
            },
            {
                "id": "flow_microstructure",
                "path": "automation_intelligence/flow/latest.json",
                "remote_blob_sha": "c" * 40,
                "run_id": "flow-1",
                "run_status": "RUN_PERSISTED",
                "evidence_status": "HISTORICAL_COLLECTION_EVIDENCE",
                "collection_only": True,
                "research_context_eligible": True,
                "candidate_evidence_eligible": False,
                "foreign_evidence_only": True,
                "requires_foundry_and_evaluator": True,
                "summary": {
                    "DATA_GAPS": ["No direct NQ depth in this run."],
                    "observations": {"BTC": {"funding_percent": 0.003}},
                },
                "subject": "Flow Microstructure",
                "execution_authorized": False,
                "production_decision_authorized": False,
            },
        ],
        "truth_contract": {
            "federation_schema": "icarus-engine-brain-federation-v1",
            "historical_context_mode": "RESEARCH_CONTEXT_ONLY",
            "historical_context_never_bypasses_foundry": True,
            "historical_context_never_bypasses_evaluator": True,
            "historical_context_never_grants_shadow_qualification": True,
            "historical_context_never_grants_execution_authority": True,
            "durability_receipts_are_substantive_evidence": False,
            "automatic_model_promotion": False,
            "automatic_execution_authority": False,
            "production_decision_authorized": False,
        },
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


@pytest.fixture
def intake_http(tmp_path):
    port = Portfolio(Journal(":memory:"), str(tmp_path))
    srv = serve(port, 0, token="federated-intake-token", start=False)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def request(method: str, route: str, *, body=None, auth=True):
        headers = {}
        if auth:
            headers["Authorization"] = "Bearer federated-intake-token"
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


def test_federated_intake_api_syncs_canonical_brain_context_without_creating_candidates(intake_http):
    port, srv, request = intake_http
    paused_before = port.paused
    runners_before = list(port.runners)

    code, body = request("GET", "/api/ascendancy/federated-intake", auth=False)
    assert code == 401
    assert "admin token" in body["detail"]

    code, empty = request("GET", "/api/ascendancy/federated-intake")
    assert code == 200
    assert empty["proposal_count"] == 0
    assert empty["candidate_evidence_count"] == 0

    srv.brain_remote_sync.status = lambda: _federation_snapshot()

    code, synced = request(
        "POST",
        "/admin/ascendancy/federated-intake-sync",
        body={},
    )
    assert code == 200, synced
    assert synced["trading_state_unchanged"] is True
    assert synced["new_proposal_count"] == 3
    assert synced["candidate_evidence_count"] == 0
    assert synced["automatic_candidate_creation"] is False
    assert synced["execution_authorized"] is False
    assert synced["production_decision_authorized"] is False

    code, state = request("GET", "/api/ascendancy/federated-intake")
    assert code == 200
    assert state["proposal_count"] == 3
    assert state["candidate_evidence_count"] == 0
    assert state["truth_contract"]["research_prompt_is_not_a_foundry_candidate"] is True
    assert srv.ascendancy_foundry.snapshot()["candidate_count"] == 0

    code, again = request(
        "POST",
        "/admin/ascendancy/federated-intake-sync",
        body={},
    )
    assert code == 200
    assert again["new_proposal_count"] == 0

    assert port.paused is paused_before
    assert list(port.runners) == runners_before


def test_federated_intake_runtime_fails_closed_on_degraded_remote_state(intake_http):
    _, srv, request = intake_http
    degraded = _federation_snapshot()
    degraded["peer_packet_fresh"] = False
    srv.brain_remote_sync.status = lambda: degraded

    code, body = request(
        "POST",
        "/admin/ascendancy/federated-intake-sync",
        body={},
    )
    assert code == 400
    assert "fresh" in body["detail"].lower()
    assert srv.ascendancy_federated_intake.snapshot()["proposal_count"] == 0


def test_federated_intake_is_registered_visible_and_control_plane_accessible():
    server = (REPO / "icarus_engine/server.py").read_text(encoding="utf-8")
    brain = (REPO / "icarus_engine/brain.py").read_text(encoding="utf-8")
    ui = (REPO / "icarus_engine/ascendancy-ui.js").read_text(encoding="utf-8")

    assert "FederatedResearchIntake" in server
    assert 'p.path == "/api/ascendancy/federated-intake"' in server
    assert 'p.path == "/admin/ascendancy/federated-intake-sync"' in server
    assert 'ControlAction("sync.ascendancy_federated_intake"' in server
    assert "brain_remote_sync.status()" in server

    assert '"id": "ascendancy-federated-intake"' in brain

    assert "FEDERATED RESEARCH INTAKE" in ui
    assert "/api/ascendancy/federated-intake" in ui
    assert "RESEARCH_PROMPT_ONLY" in ui
    assert "candidate evidence=false" in ui.lower()
    assert "automatic candidate creation=false" in ui.lower()
