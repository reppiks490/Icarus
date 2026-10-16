"""Canonical futures product authority for ICARUS.

This module is the single static authority for the 32 owner-directed futures
roots.  Runtime assets, Databento identities, dated-contract candidates,
capability indexes, Brain evidence, and asset command centers derive from this
catalog instead of copying contract economics into independent tables.

Two qualification layers are intentionally distinct:

* ``runtime_qualified`` means the continuous analytical identity and static
  contract economics are admitted into ICARUS.  It does not assert that a
  provider entitlement is currently healthy; provider evidence is evaluated by
  the system index at runtime.
* ``execution_qualified`` means ICARUS has an independently verified static
  dated-contract rule for producing a *candidate* contract.  It does not
  authorize an order. Exact broker contract-details readback, reconciliation,
  risk authorization, and the owner execution policy remain separate gates.

Live execution remains disabled by owner policy.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping, Optional


MONTHLY = "FGHJKMNQUVXZ"
QUARTERLY = "HMUZ"


@dataclass(frozen=True)
class FuturesProduct:
    root: str
    name: str
    provider_symbol: str
    tv_symbol: str
    exchange: str
    asset_class: str
    tick_size: float
    point_value: float
    full_root: str
    ratio_to_full: float
    cycle: str
    roll_model: str
    execution_root: str
    session: str = "eth"
    calendar: str = "cme"
    group: str = "equity"
    runtime_qualified: bool = True
    execution_qualified: bool = True
    execution_blocker: Optional[str] = None

    @property
    def tick_value(self) -> float:
        return self.tick_size * self.point_value

    @property
    def is_micro(self) -> bool:
        return self.full_root != self.root


def _p(
    root: str,
    name: str,
    provider_symbol: str,
    tv_symbol: str,
    exchange: str,
    asset_class: str,
    tick_size: float,
    point_value: float,
    *,
    full_root: Optional[str] = None,
    ratio_to_full: float = 1.0,
    cycle: str,
    roll_model: str,
    execution_root: Optional[str] = None,
    session: str = "eth",
    calendar: str = "cme",
    group: str = "equity",
    runtime_qualified: bool = True,
    qualified: bool = True,
    blocker: Optional[str] = None,
) -> FuturesProduct:
    if qualified and blocker is not None:
        raise ValueError(f"{root}: statically qualified products cannot carry an execution blocker")
    if not qualified and not blocker:
        blocker = "dated-contract resolver rules are not yet independently qualified"
    return FuturesProduct(
        root=root,
        name=name,
        provider_symbol=provider_symbol,
        tv_symbol=tv_symbol,
        exchange=exchange,
        asset_class=asset_class,
        tick_size=tick_size,
        point_value=point_value,
        full_root=full_root or root,
        ratio_to_full=ratio_to_full,
        cycle=cycle,
        roll_model=roll_model,
        execution_root=execution_root or root,
        session=session,
        calendar=calendar,
        group=group,
        runtime_qualified=runtime_qualified,
        execution_qualified=qualified,
        execution_blocker=blocker,
    )


# Contract economics are static facts; provider/broker health is not.  All 32
# products are admitted as continuous analytical assets.  Static dated-candidate
# rules are verified for every family, while the broker-paper gate still requires
# exact contract-details readback and reconciliation before order submission.
_CATALOG = {
    # Equity indexes.
    "NQ": _p("NQ", "Nasdaq 100 E-mini", "NQ=F", "CME_MINI:NQ1!", "CME", "equity_index", 0.25, 20.0,
             cycle=QUARTERLY, roll_model="equity_third_friday", session="rth"),
    "MNQ": _p("MNQ", "Micro E-mini Nasdaq 100", "MNQ=F", "CME_MINI:MNQ1!", "CME", "equity_index", 0.25, 2.0,
              full_root="NQ", ratio_to_full=0.1, cycle=QUARTERLY, roll_model="equity_third_friday", session="rth"),
    "ES": _p("ES", "S&P 500 E-mini", "ES=F", "CME_MINI:ES1!", "CME", "equity_index", 0.25, 50.0,
             cycle=QUARTERLY, roll_model="equity_third_friday", session="rth"),
    "MES": _p("MES", "Micro E-mini S&P 500", "MES=F", "CME_MINI:MES1!", "CME", "equity_index", 0.25, 5.0,
              full_root="ES", ratio_to_full=0.1, cycle=QUARTERLY, roll_model="equity_third_friday", session="rth"),
    "YM": _p("YM", "Dow E-mini", "YM=F", "CBOT_MINI:YM1!", "CBOT", "equity_index", 1.0, 5.0,
             cycle=QUARTERLY, roll_model="equity_third_friday", session="rth"),
    "MYM": _p("MYM", "Micro E-mini Dow", "MYM=F", "CBOT_MINI:MYM1!", "CBOT", "equity_index", 1.0, 0.5,
              full_root="YM", ratio_to_full=0.1, cycle=QUARTERLY, roll_model="equity_third_friday", session="rth"),
    "RTY": _p("RTY", "E-mini Russell 2000", "RTY=F", "CME_MINI:RTY1!", "CME", "equity_index", 0.10, 50.0,
              cycle=QUARTERLY, roll_model="equity_third_friday", session="rth"),
    "M2K": _p("M2K", "Micro E-mini Russell 2000", "M2K=F", "CME_MINI:M2K1!", "CME", "equity_index", 0.10, 5.0,
              full_root="RTY", ratio_to_full=0.1, cycle=QUARTERLY, roll_model="equity_third_friday", session="rth"),

    # Precious/base metals.
    "GC": _p("GC", "Gold", "GC=F", "COMEX:GC1!", "COMEX", "metal", 0.10, 100.0,
             cycle="GJMQVZ", roll_model="metals_first_notice", group="metals", session="rth"),
    "MGC": _p("MGC", "Micro Gold", "MGC=F", "COMEX_MINI:MGC1!", "COMEX", "metal", 0.10, 10.0,
              full_root="GC", ratio_to_full=0.1, cycle="GJMQVZ", roll_model="metals_first_notice", group="metals", session="rth"),
    "SI": _p("SI", "Silver", "SI=F", "COMEX:SI1!", "COMEX", "metal", 0.005, 5000.0,
             cycle="HKNUZ", roll_model="metals_first_notice", group="metals", session="rth"),
    "SIL": _p("SIL", "Micro Silver", "SIL=F", "COMEX_MINI:SIL1!", "COMEX", "metal", 0.005, 1000.0,
              full_root="SI", ratio_to_full=0.2, cycle="HKNUZ", roll_model="metals_first_notice", group="metals", session="rth"),
    "PL": _p("PL", "Platinum", "PL=F", "NYMEX:PL1!", "NYMEX", "metal", 0.10, 50.0,
             cycle="FJNV", roll_model="third_last_business_day", group="metals"),
    "PA": _p("PA", "Palladium", "PA=F", "NYMEX:PA1!", "NYMEX", "metal", 0.50, 100.0,
             cycle=QUARTERLY, roll_model="third_last_business_day", group="metals"),
    "HG": _p("HG", "Copper", "HG=F", "COMEX:HG1!", "COMEX", "metal", 0.0005, 25000.0,
             cycle=MONTHLY, roll_model="third_last_business_day", group="metals"),
    "MHG": _p("MHG", "Micro Copper", "MHG=F", "COMEX:MHG1!", "COMEX", "metal", 0.0005, 2500.0,
              full_root="HG", ratio_to_full=0.1, cycle=MONTHLY,
              roll_model="micro_copper_prior_month_third_last_business_day", group="metals"),

    # Energy.
    "CL": _p("CL", "WTI Crude Oil", "CL=F", "NYMEX:CL1!", "NYMEX", "energy", 0.01, 1000.0,
             cycle=MONTHLY, roll_model="wti_25th_prior_month"),
    "MCL": _p("MCL", "Micro WTI Crude Oil", "MCL=F", "NYMEX:MCL1!", "NYMEX", "energy", 0.01, 100.0,
              full_root="CL", ratio_to_full=0.1, cycle=MONTHLY,
              roll_model="micro_wti_one_business_day_before_cl"),
    "NG": _p("NG", "Henry Hub Natural Gas", "NG=F", "NYMEX:NG1!", "NYMEX", "energy", 0.001, 10000.0,
             cycle=MONTHLY, roll_model="ng_three_business_days_prior_delivery"),
    "MNG": _p("MNG", "Micro Henry Hub Natural Gas", "MNG=F", "NYMEX:MNG1!", "NYMEX", "energy", 0.001, 1000.0,
              full_root="NG", ratio_to_full=0.1, cycle=MONTHLY,
              roll_model="micro_ng_one_business_day_before_ng"),

    # Major CME FX and micros.  CME expanded the micro FX suite to monthly
    # expirations; current standard contracts are also listed monthly.
    "6E": _p("6E", "Euro FX", "6E=F", "CME:6E1!", "CME", "fx", 0.00005, 125000.0,
             cycle=MONTHLY, roll_model="fx_two_business_days_before_third_wednesday"),
    "M6E": _p("M6E", "Micro EUR/USD", "M6E=F", "CME:M6E1!", "CME", "fx", 0.0001, 12500.0,
              full_root="6E", ratio_to_full=0.1, cycle=MONTHLY,
              roll_model="fx_two_business_days_before_third_wednesday"),
    "6J": _p("6J", "Japanese Yen", "6J=F", "CME:6J1!", "CME", "fx", 0.0000005, 12500000.0,
             cycle=MONTHLY, roll_model="fx_two_business_days_before_third_wednesday"),
    "MJY": _p("MJY", "Micro JPY/USD", "MJY=F", "CME:MJY1!", "CME", "fx", 0.000001, 1250000.0,
              full_root="6J", ratio_to_full=0.1, cycle=MONTHLY,
              roll_model="fx_two_business_days_before_third_wednesday"),
    "6B": _p("6B", "British Pound", "6B=F", "CME:6B1!", "CME", "fx", 0.0001, 62500.0,
             cycle=MONTHLY, roll_model="fx_two_business_days_before_third_wednesday"),
    "M6B": _p("M6B", "Micro GBP/USD", "M6B=F", "CME:M6B1!", "CME", "fx", 0.0001, 6250.0,
              full_root="6B", ratio_to_full=0.1, cycle=MONTHLY,
              roll_model="fx_two_business_days_before_third_wednesday"),
    "6A": _p("6A", "Australian Dollar", "6A=F", "CME:6A1!", "CME", "fx", 0.00005, 100000.0,
             cycle=MONTHLY, roll_model="fx_two_business_days_before_third_wednesday"),
    "M6A": _p("M6A", "Micro AUD/USD", "M6A=F", "CME:M6A1!", "CME", "fx", 0.0001, 10000.0,
              full_root="6A", ratio_to_full=0.1, cycle=MONTHLY,
              roll_model="fx_two_business_days_before_third_wednesday"),

    # U.S. Treasuries.
    "ZN": _p("ZN", "10-Year T-Note", "ZN=F", "CBOT:ZN1!", "CBOT", "rates", 0.015625, 1000.0,
             cycle=QUARTERLY, roll_model="treasury_seven_business_days_before_month_end"),
    "ZB": _p("ZB", "30-Year U.S. Treasury Bond", "ZB=F", "CBOT:ZB1!", "CBOT", "rates", 0.03125, 1000.0,
             cycle=QUARTERLY, roll_model="treasury_seven_business_days_before_month_end"),

    # CME crypto futures. BTCF is the collision-free ICARUS analytical root;
    # CME/IBKR use BTC for the dated full-size execution contract.
    "BTCF": _p("BTCF", "Bitcoin futures (CME)", "BTC=F", "CME:BTC1!", "CME", "crypto_futures", 5.0, 5.0,
               cycle=MONTHLY, roll_model="crypto_last_friday", execution_root="BTC",
               calendar="cme_crypto", group="crypto"),
    "MBT": _p("MBT", "Micro Bitcoin futures (CME)", "MBT=F", "CME:MBT1!", "CME", "crypto_futures", 5.0, 0.1,
              full_root="BTCF", ratio_to_full=0.02, cycle=MONTHLY, roll_model="crypto_last_friday",
              calendar="cme_crypto", group="crypto"),
}

FUTURES_PRODUCTS: Mapping[str, FuturesProduct] = MappingProxyType(_CATALOG)


def futures_product(root: str) -> FuturesProduct:
    key = str(root).strip().upper()
    try:
        return FUTURES_PRODUCTS[key]
    except KeyError as exc:
        raise ValueError(f"unknown canonical futures root {root!r}") from exc


def execution_qualified_products() -> Iterable[FuturesProduct]:
    return tuple(product for product in FUTURES_PRODUCTS.values() if product.execution_qualified)


def validate_catalog() -> None:
    providers = set()
    tv_symbols = set()
    for key, product in FUTURES_PRODUCTS.items():
        if key != product.root:
            raise RuntimeError(f"catalog key/root mismatch: {key!r} != {product.root!r}")
        if product.provider_symbol in providers:
            raise RuntimeError(f"duplicate provider futures identity {product.provider_symbol!r}")
        if product.tv_symbol in tv_symbols:
            raise RuntimeError(f"duplicate TradingView futures identity {product.tv_symbol!r}")
        providers.add(product.provider_symbol)
        tv_symbols.add(product.tv_symbol)

        if not product.provider_symbol.endswith("=F"):
            raise RuntimeError(f"{key}: provider identity must be continuous (=F)")
        if not product.tv_symbol.endswith("1!"):
            raise RuntimeError(f"{key}: TradingView identity must be continuous (1!)")
        if not product.execution_root:
            raise RuntimeError(f"{key}: execution root is required")
        if product.tick_size <= 0 or product.point_value <= 0:
            raise RuntimeError(f"{key}: futures economics must be positive")
        if product.execution_qualified and product.execution_blocker is not None:
            raise RuntimeError(f"{key}: qualified static resolver cannot carry a blocker")
        if not product.execution_qualified and not product.execution_blocker:
            raise RuntimeError(f"{key}: unqualified static resolver requires a blocker")

        if product.full_root not in FUTURES_PRODUCTS:
            raise RuntimeError(f"{key}: unknown full-size parent {product.full_root!r}")
        if product.full_root == key:
            if not math.isclose(product.ratio_to_full, 1.0, rel_tol=0.0, abs_tol=1e-12):
                raise RuntimeError(f"{key}: full-size product must have ratio_to_full=1")
        else:
            parent = FUTURES_PRODUCTS[product.full_root]
            if product.point_value >= parent.point_value:
                raise RuntimeError(f"{key}: micro point value must be smaller than {parent.root}")
            expected_ratio = product.point_value / parent.point_value
            if not math.isclose(product.ratio_to_full, expected_ratio, rel_tol=1e-12, abs_tol=1e-12):
                raise RuntimeError(
                    f"{key}: ratio_to_full {product.ratio_to_full} does not match economics {expected_ratio}"
                )


validate_catalog()
