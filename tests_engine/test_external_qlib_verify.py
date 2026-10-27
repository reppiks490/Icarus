"""Read-only native Qlib layout checks. Synthetic fixtures prove parser refusals only.

No test claims that a real installed Microsoft Qlib binary converter was run.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from icarus_engine.external_research import export_qlib_staging, emit_quarantined_handoff
from icarus_engine.external_qlib_prepare import prepare_qlib_csv
from icarus_engine.external_qlib_verify import (
    VerificationRejected, verify_qlib_binary, main,
)

REPO = "reppiks490/Icarus"
REV = "b" * 40
FIELDS = ("open", "high", "low", "close", "volume", "factor")


class NativeQlibVerificationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.input = self.root / "sample.csv"
        self.staged = self.root / "staging"
        self.prepared = self.root / "prepared"
        self.native = self.root / "native"
        self.write_input(2)
        self.generate_staging()
        self.handoff_id = json.loads(
            (self.prepared / "prepare_manifest.json").read_text()
        )["handoff_id"]
        self.build_mock_native_layout()

    def write_input(self, count):
        start = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
        with self.input.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(("timestamp", "contract_id", "open", "high", "low",
                             "close", "volume"))
            for i in range(count):
                stamp = (start + timedelta(minutes=5 * i)).isoformat().replace(
                    "+00:00", "Z"
                )
                writer.writerow((stamp, "NQH2026", 100 + i, 104 + i,
                                 99 + i, 103 + i, 10 + i))

    def generate_staging(self):
        export_qlib_staging(
            self.input, self.staged, instrument="NQ", contract_id="NQH2026",
            bar_seconds=300, source_id="attested_vendor", price_basis="raw",
        )
        emit_quarantined_handoff(
            self.staged, producer_repository=REPO,
            producer_revision=REV, available_at="2026-12-31T00:00:00Z",
        )
        prepare_qlib_csv(
            self.staged, self.prepared,
            expected_producer_repository=REPO,
            expected_producer_revision=REV,
        )

    def build_mock_native_layout(self):
        """A synthetic replica of documented Qlib little-endian float32 layout."""
        (self.native / "calendars").mkdir(parents=True)
        (self.native / "instruments").mkdir()
        features = self.native / "features" / "nqh2026"
        features.mkdir(parents=True)
        with (self.prepared / "qlib_input" / "NQH2026.csv").open(
            "r", encoding="utf-8", newline=""
        ) as f:
            rows = list(csv.DictReader(f))
        (self.native / "calendars" / "5min.txt").write_text(
            "".join(row["date"] + "\n" for row in rows), encoding="utf-8"
        )
        (self.native / "instruments" / "all.txt").write_text(
            f"NQH2026\t{rows[0]['date']}\t{rows[-1]['date']}\n",
            encoding="utf-8",
        )
        for field in FIELDS:
            data = struct.pack("<f", 0.0)
            data += b"".join(struct.pack("<f", float(row[field])) for row in rows)
            (features / f"{field}.5min.bin").write_bytes(data)

    def verify(self, **kw):
        args = {
            "expected_contract_id": "NQH2026",
            "expected_producer_revision": REV,
            "expected_producer_repository": REPO,
            "expected_handoff_id": self.handoff_id,
        }
        args.update(kw)
        return verify_qlib_binary(self.prepared, self.native, **args)

    def test_exact_calendar_instrument_and_every_feature_parity(self):
        before = sorted((p, p.read_bytes()) for p in self.native.rglob("*") if p.is_file())
        receipt = self.verify()
        after = sorted((p, p.read_bytes()) for p in self.native.rglob("*") if p.is_file())
        self.assertEqual(before, after)
        self.assertEqual(receipt["actual_contract_id"], "NQH2026")
        self.assertEqual(receipt["rows_rechecked"], 2)
        self.assertTrue(receipt["structural_binary_parity"])
        self.assertFalse(receipt["native_qlib_code_executed_by_this_tool"])
        self.assertFalse(receipt["vendor_authenticity_verified"])
        self.assertFalse(receipt["model_approved"])
        self.assertEqual(receipt["authority_granted"], "NONE")
        self.assertEqual(set(receipt["qlib_feature_digests"]), set(FIELDS))

    def test_pinned_revision_and_contract_are_mandatory(self):
        for arguments in (
            {"expected_contract_id": "NQM2026"},
            {"expected_producer_revision": "main"},
            {"expected_producer_revision": "c" * 40},
            {"expected_producer_repository": "attacker/other-repo"},
            {"expected_handoff_id": "e" * 64},
        ):
            with self.subTest(arguments=arguments):
                with self.assertRaises(VerificationRejected):
                    self.verify(**arguments)

    def test_calendar_can_never_omit_or_duplicate_times(self):
        path = self.native / "calendars" / "5min.txt"
        path.write_text("2026-01-05 14:30:00\n2026-01-05 14:30:00\n")
        with self.assertRaisesRegex(VerificationRejected, "calendar"):
            self.verify()

    def test_cross_contract_contamination_is_rejected(self):
        path = self.native / "instruments" / "all.txt"
        path.write_text(
            path.read_text() + "NQM2026\t2026-01-05 14:30:00\t2026-01-05 14:35:00\n"
        )
        with self.assertRaisesRegex(VerificationRejected, "instrument"):
            self.verify()

    def test_bin_corruption_is_detected_for_every_feature(self):
        for field in FIELDS:
            with self.subTest(field=field):
                path = self.native / "features" / "nqh2026" / f"{field}.5min.bin"
                original = path.read_bytes()
                path.write_bytes(original[:4] + struct.pack("<f", 999.0) + original[8:])
                with self.assertRaisesRegex(VerificationRejected, "parity mismatch"):
                    self.verify()
                path.write_bytes(original)

    def test_bin_lookahead_header_index_is_rejected(self):
        file = self.native / "features" / "nqh2026" / "close.5min.bin"
        payload = file.read_bytes()
        file.write_bytes(struct.pack("<f", 1.0) + payload[4:])
        with self.assertRaisesRegex(VerificationRejected, "calendar start index"):
            self.verify()

    def test_bin_wrong_length_is_rejected(self):
        file = self.native / "features" / "nqh2026" / "volume.5min.bin"
        file.write_bytes(file.read_bytes()[:-4])
        with self.assertRaisesRegex(VerificationRejected, "byte-length"):
            self.verify()

    def test_float32_rounding_is_not_falsely_rejected(self):
        path = self.native / "features" / "nqh2026" / "close.5min.bin"
        before = path.read_bytes()
        self.assertNotEqual(len(before), 0)
        self.assertEqual(self.verify()["rows_rechecked"], 2)

    def test_prepared_dataset_integrity_is_bound_before_binary_inspection(self):
        path = self.prepared / "qlib_input" / "NQH2026.csv"
        path.write_bytes(path.read_bytes() + b"corrupt\n")
        with self.assertRaisesRegex(VerificationRejected, "prepared CSV checksum"):
            self.verify()

    def test_nonzero_model_or_authority_flags_cannot_be_assumed_valid(self):
        manifest_path = self.prepared / "prepare_manifest.json"
        original = json.loads(manifest_path.read_text())
        for key in ("execution_authorized", "model_trained",
                    "provider_authenticity_verified", "native_qlib_binary_verified"):
            with self.subTest(key=key):
                manifest = dict(original)
                manifest[key] = True
                manifest_path.write_text(json.dumps(manifest))
                with self.assertRaises(VerificationRejected):
                    self.verify()

    def test_symlink_in_native_output_refused(self):
        path = self.native / "features" / "nqh2026" / "open.5min.bin"
        other = self.root / "external.bin"
        other.write_bytes(path.read_bytes())
        path.unlink()
        try:
            path.symlink_to(other)
        except (OSError, NotImplementedError):
            self.skipTest("No symlink support on runner")
        with self.assertRaisesRegex(VerificationRejected, "linked file"):
            self.verify()

    def test_cli_receipt_does_not_execute_third_party(self):
        with patch("builtins.print") as printer:
            self.assertEqual(main([
                "--prepared", str(self.prepared), "--qlib-dir", str(self.native),
                "--contract-id", "NQH2026", "--producer-revision", REV,
                "--producer-repository", REPO, "--handoff-id", self.handoff_id,
            ]), 0)
            printer.assert_called_once()

    def test_more_than_10000_bins_are_streamed_without_sample_ceiling(self):
        import shutil
        shutil.rmtree(self.staged)
        shutil.rmtree(self.prepared)
        shutil.rmtree(self.native)
        self.write_input(10007)
        self.generate_staging()
        self.handoff_id = json.loads(
            (self.prepared / "prepare_manifest.json").read_text()
        )["handoff_id"]
        self.build_mock_native_layout()
        self.assertEqual(self.verify()["rows_rechecked"], 10007)


if __name__ == "__main__":
    unittest.main()
