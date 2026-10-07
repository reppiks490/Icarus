from __future__ import annotations

from http.client import HTTPConnection
import json
from pathlib import Path
import threading

from icarus_engine.runtime import Journal, Portfolio
from icarus_engine.server import serve


def request(port, method, path, headers=None):
    conn=HTTPConnection("127.0.0.1",port,timeout=5)
    try:
        conn.request(method,path,headers=headers or {})
        response=conn.getresponse()
        return response.status,response.read()
    finally:
        conn.close()


def test_economic_event_endpoint_is_authenticated_and_read_only(tmp_path):
    journal=Journal(":memory:")
    portfolio=Portfolio(journal,str(tmp_path))
    srv=serve(portfolio,0,"test-token",start=False)
    srv.event_clock_sync.status=lambda: {
        "schema_version":"icarus-economic-event-sync-v1",
        "status":"degraded",
        "source_health":"degraded",
        "sources":{"BLS":{"status":"degraded","transport":"official_snapshot","rows":25}},
        "events":[{"source":"BLS","event_key":"cpi","title":"CPI","event_date":"2026-10-14",
                   "scheduled_at_utc":"2026-10-14T12:30:00+00:00","time_known":True}],
        "execution_authorized":False,
        "production_decision_authorized":False,
    }
    thread=threading.Thread(target=srv.serve_forever,daemon=True)
    thread.start()
    try:
        assert request(srv.server_port,"GET","/api/economic-events")[0]==401
        code,raw=request(
            srv.server_port,"GET","/api/economic-events",
            {"Authorization":"Bearer test-token"},
        )
        assert code==200
        data=json.loads(raw)
        assert data["status"]=="degraded"
        assert data["sources"]["BLS"]["transport"]=="official_snapshot"
        assert data["execution_authorized"] is False
        assert data["production_decision_authorized"] is False
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(5)
        journal.con.close()


def test_financial_data_ui_binds_verified_event_clock_endpoint():
    script=(Path(__file__).parents[1]/"icarus_engine"/"sources-ui.js").read_text(encoding="utf-8")
    assert "Economic event clock" in script
    assert "/api/economic-events" in script
    assert "renderEventClock" in script
    assert "s.transport" in script
    assert "snapshot_as_of" in script
    assert "exact release time not asserted" in script
    assert "date-only schedule" in script


def test_server_registers_event_clock_in_sync_lifecycle():
    text=(Path(__file__).parents[1]/"icarus_engine"/"server.py").read_text(encoding="utf-8")
    assert '"event_clock": event_clock_sync' in text
    assert 'ControlAction("sync.event_clock"' in text
    assert "event_clock_sync.start()" in text
    assert text.count("event_clock_sync.close()") >= 2
    assert "srv.event_clock_sync = event_clock_sync" in text
