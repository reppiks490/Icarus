"""Canonical ICARUS futures product authority.

This module owns static product identity and contract economics shared by the
continuous research runtime and the dated paper-execution resolver.  It does
*not* establish broker entitlement, margin sufficiency, contract-details
qualification, or live-trading authorization.

Research identities stay continuous.  Broker adapters must resolve them to an
exact dated contract and then qualify that contract with the broker before any
paper order can be submitted.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


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
    calendar: str
    session: str
    group: str
    tick_size: float
    point_value: float
    cycle: str
    roll_kind: str
    micro_of: Optional[str] = None
    feed_mode: str = "public_delayed"

    @property
    def tick_value(self) -> float:
        return self.tick_size * self.point_value

    @property
    def full_root(self) -> str:
        return self.micro_of or self.root


def _product(
    root: str,
    name: str,
    provider_symbol: str,
    tv_symbol: str,
    exchange: str,
    asset_class: str,
    tick_size: float,
    point_value: float,
    cycle: str,
    roll_kind: str,
    *,
    micro_of: Optional[str] = None,
    calendar: str = "cme",
    session: str = "rth",
    group: str = "equity",
) -> FuturesProduct:
    return FuturesProduct(
        root=root,
        name=name,
        provider_symbol=provider_symbol,
        tv_symbol=tv_symbol,
        exchange=exchange,
        asset_class=asset_class,
        calendar=calendar,
        session=session,
        group=group,
        tick_size=tick_size,
        point_value=point_value,
        cycle=cycle,
        roll_kind=roll_kind,
        micro_of=micro_of,
    )


# Static economics are intentionally explicit.  The catalog is the one source
# from which both AssetSpec (research) and ContractSpec (paper execution) are
# generated.  Product families with more serial listings than the cycle below
# intentionally use their liquid benchmark cycle for static front-contract
# resolution; broker contract-details qualification remains the final authority.
_PRODUCTS = (
    # Equity index futures.
    _product("NQ", "Nasdaq 100 E-mini", "NQ=F", "CME_MINI:NQ1!", "CME", "equity_index", 0.25, 20.0, QUARTERLY, "equity"),
    _product("MNQ", "Micro E-mini Nasdaq 100", "MNQ=F", "CME_MINI:MNQ1!", "CME", "equity_index", 0.25, 2.0, QUARTERLY, "equity", micro_of="NQ"),
    _product("ES", "S&P 500 E-mini", "ES=F", "CME_MINI:ES1!", "CME", "equity_index", 0.25, 50.0, QUARTERLY, "equity"),
    _product("MES", "Micro E-mini S&P 500", "MES=F", "CME_MINI:MES1!", "CME", "equity_index", 0.25, 5.0, QUARTERLY, "equity", micro_of="ES"),
    _product("YM", "Dow E-mini", "YM=F", "CBOT_MINI:YM1!", "CBOT", "equity_index", 1.0, 5.0, QUARTERLY, "equity"),
    _product("MYM", "Micro E-mini Dow", "MYM=F", "CBOT_MINI:MYM1!", "CBOT", "equity_index", 1.0, 0.5, QUARTERLY, "equity", micro_of="YM"),
    _product("RTY", "E-mini Russell 2000", "RTY=F", "CME_MINI:RTY1!", "CME", "equity_index", 0.10, 50.0, QUARTERLY, "equity"),
    _product("M2K", "Micro E-mini Russell 2000", "M2K=F", "CME_MINI:M2K1!", "CME", "equity_index", 0.10, 5.0, QUARTERLY, "equity", micro_of="RTY"),

    # Metals.  Benchmark active cycles are explicit; all use delivery-aware
    # conservative pre-notice rolling in the static resolver.
    _product("GC", "Gold", "GC=F", "COMEX:GC1!", "COMEX", "metal", 0.10, 100.0, "GJMQVZ", "first_notice", group="metals"),
    _product("MGC", "Micro Gold", "MGC=F", "COMEX_MINI:MGC1!", "COMEX", "metal", 0.10, 10.0, "GJMQVZ", "first_notice", micro_of="GC", group="metals"),
    _product("SI", "Silver", "SI=F", "COMEX:SI1!", "COMEX", "metal", 0.005, 5000.0, "HKNUZ", "first_notice", group="metals"),
    _product("SIL", "Micro Silver", "SIL=F", "COMEX_MINI:SIL1!", "COMEX", "metal", 0.005, 1000.0, "HKNUZ", "first_notice", micro_of="SI", group="metals"),
    _product("PL", "Platinum", "PL=F", "NYMEX:PL1!", "NYMEX", "metal", 0.10, 50.0, "FJNV", "first_notice", group="metals"),
    _product("PA", "Palladium", "PA=F", "NYMEX:PA1!", "NYMEX", "metal", 0.50, 100.0, QUARTERLY, "first_notice", group="metals"),
    _product("HG", "Copper", "HG=F", "COMEX:HG1!", "COMEX", "metal", 0.0005, 25000.0, "HKNUZ", "first_notice", session="eth", group="metals"),
    _product("MHG", "Micro Copper", "MHG=F", "COMEX:MHG1!", "COMEX", "metal", 0.0005, 2500.0, "HKNUZ", "first_notice", micro_of="HG", session="eth", group="metals"),

    # Energy futures trade monthly and use a conservative pre-notice roll.
    _product("CL", "WTI Crude Oil", "CL=F", "NYMEX:CL1!", "NYMEX", "energy", 0.01, 1000.0, MONTHLY, "first_notice", session="eth"),
    _product("MCL", "Micro WTI Crude Oil", "MCL=F", "NYMEX:MCL1!", "NYMEX", "energy", 0.01, 100.0, MONTHLY, "first_notice", micro_of="CL", session="eth"),
    _product("NG", "Henry Hub Natural Gas", "NG=F", "NYMEX:NG1!", "NYMEX", "energy", 0.001, 10000.0, MONTHLY, "first_notice", session="eth"),
    _product("MNG", "Micro Henry Hub Natural Gas", "MNG=F", "NYMEX:MNG1!", "NYMEX", "energy", 0.001, 1000.0, MONTHLY, "first_notice", micro_of="NG", session="eth"),

    # Major CME FX futures and their micro counterparts.  Static resolution
    # follows the benchmark quarterly cycle; broker qualification handles serials.
    _product("6E", "Euro FX", "6E=F", "CME:6E1!", "CME", "fx", 0.00005, 125000.0, QUARTERLY, "fx", session="eth"),
    _product("M6E", "Micro EUR/USD", "M6E=F", "CME:M6E1!", "CME", "fx", 0.0001, 12500.0, QUARTERLY, "fx", micro_of="6E", session="eth"),
    _product("6J", "Japanese Yen", "6J=F", "CME:6J1!", "CME", "fx", 0.0000005, 12500000.0, QUARTERLY, "fx", session="eth"),
    _product("MJY", "Micro JPY/USD", "MJY=F", "CME:MJY1!", "CME", "fx", 0.000001, 1250000.0, QUARTERLY, "fx", micro_of="6J", session="eth"),
    _product("6B", "British Pound", "6B=F", "CME:6B1!", "CME", "fx", 0.0001, 62500.0, QUARTERLY, "fx", session="eth"),
    _product("M6B", "Micro GBP/USD", "M6B=F", "CME:M6B1!", "CME", "fx", 0.0001, 6250.0, QUARTERLY, "fx", micro_of="6B", session="eth"),
    _product("6A", "Australian Dollar", "6A=F", "CME:6A1!", "CME", "fx", 0.00005, 100000.0, QUARTERLY, "fx", session="eth"),
    _product("M6A", "Micro AUD/USD", "M6A=F", "CME:M6A1!", "CME", "fx", 0.0001, 10000.0, QUARTERLY, "fx", micro_of="6A", session="eth"),

    # U.S. Treasury futures.
    _product("ZN", "10-Year T-Note", "ZN=F", "CBOT:ZN1!", "CBOT", "rates", 0.015625, 1000.0, QUARTERLY, "treasury", session="eth"),
    _product("ZB", "30-Year U.S. Treasury Bond", "ZB=F", "CBOT:ZB1!", "CBOT", "rates", 0.03125, 1000.0, QUARTERLY, "treasury", session="eth"),

    # CME Bitcoin futures.  The static resolver follows the six-consecutive-month
    # lane; exact last-trade dates are re-qualified by the broker before paper use.
    _product("BTCF", "Bitcoin futures (CME)", "BTC=F", "CME:BTC1!", "CME", "crypto_futures", 5.0, 5.0, MONTHLY, "crypto", calendar="cme_crypto", session="eth", group="crypto"),
    _product("MBT", "Micro Bitcoin futures (CME)", "MBT=F", "CME:MBT1!", "CME", "crypto_futures", 5.0, 0.1, MONTHLY, "crypto", micro_of="BTCF", calendar="cme_crypto", session="eth", group="crypto"),
)

PRODUCTS: Dict[str, FuturesProduct] = {product.root: product for product in _PRODUCTS}

if len(PRODUCTS) != len(_PRODUCTS):
    raise RuntimeError("duplicate futures product root in canonical catalog")

for _root, _product_value in PRODUCTS.items():
    if _root != _product_value.root:
        raise RuntimeError(f"futures product key/root mismatch: {_root!r}")
    if _product_value.tick_size <= 0 or _product_value.point_value <= 0:
        raise RuntimeError(f"{_root}: futures economics must be positive")
    if _product_value.micro_of:
        _parent = PRODUCTS.get(_product_value.micro_of)
        if _parent is None:
            raise RuntimeError(f"{_root}: unknown micro parent {_product_value.micro_of!r}")
        if _product_value.point_value >= _parent.point_value:
            raise RuntimeError(f"{_root}: micro point value must be smaller than {_parent.root}")


def product(root: str) -> FuturesProduct:
    """Return one canonical product by ICARUS root, failing closed if unknown."""
    key = str(root).strip().upper()
    try:
        return PRODUCTS[key]
    except KeyError as exc:
        raise ValueError(f"unknown canonical futures root {root!r}") from exc
