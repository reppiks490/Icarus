from __future__ import annotations

from datetime import date

import pytest

from icarus_engine.futures_catalog import FUTURES_PRODUCTS
from icarus_futures.contracts import SPECS, contract_dates, parse_continuous, resolve


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
def test_product_specific_last_trade_dates(root, year, month, expected_last):
    spec = SPECS[root]
    last, roll = contract_dates(spec, year, month)
    assert last == expected_last
    assert roll <= last


def test_all_32_catalog_roots_have_structural_execution_specs():
    assert set(SPECS) == set(FUTURES_PRODUCTS)
    for root in FUTURES_PRODUCTS:
        spec, rank = parse_continuous(f"{root}1!")
        assert spec.root == root
        assert rank == 1


def test_canonical_bitcoin_root_maps_to_real_cme_contract_code():
    front = resolve("BTCF1!", date(2026, 10, 16))
    micro = resolve("MBT1!", date(2026, 10, 16))
    assert front["contract"] == "BTCV26"
    assert micro["contract"] == "MBTV26"


def test_representative_front_contracts_are_deterministic_on_current_audit_date():
    expected = {
        "6E": "6EZ26",
        "HG": "HGV26",
        "MHG": "MHGX26",
        "PL": "PLV26",
        "PA": "PAZ26",
        "NG": "NGX26",
        "MNG": "MNGX26",
        "CL": "CLZ26",
        "MCL": "MCLZ26",
        "ZN": "ZNZ26",
        "ZB": "ZBZ26",
        "BTCF": "BTCV26",
        "MBT": "MBTV26",
    }
    for root, code in expected.items():
        first = resolve(f"{root}1!", date(2026, 10, 16))
        second = resolve(f"{root}1!", date(2026, 10, 16))
        assert first == second
        assert first["contract"] == code
        assert first["roll_date"] <= first["last_date"]
