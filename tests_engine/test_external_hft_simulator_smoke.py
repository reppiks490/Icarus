"""Synthetic-only HFTBacktest native runtime smoke safety regressions."""
from __future__ import annotations

import hashlib
import importlib.util
import unittest
from unittest.mock import patch

from icarus_engine.external_hft_simulator_smoke import (
    COLUMNS, FIXTURE_CONTRACT, NativeSmokeError, PINNED_HFTBACKTEST_VERSION,
    _assert_event_dtype, _fixture, _runtime, run_synthetic_native_smoke,
)


class OfflineContractTests(unittest.TestCase):
    def test_embedded_fixture_is_deterministic_and_no_vendor_data(self):
        raw = _fixture()
        self.assertEqual(raw, _fixture())
        self.assertEqual(len(raw.splitlines()), 6)
        self.assertEqual(raw.count(FIXTURE_CONTRACT.encode()), 5)
        self.assertEqual(len(hashlib.sha256(raw).hexdigest()), 64)
        self.assertNotIn(b"order_id", raw)

    def test_version_is_pinned(self):
        self.assertEqual(PINNED_HFTBACKTEST_VERSION, "2.4.4")

    def test_missing_dependency_refused_not_downloaded(self):
        with patch("icarus_engine.external_hft_simulator_smoke.import_module",
                   side_effect=ImportError("not installed")):
            with self.assertRaisesRegex(NativeSmokeError, "no auto-install"):
                _runtime()

    def test_mismatched_version_refused(self):
        class FakeHft:
            __version__ = "99.0"
        with patch("icarus_engine.external_hft_simulator_smoke.import_module",
                   side_effect=[FakeHft(), object(), object()]):
            with self.assertRaisesRegex(NativeSmokeError, "unapproved"):
                _runtime()

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy optional in stdlib suite")
    def test_numpy_dtype_abi_mismatch_refused(self):
        import numpy as np
        correct = np.dtype([
            ("ev", "<u8"), ("exch_ts", "<i8"), ("local_ts", "<i8"),
            ("px", "<f8"), ("qty", "<f8"), ("order_id", "<u8"),
            ("ival", "<i8"), ("fval", "<f8"),
        ], align=True)
        _assert_event_dtype(np, correct, correct)
        # NPY readback drops the dtype's 'align=True' flag but keeps ABI offsets.
        unaligned_metadata = np.dtype([(name, correct.fields[name][0])
                                       for name in COLUMNS], align=False)
        self.assertFalse(unaligned_metadata.isalignedstruct)
        _assert_event_dtype(np, unaligned_metadata, correct)
        wrong = np.dtype([(key, "<i8") for key in COLUMNS], align=True)
        with self.assertRaisesRegex(NativeSmokeError, "mismatch"):
            _assert_event_dtype(np, correct, wrong)
        with self.assertRaisesRegex(NativeSmokeError, "mismatch"):
            _assert_event_dtype(np, wrong, correct)

    @unittest.skipUnless(importlib.util.find_spec("hftbacktest"), "Pinned HFTBacktest optional")
    def test_actual_pinned_runtime_executes_no_orders_on_synthetic_fixture(self):
        report = run_synthetic_native_smoke()
        self.assertEqual(report["status"], "SYNTHETIC_NATIVE_RUNTIME_SMOKE_ONLY")
        self.assertEqual(report["rows_source_verified"], 5)
        self.assertEqual(report["fixture_events_scheduled_before_probe"], 3)
        self.assertEqual(report["order_submissions"], 0)
        self.assertTrue(report["native_simulator_invoked"])
        self.assertTrue(report["upstream_event_dtype_parity_verified"])
        self.assertEqual(report["synthetic_best_bid"], 15000.25)
        self.assertEqual(report["synthetic_best_ask"], 15000.50)
        for key in ("book_snapshot_verified", "source_authenticity_verified",
                    "entitlement_verified", "queue_latency_fee_models_calibrated",
                    "empirical_fill_quality_verified", "protected_holdout_approved",
                    "training_approved", "execution_authorized"):
            self.assertIs(report[key], False)
        self.assertEqual(report["authority_granted"], "NONE")


if __name__ == "__main__":
    unittest.main()
