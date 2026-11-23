"""Phase 21: observed-byte claims NEVER become confirmed fills or licensed data."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from icarus_engine.omnigenesis.contracts import identity
from icarus_engine.omnigenesis.historical_paper import run_historical_paper_replay


def example(seed=0, rows=160, receipt_lag_seconds=90):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = []
    price = 10000
    for i in range(rows):
        opened = start + timedelta(minutes=i)
        closed = opened + timedelta(seconds=50)
        received = closed + timedelta(seconds=receipt_lag_seconds - 50)
        # Toy OHLC fixture only, explicitly not an exchange historical feed.
        next_price = max(100, price + (4 if i // 16 % 2 == 0 else -4) + ((i + seed) % 5 - 2))
        bars.append({
            "bar_id": f"t-{i:05d}",
            "opened_at": opened.isoformat(),
            "closed_at": closed.isoformat(),
            "received_at": received.isoformat(),
            "open_ticks": price,
            "high_ticks": max(price, next_price) + 2,
            "low_ticks": min(price, next_price) - 2,
            "close_ticks": next_price,
        })
        price = next_price
    return {
        "schema_version": "icarus-omnigenesis-historical-paper-v1",
        "evidence": {
            "asset": "NQ", "source_commit": "a" * 40,
            "provider": "OPERATOR-FABRICATED-TEST",
            "license_reference": "NOT-AN-EXCHANGE-FEED",
            "captured_at": (start + timedelta(minutes=rows + 4)).isoformat(),
            "declared_sha256": identity({"bars": bars}),
        },
        "bars": bars,
        "strategy": {"kind": "SMA_CROSS", "fast": 3, "slow": 12, "direction": "trend"},
        "execution": {"contracts": 1, "tick_value_cents": 125,
                      "fee_per_contract_cents": 250, "slippage_ticks": 2,
                      "latency_bars": 1},
        "risk": {"initial_cash_cents": 20_000_000, "max_loss_cents": 5_000_000,
                 "max_drawdown_cents": 5_000_000, "max_order_events": 100},
    }


def digest(spec):
    spec["evidence"]["declared_sha256"] = identity({"bars": spec["bars"]})
    return spec


def test_historical_late_receipts_delay_entries_and_preserve_causal_evidence():
    spec = example()
    report = run_historical_paper_replay(spec)
    assert report == run_historical_paper_replay(spec)
    assert report["receipt_id"] == identity({k: v for k, v in report.items()
                                            if k != "receipt_id"})
    assert report["evidence_kind"] == "OPERATOR_CLAIMED_BARS_HYPOTHETICAL_FILLS"
    assert report["actual_exchange_fills_verified"] is False
    assert report["profitability_verified"] is False
    assert report["provider_license_verified"] is False
    assert report["source_authenticity_verified"] is False
    assert report["authority"]["execution_authorized"] is False
    assert report["broker_order_count"] == 0
    assert report["modeled_results"]["extra_causality_delay_bars"] > 0
    assert report["modeled_results"]["final_position_contracts"] == 0
    assert report["terminal_settlement_is_model_quote"] is True
    assert report["bar_count"] == len(spec["bars"])


def test_no_extra_delay_when_receipts_arrive_before_next_open():
    rapid = run_historical_paper_replay(example(receipt_lag_seconds=51))
    late = run_historical_paper_replay(example(receipt_lag_seconds=90))
    assert rapid["modeled_results"]["extra_causality_delay_bars"] == 0
    assert late["modeled_results"]["extra_causality_delay_bars"] > 0
    assert rapid["bars_sha256"] != late["bars_sha256"]


@pytest.mark.parametrize("mutate,pattern", [
    (lambda s: s["bars"][0].update(close_ticks=5555), "SHA-256 mismatch"),
    (lambda s: s["evidence"].update(source_commit="signed"), "source commit"),
    (lambda s: s["evidence"].update(declared_sha256="!"), "SHA-256"),
    (lambda s: s["bars"][1].update(bar_id="t-00000"), "duplicate bar ID"),
    (lambda s: s["bars"][0].update(open_ticks=True), "integer"),
    (lambda s: s["bars"][0].update(high_ticks=1), "inconsistent"),
    (lambda s: s["bars"][2].update(received_at="2025-01-01T00:00:00Z"), "bar not available"),
    (lambda s: s["bars"][1].update(opened_at=s["bars"][0]["opened_at"]), "non-increasing"),
    (lambda s: s["bars"][4].update(received_at=s["bars"][3]["received_at"]), "out-of-order"),
    (lambda s: s["bars"][0].update(extra_private_token="NO"), "bar fields"),
    (lambda s: s.update(broker_credentials="FORBIDDEN"), "schema"),
])
def test_rejects_forged_receipts_inconsistent_ohlc_and_broker_surface(mutate, pattern):
    spec = example()
    mutate(spec)
    with pytest.raises(ValueError, match=pattern):
        run_historical_paper_replay(spec)


def test_same_bytes_matching_operator_hash_cannot_claim_externally_verified():
    spec = example(seed=33)
    spec["bars"][7]["close_ticks"] += 1
    spec["bars"][7]["high_ticks"] += 1
    digest(spec)
    report = run_historical_paper_replay(spec)
    assert report["bars_sha256"] == spec["evidence"]["declared_sha256"]
    assert report["source_commit_verified"] is False
    assert report["provider_license_verified"] is False
    assert report["actual_exchange_fills_verified"] is False
    assert report["production_qualified"] is False


def test_all_historical_inputs_are_immutable_and_reproducible():
    spec = example(seed=1)
    before = deepcopy(spec)
    first = run_historical_paper_replay(spec)
    second = run_historical_paper_replay(spec)
    assert spec == before
    assert first == second


def test_late_last_risk_exit_not_claimed_as_executed_fill():
    spec = example(rows=140)
    spec["risk"]["max_drawdown_cents"] = 1
    spec["risk"]["max_loss_cents"] = 1
    report = run_historical_paper_replay(spec)
    assert report["actual_exchange_fills_verified"] is False
    assert report["modeled_results"]["forced_flat_at_end"] is True
    assert report["terminal_settlement_is_model_quote"] is True
    assert report["modeled_results"]["max_mark_to_market_drawdown_cents"] >= 0
