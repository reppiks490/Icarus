from __future__ import annotations

import math

import pytest

from icarus_engine.futures_catalog import FUTURES_PRODUCTS


EXPECTED_ROOTS = {
    "NQ", "MNQ", "ES", "MES", "YM", "MYM", "RTY", "M2K",
    "GC", "MGC", "SI", "SIL", "PL", "PA", "HG", "MHG",
    "CL", "MCL", "NG", "MNG",
    "6E", "M6E", "6J", "MJY", "6B", "M6B", "6A", "M6A",
    "ZN", "ZB", "BTCF", "MBT",
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
