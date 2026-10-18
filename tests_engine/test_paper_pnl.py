"""Independent accounting vectors: four ledgers, known sums and missing evidence."""
from copy import deepcopy
from fractions import Fraction
import math

import pytest

from icarus_engine.paper_pnl import validate_paper_pnl


def ledgers():
    return [dict(id=f"cc{i}", currency="USD", runtime_available=True,
                 snapshot_ts=1000, realized_pnl=value, open_pnl=mark,
                 open_positions=1, oldest_open_mark_ts=995)
            for i, value, mark in [(1, 100, 5), (2, -40, -2), (3, 20, 0), (4, 7, 3)]]


def aggregate(rows=None, **kwargs):
    return validate_paper_pnl(ledgers() if rows is None else rows, as_of_ts=1000, **kwargs)["aggregate"]


def test_four_independent_ledgers_sum_known_money_and_preserve_provenance():
    result = aggregate()
    assert result["realized_pnl"] == 87
    assert result["open_pnl"] == 6
    assert result["total_pnl"] == 93
    assert result["currency"] == "USD"
    assert result["accounting_complete"] is True
    assert result["fees_status"] == "NOT_INDEPENDENTLY_VERIFIED"
    assert result["broker_reconciliation_status"] == "UNRECONCILED_SIMULATION"
    assert "live=1" in result["basis"]


@pytest.mark.parametrize("field,value", [
    ("realized_pnl", True), ("realized_pnl", "100"), ("realized_pnl", math.nan),
    ("realized_pnl", math.inf), ("realized_pnl", -math.inf),
    ("realized_pnl", 10**1000), ("realized_pnl", 2**53),
    ("realized_pnl", None), ("open_pnl", False), ("open_pnl", "5"),
    ("open_pnl", math.nan), ("open_pnl", 10**1000),
])
def test_invalid_money_never_becomes_zero_or_numeric_coercion(field, value):
    rows = ledgers()
    rows[0][field] = value
    result = aggregate(rows)
    assert result["total_pnl"] is None
    assert result["accounting_complete"] is False
    if field == "open_pnl":
        assert result["realized_pnl"] == 87
    else:
        assert result["realized_pnl"] is None


@pytest.mark.parametrize("mutation", [
    lambda rows: rows.pop(),
    lambda rows: rows.append(dict(rows[0])),
    lambda rows: rows[0].update(id="cc2"),
    lambda rows: rows[0].update(id="cc5"),
    lambda rows: rows[0].update(runtime_available=False),
    lambda rows: rows[0].update(runtime_available="true"),
    lambda rows: rows[0].update(currency="EUR"),
    lambda rows: rows[0].update(currency="usd"),
    lambda rows: rows[0].pop("currency"),
    lambda rows: rows.__setitem__(0, None),
])
def test_incomplete_or_mixed_accounts_cannot_report_a_combined_total(mutation):
    rows = ledgers()
    mutation(rows)
    result = aggregate(rows)
    assert result["total_pnl"] is None
    assert result["realized_pnl"] is None
    assert result["accounting_complete"] is False


@pytest.mark.parametrize("field,value", [
    ("snapshot_ts", 909), ("snapshot_ts", 1001), ("snapshot_ts", True),
    ("snapshot_ts", "1000"), ("snapshot_ts", 1000.0),
    ("oldest_open_mark_ts", 909), ("oldest_open_mark_ts", 1001),
    ("oldest_open_mark_ts", None), ("oldest_open_mark_ts", True),
    ("oldest_open_mark_ts", "995"),
    ("open_positions", True), ("open_positions", -1), ("open_positions", "1"),
])
def test_stale_future_or_invalid_evidence_suppresses_total(field, value):
    rows = ledgers()
    rows[0][field] = value
    result = aggregate(rows)
    assert result["total_pnl"] is None
    if field != "snapshot_ts":
        assert result["realized_pnl"] == 87


def test_exact_age_limit_is_accepted_and_mark_cannot_postdate_snapshot():
    rows = ledgers()
    rows[0].update(snapshot_ts=910, oldest_open_mark_ts=910)
    assert aggregate(rows)["total_pnl"] == 93
    rows[0]["oldest_open_mark_ts"] = 911
    assert aggregate(rows)["total_pnl"] is None


def test_known_realized_is_available_while_open_marks_are_unknown():
    rows = ledgers()
    rows[2].update(oldest_open_mark_ts=None)
    result = aggregate(rows)
    assert result["realized_pnl"] == 87
    assert result["open_pnl"] is None
    assert result["total_pnl"] is None


def test_flat_ledger_zero_needs_no_mark_but_nonzero_open_is_inconsistent():
    rows = ledgers()
    rows[0].update(open_positions=0, open_pnl=0, oldest_open_mark_ts=None)
    assert aggregate(rows)["total_pnl"] == 88
    rows[0]["open_pnl"] = 5
    assert aggregate(rows)["total_pnl"] is None


def test_missing_runtime_does_not_turn_into_four_zero_ledgers():
    rows = ledgers()
    rows[0].update(runtime_available=False, realized_pnl=0, open_pnl=0, open_positions=0)
    result = validate_paper_pnl(rows, as_of_ts=1000)
    assert result["profiles"][0]["realized_pnl"] is None
    assert result["aggregate"]["total_pnl"] is None


def test_input_is_immutable_and_numbers_are_normalized_to_safe_floats():
    rows = ledgers()
    rows[0]["realized_pnl"] = Fraction(200, 2)
    before = deepcopy(rows)
    result = validate_paper_pnl(rows, as_of_ts=1000)
    assert rows == before
    assert type(result["profiles"][0]["realized_pnl"]) is float
    assert result["paper_only"] is True
    assert result["execution_authorized"] is False


def test_reordering_valid_ids_does_not_change_aggregate():
    assert aggregate(list(reversed(ledgers()))) == aggregate()


def test_unsafe_sum_cannot_report_complete_valuation():
    rows = ledgers()
    for row in rows:
        row["realized_pnl"] = 2**52
    assert aggregate(rows)["realized_pnl"] is None
    assert aggregate(rows)["total_pnl"] is None


def test_opposite_unsafe_ledger_totals_cannot_cancel_into_authority():
    rows = ledgers()
    rows[0].update(realized_pnl=2**53 - 1, open_pnl=2**53 - 1)
    rows[1].update(realized_pnl=-(2**53 - 1), open_pnl=-(2**53 - 1))
    result = validate_paper_pnl(rows, as_of_ts=1000)
    assert result["profiles"][0]["accounting_complete"] is False
    assert result["profiles"][1]["accounting_complete"] is False
    assert result["aggregate"]["total_pnl"] is None
    assert result["aggregate"]["accounting_complete"] is False


@pytest.mark.parametrize("kwargs", [
    {"as_of_ts": True}, {"as_of_ts": "1000"}, {"as_of_ts": -1},
    {"as_of_ts": 10**1000}, {"as_of_ts": 1000, "max_mark_age_seconds": -1},
    {"as_of_ts": 1000, "max_snapshot_age_seconds": False},
])
def test_invalid_global_clock_contract_raises(kwargs):
    with pytest.raises(ValueError):
        validate_paper_pnl(ledgers(), **kwargs)
