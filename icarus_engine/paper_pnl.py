"""Pure, fail-closed valuation contract for four independent simulated ledgers.

``validate_paper_pnl`` accepts a list/tuple of exactly four mappings with unique
IDs cc1..cc4. Every mapping supplies ``currency`` (uppercase three-letter account
currency), ``runtime_available`` (literal True), ``snapshot_ts`` (UTC epoch
seconds), ``realized_pnl``, ``open_pnl`` and ``open_positions``. An open ledger
also supplies ``oldest_open_mark_ts``: the oldest observed mark across *every*
open position. The caller must supply None when any position lacks a mark.
This function validates the caller's evidence; it cannot establish its truth.

Amounts must be finite real numbers, excluding booleans, with magnitude at most
2**53-1. Strings are never converted. Timestamps and counts are nonnegative
integers within the same safe range. Snapshots must not postdate ``as_of_ts``;
marks must not postdate either their snapshot or as-of time. Age thresholds are
inclusive. Flat ledgers need an explicit zero open P&L and require no mark.

Missing/stale runtime or mixed currencies prevents a combined realized value.
Missing/stale marks preserve independently valid realized P&L but suppress open
and total valuation. No currency conversion, broker reconciliation, fee audit or
execution authority is inferred. The realized basis is persisted live=1 closure
time accounting, which can include positions originating in warmup.
"""
from __future__ import annotations

import math
from numbers import Real
import re
from typing import Any, Mapping


_IDS = frozenset(("cc1", "cc2", "cc3", "cc4"))
_MAX_SAFE = 2**53 - 1
_BASIS = ("simulated paper: persisted live=1 closures after paper cutover, including "
          "possible warmup-origin positions; current open marks separate; replay excluded")


def _integer(value: Any) -> bool:
    return type(value) is int and 0 <= value <= _MAX_SAFE


def _money(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    try:
        if abs(value) > _MAX_SAFE:
            return None
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _sum(values: list[float]) -> float | None:
    try:
        result = math.fsum(values)
    except (ValueError, OverflowError):
        return None
    return _money(result)


def validate_paper_pnl(
    ledgers: Any, *, as_of_ts: int, max_snapshot_age_seconds: int = 90,
    max_mark_age_seconds: int = 90,
) -> dict[str, Any]:
    """Return safe per-ledger values and a complete-or-unknown four-ledger sum.

    Bad global clock parameters raise ValueError. Bad/missing ledger evidence
    produces None amounts and explicit reasons instead of fabricated zeroes.
    Input mappings are never mutated. The result contains JSON-compatible data.
    """
    for name, value in (("as_of_ts", as_of_ts),
                        ("max_snapshot_age_seconds", max_snapshot_age_seconds),
                        ("max_mark_age_seconds", max_mark_age_seconds)):
        if not _integer(value):
            raise ValueError(f"{name} must be a nonnegative safe integer")

    reasons: list[str] = []
    if not isinstance(ledgers, (list, tuple)) or len(ledgers) != 4:
        reasons.append("FOUR_LEDGERS_REQUIRED")
    # Bound malformed input processing; the contract has exactly four rows.
    source = ledgers if isinstance(ledgers, (list, tuple)) and len(ledgers) <= 4 else ()
    profiles: list[dict[str, Any]] = []
    for raw in source:
        row_reasons: list[str] = []
        row: Mapping[str, Any] = raw if isinstance(raw, Mapping) else {}
        if not isinstance(raw, Mapping):
            row_reasons.append("LEDGER_NOT_OBJECT")
        identity = row.get("id")
        if not isinstance(identity, str) or identity not in _IDS:
            row_reasons.append("INVALID_LEDGER_ID")
            identity = None
        currency = row.get("currency")
        if not isinstance(currency, str) or re.fullmatch(r"[A-Z]{3}", currency) is None:
            row_reasons.append("ACCOUNT_CURRENCY_REQUIRED")
            currency = None
        if row.get("runtime_available") is not True:
            row_reasons.append("RUNTIME_UNAVAILABLE")
        snapshot = row.get("snapshot_ts")
        if not _integer(snapshot):
            row_reasons.append("INVALID_SNAPSHOT_TIMESTAMP")
        elif snapshot > as_of_ts:
            row_reasons.append("SNAPSHOT_IN_FUTURE")
        elif as_of_ts - snapshot > max_snapshot_age_seconds:
            row_reasons.append("SNAPSHOT_STALE")

        realized = _money(row.get("realized_pnl"))
        if realized is None:
            row_reasons.append("REALIZED_PNL_INVALID")
        # Identity/currency/runtime/clock are prerequisites to trusting amounts.
        trusted = not row_reasons
        realized = realized if trusted else None
        open_value = _money(row.get("open_pnl"))
        if open_value is None:
            row_reasons.append("OPEN_PNL_UNKNOWN_OR_INVALID")
        count = row.get("open_positions")
        if not _integer(count):
            row_reasons.append("OPEN_POSITION_COUNT_INVALID")
        elif count == 0:
            if open_value is not None and open_value != 0:
                row_reasons.append("FLAT_LEDGER_OPEN_PNL_NONZERO")
        else:
            mark = row.get("oldest_open_mark_ts")
            if not _integer(mark):
                row_reasons.append("OPEN_MARK_TIMESTAMP_UNKNOWN_OR_INVALID")
            elif mark > as_of_ts or (_integer(snapshot) and mark > snapshot):
                row_reasons.append("OPEN_MARK_IN_FUTURE")
            elif as_of_ts - mark > max_mark_age_seconds:
                row_reasons.append("OPEN_MARK_STALE")
        if row_reasons:
            open_value = None
        total = _sum([realized, open_value]) if realized is not None and open_value is not None else None
        if realized is not None and open_value is not None and total is None:
            row_reasons.append("TOTAL_PNL_OUT_OF_RANGE")
        profiles.append({"id": identity, "currency": currency,
                         "runtime_available": row.get("runtime_available") is True,
                         "realized_pnl": realized, "open_pnl": open_value,
                         "total_pnl": total, "accounting_complete": total is not None,
                         "reasons": row_reasons})

    identities = [row["id"] for row in profiles]
    if len(identities) != 4 or set(identities) != _IDS:
        reasons.append("FOUR_UNIQUE_WORKSPACE_IDENTITIES_REQUIRED")
    currencies = {row["currency"] for row in profiles}
    currency = next(iter(currencies)) if len(currencies) == 1 and None not in currencies else None
    if currency is None:
        reasons.append("SAME_EXPLICIT_ACCOUNT_CURRENCY_REQUIRED")
    identities_complete = not reasons
    realized_total = None
    open_total = None
    if identities_complete:
        if all(row["realized_pnl"] is not None for row in profiles):
            realized_total = _sum([row["realized_pnl"] for row in profiles])
        if all(row["open_pnl"] is not None for row in profiles):
            open_total = _sum([row["open_pnl"] for row in profiles])
    if realized_total is None:
        reasons.append("COMBINED_REALIZED_PNL_UNAVAILABLE")
    if open_total is None:
        reasons.append("COMBINED_OPEN_PNL_UNAVAILABLE")
    complete_rows = all(row["accounting_complete"] for row in profiles)
    total = (_sum([realized_total, open_total])
             if complete_rows and realized_total is not None and open_total is not None else None)
    if not complete_rows:
        reasons.append("INDIVIDUAL_LEDGER_VALUATION_INCOMPLETE")
    if complete_rows and realized_total is not None and open_total is not None and total is None:
        reasons.append("COMBINED_TOTAL_PNL_OUT_OF_RANGE")
    return {"schema_version": "icarus.paper-pnl.v1", "as_of_ts": as_of_ts,
            "paper_only": True, "execution_authorized": False, "profiles": profiles,
            "aggregate": {"workspace_count": len(profiles), "currency": currency,
                          "realized_pnl": realized_total, "open_pnl": open_total,
                          "total_pnl": total, "accounting_complete": total is not None,
                          "reasons": reasons, "basis": _BASIS,
                          "fees_status": "NOT_INDEPENDENTLY_VERIFIED",
                          "broker_reconciliation_status": "UNRECONCILED_SIMULATION"}}
