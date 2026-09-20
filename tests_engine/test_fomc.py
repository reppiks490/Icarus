# Grok (xAI) — 2026-09-20. Whole file. FOMC decision days — public Fed calendar, no invented dates.
"""FOMC blackout list: decision (2nd) day of each scheduled meeting."""
from __future__ import annotations

from datetime import date

from icarus_engine.doctor import fomc_coverage, inspect
from icarus_engine.strategy.inputs import Inputs
from icarus_engine.strategy.meta import load_meta


# federalreserve.gov/newsevents/pressreleases/monetary20250905a.htm (2027 tentative)
_FOMC_2027_DECISION = (
    "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-09",
    "2027-07-28", "2027-09-15", "2027-10-27", "2027-12-08",
)


def test_default_inputs_include_2027_decision_days():
    days = {s for s in Inputs().fomc_dates.replace(" ", "").split(",") if s}
    for d in _FOMC_2027_DECISION:
        assert d in days
    assert "2028-01-26" in days  # first 2028 meeting, same Fed release
    # convention: the *decision* day, matching 2026-10-28 not 2026-10-27
    assert "2026-10-28" in days and "2026-10-27" not in days


def test_pine_meta_default_matches_inputs():
    meta = {e["name"]: e for e in load_meta()}
    compact = Inputs().fomc_dates.replace(" ", "").replace("\n", "")
    assert meta["fomc_dates"]["default"].replace(" ", "") == compact


def test_fomc_coverage_and_doctor_warn_inside_90_days(tmp_path):
    last = fomc_coverage()
    assert last == date(2028, 1, 26)
    rep = inspect(str(tmp_path), today=date(2026, 9, 20))
    by_name = {i["name"]: i for i in rep["items"]}
    assert by_name["FOMC decision-day list"]["ok"] is True
    late = inspect(str(tmp_path), today=date(2027, 12, 1))
    hol = {i["name"]: i for i in late["items"]}["FOMC decision-day list"]
    assert hol["ok"] is False and hol["level"] == "warn"
    assert late["ok"] is True
