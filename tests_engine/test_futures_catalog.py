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


def test_catalog_is_immutable_authority():
    with pytest.raises(TypeError):
        FUTURES_PRODUCTS["FAKE"] = FUTURES_PRODUCTS["NQ"]


def test_catalog_identities_are_continuous_unique_and_fail_closed_by_construction():
    provider = [p.provider_symbol for p in FUTURES_PRODUCTS.values()]
    tv = [p.tv_symbol for p in FUTURES_PRODUCTS.values()]
    assert len(provider) == len(set(provider))
    assert len(tv) == len(set(tv))
    for root, product in FUTURES_PRODUCTS.items():
        assert product.root == root
        assert product.provider_symbol.endswith("=F")
        assert product.tv_symbol.endswith("1!")
        assert product.execution_root
        assert product.tick_size > 0
        assert product.point_value > 0
        assert product.exchange
        assert product.asset_class
        assert product.session in {"rth", "eth"}
        assert product.calendar in {"cme", "cme_crypto"}

    assert FUTURES_PRODUCTS["BTCF"].execution_root == "BTC"
    assert FUTURES_PRODUCTS["MBT"].execution_root == "MBT"


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


def test_all_32_products_are_runtime_admitted_but_provider_health_remains_separate():
    admitted = {root for root, product in FUTURES_PRODUCTS.items() if product.runtime_qualified}
    assert admitted == EXPECTED_ROOTS
    for product in FUTURES_PRODUCTS.values():
        assert isinstance(product.runtime_qualified, bool)


def test_static_dated_contract_qualification_is_explicit_for_every_root():
    qualified = {root for root, product in FUTURES_PRODUCTS.items() if product.execution_qualified}
    assert qualified == EXPECTED_ROOTS
    for product in FUTURES_PRODUCTS.values():
        assert product.execution_blocker is None
        assert product.cycle
        assert product.roll_model


def test_static_fx_resolution_uses_quarterly_benchmark_cycle():
    # Standard FX also lists serial months, but the continuous benchmark and all
    # micro contracts use the March quarterly cycle for deterministic static routing.
    for root in ("6E", "M6E", "6J", "MJY", "6B", "M6B", "6A", "M6A"):
        assert FUTURES_PRODUCTS[root].cycle == "HMUZ"


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


def test_all_catalogued_futures_resolve_as_continuous_runtime_assets():
    for root, product in FUTURES_PRODUCTS.items():
        assert REGISTRY[root].symbol == root
        assert resolve_asset(root).symbol == root
        assert resolve_asset(f"{root}1!").symbol == root
        assert resolve_asset(product.provider_symbol).symbol == root

    for dated in ("HGZ26", "MCLF27", "NGH27", "6EM26", "M6BZ27", "ZNH27", "ZBZ27"):
        with pytest.raises(ValueError, match="continuous-only"):
            resolve_asset(dated)


def test_execution_specs_are_derived_from_all_statically_qualified_products():
    assert set(SPECS) == EXPECTED_ROOTS
    for root, spec in SPECS.items():
        product = FUTURES_PRODUCTS[root]
        assert spec.root == root
        assert spec.execution_root == product.execution_root
        assert spec.exchange == product.exchange
        assert spec.tick_size == pytest.approx(product.tick_size)
        assert spec.tick_value == pytest.approx(product.tick_value)
        assert spec.point_value == pytest.approx(product.point_value)
        assert spec.full_root == product.full_root
        assert spec.ratio_to_full == pytest.approx(product.ratio_to_full)
        assert spec.cycle == product.cycle
        assert spec.roll_model == product.roll_model


def test_all_products_have_deterministic_static_dated_candidates_without_authorizing_execution():
    on = date(2026, 10, 16)
    for root in sorted(EXPECTED_ROOTS):
        symbol = f"{root}1!"
        spec, nth = parse_continuous(symbol)
        assert spec.root == root and nth == 1
        first = resolve_contract(symbol, on)
        second = resolve_contract(symbol, on)
        assert first == second
        assert first["contract"].startswith(spec.execution_root)
        assert first["roll_date"] <= first["last_date"]
        assert first["static_resolution"] is True
        assert first["broker_qualification_required"] is True
        assert first["execution_authorized"] is False


def test_representative_product_families_resolve_expected_current_candidates():
    on = date(2026, 10, 16)
    expected = {
        "NQ1!": "NQZ26",
        "GC1!": "GCZ26",
        "PL1!": "PLV26",
        "HG1!": "HGV26",
        "MHG1!": "MHGX26",
        "CL1!": "CLZ26",
        "MCL1!": "MCLZ26",
        "NG1!": "NGX26",
        "MNG1!": "MNGX26",
        "6E1!": "6EZ26",
        "M6E1!": "M6EZ26",
        "ZN1!": "ZNZ26",
        "ZB1!": "ZBZ26",
        "BTCF1!": "BTCV26",
        "MBT1!": "MBTV26",
    }
    for continuous, dated in expected.items():
        assert resolve_contract(continuous, on)["contract"] == dated


def test_wti_conservative_roll_boundary_advances_before_expiration():
    assert resolve_contract("CL1!", date(2026, 10, 15))["contract"] == "CLX26"
    after_cutoff = resolve_contract("CL1!", date(2026, 10, 16))
    assert after_cutoff["contract"] == "CLZ26"
    assert after_cutoff["roll_date"] > "2026-10-16"


def test_runtime_and_execution_layers_fail_closed_for_bad_or_dated_identities():
    for dated in ("CLZ26", "6EZ26", "BTCV26"):
        with pytest.raises(ValueError, match="continuous-only"):
            resolve_asset(dated)
    for unknown in ("ZZ1!", "ZZ=F"):
        with pytest.raises(ValueError):
            resolve_asset(unknown)
    with pytest.raises(ValueError, match="not a continuous futures identity"):
        parse_continuous("CLZ26")
