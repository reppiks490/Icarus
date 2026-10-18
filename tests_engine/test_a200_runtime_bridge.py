from dataclasses import replace

import pytest

from icarus_engine.a200_runtime_bridge import A200RuntimeBatch, assess_runtime_eligibility
from icarus_engine.bar_receipts import make_bar_batch_receipt
from icarus_engine.market_universe import snapshot
from icarus_engine.pine.timeframe import Bar


def _batch(*, mapping="UNVERIFIED", entitlement="UNKNOWN", qualified=False):
    row = snapshot()["instruments"][0]
    bars = [Bar(1_799_999_700, 100.0, 101.0, 99.0, 100.5, 10.0)]
    checked, receipt = make_bar_batch_receipt(
        instrument_id=row["instrument_id"], provider="yahoo",
        expected_provider_symbol="NVDA", observed_provider_symbol="NVDA",
        interval_seconds=60, requested_start_ts=1_799_999_700,
        requested_end_ts=1_800_000_000, bars=bars,
        fetched_at_ns=1_800_000_000_000_000_000,
        received_at_ns=1_800_000_000_000_000_001,
        provider_mapping_status=mapping, entitlement_status=entitlement,
    )
    # Receipt qualification is calculated by the validator. The supplied flag is
    # intentionally asserted to prevent a fixture accidentally claiming a lie.
    assert receipt.historical_bars_qualified is False
    return A200RuntimeBatch.from_history(row["instrument_id"], "yahoo", checked, receipt)


def test_candidate_history_is_carried_without_runtime_promotion():
    batch = _batch()
    result = assess_runtime_eligibility(
        batch, canonical_identity_verified=False, live_feed_qualified=False,
    )
    assert batch.receipt.instrument_id == batch.instrument_id
    assert batch.receipt.provider == batch.provider
    assert not result.eligible
    assert set(result.reasons) == {
        "canonical_identity_unverified", "provider_mapping_unverified",
        "provider_entitlement_unverified", "historical_bars_unqualified",
        "live_feed_unqualified",
    }
    assert result.execution_authorized is False


@pytest.mark.parametrize("value", ["UNVERIFIED", 1, object()])
def test_truthy_non_booleans_cannot_pass_eligibility_gates(value):
    batch = _batch()
    result = assess_runtime_eligibility(
        batch, canonical_identity_verified=value, live_feed_qualified=value,
    )
    assert "canonical_identity_unverified" in result.reasons
    assert "live_feed_unqualified" in result.reasons
    assert result.eligible is False


def test_manual_receipt_cannot_use_non_boolean_historical_qualification():
    batch = _batch()
    forged_receipt = replace(batch.receipt, historical_bars_qualified="yes")
    with pytest.raises(ValueError, match="must be a boolean"):
        A200RuntimeBatch.from_history(batch.instrument_id, batch.provider, batch.bars, forged_receipt)


def test_receipt_cannot_be_reassigned_to_another_catalog_instrument():
    batch = _batch()
    with pytest.raises(ValueError, match="does not match its receipt"):
        A200RuntimeBatch.from_history("different-instrument", batch.provider, batch.bars, batch.receipt)


def test_same_length_substituted_bars_are_rejected_by_receipt_checksum():
    batch = _batch()
    tampered = (Bar(batch.bars[0].ts, batch.bars[0].o, batch.bars[0].h,
                    batch.bars[0].l, batch.bars[0].c + 0.01, batch.bars[0].v),)
    with pytest.raises(ValueError, match="do not match the validated receipt checksum"):
        A200RuntimeBatch.from_history(batch.instrument_id, batch.provider, tampered, batch.receipt)


def test_mutable_input_sequence_is_copied_into_immutable_batch():
    batch = _batch()
    input_bars = list(batch.bars)
    copied = A200RuntimeBatch(batch.instrument_id, batch.provider, input_bars, batch.receipt)
    input_bars[0] = Bar(input_bars[0].ts, input_bars[0].o, input_bars[0].h,
                        input_bars[0].l, input_bars[0].c + 0.01, input_bars[0].v)
    assert isinstance(copied.bars, tuple)
    assert copied.bars[0] == batch.bars[0]


def test_empty_or_incomplete_history_batch_is_rejected():
    batch = _batch()
    with pytest.raises(ValueError, match="non-empty"):
        A200RuntimeBatch.from_history(batch.instrument_id, batch.provider, (), replace(batch.receipt, row_count=0))


@pytest.mark.parametrize("timestamp", [1_799_999_700.5, 1_799_999_700.0, "1799999700", True])
def test_timestamp_coercion_cannot_reuse_a_validated_receipt(timestamp):
    batch = _batch()
    altered = replace(batch.bars[0], ts=timestamp)
    with pytest.raises(ValueError, match="timestamp must be an integer"):
        A200RuntimeBatch.from_history(batch.instrument_id, batch.provider, [altered], batch.receipt)


def test_non_bar_row_cannot_impersonate_validated_history():
    from types import SimpleNamespace

    batch = _batch()
    altered = SimpleNamespace(**vars(batch.bars[0]))
    with pytest.raises(ValueError, match="non-Bar"):
        A200RuntimeBatch.from_history(batch.instrument_id, batch.provider, [altered], batch.receipt)


@pytest.mark.parametrize("field", ["o", "h", "l", "c", "v"])
def test_numeric_strings_cannot_reuse_a_validated_receipt(field):
    batch = _batch()
    altered = replace(batch.bars[0], **{field: str(getattr(batch.bars[0], field))})
    with pytest.raises(ValueError, match="OHLCV must be numeric"):
        A200RuntimeBatch.from_history(batch.instrument_id, batch.provider, [altered], batch.receipt)


def test_unchanged_history_preserves_exact_receipt_and_bar_identity():
    batch = _batch()
    copied = A200RuntimeBatch.from_history(batch.instrument_id, batch.provider, batch.bars, batch.receipt)
    assert copied.receipt is batch.receipt
    assert copied.bars[0] is batch.bars[0]


def test_numeric_decimal_values_preserve_receipt_checksum_semantics():
    from decimal import Decimal

    batch = _batch()
    altered = replace(batch.bars[0], **{field: Decimal(str(getattr(batch.bars[0], field)))
                                      for field in ("o", "h", "l", "c", "v")})
    copied = A200RuntimeBatch.from_history(batch.instrument_id, batch.provider, [altered], batch.receipt)
    assert copied.bars[0] is altered
    assert copied.receipt is batch.receipt
