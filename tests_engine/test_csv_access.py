# Grok (xAI) — 2026-09-22.
from icarus_engine.csv_access import list_csvs

def test_lists_exec_and_candidate(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_CSV_ROOT", str(tmp_path))
    (tmp_path / "CME_MINI_NQ1!, 1.csv").write_text("time,close\n1,1\n")
    (tmp_path / "BATS_AAPL, 60.csv").write_text("time,close\n1,1\n")
    all_rows = list_csvs("all", explicit=str(tmp_path))
    kinds = {r["kind"] for r in all_rows}
    assert "execution" in kinds and "candidate" in kinds
    cands = list_csvs("candidates", asset="AAPL", explicit=str(tmp_path))
    assert len(cands) == 1 and cands[0]["kind"] == "candidate"
