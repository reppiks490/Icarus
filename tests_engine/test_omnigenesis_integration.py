"""OMNIGENESIS authenticated server integration and dashboard contracts."""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest

from icarus_engine.omnigenesis import ResearchLedger, evaluate_dataset
from icarus_engine.runtime import Journal, Portfolio
from icarus_engine.server import serve


@pytest.fixture
def ic_http(tmp_path):
    port = Portfolio(Journal(":memory:"), str(tmp_path))
    srv = serve(port, 0, token="omnigenesis-test-owner", start=False)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def request(path, auth=True, method="GET", data=None):
        headers = {"Authorization": "Bearer omnigenesis-test-owner"} if auth else {}
        req = urllib.request.Request(base + path, headers=headers,
                                     method=method, data=data)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status, response.read(), response.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers

    yield tmp_path, request
    srv.shutdown()
    srv.server_close()
    thread.join(5)
    port.journal.con.close()


def dataset():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(100):
        t = start + timedelta(minutes=i)
        f = (i * 17) % 19 - 9
        rows.append({
            "record_id": f"id-{i:04d}",
            "asset": "NQ",
            "decision_at": t.isoformat(),
            "observed_at": (t - timedelta(seconds=2)).isoformat(),
            "received_at": (t - timedelta(seconds=1)).isoformat(),
            "label_resolved_at": (t + timedelta(seconds=30)).isoformat(),
            "feature": f,
            "outcome": f >= 1,
            "source_record_id": f"intake:{i}",
        })
    return {"dataset_id": "auth-test-data", "source_commit": "a"*40, "records": rows}


def test_snapshot_is_authenticated_read_only_and_query_free(ic_http):
    root, request = ic_http
    code, raw, _ = request("/api/omnigenesis", auth=False)
    assert code == 401
    assert "admin token" in json.loads(raw)["detail"]
    code, raw, _ = request("/api/omnigenesis?asset=NQ")
    assert code == 400
    code, raw, _ = request("/api/omnigenesis")
    assert code == 200
    snap = json.loads(raw)
    assert snap["study_count"] == 0
    assert snap["authority"]["execution_authorized"] is False
    assert snap["authority"]["production_decision_authorized"] is False
    assert snap["status"] == "RESEARCH_ONLY"
    assert (root/"research"/"omnigenesis.sqlite3").exists()


def test_authenticated_server_reflects_only_derived_ledger(ic_http):
    root, request = ic_http
    report = evaluate_dataset(dataset())
    ResearchLedger(root).append(report)
    code, raw, _ = request("/api/omnigenesis")
    assert code == 200
    snap = json.loads(raw)
    assert snap["study_count"] == 1
    assert snap["recent_studies"][0]["study_id"] == report["study_id"]
    assert "source_record_id" not in raw.decode()
    assert "feature" not in raw.decode()
    assert "label_resolved_at" not in raw.decode()


def test_dashboard_exposes_real_research_tab_and_assets(ic_http):
    _, request = ic_http
    code, html, _ = request("/", auth=False)
    assert code == 200
    assert b'OMNIGENESIS' in html
    assert b'/omnigenesis-ui.js' in html
    assert b'/omnigenesis-ui.css' in html
    code, script, _ = request("/omnigenesis-ui.js", auth=False)
    assert code == 200
    assert b'/api/omnigenesis' in script
    assert b'DECORATIVE MOTION' in script
    code, css, _ = request("/omnigenesis-ui.css", auth=False)
    assert code == 200
    assert b'og-root' in css
    code, _, _ = request("/admin/omnigenesis", method="POST", data=b"{}")
    assert code in (400, 404, 405)
