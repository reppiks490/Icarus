"""Untrusted handoff consumer contract, isolated and offline for every Python target."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from icarus_engine.external_research import export_qlib_staging, emit_quarantined_handoff
from icarus_engine.external_research_verify import (
    VerificationRejected, main, verify_candidate,
)

SOURCE = (
    "timestamp,contract_id,open,high,low,close,volume\n"
    "2026-01-05T14:30:00Z,NQH2026,100,102,98,101,6\n"
    "2026-01-05T14:35:00Z,NQH2026,101,103,100,102,9\n"
)
REPO = "reppiks490/Icarus"
REV = "a" * 40
AVAILABLE = "2026-01-06T00:00:00Z"


class VerifyCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "tape.csv"
        self.staging = self.base / "stage"
        self.source.write_text(SOURCE, encoding="utf-8")
        export_qlib_staging(
            self.source, self.staging, instrument="NQ",
            contract_id="NQH2026", bar_seconds=300,
            source_id="licensed_vendor", price_basis="raw",
        )
        emit_quarantined_handoff(
            self.staging, producer_repository=REPO,
            producer_revision=REV, available_at=AVAILABLE,
        )
        self.manifest = self.staging / "manifest.json"
        self.data = self.staging / "qlib-bars.csv"
        self.evidence = self.staging / "candidate_handoff" / "evidence_record.json"
        self.handoff = self.staging / "candidate_handoff" / "handoff.json"

    def verify(self, **overrides):
        args = dict(
            expected_producer_repository=REPO,
            expected_producer_revision=REV,
        )
        args.update(overrides)
        return verify_candidate(self.staging, **args)

    @staticmethod
    def read(path):
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def write(path, payload):
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n",
                        encoding="utf-8")

    def rehash(self):
        """Simulate an attacker capable of rewriting every *untrusted* hash."""
        manifest = self.read(self.manifest)
        evidence = self.read(self.evidence)
        handoff = self.read(self.handoff)
        out_hash = sha256(self.data.read_bytes()).hexdigest()
        manifest["export_sha256"] = out_hash
        evidence["payload"]["export_sha256"] = out_hash
        available = datetime.fromisoformat(
            evidence["available_at"].replace("Z", "+00:00")
        ).astimezone(timezone.utc)
        identity = sha256(
            f"{REPO}|{REV}|{manifest['source_sha256']}|"
            f"{out_hash}|{available.isoformat()}".encode()
        ).hexdigest()
        evidence["evidence_id"] = identity
        handoff["handoff_id"] = identity
        handoff["evidence_ids"] = [identity]
        self.write(self.manifest, manifest)
        self.write(self.evidence, evidence)
        hashes = {
            "qlib-bars.csv": out_hash,
            "manifest.json": sha256(self.manifest.read_bytes()).hexdigest(),
            "candidate_handoff/evidence_record.json": sha256(
                self.evidence.read_bytes()).hexdigest(),
        }
        for artifact in handoff["artifacts"]:
            artifact["hash"] = hashes[artifact["path"]]
        self.write(self.handoff, handoff)

    def test_valid_canonical_handoff_is_a_quarantined_read_only_receipt(self):
        before = {str(p): sha256(p.read_bytes()).hexdigest()
                  for p in (self.manifest, self.data, self.evidence, self.handoff)}
        result = self.verify()
        after = {str(p): sha256(p.read_bytes()).hexdigest()
                 for p in (self.manifest, self.data, self.evidence, self.handoff)}
        self.assertEqual(before, after)
        self.assertEqual(result["rows_rechecked"], 2)
        self.assertTrue(result["candidate_structurally_valid"])
        self.assertTrue(result["timestamps_and_ohlcv_rechecked"])
        self.assertFalse(result["provider_authenticity_verified"])
        self.assertFalse(result["approved_for_training"])
        self.assertFalse(result["approved_for_execution"])
        self.assertEqual(result["authority_granted"], "NONE")

    def test_correct_artifact_hash_is_not_enough_to_override_duplicate_bar(self):
        self.data.write_text(
            self.data.read_text() +
            "NQ,2026-01-05T14:35:00Z,101,103,100,102,9\n"
        )
        self.rehash()
        with self.assertRaisesRegex(VerificationRejected, "duplicate"):
            self.verify()

    def test_correct_artifact_hash_is_not_enough_to_override_bad_ohlc(self):
        self.data.write_text(
            self.data.read_text().replace("100,102,98,101,6", "100,99,98,101,6")
        )
        self.rehash()
        with self.assertRaisesRegex(VerificationRejected, "OHLCV"):
            self.verify()

    def test_recomputed_hash_cannot_hide_manifest_row_count_forgery(self):
        m = self.read(self.manifest)
        m["rows"] = 50
        self.write(self.manifest, m)
        self.rehash()
        with self.assertRaisesRegex(VerificationRejected, "row count"):
            self.verify()

    def test_recomputed_hash_cannot_hide_manifest_time_forgery(self):
        m = self.read(self.manifest)
        m["first_utc"] = "2026-01-05T14:25:00Z"
        self.write(self.manifest, m)
        self.rehash()
        with self.assertRaisesRegex(VerificationRejected, "timestamps"):
            self.verify()

    def test_tampering_unchanged_artifact_fails_integrity(self):
        self.data.write_bytes(self.data.read_bytes() + b"\n")
        with self.assertRaisesRegex(VerificationRejected, "checksum"):
            self.verify()

    def test_expected_repository_and_exact_commit_are_mandatory(self):
        for overrides in (
            {"expected_producer_repository": "some/other-repo"},
            {"expected_producer_revision": "b" * 40},
            {"expected_producer_revision": "main"},
        ):
            with self.subTest(overrides=overrides):
                with self.assertRaises(VerificationRejected):
                    self.verify(**overrides)

    def test_handoff_artifact_path_traversal_refused(self):
        obj = self.read(self.handoff)
        obj["artifacts"][0]["path"] = "../outside.csv"
        self.write(self.handoff, obj)
        with self.assertRaisesRegex(VerificationRejected, "artifact"):
            self.verify()

    def test_handoff_authority_escalation_denied(self):
        obj = self.read(self.handoff)
        obj["authority_granted"] = "RELEASE"
        self.write(self.handoff, obj)
        with self.assertRaisesRegex(VerificationRejected, "authority"):
            self.verify()

    def test_evidence_staleness_cannot_be_removed(self):
        evidence = self.read(self.evidence)
        evidence["quality"]["stale"] = False
        self.write(self.evidence, evidence)
        self.rehash()
        with self.assertRaisesRegex(VerificationRejected, "stale"):
            self.verify()

    def test_broker_decision_context_is_disallowed(self):
        evidence = self.read(self.evidence)
        evidence["decision_context_at"] = AVAILABLE
        self.write(self.evidence, evidence)
        self.rehash()
        with self.assertRaisesRegex(VerificationRejected, "decision"):
            self.verify()

    def test_denied_source_flags_are_not_editable_into_verified(self):
        manifest = self.read(self.manifest)
        manifest["source_authenticity_verified"] = True
        self.write(self.manifest, manifest)
        self.rehash()
        with self.assertRaisesRegex(VerificationRejected, "authority"):
            self.verify()

    def test_duplicate_json_keys_are_rejected(self):
        self.handoff.write_text('{"schema_version": "1", "schema_version":"2"}')
        with self.assertRaisesRegex(VerificationRejected, "duplicate JSON"):
            self.verify()

    def test_symlinked_candidate_artifact_cannot_escape_staging(self):
        other = self.base / "replacement.json"
        other.write_bytes(self.evidence.read_bytes())
        self.evidence.unlink()
        try:
            self.evidence.symlink_to(other)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation not available on this runner")
        with self.assertRaisesRegex(VerificationRejected, "regular file"):
            self.verify()

    def test_cli_success_is_read_only_and_offline(self):
        with patch("builtins.print") as printer:
            self.assertEqual(main([
                "--staging", str(self.staging),
                "--producer-repository", REPO,
                "--producer-revision", REV,
            ]), 0)
            printer.assert_called_once()
        self.assertEqual(len(list(self.staging.iterdir())), 3)


if __name__ == "__main__":
    unittest.main()
