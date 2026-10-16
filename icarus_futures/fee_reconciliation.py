"""Pure reconciliation of normalized execution fills and statement fee rows.

This module deliberately has no broker statement parser, network access, persistence,
or order-routing behavior. Adapters must first translate their source records into
these types while preserving the provider's statement-row identity and SHA-256 digest.
The normalized matcher validates digest shape only; the eventual importer must
compute and verify the digest against source-row bytes before creating a row.
Amounts use signed ``Decimal`` values: positive debits increase costs, negative
credits/rebates reduce them, and zero is preserved as reported.
Inputs are bounded to 128 coefficient digits and a Decimal exponent between -128
and 128 so malformed statement values cannot trigger unbounded integer expansion.

Source motivation: ``reppiks490/Icarus-engine``
``coordination/source-material/20261015-screen-recordings-transcript.md`` at the
Wednesday 10:32–10:38 PM recording segment requests matching imported broker fills
to statement commissions and fees. This module implements only the normalized local
matching core; it does not claim provider statement import.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from typing import Iterable


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_MAX_AMOUNT_DIGITS = 128
_MAX_AMOUNT_EXPONENT = 128


@dataclass(frozen=True, order=True)
class FillIdentity:
    account_id: str
    fill_id: str
    currency: str


@dataclass(frozen=True)
class FeeStatementRow:
    source_id: str
    source_row_id: str
    source_hash: str
    account_id: str
    fill_id: str
    currency: str
    component: str
    amount: Decimal | str | int


@dataclass(frozen=True)
class MatchedFee:
    identity: FillIdentity
    source_id: str
    source_row_id: str
    source_hash: str
    component: str
    amount: Decimal
    direction: str


@dataclass(frozen=True)
class FeeTotal:
    identity: FillIdentity
    amount: Decimal


@dataclass(frozen=True)
class FeeIssue:
    row: FeeStatementRow
    reason: str


@dataclass(frozen=True)
class FeeReconciliation:
    matched: tuple[MatchedFee, ...]
    totals: tuple[FeeTotal, ...]
    unmatched: tuple[FeeIssue, ...]
    ambiguous: tuple[FeeIssue, ...]
    duplicate_source_rows: tuple[tuple[str, str], ...]


def _required_text(value: str, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{field} must be a non-empty trimmed string")
    return value


def _currency(value: str) -> str:
    value = _required_text(value, "currency")
    if not _CURRENCY_RE.fullmatch(value):
        raise ValueError("currency must be a three-letter uppercase code")
    return value


def _amount(value: Decimal | str | int) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("fee amount must be Decimal, integer, or decimal text")
    try:
        amount = value if isinstance(value, Decimal) else Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("fee amount is not a valid decimal") from exc
    if not amount.is_finite():
        raise ValueError("fee amount must be finite")
    parts = amount.as_tuple()
    if (len(parts.digits) > _MAX_AMOUNT_DIGITS
            or not isinstance(parts.exponent, int)
            or abs(parts.exponent) > _MAX_AMOUNT_EXPONENT):
        raise ValueError("fee amount exceeds supported precision or scale")
    return amount


def _exact_sum(values: list[Decimal]) -> Decimal:
    """Add finite Decimals without inheriting the process-global precision context."""
    if not values:
        return Decimal(0)
    parts = [value.as_tuple() for value in values]
    exponent = min(part.exponent for part in parts)
    coefficient = 0
    for part in parts:
        digits = int("".join(str(digit) for digit in part.digits) or "0")
        if part.sign:
            digits = -digits
        coefficient += digits * (10 ** (part.exponent - exponent))
    digits = tuple(int(char) for char in str(abs(coefficient))) or (0,)
    return Decimal((1 if coefficient < 0 else 0, digits, exponent))


def _normalize_fill(fill: FillIdentity) -> FillIdentity:
    if not isinstance(fill, FillIdentity):
        raise ValueError("fills must be FillIdentity records")
    return FillIdentity(
        account_id=_required_text(fill.account_id, "account_id"),
        fill_id=_required_text(fill.fill_id, "fill_id"),
        currency=_currency(fill.currency),
    )


def _normalize_row(row: FeeStatementRow) -> tuple[FeeStatementRow, Decimal]:
    if not isinstance(row, FeeStatementRow):
        raise ValueError("fee rows must be FeeStatementRow records")
    source_id = _required_text(row.source_id, "source_id")
    row_id = _required_text(row.source_row_id, "source_row_id")
    source_hash = _required_text(row.source_hash, "source_hash")
    if not _SHA256_RE.fullmatch(source_hash):
        raise ValueError("source_hash must be a lowercase SHA-256 hex digest")
    account_id = _required_text(row.account_id, "account_id")
    fill_id = _required_text(row.fill_id, "fill_id")
    currency = _currency(row.currency)
    component = _required_text(row.component, "component")
    amount = _amount(row.amount)
    normalized = FeeStatementRow(source_id, row_id, source_hash, account_id,
                                 fill_id, currency, component, amount)
    return normalized, amount


def reconcile_fees(
    fills: Iterable[FillIdentity], rows: Iterable[FeeStatementRow]
) -> FeeReconciliation:
    """Match statement rows to exactly one fill using account, currency, and fill ID.

    Repeated identical statement rows (same source and row ID) are idempotently
    counted once. A reused row identity with different contents is rejected. A fee
    row with no exact fill match is reported as unmatched; multiple exact fill
    matches are reported as ambiguous. Cross-account or cross-currency IDs never
    match. Input ordering does not affect the returned tuples.
    """
    fills_by_id: dict[str, list[FillIdentity]] = defaultdict(list)
    for raw_fill in fills:
        fill = _normalize_fill(raw_fill)
        fills_by_id[fill.fill_id].append(fill)

    deduplicated: dict[tuple[str, str], tuple[FeeStatementRow, Decimal]] = {}
    duplicate_source_rows: set[tuple[str, str]] = set()
    for raw_row in rows:
        row, amount = _normalize_row(raw_row)
        source_key = (row.source_id, row.source_row_id)
        prior = deduplicated.get(source_key)
        if prior is not None:
            if prior[0] != row:
                raise ValueError("statement source row identity was reused with different contents")
            duplicate_source_rows.add(source_key)
            continue
        deduplicated[source_key] = (row, amount)

    matched: list[MatchedFee] = []
    unmatched: list[FeeIssue] = []
    ambiguous: list[FeeIssue] = []
    totals: dict[FillIdentity, list[Decimal]] = defaultdict(list)

    for row, amount in deduplicated.values():
        candidates = [identity for identity in fills_by_id.get(row.fill_id, ())
                      if identity.account_id == row.account_id
                      and identity.currency == row.currency]
        if len(candidates) > 1:
            ambiguous.append(FeeIssue(row, "multiple_exact_fill_matches"))
            continue
        if not candidates:
            same_fill_id = fills_by_id.get(row.fill_id, ())
            if any(identity.account_id == row.account_id for identity in same_fill_id):
                reason = "currency_mismatch"
            elif same_fill_id:
                reason = "account_mismatch"
            else:
                reason = "fill_not_found"
            unmatched.append(FeeIssue(row, reason))
            continue

        identity = candidates[0]
        direction = "debit" if amount > 0 else "credit" if amount < 0 else "zero"
        matched.append(MatchedFee(identity, row.source_id, row.source_row_id,
                                  row.source_hash, row.component, amount, direction))
        totals[identity].append(amount)

    matched.sort(key=lambda item: (item.identity, item.source_id, item.source_row_id,
                                   item.component, item.amount))
    unmatched.sort(key=lambda item: (item.row.source_id, item.row.source_row_id, item.reason))
    ambiguous.sort(key=lambda item: (item.row.source_id, item.row.source_row_id, item.reason))
    ordered_totals = tuple(FeeTotal(identity, _exact_sum(amounts))
                          for identity, amounts in sorted(totals.items()))
    return FeeReconciliation(
        matched=tuple(matched),
        totals=ordered_totals,
        unmatched=tuple(unmatched),
        ambiguous=tuple(ambiguous),
        duplicate_source_rows=tuple(sorted(duplicate_source_rows)),
    )
