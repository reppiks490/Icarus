"""Real-data-only gauge tests against the exact committed Engine checkout."""
from __future__ import annotations

import os
from pathlib import Path
import unittest

from icarus_engine.engine_evidence_gauges import build_real_engine_evidence_gauges


ROOT = os.environ.get("ICARUS_ENGINE_REAL_ROOT")
COMMIT = os.environ.get("ICARUS_ENGINE_REAL_COMMIT")


@unittest.skipUnless(ROOT and COMMIT, "requires exact real Icarus-engine checkout")
class RealEngineEvidenceGaugeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.value = build_real_engine_evidence_gauges(
            Path(ROOT),
            expected_commit=COMMIT,
        )

    def test_real_evidence_identity_and_no_edge_claim(self):
        self.assertEqual(self.value["producer_commit"], COMMIT)
        self.assertEqual(self.value["provider_current_collected_rows"], 63_531)
        self.assertEqual(self.value["sec_fact_rows"], 16_000)
        self.assertEqual(self.value["sec_filing_rows"], 2_380)
        self.assertEqual(self.value["native_run_id"], "native-40610466093-1")
        self.assertIsNone(self.value["aggregate_edge_score"])
        self.assertFalse(self.value["edge_claim_allowed"])
        self.assertFalse(self.value["automatic_model_promotion"])
        self.assertFalse(self.value["production_decision_authorized"])
        self.assertFalse(self.value["execution_authorized"])

    def test_real_sentinel_health_gauges_match_committed_counts(self):
        gauges = self.value["gauges"]
        ok = gauges["sentinel_health_ok"]
        bad = gauges["sentinel_blocked_or_failing"]
        self.assertEqual((ok["numerator"], ok["denominator"], ok["value_pct"]), (38, 86, 44.19))
        self.assertEqual((bad["numerator"], bad["denominator"], bad["value_pct"]), (43, 86, 50.0))
        self.assertEqual(ok["direction"], "higher_is_better")
        self.assertEqual(bad["direction"], "lower_is_better")

    def test_real_provider_delivery_gauge_is_not_catalog_completeness(self):
        gauge = self.value["gauges"]["provider_substantive_delivery"]
        self.assertEqual((gauge["numerator"], gauge["denominator"]), (3, 14))
        self.assertEqual(gauge["value_pct"], 21.43)
        self.assertIn("not completeness", gauge["interpretation"].lower())

    def test_real_native_and_crossrepo_gates_are_verified(self):
        gauges = self.value["gauges"]
        self.assertEqual(gauges["native_lane_verified"]["value_pct"], 100.0)
        self.assertEqual(gauges["interrepo_acceptance_verified"]["value_pct"], 100.0)
        self.assertEqual(gauges["sec_edgar_manifest_integrity"]["value_pct"], 100.0)

    def test_every_gauge_explicitly_denies_trading_edge_and_execution(self):
        for gauge in self.value["gauges"].values():
            self.assertFalse(gauge["trading_edge_metric"])
            self.assertFalse(gauge["execution_authorized"])
            self.assertGreater(gauge["denominator"], 0)


if __name__ == "__main__":
    unittest.main()
