"""OMNIGENESIS offline observatory reflects only real derived records."""
from __future__ import annotations

import pytest

from icarus_engine.omnigenesis import ResearchLedger
from icarus_engine.omnigenesis.simulation import replay_book, synthetic_scenario
from icarus_engine.omnigenesis.observatory import render_observatory


def test_offline_dashboard_uses_real_stored_artifacts(tmp_path):
    ledger=ResearchLedger(tmp_path)
    report=replay_book(synthetic_scenario(52, 50))
    artifact=ledger.append_artifact("synthetic_book", report)
    output=tmp_path/"research"/"observatory.html"
    exported=render_observatory(ledger.snapshot(), output)
    assert exported==output
    html=output.read_text(encoding="utf-8")
    assert "OFFLINE SNAPSHOT — NO LIVE DATA" in html
    assert artifact in html
    assert "synthetic_book" in html
    assert "animated" not in html.lower() or "offline" in html.lower()
    assert "model learning" in html
    assert "__SNAPSHOT__" not in html


def test_malformed_snapshot_rejected_without_file_output(tmp_path):
    ledger=ResearchLedger(tmp_path)
    payload=ledger.snapshot()
    payload["authority"]["execution_authorized"]=True
    target=tmp_path/"bad.html"
    with pytest.raises(ValueError,match="research-only"):
        render_observatory(payload,target)
    assert not target.exists()


def test_script_escape_preserves_data_as_nonexecutable_json(tmp_path):
    ledger=ResearchLedger(tmp_path)
    snap=ledger.snapshot()
    # Crafted dataset ID tests the offline JSON script escape, not a valid
    # upstream research report. HTML must not create executable script tags.
    snap["recent_studies"]=[{
        "study_id":"a"*64,
        "dataset_id":"</script><script>alert(1)</script>",
        "asset":"NQ","status":"REJECTED",
        "holdout_brier_improvement":0,
    }]
    path=render_observatory(snap,tmp_path/"safe.html")
    html=path.read_text(encoding="utf-8")
    assert "</script><script>alert" not in html
    assert "\\u003c/script" in html
    assert html.count('<script type="application/json" id="snapshot-data">')==1
