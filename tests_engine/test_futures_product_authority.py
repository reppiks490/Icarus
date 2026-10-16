from datetime import date

import pytest

from icarus_engine.assets import REGISTRY, resolve as resolve_asset
from icarus_futures.contracts import SPECS, parse_continuous, resolve as resolve_contract
from icarus_futures.products import PRODUCTS


EXPECTED_FUTURES_ROOTS = {
    "NQ", "MNQ", "ES", "MES", "YM", "MYM", "RTY", "M2K",
    "GC", "MGC", "SI", "SIL", "PL", "PA", "HG", "MHG",
    "CL", "MCL", "NG", "MNG",
    "6E", "M6E", "6J", "MJY", "6B", "M6B", "6A", "M6A",
    "ZN", "ZB", "BTCF", "MBT",
}

MICRO_PARENTS = {
    "MNQ": "NQ",
    "MES": "ES",
    "MYM": "YM",
    "M2K": "RTY",
    "MGC": "GC",
    "SIL": "SI",
    "MHG": "HG",
    "MCL": "CL",
    "MNG": "NG",
    "M6E": "6E",
    "MJY": "6J",
    "M6B": "6B",
    "M6A": "6A",
    "MBT": "BTCF",
}


def test_product_authority_contains_exact_recovered_futures_universe():
    assert set(PRODUCTS) == EXPECTED_FUTURES_ROOTS


def test_runtime_and_execution_views_match_product_authority():
    runtime_futures = {root for root, spec in REGISTRY.items() if spec.kind == "futures"}
    assert runtime_futures == EXPECTED_FUTURES_ROOTS
    assert set(SPECS) == EXPECTED_FUTURES_ROOTS

    for root, product in PRODUCTS.items():
        runtime = REGISTRY[root]
        execution = SPECS[root]

        assert runtime.symbol == root
        assert runtime.ticker == product.provider_symbol
        assert runtime.tv_symbol == product.tv_symbol
        assert runtime.mintick == pytest.approx(product.tick_size)
        assert runtime.multiplier == pytest.approx(product.point_value)
        assert runtime.exchange == product.exchange
        assert runtime.asset_class == product.asset_class
        assert runtime.micro_of == product.micro_of

        assert execution.root == root
        assert execution.exchange == product.exchange
        assert execution.tick_size == pytest.approx(product.tick_size)
        assert execution.tick_value == pytest.approx(product.tick_value)
        assert execution.point_value == pytest.approx(product.point_value)


def test_every_product_has_self_consistent_tick_economics():
    for product in PRODUCTS.values():
        assert product.tick_value == pytest.approx(product.tick_size * product.point_value)
        assert product.tick_size > 0
        assert product.point_value > 0


def test_micro_products_have_independent_smaller_economics_and_ratio():
    assert {root for root, product in PRODUCTS.items() if product.micro_of} == set(MICRO_PARENTS)

    for micro_root, parent_root in MICRO_PARENTS.items():
        micro = PRODUCTS[micro_root]
        parent = PRODUCTS[parent_root]
        assert micro.micro_of == parent_root
        assert micro.point_value < parent.point_value
        assert SPECS[micro_root].ratio_to_full == pytest.approx(micro.point_value / parent.point_value)


def test_every_product_parses_and_resolves_from_continuous_identity():
    session_date = date(2026, 10, 16)
    for root in sorted(EXPECTED_FUTURES_ROOTS):
        spec, rank = parse_continuous(f"{root}1!")
        assert spec.root == root
        assert rank == 1

        resolved = resolve_contract(f"{root}1!", session_date)
        assert resolved["continuous"] == f"{root}1!"
        assert resolved["contract"].startswith(root)
        assert resolved["contract"] != f"{root}1!"
        assert resolved["roll_date"] > session_date.isoformat()


def test_representative_families_resolve_deterministically_mid_cycle():
    session_date = date(2026, 10, 16)
    expected = {
        "NQ1!": "NQZ26",
        "GC1!": "GCZ26",
        "CL1!": "CLX26",
        "6E1!": "6EZ26",
        "ZN1!": "ZNZ26",
        "BTCF1!": "BTCFX26",
    }
    for continuous, dated in expected.items():
        assert resolve_contract(continuous, session_date)["contract"] == dated


def test_runtime_still_fails_closed_for_dated_and_unknown_futures_styles():
    for symbol in ("CLZ26", "6EZ26", "ZZ1!", "ZZ=F"):
        with pytest.raises(ValueError):
            resolve_asset(symbol)
