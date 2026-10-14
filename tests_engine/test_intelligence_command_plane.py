from __future__ import annotations

from fastapi.testclient import TestClient

from icarus_engine.intelligence_gateway import GatewayConfig, create_intelligence_gateway_app


def _headers(token: str) -> dict[str, str]:
    return {"host": "localhost", "authorization": f"Bearer {token}"}


def _app(tmp_path, *, enabled: bool = True):
    identity = {"principal_id": "requester", "principal_kind": "human"} if enabled else None
    credentials = (
        {
            "worker-token": {"principal_id": "worker", "principal_kind": "agent"},
            "analyst-token": {"principal_id": "analyst", "principal_kind": "agent"},
            "reviewer-token": {"principal_id": "reviewer", "principal_kind": "human"},
        }
        if enabled
        else None
    )
    return create_intelligence_gateway_app(
        db_path=str(tmp_path / "gateway.db"),
        bearer_token="gateway-token",
        config=GatewayConfig(command_identity=identity, command_credentials=credentials),
    )


def test_command_plane_is_absent_without_server_bound_identity(tmp_path):
    app = _app(tmp_path, enabled=False)
    with TestClient(app) as client:
        page = client.get("/command", headers={"host": "localhost"})
        identity = client.get("/v1/identity", headers=_headers("gateway-token"))
    assert page.status_code == 404
    assert identity.status_code == 404


def test_command_identity_is_server_bound_and_rejects_client_actor_fields(tmp_path):
    app = _app(tmp_path)
    with TestClient(app) as client:
        requester = client.get("/v1/identity", headers=_headers("gateway-token"))
        worker = client.get("/v1/identity", headers=_headers("worker-token"))
        rejected = client.get("/v1/identity", headers=_headers("wrong-token"))
        forged = client.post(
            "/v1/work",
            headers=_headers("gateway-token"),
            json={
                "target_kind": "principal",
                "target_id": "worker",
                "work_kind": "research",
                "idempotency_key": "forged-actor",
                "objective": "Attempt to select an actor from the request body.",
                "actor_principal": "administrator",
            },
        )
    assert requester.status_code == worker.status_code == 200
    assert requester.json()["principal_id"] == "requester"
    assert worker.json()["principal_id"] == "worker"
    assert rejected.status_code == 401
    assert forged.status_code == 400


def test_command_work_presence_incident_decomposition_and_council_are_journaled(tmp_path):
    app = _app(tmp_path)
    headers = {"requester": _headers("gateway-token"), "worker": _headers("worker-token"),
               "analyst": _headers("analyst-token"),
               "reviewer": _headers("reviewer-token")}
    with TestClient(app) as client:
        created = client.post(
            "/v1/work",
            headers=headers["requester"],
            json={
                "target_kind": "principal",
                "target_id": "worker",
                "work_kind": "research",
                "idempotency_key": "mobile-command-001",
                "objective": "Review a bounded evidence packet.",
                "required_capabilities": ["macro"],
                "reviewer_principals": ["reviewer"],
                "constraints": {
                    "decomposition_plan": {
                        "plan_id": "evidence-plan-1",
                        "tasks": [{
                            "target_principal": "analyst",
                            "work_kind": "evidence",
                            "objective": "Collect an independent evidence set.",
                        }],
                    }
                },
            },
        )
        assert created.status_code == 201, created.text
        work_id = created.json()["work"]["work_id"]
        visible = client.get("/v1/work?limit=100", headers=headers["worker"])
        assert visible.status_code == 200
        assert [item["work_id"] for item in visible.json()["works"]] == [work_id]

        presence = client.post("/v1/presence", headers=headers["worker"],
                               json={"capabilities": ["macro"], "ttl_seconds": 60})
        assert presence.status_code == 200
        assert presence.json()["principal_id"] == "worker"
        analyst_presence = client.post("/v1/presence", headers=headers["analyst"],
                                       json={"capabilities": ["macro"], "ttl_seconds": 60})
        assert analyst_presence.status_code == 200
        available = client.get("/v1/presence?capability=macro", headers=headers["requester"]).json()["presence"]
        assert {item["principal_id"] for item in available} == {"analyst", "worker"}

        room = client.post(f"/v1/work/{work_id}/incidents", headers=headers["requester"], json={"members": ["worker"]})
        assert room.status_code == 200
        posted = client.post(f"/v1/work/{work_id}/incidents/messages", headers=headers["worker"],
                             json={"body": "Evidence collection is underway.", "operation_id": "incident-update-1"})
        assert posted.status_code == 200
        replay = client.post(f"/v1/work/{work_id}/incidents/messages", headers=headers["worker"],
                             json={"body": "Evidence collection is underway.", "operation_id": "incident-update-1"})
        assert replay.status_code == 200
        assert replay.json()["result"]["idempotent"] is True

        review = client.post(f"/v1/work/{work_id}/councils/evidence-review/votes", headers=headers["reviewer"],
                             json={"vote": "challenge", "claim": "The sample needs another independent source.",
                                   "operation_id": "review-1"})
        assert review.status_code == 200
        council = client.get(f"/v1/work/{work_id}/councils/evidence-review", headers=headers["requester"])
        assert council.status_code == 200
        assert council.json()["council"]["challenge_count"] == 1

        current = client.get(f"/v1/work/{work_id}", headers=headers["worker"]).json()["work"]
        accepted = client.post(
            f"/v1/work/{work_id}/transitions",
            headers=headers["worker"],
            json={"transition": "accepted", "operation_id": "accept-1",
                  "expected_head_event_id": current["head_event_id"], "data": {}},
        )
        assert accepted.status_code == 200, accepted.text
        children = accepted.json()["automatic_coordination"]["children"]
        assert len(children) == 1
        child_id = children[0]["work_id"]
        assert child_id
        child = client.get(f"/v1/work/{child_id}", headers=headers["analyst"])
        assert child.status_code == 200
        assert child.json()["work"]["parent_work_id"] == work_id
        child_head = child.json()["work"]["head_event_id"]
        child_accepted = client.post(
            f"/v1/work/{child_id}/transitions", headers=headers["analyst"],
            json={"transition": "accepted", "operation_id": "child-accept-1",
                  "expected_head_event_id": child_head, "data": {}},
        )
        assert child_accepted.status_code == 200
        child_head = child_accepted.json()["work"]["head_event_id"]
        child_completed = client.post(
            f"/v1/work/{child_id}/transitions", headers=headers["analyst"],
            json={"transition": "completed", "operation_id": "child-complete-1",
                  "expected_head_event_id": child_head,
                  "data": {"result": {"evidence_summary": "Independent evidence recorded."},
                           "unresolved_challenge_ids": []}},
        )
        assert child_completed.status_code == 200
        synthesis = client.post(
            f"/v1/work/{work_id}/syntheses", headers=headers["worker"],
            json={"operation_id": "synthesis-1", "child_work_ids": [child_id],
                  "summary": "The child evidence supports the bounded result.", "complete": True},
        )
        assert synthesis.status_code == 200, synthesis.text
        assert synthesis.json()["result"]["work"]["state"] == "COMPLETED"

        escalation_request = client.post(
            "/v1/work", headers=headers["requester"],
            json={"target_kind": "principal", "target_id": "worker", "work_kind": "investigation",
                  "idempotency_key": "escalation-work-1", "objective": "Route a second set of evidence work.",
                  "required_capabilities": ["macro"]},
        )
        assert escalation_request.status_code == 201
        escalation_id = escalation_request.json()["work"]["work_id"]
        escalation_head = escalation_request.json()["work"]["head_event_id"]
        escalation_accept = client.post(
            f"/v1/work/{escalation_id}/transitions", headers=headers["worker"],
            json={"transition": "accepted", "operation_id": "escalation-accept-1",
                  "expected_head_event_id": escalation_head, "data": {}},
        )
        assert escalation_accept.status_code == 200
        routed = client.post(
            f"/v1/work/{escalation_id}/escalations", headers=headers["worker"],
            json={"operation_id": "escalation-route-1", "target_principal": "analyst"},
        )
        assert routed.status_code == 200, routed.text
        assert routed.json()["result"]["selected_principal"] == "analyst"
        assert routed.json()["result"]["child"]["work_id"]
        assert routed.json()["incident"]["room_id"]

        events = client.get(f"/v1/work/{work_id}/incidents", headers=headers["worker"])
        assert events.status_code == 200
        assert len(events.json()["result"]["events"]) == 2

