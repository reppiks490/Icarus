from __future__ import annotations

import math
from datetime import date

import pytest

from icarus_engine.assets import REGISTRY, resolve as resolve_asset
from icarus_engine.futures_catalog import FUTURES_PRODUCTS
from icarus_futures.contracts import SPECS, parse_continuous, resolve as resolve_contract


EXPECTED_ROOTS = {
    "NQ", "MNQ", "ES", "MES", "YM", "MYM", "RTY", "M2K",
    "GC", "MGC", "SI", "SIL", "PL", "PA", "HG", "MHG",
    "CL", "MCL", "NG", "MNG",
    "6E", "M6E", "6J", "MJY", "6B", "M6B", "6A", "M6A",
    "ZN", "ZB", "BTCF", "MBT",
}

EXPECTED_RUNTIME_ROOTS = {
    "NQ", "MNQ", "ES", "MES", "YM", "MYM", "RTY", "M2K",
    "GC", "MGC", "SI", "SIL", "PL", "PA", "BTCF", "MBT",
}

MICRO_PAIRS = {
    "MNQ": ("NQ", 0.1),
    "MES": ("ES", 0.1),
    "MYM": ("YM", 0.1),
    "M2K": ("RTY", 0.1),
    "MGC": ("GC", 0.1),
    "SIL": ("SI", 0.2),
    "MHG": ("HG", 0.1),
    "MCL": ("CL", 0.1),
    "MNG": ("NG", 0.1),
    "M6E": ("6E", 0.1),
    "MJY": ("6J", 0.1),
    "M6B": ("6B", 0.1),
    "M6A": ("6A", 0.1),
    "MBT": ("BTCF", 0.02),
}


def test_catalog_covers_exact_recovered_owner_futures_universe():
    assert set(FUTURES_PRODUCTS) == EXPECTED_ROOTS


def test_catalog_identities_are_continuous_unique_and_fail_closed_by_construction():
    provider = [p.provider_symbol for p in FUTURES_PRODUCTS.values()]
    tv = [p.tv_symbol for p in FUTURES_PRODUCTS.values()]
    assert len(provider) == len(set(provider))
    assert len(tv) == len(set(tv))
    for root, product in FUTURES_PRODUCTS.items():
        assert product.root == root
        assert product.provider_symbol.endswith("=F")
        assert product.tv_symbol.endswith("1!")
        assert product.tick_size > 0
        assert product.point_value > 0
        assert product.exchange
        assert product.asset_class
        assert product.session in {"rth", "eth"}
        assert product.calendar in {"cme", "cme_crypto"}


def test_catalog_economics_are_self_consistent():
    for product in FUTURES_PRODUCTS.values():
        assert product.tick_value > 0
        assert math.isclose(
            product.tick_value,
            product.tick_size * product.point_value,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ), product.root


def test_micro_contracts_never_inherit_full_size_economics():
    for micro, (parent, ratio) in MICRO_PAIRS.items():
        child = FUTURES_PRODUCTS[micro]
        full = FUTURES_PRODUCTS[parent]
        assert child.full_root == parent
        assert child.ratio_to_full == pytest.approx(ratio)
        assert child.point_value == pytest.approx(full.point_value * ratio)
        assert child.point_value < full.point_value


def test_execution_qualification_is_explicit_not_inferred_from_registration():
    for product in FUTURES_PRODUCTS.values():
        assert isinstance(product.execution_qualified, bool)
        if product.execution_qualified:
            assert product.execution_blocker is None
            assert product.cycle
            assert product.roll_model
        else:
            assert product.execution_blocker


def test_runtime_admission_is_separate_from_dated_contract_execution_qualification():
    admitted = {root for root, product in FUTURES_PRODUCTS.items() if product.runtime_qualified}
    assert admitted == EXPECTED_RUNTIME_ROOTS
    for product in FUTURES_PRODUCTS.values():
        assert isinstance(product.runtime_qualified, bool)


def test_runtime_registry_is_derived_from_the_same_32_root_authority():
    runtime_futures = {root for root, spec in REGISTRY.items() if spec.kind == "futures"}
    assert runtime_futures == EXPECTED_ROOTS
    for root, product in FUTURES_PRODUCTS.items():
        spec = REGISTRY[root]
        assert spec.ticker == product.provider_symbol
        assert spec.tv_symbol == product.tv_symbol
        assert spec.mintick == pytest.approx(product.tick_size)
        assert spec.multiplier == pytest.approx(product.point_value)
        assert spec.calendar == product.calendar
        assert spec.session == product.session
        assert spec.group == product.group
        assert spec.exchange == product.exchange
        assert spec.asset_class == product.asset_class
        assert spec.micro_of == (product.full_root if product.full_root != product.root else None)


def test_catalogued_but_unqualified_futures_are_discoverable_and_runtime_fail_closed():
    for root, product in FUTURES_PRODUCTS.items():
        assert REGISTRY[root].symbol == root
        if product.runtime_qualified:
            assert resolve_asset(f"{root}1!").symbol == root
            assert resolve_asset(product.provider_symbol).symbol == root
        else:
            with pytest.raises(ValueError, match="unsupported continuous futures"):
                resolve_asset(f"{root}1!")
            with pytest.raises(ValueError, match="unsupported continuous futures"):
                resolve_asset(product.provider_symbol)
    for dated in ("HGZ26", "MCLF27", "NGH27", "6EM26", "M6BZ27", "ZNH27", "ZBZ27"):
        with pytest.raises(ValueError, match="continuous-only"):
            resolve_asset(dated)


def test_execution_specs_are_derived_only_from_explicitly_qualified_products():
    qualified = {root for root, product in FUTURES_PRODUCTS.items() if product.execution_qualified}
    assert set(SPECS) == qualified
    for root, spec in SPECS.items():
        product = FUTURES_PRODUCTS[root]
        assert spec.root == root
        assert spec.exchange == product.exchange
        assert spec.tick_size == pytest.approx(product.tick_size)
        assert spec.tick_value == pytest.approx(product.tick_value)
        assert spec.point_value == pytest.approx(product.point_value)
        assert spec.full_root == product.full_root
        assert spec.ratio_to_full == pytest.approx(product.ratio_to_full)
        assert spec.cycle == product.cycle
        assert spec.roll_model == product.roll_model


def test_execution_qualified_products_resolve_deterministically_and_unqualified_fail_closed():
    for root, product in FUTURES_PRODUCTS.items():
        symbol = f"{root}1!"
        if product.execution_qualified:
            spec, nth = parse_continuous(symbol)
            assert spec.root == root and nth == 1
            first = resolve_contract(symbol, date(2026, 10, 16))
            second = resolve_contract(symbol, date(2026, 10, 16))
            assert first == second
            assert first["contract"].startswith(root)
            assert first["roll_date"] <= first["last_date"]
        else:
            with pytest.raises(ValueError, match="not a continuous futures identity"):
                parse_continuous(symbol)
