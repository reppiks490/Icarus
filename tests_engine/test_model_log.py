# Grok (xAI) — 2026-09-22.
from icarus_engine.model_log import log_action

def test_log_prepends(tmp_path, monkeypatch):
    p = tmp_path / "HANDOFF_LOG.md"
    p.write_text("# Handoff log\n\n## old\n")
    monkeypatch.chdir(tmp_path)
    import icarus_engine.model_log as ml
    monkeypatch.setattr(ml, "LOG", p)
    ml.log_action("Astra", "fitted NQ clock", "holdout=0.51", override=True)
    text = p.read_text()
    assert text.startswith("# Handoff log\n")
    assert "Astra OVERRIDE" in text and "fitted NQ clock" in text
    assert text.index("Astra") < text.index("## old")
