# Grok (xAI) — 2026-09-20. Whole file. Local plant: drop ingest, supervisor, FileFeed-offline.
"""Plant infrastructure — no network, no broker, no invented ticks."""
from __future__ import annotations

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
    assert "--roll" in svc.argv and "none" in svc.argv
    assert svc.health_url == "http://127.0.0.1:8791/healthz"
    live = default_engine_service(str(tmp_path), "/repo", offline=False)
    assert "--roll" not in live.argv  # do not override GC's registry roll=none


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
    try:
        os.kill(pid, 0)
        still = True
    except OSError:
        still = False
    assert still is False
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
    assert spec.roll == "volume"
    r = port.make_runner(spec)
    assert spec.roll == "none"
    assert r.cfg.base_dir == str(tmp_path)
    assert r.feed is port.feeds["yahoo"]
    assert r.roller is None


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


def test_plant_cli_setup_writes_next_txt(tmp_path, capsys):
    rc = plant_main(["--root", str(tmp_path), "setup"])
    assert rc == 0
    nxt = tmp_path / "NEXT.txt"
    assert nxt.is_file()
    text = nxt.read_text(encoding="utf-8")
    assert "Download chart data" in text and "history" in text
    out = capsys.readouterr().out
    assert "Essential" in out


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
    assert "python.exe does not" in ps1
    assert "start-plant.ps1" in bat
    assert "Essential" in setup and "start-plant.bat" in setup
    assert "Downloads" in setup


def test_ingest_downloads_only_registry_charts(tmp_path):
    from pathlib import Path
    plant = tmp_path / "plant"
    inbox = tmp_path / "dl"
    inbox.mkdir()
    plant.mkdir()
    (inbox / "notes.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (inbox / "NQ1!.csv").write_text(_CSV, encoding="utf-8")
    recs = ingest_downloads(str(plant), dirs=[str(inbox)])
    assert len(recs) == 1 and recs[0]["symbol"] == "NQ"
    dest = plant / "history" / "NQ_1m.csv"
    assert dest.is_file()
    again = ingest_downloads(str(plant), dirs=[str(inbox)])
    assert again == []
    src = Path(__file__).parents[1] / "icarus_plant" / "supervisor.py"
    text = src.read_text(encoding="utf-8")
    assert "CREATE_NEW_PROCESS_GROUP" in text and "start_new_session" in text
