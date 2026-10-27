"""Offline contract tests: synthetic bytes are not market data or vendor evidence."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from icarus_engine.external_quant_catalog import CatalogRejected, verify_catalog, SCHEMA

REPO = "reppiks490/Icarus"
REV = "a" * 40


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "research").mkdir()
        self.payload = b"synthetic fixture only\n"
        (self.root / "research" / "candidate.csv").write_bytes(self.payload)
        self.artifact = {
            "artifact_id": "candidate-1", "path": "research/candidate.csv",
            "sha256": hashlib.sha256(self.payload).hexdigest(),
            "size_bytes": len(self.payload), "source_repository": "microsoft/qlib",
            "source_revision": "b" * 40, "license_id": "MIT",
            "rights_verified": False, "source_authenticity_verified": False,
            "holdout_approved": False, "execution_authorized": False,
        }
        self.manifest = {"schema_version": SCHEMA, "producer_repository": REPO,
                         "producer_revision": REV, "artifacts": [self.artifact]}
        self.save()

    def save(self):
        (self.root / "catalog.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def verify(self):
        return verify_catalog(self.root, expected_producer_repository=REPO,
                              expected_producer_revision=REV)

    def rejected(self):
        with self.assertRaises(CatalogRejected):
            self.verify()

    def test_valid_quarantined_receipt(self):
        result = self.verify()
        self.assertEqual(result["artifacts_rechecked"], 1)
        self.assertEqual(result["bytes_rechecked"], len(self.payload))
        self.assertEqual(result["distinct_source_revisions"], 1)
        self.assertEqual(result["authority_granted"], "NONE")
        self.assertEqual(result["research_admission"], "QUARANTINED")
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["training_approved"])
        self.assertEqual(result, self.verify())

    def test_multi_artifact_no_sampling(self):
        for i in range(50):
            data = bytes([i]) * 100
            name = f"research/file{i}.bin"
            (self.root / name).write_bytes(data)
            item = dict(self.artifact, artifact_id=f"id-{i}", path=name,
                        sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data))
            self.manifest["artifacts"].append(item)
        self.save()
        result = self.verify()
        self.assertEqual(result["artifacts_rechecked"], 51)
        self.assertEqual(result["bytes_rechecked"], len(self.payload) + 5000)

    def test_modified_bytes_rejected(self):
        (self.root / "research/candidate.csv").write_bytes(b"changed")
        self.rejected()

    def test_same_size_tamper_rejected(self):
        (self.root / "research/candidate.csv").write_bytes(b"!" * len(self.payload))
        self.rejected()

    def test_wrong_declared_size(self):
        self.artifact["size_bytes"] += 1
        self.save()
        self.rejected()

    def test_sha_malformed(self):
        self.artifact["sha256"] = "0" * 63
        self.save()
        self.rejected()

    def test_false_authority_required(self):
        for field in ("rights_verified", "source_authenticity_verified",
                      "holdout_approved", "execution_authorized"):
            with self.subTest(field=field):
                self.artifact[field] = True
                self.save()
                self.rejected()
                self.artifact[field] = False

    def test_missing_flag_rejected(self):
        del self.artifact["execution_authorized"]
        self.save()
        self.rejected()

    def test_unexpected_field_rejected(self):
        self.artifact["provider_secret"] = "not-a-secret"
        self.save()
        self.rejected()

    def test_unsafe_paths_rejected(self):
        for bad in ("../candidate.csv", "/etc/passwd", "research/../candidate.csv",
                    "research\\candidate.csv", "research//candidate.csv",
                    "research/.env", "research/%2e%2e/candidate.csv"):
            with self.subTest(bad=bad):
                self.artifact["path"] = bad
                self.save()
                self.rejected()

    def test_self_reference_rejected(self):
        self.artifact["path"] = "catalog.json"
        self.save()
        self.rejected()

    def test_symlink_file_rejected(self):
        link = self.root / "research" / "link.csv"
        try:
            link.symlink_to(self.root / "research" / "candidate.csv")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        self.artifact["path"] = "research/link.csv"
        self.save()
        self.rejected()

    def test_symlink_ancestor_rejected(self):
        link = self.root / "alias"
        try:
            link.symlink_to(self.root / "research", target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        self.artifact["path"] = "alias/candidate.csv"
        self.save()
        self.rejected()

    def test_symlink_manifest_rejected(self):
        source = self.root / "source.json"
        (self.root / "catalog.json").rename(source)
        try:
            (self.root / "catalog.json").symlink_to(source)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        self.rejected()

    def test_duplicate_id_and_path_rejected(self):
        self.manifest["artifacts"].append(dict(self.artifact))
        self.save()
        self.rejected()
        self.manifest["artifacts"][1]["artifact_id"] = "other"
        self.save()
        self.rejected()

    def test_duplicate_json_key_rejected(self):
        (self.root / "catalog.json").write_text('{"schema_version":"x","schema_version":"y"}')
        self.rejected()

    def test_empty_artifacts_rejected(self):
        self.manifest["artifacts"] = []
        self.save()
        self.rejected()

    def test_wrong_producer_rejected(self):
        with self.assertRaises(CatalogRejected):
            verify_catalog(self.root, expected_producer_repository=REPO,
                           expected_producer_revision="c" * 40)

    def test_invalid_revision_rejected(self):
        self.artifact["source_revision"] = "short"
        self.save()
        self.rejected()

    def test_license_missing_rejected(self):
        self.artifact["license_id"] = ""
        self.save()
        self.rejected()

    def test_bool_is_not_size(self):
        self.artifact["size_bytes"] = True
        self.save()
        self.rejected()

    def test_manifest_root_symlink_rejected(self):
        link = self.root.parent / (self.root.name + "-link")
        try:
            link.symlink_to(self.root, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        self.addCleanup(link.unlink)
        with self.assertRaises(CatalogRejected):
            verify_catalog(link, expected_producer_repository=REPO,
                           expected_producer_revision=REV)


if __name__ == "__main__":
    unittest.main()
