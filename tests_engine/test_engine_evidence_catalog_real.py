"""Integration tests against the actual pinned Icarus-engine evidence checkout.

No synthetic fixtures are created. Dedicated CI supplies ICARUS_ENGINE_REAL_ROOT and
ICARUS_ENGINE_REAL_COMMIT and validates the committed peer evidence in place.
"""
from __future__ import annotations

import os
from pathlib import Path
import unittest

from icarus_engine.engine_evidence_catalog import (
    EvidenceCatalogError,
    build_real_engine_evidence_catalog,
)


ROOT = os.environ.get("ICARUS_ENGINE_REAL_ROOT")
COMMIT = os.environ.get("ICARUS_ENGINE_REAL_COMMIT")


@unittest.skipUnless(ROOT and COMMIT, "requires pinned real Icarus-engine checkout")
class RealEngineEvidenceCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(ROOT)
        cls.catalog = build_real_engine_evidence_catalog(
            cls.root,
            expected_commit=COMMIT,
        )

    def test_exact_real_engine_commit_and_authority_boundary(self):
        value = self.catalog
        self.assertEqual(value["producer_repository"], "reppiks490/Icarus-engine")
        self.assertEqual(value["producer_commit"], COMMIT)
        self.assertFalse(value["raw_payloads_copied"])
        self.assertEqual(value["provider_requests_made"], 0)
        self.assertFalse(value["new_collection_performed"])
        self.assertFalse(value["automatic_model_promotion"])
        self.assertFalse(value["production_decision_authorized"])
        self.assertFalse(value["execution_authorized"])

    def test_real_provider_receipts_are_consumed_not_invented(self):
        snapshot = self.catalog["provider_snapshot"]
        self.assertGreater(snapshot["provider_count"], 0)
        self.assertGreater(snapshot["current_collected_rows"], 0)
        self.assertIn("massive", snapshot["providers"])
        self.assertGreaterEqual(snapshot["providers"]["massive"]["collected_rows"], 20_000)
        self.assertTrue(snapshot["providers"]["massive"]["substantive_work_performed"])
        self.assertIn("fred", snapshot["providers"])
        self.assertGreater(snapshot["providers"]["fred"]["collected_rows"], 0)
        self.assertGreater(len(snapshot["substantive_providers"]), 0)

    def test_real_sec_edgar_committed_manifest_is_bound(self):
        sec = self.catalog["sec_edgar"]
        self.assertEqual(sec["fact_rows"], 16_000)
        self.assertEqual(sec["filing_rows"], 2_380)
        self.assertEqual(sec["ticker_count"], 8)
        self.assertEqual(len(sec["facts_sha256"]), 64)
        self.assertEqual(len(sec["filing_sha256"]), 64)

    def test_real_native_research_and_interrepo_acceptance_are_visible(self):
        native = self.catalog["native_research"]
        self.assertEqual(native["run_id"], "native-40610466093-1")
        self.assertEqual(set(native["lanes"]), {"aion", "daedalus", "flow", "macro", "omega"})
        for lane in native["lanes"].values():
            self.assertEqual(lane["status"], "VERIFIED")
            self.assertTrue(lane["substantive_work_performed"])
            self.assertIsInstance(lane["receipt_path"], str)
        acceptance = self.catalog["interrepo_acceptance"]
        self.assertEqual(acceptance["status"], "VERIFIED_PRIOR_PACKET")
        self.assertIsInstance(acceptance["accepted_peer_packet_id"], str)

    def test_real_sentinel_health_is_preserved_instead_of_hidden(self):
        counts = self.catalog["sentinel_counts"]
        self.assertGreater(counts.get("OK", 0), 0)
        self.assertGreater(counts.get("BLOCKED", 0), 0)
        self.assertGreater(counts.get("FAILING", 0), 0)

    def test_wrong_peer_commit_is_rejected_before_consumption(self):
        with self.assertRaisesRegex(EvidenceCatalogError, "checkout mismatch"):
            build_real_engine_evidence_catalog(
                self.root,
                expected_commit="0" * 40,
            )


if __name__ == "__main__":
    unittest.main()
