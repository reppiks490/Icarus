"""Isolated native HFTBacktest temporal parity and future-leak regressions."""
from __future__ import annotations

import hashlib
import importlib.util
import unittest
from unittest.mock import patch

from icarus_engine.external_hft_simulator_smoke import _fixture, NativeSmokeError
from icarus_engine.external_hft_temporal_parity import (
    STEP_EARLY_NS, STEP_FULL_NS, TemporalParityError,
    _assert_same, _future_variant, _replay, run_synthetic_temporal_parity,
)


class OfflineContractTests(unittest.TestCase):
    def test_future_mutation_preserves_header_and_first_three_events(self):
        before = _fixture().splitlines()
        after = _future_variant().splitlines()
        self.assertEqual(len(before), 6)
        self.assertEqual(before[:4], after[:4])
        self.assertNotEqual(before[4:], after[4:])
        self.assertEqual(before[4].split(b",")[2], b"depth_update")
        self.assertEqual(after[4].split(b",")[-1], b"0")
        self.assertEqual(after[5].split(b",")[-1], b"0")
        self.assertNotEqual(hashlib.sha256(_fixture()).digest(),
                            hashlib.sha256(_future_variant()).digest())

    def test_probes_are_ordered_before_last_event(self):
        self.assertEqual(STEP_EARLY_NS, 2_500_000_000)
        self.assertEqual(STEP_FULL_NS, 3_500_000_000)
        self.assertLess(STEP_EARLY_NS, STEP_FULL_NS)
        self.assertLess(STEP_FULL_NS, 4_000_000_000)

    def test_mismatched_native_replay_states_refused(self):
        with self.assertRaisesRegex(TemporalParityError, "diverged"):
            _assert_same((15000.25, 15000.50, 0.0),
                         (15000.00, 15000.50, 0.0), "future event leakage")

    def test_invalid_time_slices_refused_without_native_order_calls(self):
        for slices in ([], [0], [-1], [True], [1.0]):
            with self.subTest(slices=slices):
                with self.assertRaisesRegex(TemporalParityError, "time slices"):
                    _replay(None, None, slices)

    def test_missing_hftbacktest_is_not_auto_installed(self):
        with patch("icarus_engine.external_hft_temporal_parity._runtime",
                   side_effect=NativeSmokeError("pinned HFTBacktest required")):
            with self.assertRaisesRegex(NativeSmokeError, "pinned"):
                run_synthetic_temporal_parity()

    @unittest.skipUnless(importlib.util.find_spec("hftbacktest"),
                         "Pinned HFTBacktest optional in ordinary tests")
    def test_actual_native_rust_simulator_temporal_parity(self):
        report = run_synthetic_temporal_parity()
        self.assertEqual(report["status"], "SYNTHETIC_NATIVE_TEMPORAL_PARITY_ONLY")
        self.assertEqual(report["hftbacktest_version"], "2.4.4")
        self.assertEqual(report["rows_per_fixture"], 5)
        self.assertTrue(report["early_time_slicing_parity"])
        self.assertTrue(report["full_time_slicing_parity"])
        self.assertTrue(report["synthetic_future_event_nonleak"])
        self.assertTrue(report["synthetic_late_mutation_effect_observed"])
        self.assertEqual(report["synthetic_early_bid"], 15000.25)
        self.assertEqual(report["synthetic_early_ask"], 15000.50)
        self.assertEqual(report["order_submissions"], 0)
        self.assertNotEqual(report["original_native_sha256"],
                            report["future_mutation_native_sha256"])
        for key in ("initial_book_snapshot_verified",
                    "licensed_source_authenticity_verified",
                    "exchange_clock_sync_verified",
                    "queue_latency_fee_models_calibrated",
                    "empirical_fill_quality_verified",
                    "protected_holdout_approved",
                    "training_approved", "execution_authorized"):
            self.assertIs(report[key], False)
        self.assertEqual(report["authority_granted"], "NONE")


if __name__ == "__main__":
    unittest.main()
