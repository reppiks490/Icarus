"""Workspace panel tests using actual committed Engine evidence when configured."""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from icarus_engine.workspace_intelligence_panels import WorkspaceIntelligencePanels


REAL_ROOT = os.environ.get("ICARUS_ENGINE_REAL_ROOT")
REAL_COMMIT = os.environ.get("ICARUS_ENGINE_REAL_COMMIT")


def panels(root: Path):
    port = SimpleNamespace(base_dir=str(root), runners={}, runner_list=lambda: [])
    runtime = SimpleNamespace(root=root, port=port)
    engines = SimpleNamespace()
    return WorkspaceIntelligencePanels(runtime, engines)


class WorkspaceEngineEvidenceBoundaryTests(unittest.TestCase):
    def test_unconfigured_panel_is_explicitly_unavailable_and_read_only(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ,
            {"ICARUS_ENGINE_EVIDENCE_ROOT": "", "ICARUS_ENGINE_EVIDENCE_COMMIT": ""},
            clear=False,
        ):
            value = panels(Path(td)).read("federation/engine-evidence", {})
        self.assertEqual(value["status"], "UNAVAILABLE")
        self.assertEqual(value["reason"], "ENGINE_EVIDENCE_CHECKOUT_NOT_CONFIGURED")
        self.assertFalse(value["synthetic_market_evidence_used"])
        self.assertFalse(value["execution_authorized"])

    @unittest.skipUnless(REAL_ROOT and REAL_COMMIT, "requires exact real Icarus-engine checkout")
    def test_workspace_panel_reads_actual_pinned_engine_evidence(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ,
            {
                "ICARUS_ENGINE_EVIDENCE_ROOT": REAL_ROOT,
                "ICARUS_ENGINE_EVIDENCE_COMMIT": REAL_COMMIT,
            },
            clear=False,
        ):
            obj = panels(Path(td))
            value = obj.read("federation/engine-evidence", {})
            self.assertNotIn("research", obj.__dict__)
            self.assertNotIn("learning", obj.__dict__)
        self.assertEqual(value["status"], "AVAILABLE")
        self.assertEqual(value["producer_commit"], REAL_COMMIT)
        self.assertEqual(value["provider"]["current_collected_rows"], 63_531)
        self.assertEqual(value["sec_edgar"]["fact_rows"], 16_000)
        self.assertEqual(value["sec_edgar"]["filing_rows"], 2_380)
        self.assertEqual(value["native_research"]["run_id"], "native-40610466093-1")
        self.assertIsNone(value["aggregate_edge_score"])
        self.assertFalse(value["edge_claim_allowed"])
        self.assertFalse(value["synthetic_market_evidence_used"])
        self.assertFalse(value["automatic_model_promotion"])
        self.assertFalse(value["production_decision_authorized"])
        self.assertFalse(value["execution_authorized"])
        self.assertGreater(len(value["blockers"]["provider_blocked"]), 0)
        self.assertGreater(len(value["blockers"]["source_consumption_blocked"]), 0)

    @unittest.skipUnless(REAL_ROOT and REAL_COMMIT, "requires exact real Icarus-engine checkout")
    def test_wrong_engine_revision_blocks_panel_instead_of_drifting(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ,
            {
                "ICARUS_ENGINE_EVIDENCE_ROOT": REAL_ROOT,
                "ICARUS_ENGINE_EVIDENCE_COMMIT": "0" * 40,
            },
            clear=False,
        ):
            value = panels(Path(td)).read("federation/engine-evidence", {})
        self.assertEqual(value["status"], "BLOCKED")
        self.assertEqual(value["reason"], "ENGINE_EVIDENCE_VALIDATION_FAILED")
        self.assertFalse(value["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
