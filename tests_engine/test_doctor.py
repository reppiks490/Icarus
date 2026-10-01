# Grok (xAI) — 2026-09-20. Whole file. Offline doctor CLI.
"""Offline doctor — no network."""
from __future__ import annotations

from datetime import date

from icarus_engine.cli import main as engine_main
from icarus_engine.doctor import inspect


def test_doctor_warns_without_history_and_does_not_fail(tmp_path):
    (tmp_path / "history").mkdir()
    (tmp_path / "pine").mkdir()
    (tmp_path / "pine" / "ALERT_TEMPLATE.json").write_text("{}")
    rep = inspect(str(tmp_path), today=date(2026, 9, 20))
    assert rep["ok"] is True
    assert rep["fails"] == 0
    assert rep["warns"] >= 1
    by_name = {i["name"]: i for i in rep["items"]}
    assert by_name["TradingView chart dumps in history/"]["ok"] is False
    assert by_name["TradingView chart dumps in history/"]["level"] == "warn"
    assert by_name["CME equity holiday table"]["ok"] is True
    assert by_name["CME equity holiday table"]["level"] == "ok"
    assert by_name["TradingView alert template"]["ok"] is True
    assert by_name["continuous-only futures registry"]["ok"] is True
    assert by_name["continuous-only futures registry"]["level"] == "ok"


def test_doctor_holiday_warning_inside_90_days(tmp_path):
    rep = inspect(str(tmp_path), today=date(2027, 11, 1))
    by_name = {i["name"]: i for i in rep["items"]}
    hol = by_name["CME equity holiday table"]
    assert hol["ok"] is False and hol["level"] == "warn"
    assert rep["ok"] is True  # warnings are not failures


def test_doctor_flags_replace_me_secrets(tmp_path):
    (tmp_path / ".env").write_text("WEBHOOK_SECRET=replace-me\nADMIN_TOKEN=replace-me-too\n")
    rep = inspect(str(tmp_path), today=date(2026, 9, 20))
    assert rep["ok"] is False and rep["fails"] >= 2
    names = {i["name"] for i in rep["items"] if not i["ok"] and i["level"] == "fail"}
    assert "WEBHOOK_SECRET" in names and "ADMIN_TOKEN" in names


def test_doctor_cli_json(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    rc = engine_main(["doctor", "--json"])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"ok": true' in out or '"ok":true' in out
    assert "Yahoo" in out


def test_doctor_databento_requires_key_without_network(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_FEED", "databento")
    monkeypatch.delenv("DATABENTO_API_KEY", raising=False)
    rep = inspect(str(tmp_path), today=date(2026, 9, 20))
    by_name = {i["name"]: i for i in rep["items"]}
    item = by_name["Databento adapter prerequisites"]
    assert item["ok"] is False and item["level"] == "fail"
    assert "DATABENTO_API_KEY=missing" in item["detail"]


def test_doctor_databento_accepts_key_from_plant_env_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_FEED", "databento")
    monkeypatch.delenv("DATABENTO_API_KEY", raising=False)
    monkeypatch.delenv("DATABENTO_DATASET", raising=False)
    monkeypatch.delenv("DATABENTO_ROLL_RULE", raising=False)
    monkeypatch.setattr("icarus_engine.doctor.importlib.util.find_spec", lambda name: object() if name == "databento" else None)
    (tmp_path / ".env").write_text(
        "WEBHOOK_SECRET=local-secret\n"
        "ADMIN_TOKEN=local-admin\n"
        "DATABENTO_API_KEY=db-local-key\n"
        "DATABENTO_DATASET=GLBX.MDP3\n"
        "DATABENTO_ROLL_RULE=v\n",
        encoding="utf-8",
    )
    rep = inspect(str(tmp_path), today=date(2026, 9, 20))
    item = {i["name"]: i for i in rep["items"]}["Databento adapter prerequisites"]
    assert item["ok"] is True
    assert "DATABENTO_API_KEY=set" in item["detail"]
    assert "dataset=GLBX.MDP3" in item["detail"] and "roll_rule=v" in item["detail"]


def test_doctor_databento_rejects_bad_dataset_or_roll_rule(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_FEED", "databento")
    monkeypatch.delenv("DATABENTO_API_KEY", raising=False)
    monkeypatch.delenv("DATABENTO_DATASET", raising=False)
    monkeypatch.delenv("DATABENTO_ROLL_RULE", raising=False)
    monkeypatch.setattr("icarus_engine.doctor.importlib.util.find_spec", lambda name: object() if name == "databento" else None)
    (tmp_path / ".env").write_text(
        "WEBHOOK_SECRET=local-secret\n"
        "ADMIN_TOKEN=local-admin\n"
        "DATABENTO_API_KEY=db-local-key\n"
        "DATABENTO_DATASET=BAD.DATASET\n"
        "DATABENTO_ROLL_RULE=x\n",
        encoding="utf-8",
    )
    rep = inspect(str(tmp_path), today=date(2026, 9, 20))
    item = {i["name"]: i for i in rep["items"]}["Databento adapter prerequisites"]
    assert item["ok"] is False and item["level"] == "fail"
    assert "BAD.DATASET" in item["detail"] and "roll_rule=x" in item["detail"]
