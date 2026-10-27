"""Qlib input CSV preparation: no Qlib import, source download, model or broker."""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from icarus_engine.external_research import (
    emit_quarantined_handoff,
    export_qlib_staging,
)
from icarus_engine.external_qlib_prepare import main, prepare_qlib_csv
from icarus_engine.external_research_verify import VerificationRejected, verify_candidate


REPO = "reppiks490/Icarus"
REV = "a" * 40


class QlibPrepareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "input.csv"
        self.staging = self.root / "quarantine"
        self.prepared = self.root / "qlib_ready"
        self.create_bar_source(n=2, period=300)
        self.make_staging(period=300)

    def create_bar_source(self, n, period, contract="NQH2026"):
        start = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
        with self.source.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(["timestamp", "contract_id", "open", "high",
                             "low", "close", "volume"])
            for i in range(n):
                time = start + timedelta(seconds=i * period)
                writer.writerow([
                    time.isoformat().replace("+00:00", "Z"),
                    contract, 100, 103, 99, 102, i + 1,
                ])

    def make_staging(self, period, contract="NQH2026"):
        export_qlib_staging(
            self.source, self.staging,
            instrument="NQ", contract_id=contract,
            bar_seconds=period, source_id="approved_vendor",
            price_basis="raw",
        )
        emit_quarantined_handoff(
            self.staging, producer_repository=REPO,
            producer_revision=REV, available_at="2026-12-31T00:00:00Z",
        )

    def prepare(self, **kwargs):
        options = dict(
            expected_producer_repository=REPO,
            expected_producer_revision=REV,
        )
        options.update(kwargs)
        return prepare_qlib_csv(self.staging, self.prepared, **options)

    def test_prepares_actual_contract_csv_with_explicit_utc_provenance(self):
        rec = self.prepare()
        file = self.prepared / "qlib_input" / "NQH2026.csv"
        with file.open(newline="", encoding="utf-8") as f:
            records = list(csv.DictReader(f))
        self.assertEqual(
            list(records[0]),
            ["date", "open", "high", "low", "close", "volume", "factor"],
        )
        self.assertEqual(records[0]["date"], "2026-01-05 14:30:00")
        self.assertEqual(records[1]["date"], "2026-01-05 14:35:00")
        self.assertTrue(all(row["factor"] == "1" for row in records))
        self.assertEqual(rec["qlib_frequency"], "5min")
        self.assertEqual(rec["naive_datetime_interpretation"], "UTC")
        self.assertEqual(rec["qlib_csv_sha256"], sha256(file.read_bytes()).hexdigest())
        self.assertEqual(rec["rows"], 2)
        self.assertFalse(rec["native_qlib_binary_verified"])
        self.assertFalse(rec["model_trained"])
        self.assertFalse(rec["execution_authorized"])
        self.assertEqual(rec["authority_granted"], "NONE")

    def test_output_already_existing_is_not_overwritten(self):
        self.prepared.mkdir()
        keep = self.prepared / "important"
        keep.write_text("never touch")
        with self.assertRaisesRegex(VerificationRejected, "must not exist"):
            self.prepare()
        self.assertEqual(keep.read_text(), "never touch")

    def test_wrong_pinned_revision_is_rejected_before_write(self):
        with self.assertRaises(VerificationRejected):
            self.prepare(expected_producer_revision="b" * 40)
        self.assertFalse(self.prepared.exists())

    def test_hash_changed_after_consumer_check_is_rejected_before_publish(self):
        genuine = verify_candidate

        def tamper(*args, **kwargs):
            result = genuine(*args, **kwargs)
            path = self.staging / "qlib-bars.csv"
            path.write_bytes(path.read_bytes() + b"\n")
            return result

        with patch("icarus_engine.external_qlib_prepare.verify_candidate",
                   side_effect=tamper):
            with self.assertRaisesRegex(VerificationRejected, "source changed"):
                self.prepare()
        self.assertFalse(self.prepared.exists())

    def test_nonstandard_cadence_is_explicitly_refused(self):
        import shutil
        shutil.rmtree(self.staging)
        self.create_bar_source(n=2, period=420)
        self.make_staging(period=420)
        with self.assertRaisesRegex(VerificationRejected, "fixed-minute"):
            self.prepare()
        self.assertFalse(self.prepared.exists())

    def test_continuous_alias_is_refused_as_concrete_qlib_contract(self):
        import shutil
        shutil.rmtree(self.staging)
        self.create_bar_source(n=2, period=300, contract="NQ1!")
        self.make_staging(period=300, contract="NQ1!")
        with self.assertRaisesRegex(VerificationRejected, "concrete safe"):
            self.prepare()
        self.assertFalse(self.prepared.exists())

    def test_exporting_10k_bars_does_not_apply_arbitrary_sample_cap(self):
        import shutil
        shutil.rmtree(self.staging)
        self.create_bar_source(n=10005, period=300)
        self.make_staging(period=300)
        record = self.prepare()
        self.assertEqual(record["rows"], 10005)
        with (self.prepared / "qlib_input" / "NQH2026.csv").open(
            "r", encoding="utf-8", newline=""
        ) as f:
            self.assertEqual(sum(1 for _ in csv.reader(f)), 10006)

    def test_cli_can_prepare_without_importing_qlib(self):
        with patch("builtins.print") as emit:
            result = main([
                "--staging", str(self.staging),
                "--output", str(self.prepared),
                "--producer-repository", REPO,
                "--producer-revision", REV,
            ])
        self.assertEqual(result, 0)
        emit.assert_called_once()
        self.assertTrue((self.prepared / "prepare_manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
