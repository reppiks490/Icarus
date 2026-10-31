"""Metadata-only tests. No synthetic market inputs or external source execution."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from icarus_engine.external_capability_context import ContextError, build_context

OWNER_SHA = "d5f1bd43e217f2ad7009bab1cff09e9fd422ecc5"
ENGINE_SHA = "5c9d9921ce7a8fa9479d59b72047514f7a51c50c"


def inventory():
    return {
        "schema_version": "icarus-external-source-inventory-v1",
        "source_archive": {"filename": "ICARUS-GitHub-source-snapshots.tar.zst",
                           "verified_actual_archive_sha256": True, "sha256": "a" * 64},
        "counts": {"distinct_identity_union": 2, "verified_snapshot_repositories": 1,
                   "named_without_snapshot": 1, "snapshot_not_named": 0,
                   "installed_verified": 0, "actually_invoked_verified": 0,
                   "exact_head_integration_verified": 0},
        "repo_entries": [
            {"repository": "morluto/rea", "source_commit": "a" * 40,
             "source_archive": "ICARUS-GitHub-source-snapshots.tar.zst",
             "archive_directory": "source-repos/rea", "snapshot_verified": True,
             "installed": "unverified", "actually_used_by_icarus": "unverified",
             "exact_head_integration_ci": "unverified", "source_license_filenames": ["LICENSE"],
             "source_list_membership": ["all", "starred"]},
            {"repository": "NVIDIA/OpenShell", "source_commit": None, "source_archive": None,
             "archive_directory": None, "snapshot_verified": False,
             "installed": "unverified", "actually_used_by_icarus": "unverified",
             "exact_head_integration_ci": "unverified", "source_license_filenames": [],
             "source_list_membership": ["all"]},
        ],
    }


def federation():
    return {"schema_version": "icarus-federated-repo-evidence-v1",
            "authority": "RESEARCH_EVIDENCE_ONLY", "repositories": [
                {"repository": "reppiks490/Icarus-engine", "role": "canonical_data",
                 "data_authority": "CANONICAL", "evidence_paths": ["config/data_ingestion_manifest.json"]}
            ]}


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.inv = inventory()
        self.fed = federation()

    def run_context(self):
        a = self.root / "owner.json"
        b = self.root / "engine.json"
        a.write_text(json.dumps(self.inv), encoding="utf-8")
        b.write_text(json.dumps(self.fed), encoding="utf-8")
        return build_context(a, b, owner_revision=OWNER_SHA, engine_revision=ENGINE_SHA)

    def test_source_context_never_grants_usage(self):
        ctx = self.run_context()
        self.assertEqual(ctx["counts"]["discovered"], 2)
        self.assertEqual(ctx["counts"]["accessible_source_snapshots"], 1)
        self.assertEqual(ctx["counts"]["deep_source_api_inspected_verified"], 0)
        self.assertEqual(ctx["counts"]["actually_invoked_verified"], 0)
        self.assertEqual(ctx["counts"]["blocked_for_verified_usage"], 2)
        self.assertFalse(ctx["policy"]["market_edge_claim_allowed"])
        self.assertFalse(ctx["external_repositories"][0]["execution_authorized"])
        self.assertFalse(ctx["owner_inventory"]["archive_reverified_by_this_consumer"])

    def test_candidate_mapping_is_not_runtime_use(self):
        rows = {r["repository"]: r for r in self.run_context()["external_repositories"]}
        self.assertIn("sandboxing", rows["morluto/rea"]["candidate_subsystems_not_verified"])
        self.assertFalse(rows["morluto/rea"]["actually_invoked_by_icarus"])

    def test_reject_forged_invocation(self):
        self.inv["repo_entries"][0]["actually_used_by_icarus"] = "verified"
        with self.assertRaisesRegex(ContextError, "runtime usage"):
            self.run_context()

    def test_reject_forged_ci(self):
        self.inv["repo_entries"][0]["exact_head_integration_ci"] = "verified"
        with self.assertRaisesRegex(ContextError, "exact-head"):
            self.run_context()

    def test_reject_forged_install(self):
        self.inv["repo_entries"][0]["installed"] = "installed"
        with self.assertRaisesRegex(ContextError, "installed claim"):
            self.run_context()

    def test_reject_duplicate_identity_case_insensitive(self):
        self.inv["repo_entries"][1]["repository"] = "MORLUTO/REA"
        with self.assertRaisesRegex(ContextError, "duplicate external"):
            self.run_context()

    def test_reject_path_escape(self):
        self.inv["repo_entries"][0]["archive_directory"] = "source-repos/../escape"
        with self.assertRaisesRegex(ContextError, "archive directory"):
            self.run_context()

    def test_reject_unverified_source_commit(self):
        self.inv["repo_entries"][1]["source_commit"] = "a" * 40
        with self.assertRaisesRegex(ContextError, "unverified snapshot"):
            self.run_context()

    def test_reject_count_mismatch(self):
        self.inv["counts"]["distinct_identity_union"] = 3
        with self.assertRaisesRegex(ContextError, "count mismatch"):
            self.run_context()

    def test_reject_bad_authority(self):
        self.fed["authority"] = "EXECUTION_AUTHORIZED"
        with self.assertRaisesRegex(ContextError, "authority"):
            self.run_context()

    def test_reject_unpinned_checkout(self):
        a = self.root / "owner.json"
        b = self.root / "engine.json"
        a.write_text(json.dumps(self.inv))
        b.write_text(json.dumps(self.fed))
        with self.assertRaisesRegex(ContextError, "pinned"):
            build_context(a, b, owner_revision="main", engine_revision=ENGINE_SHA)

    def test_reject_symlinked_input(self):
        target = self.root / "actual.json"
        target.write_text(json.dumps(self.inv))
        link = self.root / "owner.json"
        link.symlink_to(target)
        engine = self.root / "engine.json"
        engine.write_text(json.dumps(self.fed))
        with self.assertRaisesRegex(ContextError, "non-symlink"):
            build_context(link, engine, owner_revision=OWNER_SHA, engine_revision=ENGINE_SHA)

    def test_reject_duplicate_json_keys(self):
        owner = self.root / "owner.json"
        owner.write_text('{"schema_version":"x","schema_version":"y"}')
        engine = self.root / "engine.json"
        engine.write_text(json.dumps(self.fed))
        with self.assertRaisesRegex(ContextError, "duplicate JSON"):
            build_context(owner, engine, owner_revision=OWNER_SHA, engine_revision=ENGINE_SHA)

    def test_reject_nonfinite_json(self):
        owner = self.root / "owner.json"
        owner.write_text('{"x":NaN}')
        engine = self.root / "engine.json"
        engine.write_text(json.dumps(self.fed))
        with self.assertRaisesRegex(ContextError, "nonfinite"):
            build_context(owner, engine, owner_revision=OWNER_SHA, engine_revision=ENGINE_SHA)

    def test_reject_mismatched_snapshot_count(self):
        self.inv["counts"]["verified_snapshot_repositories"] = 2
        with self.assertRaisesRegex(ContextError, "snapshot count"):
            self.run_context()

    def test_reject_wrong_named_only_count(self):
        self.inv["counts"]["named_without_snapshot"] = 0
        with self.assertRaisesRegex(ContextError, "named-only"):
            self.run_context()

    def test_fork_aliases_share_one_source_commit(self):
        self.inv["repo_entries"][1].update({
            "repository": "reppiks490/rea", "source_commit": "a" * 40,
            "source_archive": "ICARUS-GitHub-source-snapshots.tar.zst",
            "archive_directory": "source-repos/reppiks490__rea", "snapshot_verified": True})
        self.inv["counts"].update({"verified_snapshot_repositories": 2, "named_without_snapshot": 0})
        ctx = self.run_context()
        self.assertEqual(ctx["counts"]["distinct_source_commits"], 1)
        self.assertEqual(ctx["counts"]["actually_invoked_verified"], 0)
        self.assertEqual(len(ctx["external_repositories"][0]["same_commit_identity_group"]), 2)

    def test_real_pinned_cross_repo_ledgers_when_available(self):
        owner = os.environ.get("ICARUS_OWNER_INVENTORY")
        engine = os.environ.get("ICARUS_ENGINE_FEDERATION")
        if not owner or not engine:
            self.skipTest("authentic cross-repository checkouts not configured")
        ctx = build_context(owner, engine, owner_revision=OWNER_SHA, engine_revision=ENGINE_SHA)
        self.assertEqual(ctx["counts"]["discovered"], 72)
        self.assertEqual(ctx["counts"]["accessible_source_snapshots"], 43)
        self.assertEqual(ctx["counts"]["actually_invoked_verified"], 0)
        self.assertEqual(ctx["counts"]["tested_exact_head_verified"], 0)
        self.assertEqual(ctx["counts"]["blocked_for_verified_usage"], 72)
        self.assertEqual(len(ctx["engine_federation"]["roles"]), 6)


if __name__ == "__main__":
    unittest.main()
