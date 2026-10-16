# CL (Claude, Anthropic) — 2026-10-04 — icarus_futures.contracts: CME contract economics, continuous identities, rolls
"""Qualified dated-contract resolution for ICARUS futures.

Continuous analytical identities live in :mod:`icarus_engine.futures_catalog`.
Only products whose dated-contract rules are explicitly marked
``execution_qualified`` enter :data:`SPECS`; registered-but-unqualified products
therefore fail closed instead of inheriting another product family's roll rule.

Current qualified families preserve the existing proven behavior:

* equity index (H M U Z): roll Monday prior to third-Friday expiration;
* GC/MGC/SI/SIL metals: roll ``METALS_ROLL_BDAYS`` business days before first
  notice day (last business day of the month before contract month).

Additional product families are promoted only after product-specific expiry/roll
semantics and broker contract readback are tested.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from icarus_engine.futures_catalog import FUTURES_PRODUCTS, FuturesProduct

MONTH_CODES = "FGHJKMNQUVXZ"
EQUITY_ROLL_WEEKDAY_BEFORE = 4   # Monday = 3rd Friday - 4 days
EXPIRY_HOLIDAYS = {date(2026, 6, 19)}  # Juneteenth 2026 fell on a 3rd Friday (verified)
METALS_ROLL_BDAYS = 2


@dataclass(frozen=True)
class ContractSpec:
    root: str
    exchange: str
    tick_size: float
    tick_value: float
    cluster: str
    full_root: str
    ratio_to_full: float
    cycle: str
    roll_model: str

    @property
    def point_value(self) -> float:
        return self.tick_value / self.tick_size

    @property
    def kind(self) -> str:
        """Backward-compatible family label for older callers."""
        if self.roll_model == "equity_third_friday":
            return "equity"
        if self.roll_model == "metals_first_notice":
            return "metals"
        return self.roll_model

    def notional(self, qty: float, price: float) -> float:
        return abs(qty) * price * self.point_value

    def full_equivalent(self, qty: float) -> float:
        return qty * self.ratio_to_full


def _contract_spec(product: FuturesProduct) -> ContractSpec:
    if not product.execution_qualified:
        raise ValueError(f"{product.root}: cannot build execution spec for unqualified product")
    return ContractSpec(
        root=product.root,
        exchange=product.exchange,
        tick_size=product.tick_size,
        tick_value=product.tick_value,
        cluster=product.asset_class,
        full_root=product.full_root,
        ratio_to_full=product.ratio_to_full,
        cycle=product.cycle,
        roll_model=product.roll_model,
    )


SPECS = {
    root: _contract_spec(product)
    for root, product in FUTURES_PRODUCTS.items()
    if product.execution_qualified
}

_CONT = re.compile(r"^(?:[A-Z0-9_]+:)?([A-Z0-9]+?)(\d)!$")


def parse_continuous(symbol: str) -> tuple[ContractSpec, int]:
    """Return ``(spec, rank)`` for an execution-qualified continuous identity.

    Registration is intentionally insufficient.  A product remains unrouteable until
    its product-specific resolver and broker-readback path have been qualified.
    """
    m = _CONT.match(symbol.strip().upper())
    if not m or m.group(1) not in SPECS:
        raise ValueError(f"not a continuous futures identity: {symbol!r}")
    return SPECS[m.group(1)], int(m.group(2))


def _third_friday(y: int, m: int) -> date:
    d = date(y, m, 1)
    d += timedelta(days=(4 - d.weekday()) % 7)
    return d + timedelta(days=14)


def _last_bday_before(y: int, m: int) -> date:
    d = date(y, m, 1) - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _minus_bdays(d: date, n: int) -> date:
    while n:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def contract_dates(spec: ContractSpec, y: int, m: int) -> tuple[date, date]:
    """Return ``(last relevant date, roll date)`` for a qualified contract month."""
    if spec.roll_model == "equity_third_friday":
        third = _third_friday(y, m)
        exp = third
        while exp in EXPIRY_HOLIDAYS or exp.weekday() >= 5:
            exp -= timedelta(days=1)
        return exp, third - timedelta(days=EQUITY_ROLL_WEEKDAY_BEFORE)
    if spec.roll_model == "metals_first_notice":
        fnd = _last_bday_before(y, m)
        return fnd, _minus_bdays(fnd, METALS_ROLL_BDAYS)
    raise ValueError(
        f"{spec.root}: execution resolver {spec.roll_model!r} is not implemented/qualified"
    )


def code(spec: ContractSpec, y: int, m: int) -> str:
    return f"{spec.root}{MONTH_CODES[m - 1]}{y % 100:02d}"


def resolve(symbol: str, on: date) -> dict:
    """Front (or n-th) dated contract for a qualified continuous identity."""
    spec, nth = parse_continuous(symbol)
    if nth < 1:
        raise ValueError("continuous futures rank must be >= 1")
    months = [MONTH_CODES.index(c) + 1 for c in spec.cycle]
    chain = []
    for y in (on.year - 1, on.year, on.year + 1, on.year + 2):
        for m in months:
            last, roll = contract_dates(spec, y, m)
            if roll > on:
                chain.append((roll, y, m, last))
    chain.sort()
    if len(chain) < nth:
        raise ValueError(f"{spec.root}{nth}!: no qualified contract available for {on.isoformat()}")
    roll, y, m, last = chain[nth - 1]
    return dict(
        continuous=f"{spec.root}{nth}!",
        contract=code(spec, y, m),
        exchange=spec.exchange,
        roll_model=spec.roll_model,
        roll_date=roll.isoformat(),
        last_date=last.isoformat(),
        weekend_roll=roll.weekday() >= 5,
    )
