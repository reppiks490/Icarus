from __future__ import annotations

import math
from datetime import date

import pytest

from icarus_engine.assets import REGISTRY, resolve as resolve_asset
from icarus_engine.futures_catalog import FUTURES_PRODUCTS
from icarus_futures.contracts import (
    SPECS,
    STRUCTURAL_SPECS,
    parse_continuous,
    parse_structural_continuous,
    resolve as resolve_contract,
    resolve_candidate,
)


EXPECTED_ROOTS = {
    "NQ", "MNQ", "ES", "MES", "YM", "MYM", "RTY", "M2K",
    "GC", "MGC", "SI", "SIL", "PL", "PA", "HG", "MHG",
    "CL", "MCL", "NG", "MNG",
    "6E", "M6E", "6J", "MJY", "6B", "M6B", "6A", "M6A",
    "ZN", "ZB", "BTCF", "MBT",
}

EXECUTION_QUALIFIED_ROOTS = {
    "NQ", "MNQ", "ES", "MES", "YM", "MYM", "RTY", "M2K",
    "GC", "MGC", "SI", "SIL",
}

MICRO_PAIRS = {
    "MNQ": ("NQ", 0.1), "MES": ("ES", 0.1), "MYM": ("YM", 0.1),
    "M2K": ("RTY", 0.1), "MGC": ("GC", 0.1), "SIL": ("SI", 0.2),
    "MHG": ("HG", 0.1), "MCL": ("CL", 0.1), "MNG": ("NG", 0.1),
    "M6E": ("6E", 0.1), "MJY": ("6J", 0.1), "M6B": ("6B", 0.1),
    "M6A": ("6A", 0.1), "MBT": ("BTCF", 0.02),
}


def test_catalog_covers_exact_recovered_owner_futures_universe():
    assert set(FUTURES_PRODUCTS) == EXPECTED_ROOTS


def test_catalog_is_immutable_authority():
    with pytest.raises(TypeError):
        FUTURES_PRODUCTS["FAKE"] = FUTURES_PRODUCTS["NQ"]


def test_catalog_identities_and_economics_are_self_consistent():
    provider = [p.provider_symbol for p in FUTURES_PRODUCTS.values()]
    tv = [p.tv_symbol for p in FUTURES_PRODUCTS.values()]
    assert len(provider) == len(set(provider))
    assert len(tv) == len(set(tv))
    for root, product in FUTURES_PRODUCTS.items():
        assert product.root == root
        assert product.provider_symbol.endswith("=F")
        assert product.tv_symbol.endswith("1!")
        assert product.execution_root
        assert product.tick_size > 0 and product.point_value > 0
        assert product.tick_value == pytest.approx(product.tick_size * product.point_value)
        assert product.exchange and product.asset_class
        assert product.session in {"rth", "eth"}
        assert product.calendar in {"cme", "cme_crypto"}
    assert FUTURES_PRODUCTS["BTCF"].execution_root == "BTC"


def test_micro_contracts_never_inherit_full_size_economics():
    for micro, (parent, ratio) in MICRO_PAIRS.items():
        child = FUTURES_PRODUCTS[micro]
        full = FUTURES_PRODUCTS[parent]
        assert child.full_root == parent
        assert child.ratio_to_full == pytest.approx(ratio)
        assert child.point_value == pytest.approx(full.point_value * ratio)
        assert child.point_value < full.point_value


def test_all_32_products_are_continuous_runtime_assets_but_execution_is_separate():
    admitted = {root for root, product in FUTURES_PRODUCTS.items() if product.runtime_qualified}
    qualified = {root for root, product in FUTURES_PRODUCTS.items() if product.execution_qualified}
    assert admitted == EXPECTED_ROOTS
    assert qualified == EXECUTION_QUALIFIED_ROOTS
    for root in EXPECTED_ROOTS - EXECUTION_QUALIFIED_ROOTS:
        assert FUTURES_PRODUCTS[root].execution_blocker


def test_runtime_registry_is_derived_from_the_same_32_root_authority():
    runtime_futures = {root for root, spec in REGISTRY.items() if spec.kind == "futures"}
    assert runtime_futures == EXPECTED_ROOTS
    for root, product in FUTURES_PRODUCTS.items():
        spec = REGISTRY[root]
        assert spec.ticker == product.provider_symbol
        assert spec.tv_symbol == product.tv_symbol
        assert spec.mintick == pytest.approx(product.tick_size)
        assert spec.multiplier == pytest.approx(product.point_value)
        assert spec.exchange == product.exchange
        assert spec.asset_class == product.asset_class


def test_all_catalogued_futures_resolve_as_continuous_runtime_assets():
    for root, product in FUTURES_PRODUCTS.items():
        assert resolve_asset(root).symbol == root
        assert resolve_asset(f"{root}1!").symbol == root
        assert resolve_asset(product.provider_symbol).symbol == root


def test_structural_specs_cover_all_32_but_execution_specs_remain_qualified_subset():
    assert set(STRUCTURAL_SPECS) == EXPECTED_ROOTS
    assert set(SPECS) == EXECUTION_QUALIFIED_ROOTS
    for root, spec in STRUCTURAL_SPECS.items():
        product = FUTURES_PRODUCTS[root]
        assert spec.root == root
        assert spec.execution_root == product.execution_root
        assert spec.point_value == pytest.approx(product.point_value)
        assert spec.roll_model == product.roll_model
        assert spec.execution_qualified is product.execution_qualified


def test_all_32_have_static_candidates_without_becoming_execution_routes():
    on = date(2026, 10, 16)
    for root in sorted(EXPECTED_ROOTS):
        spec, rank = parse_structural_continuous(f"{root}1!")
        assert spec.root == root and rank == 1
        first = resolve_candidate(f"{root}1!", on)
        second = resolve_candidate(f"{root}1!", on)
        assert first == second
        assert first["contract"].startswith(spec.execution_root)
        assert first["static_resolution"] is True
        assert first["broker_qualification_required"] is True
        assert first["execution_qualified"] is (root in EXECUTION_QUALIFIED_ROOTS)
        assert first["execution_authorized"] is False
        assert first["live_authorized"] is False


def test_unqualified_structural_candidates_cannot_enter_execution_resolver():
    for root in sorted(EXPECTED_ROOTS - EXECUTION_QUALIFIED_ROOTS):
        with pytest.raises(ValueError, match="execution-qualified|execution qualified|not a continuous futures identity"):
            parse_continuous(f"{root}1!")
        with pytest.raises(ValueError):
            resolve_contract(f"{root}1!", date(2026, 10, 16))


def test_qualified_execution_resolver_stays_available_and_non_authorizing():
    for root in sorted(EXECUTION_QUALIFIED_ROOTS):
        spec, rank = parse_continuous(f"{root}1!")
        assert spec.root == root and rank == 1
        result = resolve_contract(f"{root}1!", date(2026, 10, 16))
        assert result["execution_qualified"] is True
        assert result["execution_authorized"] is False
        assert result["broker_qualification_required"] is True


def test_bitcoin_structural_root_maps_to_real_cme_execution_root_without_routing_authority():
    candidate = resolve_candidate("BTCF1!", date(2026, 10, 16))
    assert candidate["execution_root"] == "BTC"
    assert candidate["contract"] == "BTCV26"
    assert candidate["execution_qualified"] is False
    assert candidate["execution_authorized"] is False


def test_runtime_still_fails_closed_for_dated_and_unknown_futures_styles():
    for dated in ("CLZ26", "6EZ26", "BTCV26"):
        with pytest.raises(ValueError, match="continuous-only"):
            resolve_asset(dated)
    for unknown in ("ZZ1!", "ZZ=F"):
        with pytest.raises(ValueError):
            resolve_asset(unknown)
