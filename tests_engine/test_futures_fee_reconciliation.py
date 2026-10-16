from decimal import Decimal
import hashlib

import pytest

from icarus_futures.fee_reconciliation import (
    FeeStatementRow,
    FillIdentity,
    reconcile_fees,
)


def row(row_id="row-1", *, account="DU12345", fill_id="exec-1", currency="USD",
        component="commission", amount="1.25", source="broker-statement"):
    digest = hashlib.sha256(f"{source}:{row_id}".encode()).hexdigest()
    return FeeStatementRow(source, row_id, digest, account, fill_id, currency,
                           component, amount)


def test_matches_fee_components_by_fill_account_and_currency_and_aggregates_decimal():
    fills = [FillIdentity("DU12345", "exec-1", "USD")]
    rows = [row("commission", amount="1.25"),
            row("exchange", component="exchange", amount="0.42"),
            row("rebate", component="maker-credit", amount="-0.10")]

    result = reconcile_fees(fills, rows)

    assert {(item.component, item.direction) for item in result.matched} == {
        ("commission", "debit"), ("exchange", "debit"), ("maker-credit", "credit")}
    assert result.totals[0].amount == Decimal("1.57")
    assert result.unmatched == ()
    assert result.ambiguous == ()


def test_account_and_currency_mismatches_never_cross_match():
    fills = [FillIdentity("DU12345", "shared-exec", "USD"),
             FillIdentity("DU99999", "other-exec", "USD")]
    rows = [row("wrong-account", account="DU00000", fill_id="shared-exec"),
            row("wrong-currency", account="DU12345", fill_id="shared-exec", currency="CAD"),
            row("unknown-id", account="DU12345", fill_id="missing")]

    result = reconcile_fees(fills, rows)

    assert [(issue.row.source_row_id, issue.reason) for issue in result.unmatched] == [
        ("unknown-id", "fill_not_found"),
        ("wrong-account", "account_mismatch"),
        ("wrong-currency", "currency_mismatch"),
    ]
    assert result.matched == ()


def test_identical_statement_rows_are_idempotent_and_conflicting_reuse_is_rejected():
    fill = FillIdentity("DU12345", "exec-1", "USD")
    statement_row = row(amount="2.50")

    result = reconcile_fees([fill], [statement_row, statement_row])

    assert len(result.matched) == 1
    assert result.totals[0].amount == Decimal("2.50")
    assert result.duplicate_source_rows == (("broker-statement", "row-1"),)
    conflicting = row(amount="3.50")
    with pytest.raises(ValueError, match="reused with different contents"):
        reconcile_fees([fill], [statement_row, conflicting])


def test_missing_and_ambiguous_fill_matches_are_reported_separately():
    fills = [FillIdentity("DU12345", "duplicate", "USD"),
             FillIdentity("DU12345", "duplicate", "USD")]

    result = reconcile_fees(fills, [row("ambiguous", fill_id="duplicate"),
                                    row("missing", fill_id="no-such-fill")])

    assert [(issue.row.source_row_id, issue.reason) for issue in result.ambiguous] == [
        ("ambiguous", "multiple_exact_fill_matches")]
    assert [(issue.row.source_row_id, issue.reason) for issue in result.unmatched] == [
        ("missing", "fill_not_found")]
    assert result.totals == ()


@pytest.mark.parametrize("amount", [True, 1.25, "NaN", "Infinity", "not-money"])
def test_malformed_nonfinite_and_binary_float_amounts_are_rejected(amount):
    with pytest.raises(ValueError, match="amount"):
        reconcile_fees([FillIdentity("DU12345", "exec-1", "USD")],
                       [row(amount=amount)])


def test_output_is_deterministic_and_retains_statement_row_identity_hash():
    fills = [FillIdentity("DU12345", "exec-b", "USD"),
             FillIdentity("DU12345", "exec-a", "USD")]
    rows = [row("b", fill_id="exec-b", amount="2"),
            row("a", fill_id="exec-a", amount="1")]

    forward = reconcile_fees(fills, rows)
    reverse = reconcile_fees(list(reversed(fills)), list(reversed(rows)))

    assert forward == reverse
    assert [(item.source_row_id, item.source_hash) for item in forward.matched] == [
        ("a", hashlib.sha256(b"broker-statement:a").hexdigest()),
        ("b", hashlib.sha256(b"broker-statement:b").hexdigest()),
    ]


def test_decimal_totals_do_not_round_at_the_process_default_precision():
    fill = FillIdentity("DU12345", "precision", "USD")
    first = Decimal("0.12345678901234567890123456789012")
    second = Decimal("0.00000000000000000000000000000009")

    result = reconcile_fees([fill], [row("first", fill_id="precision", amount=first),
                                    row("second", fill_id="precision", amount=second)])

    assert result.totals[0].amount == Decimal("0.12345678901234567890123456789021")


def test_invalid_currency_and_source_hash_are_rejected():
    with pytest.raises(ValueError, match="currency"):
        reconcile_fees([FillIdentity("DU12345", "exec-1", "usd")], [])

    invalid_hash = FeeStatementRow("broker-statement", "row-1", "not-a-digest",
                                   "DU12345", "exec-1", "USD", "commission", "1")
    with pytest.raises(ValueError, match="SHA-256"):
        reconcile_fees([FillIdentity("DU12345", "exec-1", "USD")], [invalid_hash])
