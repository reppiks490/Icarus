from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from icarus_engine.runtime import Journal, Portfolio
from icarus_engine.server import serve


@pytest.fixture
def apex_http(tmp_path):
    port = Portfolio(Journal(":memory:"), str(tmp_path))
    srv = serve(port, 0, token="apex-token", start=False)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def request(method: str, route: str, *, body=None, raw: bytes | None = None, auth: bool = True):
        headers = {}
        if auth:
            headers["Authorization"] = "Bearer apex-token"
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


def test_apex_http_read_routes_are_authenticated_and_truthful(apex_http):
    port, srv, request = apex_http
    status, body = request("GET", "/api/apex", auth=False)
    assert status == 401
    assert "admin token" in body["detail"]

    for route in (
        "/api/apex",
        "/api/apex/participants?asset=NQ",
        "/api/apex/crowdhunt?asset=NQ",
        "/api/apex/forces?asset=NQ",
        "/api/apex/cascades",
        "/api/apex/causality",
        "/api/apex/worlds",
        "/api/apex/epistemics",
        "/api/apex/self",
        "/api/apex/conscience",
    ):
        code, payload = request("GET", route)
        assert code == 200, (route, payload)
        assert payload["execution_authorized"] is False
        assert payload["production_decision_authorized"] is False


def test_apex_http_degraded_sibling_does_not_take_down_full_snapshot(apex_http):
    _, srv, request = apex_http
    srv.apex._siblings["chronofold"] = lambda: (_ for _ in ()).throw(RuntimeError("fixture failure"))
    code, payload = request("GET", "/api/apex?asset=NQ")
    assert code == 200
    assert payload["status"] == "DEGRADED"
    by = {row["subsystem"]: row for row in payload["siblings"]}
    assert by["chronofold"]["status"] == "DEGRADED"


def test_apex_http_research_mutations_are_strict_and_do_not_change_trading_state(apex_http):
    port, srv, request = apex_http
    paused_before = port.paused
    runners_before = list(port.runners)
    evidence = {
        "kind": "observed",
        "subject": "NQ:test",
        "value": {"asset": "NQ", "price": 25000.0},
        "source": {
            "subsystem": "test",
            "source_repo": "reppiks490/Icarus",
            "source_commit": "a" * 40,
            "source_record_id": "apex-http-1",
        },
        "observed_at": "2026-10-01T14:00:00Z",
        "received_at": "2026-10-01T14:00:01Z",
        "calculated_at": "2026-10-01T14:00:01Z",
        "valid_from": "2026-10-01T14:00:00Z",
        "valid_until": None,
        "confidence": 1.0,
        "quality": 1.0,
        "dependencies": [],
        "contradictions": [],
        "falsifiers": ["source correction"],
    }
    calls = (
        ("/admin/apex/evidence", evidence),
        ("/admin/apex/outcome", {"outcome_id": "o1", "as_of": "2026-10-01T14:00:00Z", "status": "matured"}),
        ("/admin/apex/model-observation", {"model_id": "m1", "as_of": "2026-10-01T14:00:00Z", "gap": 0.2, "state": "NORMAL"}),
        ("/admin/apex/experiment", {"id": "x1", "discrimination": 0.8, "cost": 0.1}),
    )
    for route, body in calls:
        code, payload = request("POST", route, body=body)
        assert code == 200, (route, payload)
        assert payload["execution_authorized"] is False
        assert payload["production_decision_authorized"] is False

    assert port.paused is paused_before
    assert list(port.runners) == runners_before


def test_apex_http_bad_and_oversized_json_fail_without_mutating_evidence(apex_http):
    _, srv, request = apex_http
    before = srv.apex.store.integrity_status()["evidence_rows"]
    code, body = request("POST", "/admin/apex/evidence", raw=b'{"broken":')
    assert code == 400
    assert "bad JSON body" in body["detail"]
    assert srv.apex.store.integrity_status()["evidence_rows"] == before

    oversized = b"{" + (b" " * ((1 << 20) + 1)) + b"}"
    code, body = request("POST", "/admin/apex/evidence", raw=oversized)
    assert code == 413
    assert "body too large" in body["detail"]
    assert srv.apex.store.integrity_status()["evidence_rows"] == before


def test_apex_http_admin_mutation_requires_auth_before_body_parse(apex_http):
    _, _, request = apex_http
    code, body = request("POST", "/admin/apex/evidence", raw=b'{"broken":', auth=False)
    assert code == 401
    assert "bad admin token" in body["detail"]
