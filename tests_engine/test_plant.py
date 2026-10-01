# Grok (xAI) — 2026-09-20. Whole file. Local plant: drop ingest, supervisor, FileFeed-offline.
"""Plant infrastructure — no network, no broker, no invented ticks."""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from icarus_engine.assets import parse_spec
from icarus_engine.feeds.bars import HistoryHub, parse_ohlcv_csv
from icarus_engine.runtime import Journal, Portfolio
from icarus_plant.cli import main as plant_main
from icarus_plant.downloads import ingest_downloads
from icarus_plant.drop import infer_symbol, ingest_drop, ingest_file
import icarus_plant.drop as drop_mod

drop_mod._SETTLE_SEC = 0.0  # tests write then ingest immediately
from icarus_plant.layout import ensure, plant_root
from icarus_plant.supervisor import (
    Plant,
    Service,
    default_engine_service,
    health_ok,
)

NY = ZoneInfo("America/New_York")
ET_0930 = int(datetime(2026, 9, 14, 9, 30, tzinfo=NY).timestamp())

_CSV = (
    "time,open,high,low,close,Volume\n"
    "2026-09-14T13:30:00Z,24700,24701,24699,24700.5,4\n"
    "2026-09-14T13:31:00Z,24700.5,24702,24700,24701,5\n"
)


def test_infer_symbol_strips_tv_prefix_and_tf():
    assert infer_symbol("CME_MINI_NQ1!_1m.csv") == "NQ"
    assert infer_symbol("NQ1!.csv") == "NQ"
    assert infer_symbol("NQ_20m.csv") == "NQ"
    assert infer_symbol("ES_1m.csv") == "ES"
    # TradingView Supercharts default download names
    assert infer_symbol("CME_MINI_NQ1!, 1.csv") == "NQ"
    assert infer_symbol("NQ1!, 1.csv") == "NQ"
    assert infer_symbol("CBOT_MINI_YM1!, 1.csv") == "YM"
    assert infer_symbol("CME_MINI_MNQ1!, 1.csv") == "MNQ"
    assert infer_symbol("CME_MINI_MES1!, 1.csv") == "MES"
    assert infer_symbol("CBOT_MINI_MYM1!, 1.csv") == "MYM"
    assert infer_symbol("CME_MINI_RTY1!, 1.csv") == "RTY"
    assert infer_symbol("COMEX_GC1!, 1.csv") == "GC"
    assert infer_symbol("COMEX_MGC1!, 1.csv") == "MGC"
    assert infer_symbol("COMEX_SIL1!, 1.csv") == "SIL"
    assert infer_symbol("CME_MINI_NQ1!, 1 (1).csv") == "NQ"
    assert infer_symbol("NQ1!, 60.csv") == "NQ"
    assert infer_symbol("CME_MINI_ES1!, 1D.csv") == "ES"


def test_layout_ensure_and_plant_root(tmp_path, monkeypatch):
    monkeypatch.delenv("ICARUS_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    paths = ensure()
    assert paths["root"] == os.path.abspath(str(tmp_path))
    for rel in ("history", "history/drop", "history/drop/done", "presets", "pine", "logs", "run"):
        assert os.path.isdir(os.path.join(tmp_path, rel))
    monkeypatch.setenv("ICARUS_HOME", str(tmp_path / "home"))
    assert plant_root().endswith(os.path.join("home")) or os.path.samefile(plant_root(), tmp_path / "home")


def test_ingest_drop_writes_canonical_and_moves_src(tmp_path):
    paths = ensure(str(tmp_path))
    src = os.path.join(paths["history/drop"], "CME_MINI_NQ1!_1m.csv")
    with open(src, "w", encoding="utf-8") as fh:
        fh.write(_CSV)
    recs = ingest_drop(str(tmp_path))
    assert len(recs) == 1
    assert recs[0]["symbol"] == "NQ" and recs[0]["minutes"] == 1 and recs[0]["bars"] == 2
    dest = os.path.join(tmp_path, "history", "NQ_1m.csv")
    assert os.path.isfile(dest)
    bars = parse_ohlcv_csv(open(dest, encoding="utf-8").read())
    assert len(bars) == 2 and bars[0].ts == ET_0930
    assert not os.path.isfile(src)
    assert os.path.isfile(os.path.join(paths["history/drop/done"], "CME_MINI_NQ1!_1m.csv"))


def test_ingest_file_es(tmp_path):
    src = tmp_path / "ES.csv"
    src.write_text(_CSV, encoding="utf-8")
    rec = ingest_file(str(src), root=str(tmp_path), symbol="ES")
    assert rec["symbol"] == "ES" and rec["bars"] == 2
    assert os.path.isfile(os.path.join(tmp_path, "history", "ES_1m.csv"))


def test_default_engine_service_offline_argv(tmp_path):
    svc = default_engine_service(str(tmp_path), "/repo", offline=True, assets="NQ")
    assert svc.env["ICARUS_FEED"] == "file"
    assert svc.env["ICARUS_HOME"] == os.path.abspath(str(tmp_path))
    assert "--feed" in svc.argv and "file" in svc.argv
    assert "--roll" not in svc.argv
    assert svc.health_url == "http://127.0.0.1:8791/healthz"
    live = default_engine_service(str(tmp_path), "/repo", offline=False)
    assert "--roll" not in live.argv  # continuous futures require no expiry/roll CLI override
    db = default_engine_service(str(tmp_path), "/repo", feed="databento")
    assert db.env["ICARUS_FEED"] == "databento"
    assert db.argv[db.argv.index("--feed") + 1] == "databento"


def test_supervisor_spawn_and_stop(tmp_path):
    plant = Plant(str(tmp_path), repo=str(tmp_path))
    svc = Service(
        name="dummy",
        argv=[sys.executable, "-c", "import time; time.sleep(30)"],
        health_url="",
        cwd=str(tmp_path),
        env={},
        pidfile=os.path.join(str(tmp_path), "run", "dummy.pid"),
    )
    plant.add(svc)
    plant.spawn(svc)
    assert svc.popen is not None and svc.popen.poll() is None
    pid = svc.popen.pid
    assert os.path.isfile(svc.pidfile)
    plant.stop()
    time.sleep(0.2)
    assert svc.popen is None
    from icarus_engine.process_identity import identity
    assert identity(pid) is False
    assert not os.path.isfile(svc.pidfile)


def test_health_ok_loopback(tmp_path):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import threading

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200 if self.path == "/healthz" else 404)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *a):
            return

    httpd = HTTPServer(("127.0.0.1", 0), H)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        assert health_ok(f"http://127.0.0.1:{port}/healthz") is True
        assert health_ok(f"http://127.0.0.1:{port}/nope") is False
        assert health_ok("http://127.0.0.1:1/healthz") is False
    finally:
        httpd.shutdown()


def test_plant_cli_init(tmp_path, capsys):
    rc = plant_main(["--root", str(tmp_path), "init"])
    assert rc == 0
    assert (tmp_path / "history" / "drop").is_dir()
    assert (tmp_path / "run").is_dir()
    out = capsys.readouterr().out
    assert "plant root" in out
    rc = plant_main(["--root", str(tmp_path), "ingest-drop"])
    assert rc == 0


def test_plant_cli_status_json_when_down(tmp_path, capsys):
    plant_main(["--root", str(tmp_path), "init"])
    rc = plant_main(["--root", str(tmp_path), "status", "--json"])
    assert rc == 1
    out = capsys.readouterr().out
    assert '"ok": false' in out or '"ok":false' in out


def test_portfolio_file_mode_uses_historyhub(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_FEED", "file")
    hist = tmp_path / "history"
    hist.mkdir()
    (hist / "NQ_1m.csv").write_text(
        "ts,open,high,low,close,volume\n"
        f"{ET_0930},24700,24701,24699,24700.5,4\n",
        encoding="utf-8",
    )
    port = Portfolio(Journal(":memory:"), str(tmp_path), preset=None)
    assert port.feed_mode == "file"
    assert isinstance(port.feeds["yahoo"], HistoryHub)
    spec = parse_spec("NQ")
    assert spec.roll == "continuous"
    r = port.make_runner(spec)
    assert spec.roll == "continuous"
    assert r.live_ticker == "NQ=F"
    assert r.cfg.base_dir == str(tmp_path)
    assert r.feed is port.feeds["yahoo"]
    assert not hasattr(r, "roller")


def test_file_mode_rewarm_when_csv_arrives_after_start(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_FEED", "file")
    (tmp_path / "history").mkdir()
    port = Portfolio(Journal(":memory:"), str(tmp_path), preset=None)
    r = port.make_runner(parse_spec("NQ"))
    r.warmup()
    assert r._file_waiting is True
    (tmp_path / "history" / "NQ_1m.csv").write_text(
        "ts,open,high,low,close,volume\n"
        f"{ET_0930},24700,24701,24699,24700.5,4\n"
        f"{ET_0930 + 60},24700.5,24702,24700,24701,5\n",
        encoding="utf-8",
    )
    r.poll()
    assert r._file_waiting is False
    assert r.last_sub_ts in (ET_0930, ET_0930 + 60)
    assert len(r.subbars) >= 1


def test_ingest_drop_merges_and_unique_done(tmp_path):
    paths = ensure(str(tmp_path))
    src = os.path.join(paths["history/drop"], "NQ.csv")
    with open(src, "w", encoding="utf-8") as fh:
        fh.write(_CSV)
    ingest_drop(str(tmp_path))
    dest = os.path.join(tmp_path, "history", "NQ_1m.csv")
    assert len(parse_ohlcv_csv(open(dest, encoding="utf-8").read())) == 2
    src2 = os.path.join(paths["history/drop"], "NQ.csv")
    extra = (
        "time,open,high,low,close,Volume\n"
        "2026-09-14T13:32:00Z,24701,24703,24700,24702,6\n"
    )
    with open(src2, "w", encoding="utf-8") as fh:
        fh.write(extra)
    recs = ingest_drop(str(tmp_path))
    assert recs[0]["bars"] == 3 and recs[0]["added"] == 1
    done = paths["history/drop/done"]
    names = sorted(os.listdir(done))
    assert "NQ.csv" in names and any(n.startswith("NQ.") for n in names)


def test_plant_cli_setup_accepts_root_after_subcommand(tmp_path, capsys):
    rc = plant_main(["setup", "--root", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / "NEXT.txt").is_file()
    out = capsys.readouterr().out
    assert str(tmp_path) in out or "Download chart data" in out


def test_plant_cli_setup_writes_next_txt(tmp_path, capsys):
    rc = plant_main(["--root", str(tmp_path), "setup"])
    assert rc == 0
    nxt = tmp_path / "NEXT.txt"
    assert nxt.is_file()
    text = nxt.read_text(encoding="utf-8")
    assert "Download chart data" in text and "history" in text
    out = capsys.readouterr().out
    assert "Plus" in out or "plus" in out.lower() or "Yahoo" in out


def test_start_plant_scripts_are_dummy_proof():
    from pathlib import Path
    root = Path(__file__).parents[1]
    ps1 = (root / "start-plant.ps1").read_text(encoding="utf-8")
    bat = (root / "start-plant.bat").read_text(encoding="utf-8")
    sh = (root / "start-plant.sh").read_text(encoding="utf-8")
    setup = (root / "SETUP.md").read_text(encoding="utf-8")
    assert "Grok (xAI)" in ps1 and "Grok (xAI)" in bat and "Grok (xAI)" in sh
    assert "icarus_plant" in ps1 and "--offline" in ps1
    assert "UsePyLauncher" in ps1
    assert "py.exe" in ps1
    assert "-3" in ps1
    assert "python.exe" in ps1
    assert "CME_MINI_NQ1!, 1.csv" in ps1
    assert "start-plant.ps1" in bat
    assert "Plus" in setup and "start-plant.bat" in setup
    paid = (root / "PAID_NEXT.md").read_text(encoding="utf-8")
    assert "Alpaca" in paid and "TradersPost" in paid and "PickMyTrade" in paid
    cmds = (root / "COMMANDS.md").read_text(encoding="utf-8")
    assert "127.0.0.1:8791" in cmds and "paper-export" in cmds and "start --assets NQ" in cmds
    assert "--offline" in cmds
    yahoo = (root / "start-yahoo.ps1").read_text(encoding="utf-8")
    assert "icarus_plant start --assets NQ" in yahoo
    assert "start --assets NQ --offline" not in yahoo
    assert "Downloads" in setup
    assert "CME_MINI_NQ1!, 1.csv" in setup
    bg = (root / "start-engine-background.ps1").read_text(encoding="utf-8")
    assert "py.exe" in bg
    assert "engine-background.pid" in bg
    assert "Stop-Process" in bg
    sh_bg = (root / "start-engine-background.sh").read_text(encoding="utf-8")
    assert sh_bg.count("set -euo pipefail") == 1
    assert "killing orphan" in sh_bg
    assert "run/engine-background.pid" in sh_bg
    src = (root / "icarus_plant" / "supervisor.py").read_text(encoding="utf-8")
    assert "os.kill(pid, 0)" not in src
    assert "process_identity" in src


def test_ingest_drop_quarantines_bad_and_keeps_going(tmp_path):
    drop = tmp_path / "history" / "drop"
    drop.mkdir(parents=True)
    (drop / "junk.csv").write_text("not,a,chart\n1,2,3\n", encoding="utf-8")
    (drop / "CME_MINI_NQ1!, 1.csv").write_text(_CSV, encoding="utf-8")
    recs = ingest_drop(str(tmp_path))
    goods = [r for r in recs if r.get("symbol") == "NQ"]
    bads = [r for r in recs if r.get("bad")]
    assert len(goods) == 1
    assert (tmp_path / "history" / "NQ_1m.csv").is_file()
    assert len(bads) == 1
    assert (tmp_path / "history" / "drop" / "bad" / "junk.csv").is_file()


def test_alive_never_calls_os_kill():
    import inspect
    from icarus_plant.supervisor import _alive
    src = inspect.getsource(_alive)
    assert "os.kill" not in src
    assert "identity" in src


def test_ingest_downloads_only_registry_charts(tmp_path):
    plant = tmp_path / "plant"
    inbox = tmp_path / "dl"
    inbox.mkdir()
    plant.mkdir()
    (inbox / "notes.csv").write_text("a,b\n1,2,n\n", encoding="utf-8")
    (inbox / "CME_MINI_NQ1!, 1.csv").write_text(_CSV, encoding="utf-8")
    recs = ingest_downloads(str(plant), dirs=[str(inbox)])
    assert len(recs) == 1 and recs[0]["symbol"] == "NQ"
    dest = plant / "history" / "NQ_1m.csv"
    assert dest.is_file()
    again = ingest_downloads(str(plant), dirs=[str(inbox)])
    assert again == []


def test_plant_cli_setup_survives_cp1252_stdout(tmp_path):
    """CLI setup must not crash when the inherited stdout encoding is cp1252."""
    import subprocess
    from pathlib import Path

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "cp1252"
    proc = subprocess.run(
        [sys.executable, "-m", "icarus_plant", "--root", str(tmp_path), "setup"],
        cwd=str(Path(__file__).parents[1]),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    stderr = proc.stderr.decode("utf-8", errors="replace")
    assert proc.returncode == 0, stderr


def test_plant_status_is_healthy_without_optional_bridge(tmp_path, capsys):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import threading

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200 if self.path == "/healthz" else 404)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            return

    paths = ensure(str(tmp_path))
    (tmp_path / "run" / "engine.pid").write_text(str(os.getpid()), encoding="ascii")
    httpd = HTTPServer(("127.0.0.1", 0), H)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        rc = plant_main([
            "--root", str(tmp_path), "status",
            "--engine-port", str(httpd.server_port), "--json",
        ])
        assert rc == 0
        payload = capsys.readouterr().out
        assert '"ok": true' in payload.lower()
        assert '"name": "engine"' in payload
        assert '"name": "bridge"' not in payload
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(5)


def test_supervisor_spawn_closes_parent_log_handle(tmp_path, monkeypatch):
    import icarus_plant.supervisor as supervisor

    captured = {}

    class FakePopen:
        pid = 424242

        def __init__(self, argv, **kwargs):
            captured["stdout"] = kwargs["stdout"]

        def poll(self):
            return None

    monkeypatch.setattr(supervisor.subprocess, "Popen", FakePopen)
    plant = Plant(str(tmp_path), repo=str(tmp_path))
    svc = Service(
        name="dummy",
        argv=[sys.executable, "-c", "pass"],
        health_url="",
        cwd=str(tmp_path),
        pidfile=os.path.join(str(tmp_path), "run", "dummy.pid"),
    )
    plant.spawn(svc)
    assert captured["stdout"].closed is True
    assert os.path.isfile(svc.pidfile)


def test_write_status_is_atomic_and_valid_json(tmp_path, monkeypatch):
    import icarus_plant.supervisor as supervisor

    ensure(str(tmp_path))
    calls = []
    real_replace = supervisor.os.replace

    def tracked_replace(src, dst):
        calls.append((src, dst))
        return real_replace(src, dst)

    monkeypatch.setattr(supervisor.os, "replace", tracked_replace)
    payload = {"ok": True, "services": [{"name": "engine", "alive": True}]}
    supervisor.write_status(str(tmp_path), payload)

    path = tmp_path / "run" / "status.json"
    assert json.loads(path.read_text(encoding="utf-8")) == payload
    assert calls and calls[-1][1] == str(path)
    assert not (tmp_path / "run" / "status.json.tmp").exists()


def test_start_does_not_silently_ignore_requested_bridge(tmp_path, capsys):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import threading

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200 if self.path == "/healthz" else 404)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            return

    ensure(str(tmp_path))
    (tmp_path / "run" / "plant.pid").write_text(str(os.getpid()), encoding="ascii")
    httpd = HTTPServer(("127.0.0.1", 0), H)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        rc = plant_main([
            "--root", str(tmp_path), "start", "--bridge",
            "--engine-port", str(httpd.server_port), "--bridge-port", "1",
            "--no-browser",
        ])
        assert rc == 1
        out = capsys.readouterr().out.lower()
        assert "--bridge was requested" in out
        assert "stop the plant" in out
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(5)


def test_stop_returns_failure_when_supervisor_remains_alive(tmp_path, monkeypatch, capsys):
    import icarus_plant.cli as plant_cli

    ensure(str(tmp_path))
    (tmp_path / "run" / "plant.pid").write_text("424242", encoding="ascii")
    monkeypatch.setattr(plant_cli, "_alive", lambda pid: True)
    monkeypatch.setattr(plant_cli, "_kill_pid", lambda pid: None)
    monkeypatch.setattr(plant_cli.time, "sleep", lambda seconds: None)

    rc = plant_main(["--root", str(tmp_path), "stop"])
    assert rc == 1
    err = capsys.readouterr().err.lower()
    assert "still alive" in err
    assert "refusing to claim success" in err


def test_start_rejects_healthy_engine_without_live_supervisor(tmp_path, capsys):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import threading

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200 if self.path == "/healthz" else 404)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            return

    ensure(str(tmp_path))
    httpd = HTTPServer(("127.0.0.1", 0), H)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        rc = plant_main([
            "--root", str(tmp_path), "start",
            "--engine-port", str(httpd.server_port), "--no-browser",
        ])
        assert rc == 1
        out = capsys.readouterr().out.lower()
        assert "no live plant supervisor owns it" in out
        assert "refusing to claim the plant is started" in out
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(5)


def test_plant_loads_databento_key_from_local_env_without_overriding_process_env(tmp_path, monkeypatch):
    import icarus_plant.cli as plant_cli
    (tmp_path / ".env").write_text(
        "DATABENTO_API_KEY=db-from-file\nDATABENTO_DATASET=GLBX.MDP3\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DATABENTO_API_KEY", raising=False)
    monkeypatch.delenv("DATABENTO_DATASET", raising=False)
    plant_cli._load_root_env(str(tmp_path))
    assert os.environ["DATABENTO_API_KEY"] == "db-from-file"
    assert os.environ["DATABENTO_DATASET"] == "GLBX.MDP3"

    monkeypatch.setenv("DATABENTO_API_KEY", "db-from-process")
    plant_cli._load_root_env(str(tmp_path))
    assert os.environ["DATABENTO_API_KEY"] == "db-from-process"
