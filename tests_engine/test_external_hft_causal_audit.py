"""Offline synthetic source-anchored HFT L2 causal-readiness audit regressions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from icarus_engine.external_hft_stage import stage_mbp_events
from icarus_engine.external_hft_numpy import pack_verified_l2
from icarus_engine.external_hft_causal_audit import (
    BLOCKERS, CausalAuditError, audit_causal_l2, main,
)
from icarus_engine.external_hft_verify import L2VerificationError
from icarus_engine.external_hft_native_verify import NativeVerificationError

HEADER = "sequence,contract_id,kind,side,exchange_ts_ns,local_ts_ns,price,quantity\n"
ROWS = (
    "1,NQH2026,depth_update,bid,1700000000000000000,1700000000000001000,15000.25,2\n"
    "2,NQH2026,depth_update,ask,1700000000000000100,1700000000000001200,15000.50,3\n"
    "3,NQH2026,trade,buy,1700000000000000200,1700000000000001300,15000.50,1\n"
    "4,NQH2026,depth_update,bid,1700000000000000300,1700000000000001400,15000.25,0\n"
    "5,NQH2026,depth_update,ask,1700000000000000400,1700000000000001500,15000.75,2\n"
)


class CausalAuditTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "source.csv"
        self.staging = self.root / "stage"
        self.native = self.root / "native"
        self.source.write_text(HEADER + ROWS, encoding="utf-8")
        self.rebuild()

    def options(self):
        return dict(expected_contract_id="NQH2026",
                    expected_source_id="synthetic_fixture",
                    expected_input_sha256=self.anchor,
                    expected_tick_size="0.25", expected_lot_size="1")

    def rebuild(self):
        self.anchor = hashlib.sha256(self.source.read_bytes()).hexdigest()
        if self.staging.exists():
            for file in self.staging.iterdir():
                file.unlink()
            self.staging.rmdir()
        if self.native.exists():
            for file in self.native.iterdir():
                file.unlink()
            self.native.rmdir()
        stage_mbp_events(self.source, self.staging,
                         contract_id="NQH2026", source_id="synthetic_fixture",
                         tick_size="0.25", lot_size="1")
        pack_verified_l2(self.source, self.staging, self.native, **self.options())

    def go(self, **kwargs):
        args = self.options()
        args.update(kwargs)
        return audit_causal_l2(self.source, self.staging, self.native, **args)

    def test_all_rows_asof_partial_book_and_zero_level_removal(self):
        report = self.go()
        self.assertEqual(report["status"], "REPLAY_READINESS_BLOCKED")
        self.assertEqual(report["rows_examined"], 5)
        self.assertEqual(report["depth_updates"], 4)
        self.assertEqual(report["trades"], 1)
        self.assertEqual(report["events_with_observed_two_sided_levels"], 2)
        self.assertEqual(report["trades_without_observed_two_sided_levels"], 0)
        self.assertEqual(report["active_observed_bid_levels_at_end"], 0)
        self.assertEqual(report["active_observed_ask_levels_at_end"], 2)
        self.assertEqual(report["minimum_positive_observed_spread_ticks"], 1)
        self.assertEqual(report["observed_locked_or_crossed_events"], 0)
        self.assertEqual(report["as_of_clock"], "local_ts_ns")
        self.assertEqual(report["max_consecutive_exchange_gap_ns"], 100)
        self.assertEqual(report["max_consecutive_arrival_gap_ns"], 200)
        self.assertEqual(report["min_observed_arrival_lag_ns"], 1000)
        self.assertEqual(report["max_observed_arrival_lag_ns"], 1100)
        self.assertEqual(report["sum_observed_arrival_lag_ns"], 5400)

    def test_every_readiness_gate_remains_blocked(self):
        r = self.go()
        self.assertEqual(r["blocking_gates"], list(BLOCKERS))
        self.assertIn("INITIAL_FULL_BOOK_SNAPSHOT_UNAVAILABLE", r["blocking_gates"])
        self.assertIn("HFTBACKTEST_SIMULATOR_NOT_EXECUTED", r["blocking_gates"])
        for key in ("book_snapshot_verified", "venue_nbbo_verified",
                    "queue_position_verified", "simulator_executed",
                    "empirical_fill_quality_verified", "training_approved",
                    "execution_authorized"):
            self.assertIs(r[key], False)
        self.assertEqual(r["authority_granted"], "NONE")
        self.assertIn("PARTIAL_OBSERVED_LEVELS", r["book_state_scope"])

    def test_optional_latency_threshold_diagnostic_not_authorization(self):
        r = self.go(diagnostic_latency_threshold_ns=1000)
        self.assertEqual(r["events_above_diagnostic_latency_threshold"], 4)
        self.assertEqual(r["diagnostic_latency_threshold_ns"], 1000)
        self.assertFalse(r["simulator_executed"])
        self.assertEqual(self.go()["events_above_diagnostic_latency_threshold"], None)

    def test_bad_latency_threshold_refused(self):
        for value in (-1, 0, True, 1.5, "1000", 2**63):
            with self.subTest(value=value):
                with self.assertRaises(CausalAuditError):
                    self.go(diagnostic_latency_threshold_ns=value)

    def test_crossed_observed_levels_diagnostic_is_not_proof_of_venue_book(self):
        self.source.write_text(HEADER + ROWS.replace(
            "15000.25,2\n", "15000.75,2\n"))
        self.rebuild()
        r = self.go()
        self.assertGreaterEqual(r["observed_locked_or_crossed_events"], 2)
        self.assertFalse(r["venue_nbbo_verified"])
        self.assertEqual(r["status"], "REPLAY_READINESS_BLOCKED")

    def test_trade_without_both_observed_sides_is_counted(self):
        lines = ROWS.splitlines(keepends=True)
        # One trade occurs before any depth updates; sequences remain strict.
        trade = lines[2].replace("3,NQH2026", "1,NQH2026").replace(
            "1700000000000000200,1700000000000001300",
            "1700000000000000000,1700000000000001000")
        bid = lines[0].replace("1,NQH2026", "2,NQH2026").replace(
            "1700000000000000000,1700000000000001000",
            "1700000000000000100,1700000000000001200")
        ask = lines[1].replace("2,NQH2026", "3,NQH2026").replace(
            "1700000000000000100,1700000000000001200",
            "1700000000000000200,1700000000000001300")
        self.source.write_text(HEADER + trade + bid + ask, encoding="utf-8")
        self.rebuild()
        self.assertEqual(self.go()["trades_without_observed_two_sided_levels"], 1)

    def test_one_sided_feed_cannot_be_treated_as_full_book(self):
        self.source.write_text(HEADER + ROWS.splitlines(keepends=True)[0])
        self.rebuild()
        r = self.go()
        self.assertEqual(r["events_with_observed_two_sided_levels"], 0)
        self.assertIsNone(r["minimum_positive_observed_spread_ticks"])
        self.assertIn("INITIAL_FULL_BOOK_SNAPSHOT_UNAVAILABLE", r["blocking_gates"])

    def test_original_source_tamper_refused(self):
        self.source.write_text(HEADER + ROWS.replace("15000.25,2", "15000.75,2"))
        with self.assertRaises(L2VerificationError):
            self.go()

    def test_native_binary_tamper_refused_even_with_rehashed_manifest(self):
        binary = self.native / "hft-events.npy"
        data = bytearray(binary.read_bytes())
        data[-64 + 24] ^= 1
        binary.write_bytes(data)
        manifest = self.native / "native_manifest.json"
        obj = json.loads(manifest.read_text())
        obj["npy_sha256"] = hashlib.sha256(data).hexdigest()
        manifest.write_text(json.dumps(obj))
        with self.assertRaises(NativeVerificationError):
            self.go()

    def test_independent_original_sha_anchor_required(self):
        with self.assertRaises(L2VerificationError):
            self.go(expected_input_sha256="0" * 64)

    def test_all_inputs_remain_unchanged(self):
        before = {p: p.read_bytes() for p in (
            self.source, self.staging / "manifest.json",
            self.staging / "hft-events.csv", self.native / "native_manifest.json",
            self.native / "hft-events.npy")}
        self.go()
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_full_10020_event_feed_no_sample_ceiling(self):
        with self.source.open("w", encoding="utf-8") as f:
            f.write(HEADER)
            for seq in range(1, 10021):
                t = 1700000000000000000 + seq * 1000
                f.write(f"{seq},NQH2026,depth_update,bid,{t},{t+200},15000.25,2\n")
        self.rebuild()
        r = self.go()
        self.assertEqual(r["rows_examined"], 10020)
        self.assertEqual(r["depth_updates"], 10020)
        self.assertEqual(r["active_observed_bid_levels_at_end"], 1)
        self.assertEqual(r["events_with_observed_two_sided_levels"], 0)

    def test_cli_receipt_is_read_only(self):
        with patch("builtins.print") as printer:
            self.assertEqual(main([
                "--source", str(self.source),
                "--staging", str(self.staging),
                "--native-dir", str(self.native),
                "--contract-id", "NQH2026",
                "--source-id", "synthetic_fixture",
                "--expected-input-sha256", self.anchor,
                "--tick-size", "0.25", "--lot-size", "1",
                "--diagnostic-latency-threshold-ns", "1000",
            ]), 0)
            printer.assert_called_once()


if __name__ == "__main__":
    unittest.main()
