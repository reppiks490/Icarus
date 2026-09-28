# Claude (Opus 5.5) — 2026-09-27. The product name lives in icarus_engine/brand.py; every visible place reads it
# or is kept in step with it, and one command renames it.
import shutil
import threading
from http.client import HTTPConnection
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
NAME = "DIVINE PROVIDENCE: THE HEART OF ICARUS"


def test_the_product_is_named_divine_providence():
    from icarus_engine import brand
    assert brand.NAME == NAME
    assert brand.STRATEGY == "THE PULSE OF ICARUS"          # the Pine strategy keeps its own name


@pytest.mark.parametrize("page", ["icarus_engine/dashboard.html", "icarus_bridge/dashboard.html"])
def test_dashboards_carry_the_token_not_a_hard_coded_name(page):
    from icarus_engine import brand
    raw = (REPO / page).read_bytes()
    assert raw.count(brand.TOKEN) >= 2 and b"ICARUS ENGINE" not in raw and b"ICARUS Bridge" not in raw
    shown = brand.render(raw).decode("utf-8")
    assert f"<title>{NAME}" in shown and brand.TOKEN.decode() not in shown


def test_engine_server_serves_the_branded_dashboard(tmp_path):
    from icarus_engine.runtime import Journal, Portfolio
    from icarus_engine.server import serve
    journal = Journal(":memory:")
    srv = serve(Portfolio(journal, str(tmp_path)), 0, "test-token", start=False)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        conn = HTTPConnection("127.0.0.1", srv.server_port, timeout=5)
        conn.request("GET", "/")
        body = conn.getresponse().read().decode("utf-8")
        conn.close()
    finally:
        srv.shutdown(); srv.server_close(); thread.join(5); journal.con.close()
    assert f"<title>{NAME}</title>" in body and "@BRAND@" not in body


@pytest.mark.parametrize("module", ["icarus_engine.cli", "icarus_plant.cli", "icarus_engine.trainers.__main__"])
def test_cli_help_names_the_product(module, capsys):
    import importlib
    with pytest.raises(SystemExit) as done:
        importlib.import_module(module).main(["--help"])
    assert done.value.code == 0 and NAME in capsys.readouterr().out


def test_static_text_stays_in_step_with_the_constant():
    from icarus_engine import brand
    assert brand.check(REPO) == []


def test_one_command_renames_everything(tmp_path):
    from icarus_engine import brand
    for rel in brand.STATIC_FILES:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / rel, tmp_path / rel)
    changed = brand.rename(tmp_path, "HELIOS: THE WINGS OF ICARUS")
    assert sorted(changed) == sorted(brand.STATIC_FILES)
    assert brand.check(tmp_path, "HELIOS: THE WINGS OF ICARUS") == []
    assert NAME not in (tmp_path / "icarus_engine/brand.py").read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        brand.rename(tmp_path, 'bad "quote"')
