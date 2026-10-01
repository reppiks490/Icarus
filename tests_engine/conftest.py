# Claude (Opus 5.5) — 2026-09-27. Tests never inherit the machine's plant root. With ICARUS_HOME set (the plant
# supervisor sets it; so may the owner's shell), CLI tests wrote into the real history/ instead of tmp_path.
import pytest


@pytest.fixture(autouse=True)
def _no_real_plant_root(monkeypatch):
    monkeypatch.delenv("ICARUS_HOME", raising=False)
