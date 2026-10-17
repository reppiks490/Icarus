# CL (Claude, Anthropic) — 2026-10-04 — icarus_futures.contracts: CME contract economics, continuous identities, rolls
"""Fail-closed futures contract resolution.

All 32 canonical roots have deterministic *structural candidates* for research,
dashboard inspection, and broker contract discovery. Only the explicitly
execution-qualified subset enters ``SPECS`` / ``resolve``. Calculating a dated
symbol is never treated as broker-paper authorization: exact broker contract
readback, account policy, reconciliation, risk authorization, and owner policy
remain downstream gates. Live execution remains disabled.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Mapping

from icarus_engine.futures_catalog import FUTURES_PRODUCTS, FuturesProduct

MONTH_CODES = "FGHJKMNQUVXZ"
EQUITY_ROLL_WEEKDAY_BEFORE = 4
STATIC_ROLL_LEAD_BDAYS = 2
CALENDAR_FIRST_YEAR = 2026
CALENDAR_LAST_YEAR = 2028

EQUITY_EXPIRY_HOLIDAYS = frozenset({date(2026, 6, 19), date(2027, 6, 18)})
CME_FULL_CLOSURES = frozenset({
    date(2026, 1, 1), date(2026, 4, 3), date(2026, 12, 25),
    date(2027, 1, 1), date(2027, 3, 26), date(2027, 12, 24),
    date(2028, 4, 14), date(2028, 12, 25),
})
LONDON_BANK_HOLIDAYS = frozenset({
    date(2026, 1, 1), date(2026, 4, 3), date(2026, 4, 6), date(2026, 5, 4),
    date(2026, 5, 25), date(2026, 8, 31), date(2026, 12, 25), date(2026, 12, 28),
    date(2027, 1, 1), date(2027, 3, 26), date(2027, 3, 29), date(2027, 5, 3),
    date(2027, 5, 31), date(2027, 8, 30), date(2027, 12, 27), date(2027, 12, 28),
    date(2028, 1, 3), date(2028, 4, 14), date(2028, 4, 17), date(2028, 5, 1),
    date(2028, 5, 29), date(2028, 8, 28), date(2028, 12, 25), date(2028, 12, 26),
})


@dataclass(frozen=True)
class ContractSpec:
    root: str
    execution_root: str
    exchange: str
    tick_size: float
    tick_value: float
    cluster: str
    full_root: str
    ratio_to_full: float
    cycle: str
    roll_model: str
    execution_qualified: bool

    @property
    def point_value(self) -> float:
        return self.tick_value / self.tick_size

    @property
    def kind(self) -> str:
        if self.cluster == "equity_index":
            return "equity"
        if self.cluster == "metal":
            return "metals"
        return self.roll_model

    def notional(self, qty: float, price: float) -> float:
        return abs(qty) * price * self.point_value

    def full_equivalent(self, qty: float) -> float:
        return qty * self.ratio_to_full


def _contract_spec(product: FuturesProduct) -> ContractSpec:
    return ContractSpec(
        root=product.root,
        execution_root=product.execution_root,
        exchange=product.exchange,
        tick_size=product.tick_size,
        tick_value=product.tick_value,
        cluster=product.asset_class,
        full_root=product.full_root,
        ratio_to_full=product.ratio_to_full,
        cycle=product.cycle,
        roll_model=product.roll_model,
        execution_qualified=product.execution_qualified,
    )


STRUCTURAL_SPECS = {root: _contract_spec(product) for root, product in FUTURES_PRODUCTS.items()}
SPECS = {root: spec for root, spec in STRUCTURAL_SPECS.items() if spec.execution_qualified}

_STRUCTURAL_EXECUTION_ROOT_ALIASES = {
    product.execution_root: root
    for root, product in FUTURES_PRODUCTS.items()
    if product.execution_root != root
}
_EXECUTION_ROOT_ALIASES = {
    spec.execution_root: root
    for root, spec in SPECS.items()
    if spec.execution_root != root
}
_CONT = re.compile(r"^(?:[A-Z0-9_]+:)?([A-Z0-9]+?)(\d+)!$")


def _parse_continuous(
    symbol: str,
    specs: Mapping[str, ContractSpec],
    aliases: Mapping[str, str],
    *,
    label: str,
) -> tuple[ContractSpec, int]:
    m = _CONT.match(symbol.strip().upper())
    if not m:
        raise ValueError(f"not a continuous futures identity: {symbol!r}")
    raw_root = m.group(1)
    root = raw_root if raw_root in specs else aliases.get(raw_root)
    if root is None or root not in specs:
        raise ValueError(f"not a {label} continuous futures identity: {symbol!r}")
    rank = int(m.group(2))
    if rank < 1:
        raise ValueError("continuous futures rank must be >= 1")
    return specs[root], rank


def parse_structural_continuous(symbol: str) -> tuple[ContractSpec, int]:
    """Parse any canonical root for non-authorizing static candidate discovery."""
    return _parse_continuous(
        symbol,
        STRUCTURAL_SPECS,
        _STRUCTURAL_EXECUTION_ROOT_ALIASES,
        label="structural",
    )


def parse_continuous(symbol: str) -> tuple[ContractSpec, int]:
    """Parse only roots admitted to the execution-qualified resolver."""
    try:
        return _parse_continuous(symbol, SPECS, _EXECUTION_ROOT_ALIASES, label="execution-qualified")
    except ValueError as exc:
        try:
            structural, _ = parse_structural_continuous(symbol)
        except ValueError:
            raise exc
        blocker = FUTURES_PRODUCTS[structural.root].execution_blocker or "execution route is not qualified"
        raise ValueError(f"{structural.root}: not execution-qualified: {blocker}") from exc


def _is_bday(d: date) -> bool:
    _require_calendar_coverage(d)
    return d.weekday() < 5 and d not in CME_FULL_CLOSURES


def _is_london_bday(d: date) -> bool:
    _require_calendar_coverage(d)
    return d.weekday() < 5 and d not in LONDON_BANK_HOLIDAYS


def _require_calendar_coverage(d: date) -> None:
    if not CALENDAR_FIRST_YEAR <= d.year <= CALENDAR_LAST_YEAR:
        raise ValueError(
            f"static futures calendar coverage is limited to "
            f"{CALENDAR_FIRST_YEAR}-{CALENDAR_LAST_YEAR}; got {d.isoformat()}"
        )


def _previous_bday(d: date) -> date:
    while not _is_bday(d):
        d -= timedelta(days=1)
    return d


def _previous_equity_expiry_day(d: date) -> date:
    while not _is_bday(d) or d in EQUITY_EXPIRY_HOLIDAYS:
        d -= timedelta(days=1)
    return d


def _previous_joint_btc_bday(d: date) -> date:
    while not (_is_bday(d) and _is_london_bday(d)):
        d -= timedelta(days=1)
    return d


def _minus_bdays(d: date, n: int) -> date:
    while n:
        d -= timedelta(days=1)
        if _is_bday(d):
            n -= 1
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


def _nth_last_bday_of_month(y: int, m: int, n: int) -> date:
    d = _last_bday_of_month(y, m)
    if n < 1:
        raise ValueError("n must be >= 1")
    remaining = n - 1
    while remaining:
        d -= timedelta(days=1)
        if _is_bday(d):
            remaining -= 1
    return d


def _prior_month(y: int, m: int) -> tuple[int, int]:
    return (y - 1, 12) if m == 1 else (y, m - 1)


def _last_joint_business_friday(y: int, m: int) -> date:
    if m == 12:
        d = date(y + 1, 1, 1) - timedelta(days=1)
    else:
        d = date(y, m + 1, 1) - timedelta(days=1)
    while d.weekday() != 4:
        d -= timedelta(days=1)
    return _previous_joint_btc_bday(d)


def _wti_last_trade(y: int, m: int) -> date:
    py, pm = _prior_month(y, m)
    anchor = _previous_bday(date(py, pm, 25))
    return _minus_bdays(anchor, 3)


def _ng_last_trade(y: int, m: int) -> date:
    return _minus_bdays(date(y, m, 1), 3)


def contract_dates(spec: ContractSpec, y: int, m: int) -> tuple[date, date]:
    """Return ``(last_relevant_date, conservative_roll_date)`` for a candidate."""
    model = spec.roll_model
    if model == "equity_third_friday":
        third = _third_friday(y, m)
        last = _previous_equity_expiry_day(third)
        return last, _previous_bday(third - timedelta(days=EQUITY_ROLL_WEEKDAY_BEFORE))
    if model == "metals_first_notice":
        first_notice = _last_bday_before(y, m)
        return first_notice, _minus_bdays(first_notice, STATIC_ROLL_LEAD_BDAYS)
    if model == "third_last_business_day":
        last = _nth_last_bday_of_month(y, m, 3)
        return last, _minus_bdays(last, STATIC_ROLL_LEAD_BDAYS)
    if model == "micro_copper_prior_month_third_last_business_day":
        py, pm = _prior_month(y, m)
        last = _nth_last_bday_of_month(py, pm, 3)
        return last, _minus_bdays(last, STATIC_ROLL_LEAD_BDAYS)
    if model == "wti_25th_prior_month":
        last = _wti_last_trade(y, m)
        return last, _minus_bdays(last, STATIC_ROLL_LEAD_BDAYS)
    if model == "micro_wti_one_business_day_before_cl":
        last = _minus_bdays(_wti_last_trade(y, m), 1)
        return last, _minus_bdays(last, STATIC_ROLL_LEAD_BDAYS)
    if model == "ng_three_business_days_prior_delivery":
        last = _ng_last_trade(y, m)
        return last, _minus_bdays(last, STATIC_ROLL_LEAD_BDAYS)
    if model == "micro_ng_one_business_day_before_ng":
        last = _minus_bdays(_ng_last_trade(y, m), 1)
        return last, _minus_bdays(last, STATIC_ROLL_LEAD_BDAYS)
    if model == "fx_two_business_days_before_third_wednesday":
        last = _minus_bdays(_third_wednesday(y, m), 2)
        return last, _minus_bdays(last, STATIC_ROLL_LEAD_BDAYS)
    if model == "treasury_seven_business_days_before_month_end":
        last = _minus_bdays(_last_bday_of_month(y, m), 7)
        return last, _minus_bdays(last, STATIC_ROLL_LEAD_BDAYS)
    if model == "crypto_last_friday":
        last = _last_joint_business_friday(y, m)
        return last, _minus_bdays(last, STATIC_ROLL_LEAD_BDAYS)
    raise ValueError(f"{spec.root}: static resolver {model!r} is not implemented")


def code(spec: ContractSpec, y: int, m: int) -> str:
    return f"{spec.execution_root}{MONTH_CODES[m - 1]}{y % 100:02d}"


def _resolve_spec(spec: ContractSpec, nth: int, on: date) -> dict:
    _require_calendar_coverage(on)
    months = [MONTH_CODES.index(c) + 1 for c in spec.cycle]
    chain = []
    # A candidate's roll date is within its contract year for every supported
    # family, so earlier contract years cannot contribute future candidates.
    first_year = max(CALENDAR_FIRST_YEAR, on.year)
    last_year = min(CALENDAR_LAST_YEAR, on.year + 3)
    for y in range(first_year, last_year + 1):
        for m in months:
            # Earlier delivery months have already passed their conservative
            # roll dates. In January the January delivery has already rolled
            # before the first calendar day, so it can be omitted as well.
            if (y, m) < (on.year, on.month) or (y == on.year and m == 1 and on.month == 1):
                continue
            last, roll = contract_dates(spec, y, m)
            if roll > on:
                chain.append((roll, y, m, last))
    chain.sort()
    if len(chain) < nth:
        raise ValueError(f"{spec.root}{nth}!: no static contract candidate for {on.isoformat()}")
    roll, y, m, last = chain[nth - 1]
    contract = code(spec, y, m)
    product = FUTURES_PRODUCTS[spec.root]
    return dict(
        continuous=f"{spec.root}{nth}!",
        execution_root=spec.execution_root,
        contract=contract,
        candidate_contract=contract,
        exchange=spec.exchange,
        roll_model=spec.roll_model,
        roll_date=roll.isoformat(),
        last_date=last.isoformat(),
        weekend_roll=roll.weekday() >= 5,
        front_mapping_basis="static_calendar_candidate",
        static_resolution=True,
        execution_qualified=spec.execution_qualified,
        execution_blocker=product.execution_blocker,
        broker_qualification_required=True,
        execution_authorized=False,
        live_authorized=False,
    )


def resolve_candidate(symbol: str, on: date) -> dict:
    """Resolve any canonical root to a non-authorizing static dated candidate."""
    spec, nth = parse_structural_continuous(symbol)
    return _resolve_spec(spec, nth, on)


def resolve(symbol: str, on: date) -> dict:
    """Resolve only the execution-qualified subset; never authorize an order."""
    spec, nth = parse_continuous(symbol)
    return _resolve_spec(spec, nth, on)
