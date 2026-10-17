from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from icarus_engine.futures_catalog import FUTURES_PRODUCTS
from icarus_futures.contracts import (
    SPECS,
    STRUCTURAL_SPECS,
    contract_dates,
    parse_continuous,
    parse_structural_continuous,
    resolve,
    resolve_candidate,
)


EXECUTION_QUALIFIED_ROOTS = {
    "NQ", "MNQ", "ES", "MES", "YM", "MYM", "RTY", "M2K",
    "GC", "MGC", "SI", "SIL",
}


@pytest.mark.parametrize(
    ("root", "year", "month", "expected_last"),
    [
        ("6E", 2026, 12, date(2026, 12, 14)),
        ("M6E", 2026, 12, date(2026, 12, 14)),
        ("6J", 2026, 12, date(2026, 12, 14)),
        ("MJY", 2026, 12, date(2026, 12, 14)),
        ("6B", 2026, 12, date(2026, 12, 14)),
        ("M6B", 2026, 12, date(2026, 12, 14)),
        ("6A", 2026, 12, date(2026, 12, 14)),
        ("M6A", 2026, 12, date(2026, 12, 14)),
        ("HG", 2026, 10, date(2026, 10, 28)),
        ("MHG", 2026, 11, date(2026, 10, 28)),
        ("PL", 2026, 10, date(2026, 10, 28)),
        ("PA", 2026, 12, date(2026, 12, 29)),
        ("NG", 2026, 11, date(2026, 10, 28)),
        ("MNG", 2026, 11, date(2026, 10, 27)),
        ("CL", 2026, 11, date(2026, 10, 20)),
        ("MCL", 2026, 11, date(2026, 10, 19)),
        ("ZN", 2026, 12, date(2026, 12, 21)),
        ("ZB", 2026, 12, date(2026, 12, 21)),
        ("BTCF", 2026, 10, date(2026, 10, 30)),
        ("MBT", 2026, 10, date(2026, 10, 30)),
    ],
)
def test_product_specific_static_candidate_dates(root, year, month, expected_last):
    spec = STRUCTURAL_SPECS[root]
    last, roll = contract_dates(spec, year, month)
    assert last == expected_last
    assert roll <= last


def test_all_32_roots_have_structural_specs_but_only_qualified_subset_routes():
    assert set(STRUCTURAL_SPECS) == set(FUTURES_PRODUCTS)
    assert set(SPECS) == EXECUTION_QUALIFIED_ROOTS
    for root in FUTURES_PRODUCTS:
        spec, rank = parse_structural_continuous(f"{root}1!")
        assert spec.root == root and rank == 1
        assert spec.execution_qualified is (root in EXECUTION_QUALIFIED_ROOTS)


def test_unqualified_structural_specs_fail_closed_at_execution_parser():
    for root in set(FUTURES_PRODUCTS) - EXECUTION_QUALIFIED_ROOTS:
        with pytest.raises(ValueError):
            parse_continuous(f"{root}1!")
        with pytest.raises(ValueError):
            resolve(f"{root}1!", date(2026, 10, 16))


def test_canonical_bitcoin_root_maps_to_real_cme_candidate_without_execution_authority():
    front = resolve_candidate("BTCF1!", date(2026, 10, 16))
    micro = resolve_candidate("MBT1!", date(2026, 10, 16))
    assert front["contract"] == "BTCV26"
    assert micro["contract"] == "MBTV26"
    assert front["execution_qualified"] is False
    assert micro["execution_qualified"] is False
    assert front["execution_authorized"] is False


def test_representative_structural_candidates_are_deterministic_on_current_audit_date():
    expected = {
        "6E": "6EZ26", "HG": "HGV26", "MHG": "MHGX26",
        "PL": "PLV26", "PA": "PAZ26", "NG": "NGX26", "MNG": "MNGX26",
        "CL": "CLZ26", "MCL": "MCLZ26", "ZN": "ZNZ26", "ZB": "ZBZ26",
        "BTCF": "BTCV26", "MBT": "MBTV26",
    }
    for root, code in expected.items():
        first = resolve_candidate(f"{root}1!", date(2026, 10, 16))
        second = resolve_candidate(f"{root}1!", date(2026, 10, 16))
        assert first == second
        assert first["contract"] == code
        assert first["roll_date"] <= first["last_date"]
        assert first["execution_authorized"] is False


@pytest.mark.parametrize("root", ["ES", "CL", "BTCF"])
def test_static_resolution_fails_closed_beyond_supported_calendar_years(root):
    with pytest.raises(ValueError, match="calendar coverage is limited to 2026-2028"):
        resolve_candidate(f"{root}1!", date(2029, 1, 2))


def test_business_day_helpers_fail_closed_outside_calendar_coverage():
    from icarus_futures.contracts import _is_bday, _is_london_bday

    with pytest.raises(ValueError, match="calendar coverage is limited to 2026-2028"):
        _is_bday(date(2029, 1, 1))
    with pytest.raises(ValueError, match="calendar coverage is limited to 2026-2028"):
        _is_london_bday(date(2029, 1, 1))


@pytest.mark.parametrize("gold,quantity", [("GCZ26", 1), ("MGCZ26", 10)])
@pytest.mark.parametrize("silver,position", [("SIZ26", 1), ("SILZ26", 5)])
def test_full_and_micro_metals_share_the_existing_portfolio_risk_budget(gold, quantity, silver, position):
    from icarus_futures.orders import Intent
    from icarus_futures.risk import PortfolioState, RiskGovernor

    state = PortfolioState(
        positions={silver: position},
        marks={silver: 40.0, gold: 4000.0},
        data_age_s={gold: 0.0},
    )
    intent = Intent("risk-regression", gold, "BUY", quantity, "MARKET")
    now = datetime(2026, 10, 17, tzinfo=timezone.utc)
    decision = RiskGovernor().evaluate(intent, state, now)

    # $200k silver + $400k gold breaches the existing $500k metals budget.
    assert decision.allowed is False
    assert decision.codes == ["CLUSTER_LIMIT"]

    # Exactly $500k is still permitted: the correction must preserve the limit.
    state.marks[gold] = 3000.0
    at_limit = RiskGovernor().evaluate(intent, state, now)
    assert at_limit.allowed is True
    assert at_limit.codes == []


@pytest.mark.parametrize("root", ["GC", "MGC", "SI", "SIL"])
def test_metals_keep_legacy_contract_kind_independently_of_catalog_class(root):
    assert FUTURES_PRODUCTS[root].asset_class == "metal"
    assert SPECS[root].kind == "metals"
