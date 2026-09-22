# Grok (xAI) — 2026-09-22. BATS/LSE/BCBA must not become history/NQ_1m.csv.
from pathlib import Path

from icarus_plant.drop import infer_symbol, ingest_drop, is_candidate_export
import icarus_plant.drop as drop_mod
from icarus_plant.layout import ensure

drop_mod._SETTLE_SEC = 0.0

_CSV = (
    "time,open,high,low,close,Volume\n"
    "2026-09-14T13:30:00Z,100,101,99,100.5,4\n"
    "2026-09-14T13:31:00Z,100.5,102,100,101,5\n"
)


def test_candidate_names():
    assert is_candidate_export("BATS_AAPL, 60.csv")
    assert is_candidate_export("LSE_DLY_MAG7, 30S.csv")
    assert is_candidate_export("BCBA_DLY_TSMC, 1.csv")
    assert not is_candidate_export("CME_MINI_NQ1!, 1.csv")
    assert not is_candidate_export("COMEX_GC1!, 60.csv")


def test_infer_symbol_rejects_bats():
    try:
        infer_symbol("BATS_AAPL, 60.csv")
    except ValueError as exc:
        assert "candidate" in str(exc)
        return
    raise AssertionError("BATS must not infer a registry/coinbase symbol")


def test_ingest_drop_moves_bats_to_candidates(tmp_path):
    paths = ensure(str(tmp_path))
    drop = Path(paths["history/drop"])
    (drop / "BATS_AAPL, 60.csv").write_text(_CSV, encoding="utf-8")
    (drop / "CME_MINI_NQ1!, 1.csv").write_text(_CSV, encoding="utf-8")
    recs = ingest_drop(str(tmp_path))
    nq = [r for r in recs if r.get("symbol") == "NQ"]
    cand = [r for r in recs if r.get("skipped") == "candidate_export"]
    assert len(nq) == 1
    assert len(cand) == 1
    assert (tmp_path / "history" / "NQ_1m.csv").is_file()
    assert not (tmp_path / "history" / "AAPL_1m.csv").exists()
    assert (drop / "candidates" / "BATS_AAPL, 60.csv").is_file()
