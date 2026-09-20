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


def test_doctor_holiday_warning_inside_90_days(tmp_path):
    rep = inspect(str(tmp_path), today=date(2027, 11, 1))
    by_name = {i["name"]: i for i in rep["items"]}
    hol = by_name["CME equity holiday table"]
    assert hol["ok"] is False and hol["level"] == "warn"
    assert rep["ok"] is True  # warnings are not failures


def test_doctor_flags_default_secrets(tmp_path):
    (tmp_path / ".env").write_text("WEBHOOK_SECRET=change-me\nADMIN_TOKEN=change-me-too\n")
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
