"""Adversarial tests for Phase 17 operator-supplied market-byte intake.

All fixtures are local and fabricated. Their passing does not authenticate
any provider or establish market edge.
"""
import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from icarus_engine.omnigenesis.data_intake import inspect_market_tape


T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def ts(minutes):
    return (T0 + timedelta(minutes=minutes)).isoformat()


def fixture(tmp_path):
    rows = []
    for i, minute in enumerate((0, 1, 2, 10)):
        rows.append({
            "event_id": f"trade-{i}", "sequence": i + 1,
            "contract": "NQZ6" if i < 3 else "NQH7",
            "observed_at": ts(minute),
            "received_at": (T0 + timedelta(minutes=minute, milliseconds=4)).isoformat(),
            "event_type": "trade", "side": "buy" if i % 2 else "sell",
            "price_ticks": 10000 + i, "quantity": i + 1,
        })
    tape = tmp_path / "operator.jsonl"
    write_rows(tape, rows)
    manifest = {
        "schema_version": "icarus-omnigenesis-market-manifest-v1",
        "dataset_id": "operator-research-fixture",
        "provider": "TEST ONLY",
        "venue": "TEST VENUE",
        "asset": "NQ",
        "source_category": "TRADES_NORMALIZED",
        "license_reference": "FAKE-FIXTURE-NO-VENDOR-CLAIM",
        "expected_sha256": hashlib.sha256(tape.read_bytes()).hexdigest(),
        "expected_records": len(rows),
        "contracts": [
            {"symbol": "NQZ6", "start_at": ts(-2), "end_at": ts(5), "tick_size": "0.25"},
            {"symbol": "NQH7", "start_at": ts(5), "end_at": ts(15), "tick_size": "0.25"},
        ],
        "capture_cutoff": ts(20),
    }
    return tape, manifest, rows


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def update_digest(path, manifest, rows):
    write_rows(path, rows)
    manifest["expected_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()


def test_reproducible_receipt_and_zero_vendor_authority(tmp_path):
    tape, manifest, rows = fixture(tmp_path)
    first = inspect_market_tape(tape, manifest)
    assert first == inspect_market_tape(tape, manifest)
    assert first["record_count"] == 4
    assert first["contract_count"] == 2
    assert first["min_receive_lag_us"] == 4000
    assert first["max_receive_lag_us"] == 4000
    assert first["source_authenticity_verified"] is False
    assert first["provider_license_verified"] is False
    assert first["exchange_sequence_completeness_verified"] is False
    assert first["production_qualified"] is False
    assert first["authority"]["execution_authorized"] is False
    assert "trade-0" not in json.dumps(first)
    assert set(first["event_kind_counts"]) == {"trade"}


def test_modified_bytes_fail_closed(tmp_path):
    tape, manifest, rows = fixture(tmp_path)
    rows[0]["quantity"] += 1
    write_rows(tape, rows)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        inspect_market_tape(tape, manifest)


@pytest.mark.parametrize("field,value,pattern", [
    ("event_id", "trade-1", "duplicate event"),
    ("price_ticks", True, "integer tick price"),
    ("quantity", 0, "quantity"),
    ("contract", "UNLISTED", "undeclared"),
    ("side", "flat", "side"),
    ("received_at", ts(-1), "future record"),
])
def test_adversarial_rows(tmp_path, field, value, pattern):
    tape, manifest, rows = fixture(tmp_path)
    rows[0][field] = value
    update_digest(tape, manifest, rows)
    with pytest.raises(ValueError, match=pattern):
        inspect_market_tape(tape, manifest)


def test_roll_interval_and_overlap_rejected(tmp_path):
    tape, manifest, rows = fixture(tmp_path)
    rows[3]["contract"] = "NQZ6"
    update_digest(tape, manifest, rows)
    with pytest.raises(ValueError, match="roll interval"):
        inspect_market_tape(tape, manifest)
    tape, manifest, rows = fixture(tmp_path)
    manifest["contracts"][1]["start_at"] = ts(4)
    with pytest.raises(ValueError, match="overlapping roll"):
        inspect_market_tape(tape, manifest)


def test_monotonic_receive_time_and_sequence(tmp_path):
    tape, manifest, rows = fixture(tmp_path)
    rows[1]["observed_at"] = rows[0]["observed_at"]
    rows[1]["received_at"] = rows[0]["received_at"]
    rows[1]["sequence"] = rows[0]["sequence"]
    update_digest(tape, manifest, rows)
    with pytest.raises(ValueError, match="out-of-order"):
        inspect_market_tape(tape, manifest)


def test_bounds_and_no_symlink(tmp_path):
    tape, manifest, rows = fixture(tmp_path)
    with pytest.raises(ValueError, match="byte budget"):
        inspect_market_tape(tape, manifest, max_bytes=10)
    with pytest.raises(ValueError, match="record budget"):
        inspect_market_tape(tape, manifest, max_records=3)
    alias = tmp_path / "alias.jsonl"
    alias.symlink_to(tape)
    with pytest.raises(ValueError, match="non-symlink"):
        inspect_market_tape(alias, manifest)


def test_duplicate_json_key_rejected(tmp_path):
    tape, manifest, rows = fixture(tmp_path)
    first = json.dumps(rows[0])
    damaged = first[:-1] + ',"quantity":100}'
    data = damaged + "\n" + "".join(json.dumps(x) + "\n" for x in rows[1:])
    tape.write_text(data, encoding="utf-8")
    manifest["expected_sha256"] = hashlib.sha256(tape.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="invalid JSONL"):
        inspect_market_tape(tape, manifest)


def test_captured_after_cutoff_and_unsupported_source(tmp_path):
    tape, manifest, rows = fixture(tmp_path)
    manifest["capture_cutoff"] = ts(9)
    with pytest.raises(ValueError, match="outside capture"):
        inspect_market_tape(tape, manifest)
    tape, manifest, rows = fixture(tmp_path)
    manifest["source_category"] = "REAL_VERIFIED_MBO"
    with pytest.raises(ValueError, match="source category"):
        inspect_market_tape(tape, manifest)


def test_manifest_missing_or_bad_tick_and_count(tmp_path):
    tape, manifest, rows = fixture(tmp_path)
    bad = copy.deepcopy(manifest)
    bad["expected_records"] = 5
    with pytest.raises(ValueError, match="declared record count"):
        inspect_market_tape(tape, bad)
    bad = copy.deepcopy(manifest)
    bad["contracts"][0]["tick_size"] = "0.00000000001"
    with pytest.raises(ValueError, match="tick size"):
        inspect_market_tape(tape, bad)
    bad = copy.deepcopy(manifest)
    bad.pop("license_reference")
    with pytest.raises(ValueError, match="manifest schema"):
        inspect_market_tape(tape, bad)


def test_sequence_regression_rejected_even_when_receive_time_increases(tmp_path):
    """An increasing wall clock cannot conceal an older contract sequence."""
    tape, manifest, rows = fixture(tmp_path)
    assert rows[2]["received_at"] > rows[1]["received_at"]
    rows[2]["sequence"] = rows[1]["sequence"] - 1
    update_digest(tape, manifest, rows)
    with pytest.raises(ValueError, match="per-contract sequence"):
        inspect_market_tape(tape, manifest)


def test_separate_futures_contracts_may_restart_normalized_sequence(tmp_path):
    """Contract switches are not falsely treated as a global order channel."""
    tape, manifest, rows = fixture(tmp_path)
    rows[3]["sequence"] = 1
    update_digest(tape, manifest, rows)
    receipt = inspect_market_tape(tape, manifest)
    assert receipt["contract_count"] == 2
    assert receipt["record_count"] == 4


def test_receive_time_cannot_go_backwards_when_sequence_increases(tmp_path):
    tape, manifest, rows = fixture(tmp_path)
    rows[2]["observed_at"] = rows[2]["received_at"] = rows[0]["observed_at"]
    rows[2]["sequence"] = 99
    update_digest(tape, manifest, rows)
    with pytest.raises(ValueError, match="received timestamp"):
        inspect_market_tape(tape, manifest)
