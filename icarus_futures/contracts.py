# CL (Claude, Anthropic) — 2026-10-04 — icarus_futures.contracts: CME contract economics, continuous identities, rolls
"""Continuous research identities -> conservative dated paper-contract candidates.

The canonical economics/identity source is :mod:`icarus_futures.products`.  This
module adds deterministic static roll rules so paper/shadow components can select
an exact dated candidate.  Static resolution is intentionally *not* the final
broker qualification: adapters must still read back exact contract details
(conId/localSymbol/expiry/multiplier/exchange) before a broker-paper order.

Rules implemented here are fail-closed conservative fallbacks:

* equity index: published CME Monday-before-third-Friday roll convention;
* deliverable metals: pre-first-notice roll;
* WTI / Micro WTI: contract-specific termination rule, with micro one business
  day before the corresponding CL expiry;
* Henry Hub / Micro Henry Hub: NG three business days before delivery month,
  with MNG one business day earlier;
* FX: two business days before the third Wednesday, then an additional
  conservative pre-expiry roll lead;
* 10Y/30Y Treasury: seventh business day before the final business day of the
  delivery month, then a conservative pre-expiry roll lead;
* CME Bitcoin/Micro Bitcoin: last-Friday termination with conservative lead.

Only explicitly encoded holidays are applied by the static fallback.  Therefore
``resolve`` marks its output as broker qualification required; it must never be
interpreted as proof of live-trading eligibility.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from .products import PRODUCTS

MONTH_CODES = "FGHJKMNQUVXZ"
EQUITY_ROLL_WEEKDAY_BEFORE = 4   # Monday = 3rd Friday - 4 calendar days
EXPIRY_HOLIDAYS = {date(2026, 6, 19)}  # Juneteenth 2026 fell on a 3rd Friday (verified)
STATIC_ROLL_LEAD_BDAYS = 2


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
    kind: str  # roll family from the canonical product authority

    @property
    def point_value(self) -> float:
        return self.tick_value / self.tick_size

    def notional(self, qty: float, price: float) -> float:
        return abs(qty) * price * self.point_value

    def full_equivalent(self, qty: float) -> float:
        return qty * self.ratio_to_full


def _contract_spec(root: str) -> ContractSpec:
    product = PRODUCTS[root]
    if product.micro_of:
        parent = PRODUCTS[product.micro_of]
        ratio = product.point_value / parent.point_value
    else:
        ratio = 1.0
    cluster = "metals" if product.asset_class == "metal" else product.asset_class
    return ContractSpec(
        root=product.root,
        exchange=product.exchange,
        tick_size=product.tick_size,
        tick_value=product.tick_value,
        cluster=cluster,
        full_root=product.full_root,
        ratio_to_full=ratio,
        cycle=product.cycle,
        kind=product.roll_kind,
    )


SPECS = {root: _contract_spec(root) for root in PRODUCTS}

_CONT = re.compile(r"^(?:[A-Z0-9_]+:)?([A-Z0-9]+?)(\d)!$")


def parse_continuous(symbol: str) -> tuple[ContractSpec, int]:
    """'NQ1!' or 'CME_MINI:MNQ1!' -> (spec, 1); dated codes are rejected."""
    m = _CONT.match(symbol.strip().upper())
    if not m or m.group(1) not in SPECS:
        raise ValueError(f"not a continuous futures identity: {symbol!r}")
    rank = int(m.group(2))
    if rank < 1:
        raise ValueError(f"continuous futures rank must be >= 1: {symbol!r}")
    return SPECS[m.group(1)], rank


def _is_bday(d: date) -> bool:
    return d.weekday() < 5 and d not in EXPIRY_HOLIDAYS


def _previous_bday(d: date) -> date:
    while not _is_bday(d):
        d -= timedelta(days=1)
    return d


def _third_weekday(y: int, m: int, weekday: int) -> date:
    d = date(y, m, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(days=14)


def _third_friday(y: int, m: int) -> date:
    return _third_weekday(y, m, 4)


def _third_wednesday(y: int, m: int) -> date:
    return _third_weekday(y, m, 2)


def _last_bday_of_month(y: int, m: int) -> date:
    if m == 12:
        d = date(y + 1, 1, 1) - timedelta(days=1)
    else:
        d = date(y, m + 1, 1) - timedelta(days=1)
    return _previous_bday(d)


def _last_bday_before(y: int, m: int) -> date:
    return _previous_bday(date(y, m, 1) - timedelta(days=1))


def _minus_bdays(d: date, n: int) -> date:
    while n:
        d -= timedelta(days=1)
        if _is_bday(d):
            n -= 1
    return d


def _wti_last_trade(y: int, m: int) -> date:
    """CL last trade: 3 business days before the adjusted 25th of prior month."""
    if m == 1:
        py, pm = y - 1, 12
    else:
        py, pm = y, m - 1
    anchor = _previous_bday(date(py, pm, 25))
    return _minus_bdays(anchor, 3)


def _natgas_last_trade(y: int, m: int) -> date:
    """NG last trade: 3 business days before the first day of delivery month."""
    return _minus_bdays(date(y, m, 1), 3)


def contract_dates(spec: ContractSpec, y: int, m: int) -> tuple[date, date]:
    """Return ``(last_relevant_date, conservative_roll_date)`` for a contract."""
    kind = spec.kind
    if kind == "equity":
        third = _third_friday(y, m)
        exp = _previous_bday(third)
        roll = _previous_bday(third - timedelta(days=EQUITY_ROLL_WEEKDAY_BEFORE))
        return exp, roll
    if kind == "first_notice":
        fnd = _last_bday_before(y, m)
        return fnd, _minus_bdays(fnd, STATIC_ROLL_LEAD_BDAYS)
    if kind == "wti":
        last = _wti_last_trade(y, m)
        return last, _minus_bdays(last, STATIC_ROLL_LEAD_BDAYS)
    if kind == "wti_micro":
        last = _minus_bdays(_wti_last_trade(y, m), 1)
        return last, _minus_bdays(last, STATIC_ROLL_LEAD_BDAYS)
    if kind == "natgas":
        last = _natgas_last_trade(y, m)
        return last, _minus_bdays(last, STATIC_ROLL_LEAD_BDAYS)
    if kind == "natgas_micro":
        last = _minus_bdays(_natgas_last_trade(y, m), 1)
        return last, _minus_bdays(last, STATIC_ROLL_LEAD_BDAYS)
    if kind == "fx":
        last = _minus_bdays(_third_wednesday(y, m), 2)
        return last, _minus_bdays(last, STATIC_ROLL_LEAD_BDAYS)
    if kind == "treasury":
        last = _minus_bdays(_last_bday_of_month(y, m), 7)
        return last, _minus_bdays(last, STATIC_ROLL_LEAD_BDAYS)
    if kind == "crypto":
        last = _previous_bday(_last_friday(y, m))
        return last, _minus_bdays(last, STATIC_ROLL_LEAD_BDAYS)
    raise ValueError(f"{spec.root}: unsupported static roll family {kind!r}")


def _last_friday(y: int, m: int) -> date:
    d = _last_bday_of_month(y, m)
    while d.weekday() != 4:
        d -= timedelta(days=1)
    return d


def code(spec: ContractSpec, y: int, m: int) -> str:
    return f"{spec.root}{MONTH_CODES[m - 1]}{y % 100:02d}"


def resolve(symbol: str, on: date) -> dict:
    """Resolve a continuous identity to a conservative dated paper candidate."""
    spec, nth = parse_continuous(symbol)
    months = [MONTH_CODES.index(c) + 1 for c in spec.cycle]
    chain = []
    for y in (on.year - 1, on.year, on.year + 1, on.year + 2, on.year + 3):
        for m in months:
            last, roll = contract_dates(spec, y, m)
            if roll > on:
                chain.append((roll, y, m, last))
    chain.sort()
    if len(chain) < nth:
        raise ValueError(f"unable to resolve rank {nth} for {symbol!r} on {on.isoformat()}")
    roll, y, m, last = chain[nth - 1]
    return dict(
        continuous=f"{spec.root}{nth}!",
        contract=code(spec, y, m),
        roll_date=roll.isoformat(),
        last_date=last.isoformat(),
        weekend_roll=roll.weekday() >= 5,
        static_resolution=True,
        broker_qualification_required=True,
        execution_authorized=False,
    )
