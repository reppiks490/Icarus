# CL (Claude, Anthropic) — 2026-10-04 — icarus_futures.contracts: CME contract economics, continuous identities, rolls
"""User-facing symbols stay continuous (NQ1!, MNQ1!, ES1!, GC1!, ...). Adapters that need a
dated contract call :func:`resolve`, which returns the front contract for a session date
using an explicit, configurable roll rule:

* equity index (H M U Z): expiry = 3rd Friday of the contract month; roll
  ``EQUITY_ROLL_DAYS`` calendar days before expiry (default 8, i.e. the Thursday of the
  prior week). CL research notes flag CME's published roll-date convention as needing
  confirmation, so the offset is a parameter, not a constant buried in code.
* metals: roll ``METALS_ROLL_BDAYS`` business days before first notice day
  (FND = last business day of the month before the contract month).
Exchange holidays are not modelled; dates landing on one are reported, not guessed."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

MONTH_CODES = "FGHJKMNQUVXZ"
EQUITY_ROLL_DAYS = 8
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
    kind: str  # "equity" | "metals"

    @property
    def point_value(self) -> float:
        return self.tick_value / self.tick_size

    def notional(self, qty: float, price: float) -> float:
        return abs(qty) * price * self.point_value

    def full_equivalent(self, qty: float) -> float:
        return qty * self.ratio_to_full


SPECS = {s.root: s for s in (
    ContractSpec("NQ", "CME", 0.25, 5.00, "equity_index", "NQ", 1.0, "HMUZ", "equity"),
    ContractSpec("MNQ", "CME", 0.25, 0.50, "equity_index", "NQ", 0.1, "HMUZ", "equity"),
    ContractSpec("ES", "CME", 0.25, 12.50, "equity_index", "ES", 1.0, "HMUZ", "equity"),
    ContractSpec("MES", "CME", 0.25, 1.25, "equity_index", "ES", 0.1, "HMUZ", "equity"),
    ContractSpec("YM", "CBOT", 1.0, 5.00, "equity_index", "YM", 1.0, "HMUZ", "equity"),
    ContractSpec("MYM", "CBOT", 1.0, 0.50, "equity_index", "YM", 0.1, "HMUZ", "equity"),
    ContractSpec("RTY", "CME", 0.10, 5.00, "equity_index", "RTY", 1.0, "HMUZ", "equity"),
    ContractSpec("M2K", "CME", 0.10, 0.50, "equity_index", "RTY", 0.1, "HMUZ", "equity"),
    ContractSpec("GC", "COMEX", 0.10, 10.00, "metals", "GC", 1.0, "GJMQVZ", "metals"),
    ContractSpec("MGC", "COMEX", 0.10, 1.00, "metals", "GC", 0.1, "GJMQVZ", "metals"),
    ContractSpec("SI", "COMEX", 0.005, 25.00, "metals", "SI", 1.0, "HKNUZ", "metals"),
    ContractSpec("SIL", "COMEX", 0.005, 5.00, "metals", "SI", 0.2, "HKNUZ", "metals"),
)}

_CONT = re.compile(r"^(?:[A-Z_]+:)?([A-Z0-9]+?)(\d)!$")


def parse_continuous(symbol: str) -> tuple[ContractSpec, int]:
    """'NQ1!' or 'CME_MINI:MNQ1!' -> (spec, 1). Raises for expiring codes such as NQZ2026."""
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
    """(last relevant date, roll date) for the contract of month m, year y."""
    if spec.kind == "equity":
        exp = _third_friday(y, m)
        return exp, exp - timedelta(days=EQUITY_ROLL_DAYS)
    fnd = _last_bday_before(y, m)
    return fnd, _minus_bdays(fnd, METALS_ROLL_BDAYS)


def code(spec: ContractSpec, y: int, m: int) -> str:
    return f"{spec.root}{MONTH_CODES[m - 1]}{y % 100:02d}"


def resolve(symbol: str, on: date) -> dict:
    """Front (or n-th) dated contract for a continuous identity on a session date."""
    spec, nth = parse_continuous(symbol)
    months = [MONTH_CODES.index(c) + 1 for c in spec.cycle]
    chain = []
    for y in (on.year - 1, on.year, on.year + 1, on.year + 2):
        for m in months:
            last, roll = contract_dates(spec, y, m)
            if roll > on:
                chain.append((roll, y, m, last))
    chain.sort()
    roll, y, m, last = chain[nth - 1]
    return dict(continuous=f"{spec.root}{nth}!", contract=code(spec, y, m), roll_date=roll.isoformat(),
                last_date=last.isoformat(), weekend_roll=roll.weekday() >= 5)
