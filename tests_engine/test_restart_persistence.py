"""Synthetic process recovery, not production-launcher or owner-PC certification."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from http.client import HTTPConnection
from zoneinfo import ZoneInfo

SOURCE = Path(__file__).resolve().parents[1]
IDS = ("cc1", "cc2", "cc3", "cc4")
TOKEN = "synthetic-restart-test"


def _child(state_arg, phase, ready_arg, receipt_arg):
    state = Path(state_arg).resolve()
    violations = []

    def audit(event, args):
        if event in {"socket.connect", "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr"}:
            address = args[1] if event == "socket.connect" else args[0]
            host = address[0] if isinstance(address, tuple) else address
            if host not in {"127.0.0.1", "::1", "localhost"}:
                violations.append(event)
                raise PermissionError("restart test forbids external network")
        if event == "open" and isinstance(args[0], (str, bytes)):
            path = Path(os.fsdecode(args[0])).resolve()
            credential = path.name.startswith(".env") or path.name == "credentials" or path.suffix in {".key", ".pem"}
            writing = args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
            if credential or (writing and not path.is_relative_to(state)):
                violations.append("credential_or_outside_write")
                raise PermissionError("restart test forbids credentials and outside writes")

    sys.addaudithook(audit)
    from icarus_engine.assets import parse_spec
    from icarus_engine.runtime import Journal, Portfolio
    from icarus_engine.server import serve
    import icarus_engine.runtime as runtime

    assert Path(runtime.__file__).resolve().is_relative_to(SOURCE)
    if phase == "1":
        history = state / "history"
        history.mkdir()
        # A covered ordinary session, independent of the test host's holiday/date.
        start = int(datetime(2026, 1, 6, 9, 30, tzinfo=ZoneInfo("America/New_York")).timestamp())
        (history / "NQ_1m.csv").write_text("ts,open,high,low,close,volume\n" + "".join(
            f"{start+i*60},100,100.25,99.75,100,100\n" for i in range(240)), encoding="utf-8")
    parent = Portfolio(Journal(str(state / "main.sqlite3")), str(state), preset=None, poll_sec=.1)
    parent.add_asset(parse_spec("NQ"))
    server = thread = None
    try:
        server = serve(parent, 0, token=TOKEN, start=False)
        assert server.background_workers_enabled is False
        if phase == "1":
            # Narrow only our fresh synthetic fixture; later edits use authenticated HTTP.
            for key, profile in server.command_centers.profiles.items():
                profile["assets"] = ["NQ"]
                (state / "command_centers" / f"{key}.json").write_text(json.dumps(profile), encoding="utf-8")
        parent.start()
        server.command_centers.start()
        deadline = time.monotonic() + 30
        portfolios = [parent, *server.command_centers.portfolios.values()]
        while not all(r.warm for p in portfolios for r in p.runner_list()):
            assert time.monotonic() < deadline, "file warm-up did not complete"
            time.sleep(.05)
        if phase == "1":
            now = int(time.time())
            for i, key in enumerate(IDS, 1):
                journal = server.command_centers.portfolios[key].journal
                with journal._lock:
                    journal.con.execute(
                        "INSERT INTO trades(symbol,entry_id,direction,qty,entry_price,entry_ts,exit_price,exit_ts,"
                        "exit_comment,profit,live,piece,run_id,lot_id,entry_qty,bars) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        ("NQ", "synthetic-"+key, 1, 1, 100., now-60, 100.+i, now-1,
                         "synthetic recovery fixture", 20.*i, 1, 0, journal.run_id, i, 1, 1))
                    journal.con.execute(
                        "INSERT INTO fills(symbol,ts,entry_id,side,qty,price,kind,comment,profit,position_after,live,run_id) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        ("NQ", now-1, "synthetic-"+key, "sell", 1, 100.+i, "exit", "synthetic fixture", 20.*i, 0, 1, journal.run_id))
                    journal.con.commit()
                journal.publish_dashboard_views()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        Path(ready_arg).write_text(json.dumps({"port": server.server_port}), encoding="utf-8")
        assert sys.stdin.readline().strip() == "STOP", "missing cooperative shutdown"
    finally:
        if thread is not None:
            server.shutdown()
            thread.join(10)
        if server is not None:
            server.server_close()
        parent.stop()
        parent.journal.close()
        closed = server is not None and all(p.journal._closed for p in server.command_centers.portfolios.values())
        Path(receipt_arg).write_text(json.dumps({"violations": violations, "journals_closed": closed,
                                               "thread_stopped": thread is None or not thread.is_alive()}), encoding="utf-8")


@contextmanager
def _running(state, phase):
    ready, receipt = state / f"ready-{phase}.json", state / f"receipt-{phase}.json"
    environment = {key: value for key, value in os.environ.items()
                   if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "LANG", "LC_ALL"}}
    environment.update(PYTHONPATH=str(SOURCE), PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1",
                       ICARUS_HOME=str(state), ICARUS_FEED="file", TEMP=str(state), TMP=str(state), TMPDIR=str(state))
    child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), str(state), str(phase),
                              str(ready), str(receipt)], cwd=SOURCE, env=environment,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        deadline = time.monotonic() + 45
        while not ready.exists():
            assert child.poll() is None, "recovery child exited before readiness"
            assert time.monotonic() < deadline, "recovery child readiness timed out"
            time.sleep(.05)
        yield json.loads(ready.read_text(encoding="utf-8"))["port"]
    finally:
        try:
            output, _ = child.communicate("STOP\n", timeout=20)
        except subprocess.TimeoutExpired:
            child.kill()  # Only our own child, for bounded failed-test cleanup.
            output, _ = child.communicate(timeout=5)
            raise AssertionError("cooperative child shutdown timed out: " + output)
        assert child.returncode == 0, output
        assert json.loads(receipt.read_text(encoding="utf-8")) == {
            "violations": [], "journals_closed": True, "thread_stopped": True}


def _request(port, path, body=None, token=TOKEN, context=None):
    connection = HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
        if context:
            headers["X-Icarus-Workspace"] = context
        connection.request("GET" if body is None else "POST", path,
                           json.dumps(body) if body is not None else None, headers)
        response = connection.getresponse()
        raw = response.read()
        data = json.loads(raw) if response.getheader("Content-Type", "").startswith("application/json") else raw.decode()
        return response.status, data
    finally:
        connection.close()


def _persisted(state):
    result = {}
    for key in IDS:
        folder = state / "command_centers"
        connection = sqlite3.connect(str(folder / f"{key}.sqlite3"))
        try:
            assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            trades = connection.execute("SELECT * FROM trades ORDER BY id").fetchall()
            fills = connection.execute("SELECT * FROM fills ORDER BY id").fetchall()
            assert len(trades) == len(fills) == 1
            result[key] = ((folder / f"{key}.json").read_bytes(), trades, fills)
        finally:
            connection.close()
    return result


def test_file_workspace_revisions_and_journals_survive_process_restart(tmp_path):
    expected = {}
    for phase in (1, 2):
        with _running(tmp_path, phase) as port:
            assert _request(port, "/healthz")[0] == 200
            for i, key in enumerate(IDS, 1):
                path = "/api/command-centers/" + key
                code, data = _request(port, path)
                assert code == 200 and data["profile"]["id"] == key
                assert data["runtime_feed_mode"] == "file" and data["profile"]["runtime_available"] is True
                assert data["execution_authorized"] is False and data["profile"]["pnl"]["realized_pnl"] == 20.*i
                if phase == 1:
                    revision = data["profile"]["config_revision"]
                    code, answer = _request(port, "/admin/command-centers/"+key, {
                        "expected_revision": revision, "chart": {"timeframe": str(5*i), "chart_type": "real"},
                        "inputs": {"tp1_pts": 8.+i}})
                    assert code == 200, answer
                    expected[key] = revision + 1
                code, data = _request(port, path)
                profile = data["profile"]
                assert code == 200 and profile["config_revision"] == expected[key]
                assert profile["chart"]["timeframe"] == str(5*i) and profile["chart"]["chart_type"] == "real"
                assert profile["inputs"].get("tp1_pts") == 8.+i
                for resource in ("status", "performance", "inputs/NQ"):
                    code, selected = _request(port, path+"/"+resource)
                    assert code == 200 and selected["workspace_id"] == key
                    assert selected["config_revision"] == expected[key] and selected["execution_authorized"] is False
                    if resource == "performance":
                        assert selected["realized_pnl"] == 20.*i and selected["closed_pieces"] == 1
                code, page = _request(port, "/dashboards/"+key)
                assert code == 200 and '"id": "'+key+'"' in page
            assert _request(port, "/admin/command-centers/cc1", {"inputs": {"tp1_pts": 999}}, token="invalid")[0] == 401
            assert _request(port, "/api/command-centers/cc1/status", context="cc2")[0] == 409
        current = _persisted(tmp_path)
        if phase == 1:
            before = current
        else:
            assert current == before, "saved config bytes or independent journal rows changed on restart"


if __name__ == "__main__":
    _child(*sys.argv[1:])
