"""Isolated, no-network regression contracts for external quant research staging."""
from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from icarus_engine.external_research import (
    ResearchAdmissionError,
    export_qlib_staging,
    installed_distributions,
    main,
)

HEADER = "timestamp,contract_id,open,high,low,close,volume\n"
GOOD = (
    "2026-01-05T14:30:00Z,NQH2026,100,104,99,103,15\n"
    "2026-01-05T14:35:00+00:00,NQH2026,103,105,101,102,20\n"
)


class ExternalResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input = self.root / "source.csv"
        self.output = self.root / "staging"
        self.input.write_text(HEADER + GOOD, encoding="utf-8")

    def export(self, **overrides):
        arguments = dict(
            instrument="NQ", contract_id="NQH2026", source_id="licensed_vendor",
            bar_seconds=300, price_basis="raw",
        )
        arguments.update(overrides)
        return export_qlib_staging(self.input, self.output, **arguments)

    def test_valid_raw_bars_produce_hash_bound_non_authoritative_manifest(self):
        from hashlib import sha256
        report = self.export()
        with (self.output / "qlib-bars.csv").open(newline="", encoding="utf-8") as data:
            records = list(csv.DictReader(data))
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["instrument"], "NQ")
        self.assertEqual(records[0]["datetime"], "2026-01-05T14:30:00Z")
        self.assertEqual(report["source_sha256"], sha256(self.input.read_bytes()).hexdigest())
        self.assertEqual(
            report["export_sha256"],
            sha256((self.output / "qlib-bars.csv").read_bytes()).hexdigest(),
        )
        self.assertEqual(report["rows"], 2)
        for denied in ("source_authenticity_verified", "entitlement_verified",
                       "roll_mapping_verified", "training_approved",
                       "execution_authorized"):
            self.assertIs(report[denied], False)

    def test_heikin_ashi_is_not_admissible_as_trade_prices(self):
        with self.assertRaisesRegex(ResearchAdmissionError, "Heikin"):
            self.export(price_basis="heikin_ashi")
        self.assertFalse(self.output.exists())

    def test_mixed_contract_rejected_without_partial_output(self):
        self.input.write_text(HEADER + GOOD.replace("NQH2026,103", "NQM2026,103"))
        with self.assertRaisesRegex(ResearchAdmissionError, "contract"):
            self.export()
        self.assertFalse(self.output.exists())

    def test_duplicate_bar_time_rejected(self):
        self.input.write_text(HEADER + GOOD.replace("14:35:00+00:00", "14:30:00+00:00"))
        with self.assertRaisesRegex(ResearchAdmissionError, "overlapping"):
            self.export()
        self.assertFalse(self.output.exists())

    def test_timeframe_mismatch_rejected(self):
        with self.assertRaisesRegex(ResearchAdmissionError, "overlapping"):
            self.export(bar_seconds=600)
        self.assertFalse(self.output.exists())

    def test_explicit_utc_required(self):
        self.input.write_text(HEADER + GOOD.replace("14:30:00Z", "14:30:00"))
        with self.assertRaisesRegex(ResearchAdmissionError, "UTC"):
            self.export()
        self.assertFalse(self.output.exists())

    def test_invalid_price_geometry_rejected(self):
        self.input.write_text(HEADER + GOOD.replace("100,104,99,103,15", "100,101,99,103,15"))
        with self.assertRaisesRegex(ResearchAdmissionError, "OHLCV"):
            self.export()
        self.assertFalse(self.output.exists())

    def test_nonfinite_price_and_negative_volume_rejected(self):
        for data in (GOOD.replace("100,104", "NaN,104"),
                     GOOD.replace("103,15", "103,-15")):
            with self.subTest(data=data):
                self.input.write_text(HEADER + data)
                with self.assertRaises(ResearchAdmissionError):
                    self.export()
                self.assertFalse(self.output.exists())

    def test_empty_or_bad_columns_rejected(self):
        for data in (HEADER, "time,contract_id,open,high,low,close,volume\n" + GOOD):
            with self.subTest(data=data):
                self.input.write_text(data)
                with self.assertRaises(ResearchAdmissionError):
                    self.export()
                self.assertFalse(self.output.exists())

    def test_existing_export_is_never_overwritten(self):
        self.output.mkdir()
        marker = self.output / "keep"
        marker.write_text("unchanged")
        with self.assertRaisesRegex(ResearchAdmissionError, "already exists"):
            self.export()
        self.assertEqual(marker.read_text(), "unchanged")

    def test_no_sample_ceiling_for_streamed_input(self):
        bar = "2026-01-05T14:{minute:02d}:00Z,NQH2026,100,101,99,100,1\n"
        lines = []
        from datetime import datetime, timedelta, timezone
        start = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
        for i in range(10020):
            ts = start + timedelta(minutes=5 * i)
            lines.append(f"{ts.isoformat().replace('+00:00', 'Z')},NQH2026,100,101,99,100,1\n")
        self.input.write_text(HEADER + "".join(lines))
        report = self.export()
        self.assertEqual(report["rows"], 10020)

    def test_probe_does_not_import_third_party_or_claim_runtime(self):
        with patch("icarus_engine.external_research.metadata.version", side_effect=Exception("unexpected")):
            # An exception from metadata itself is not silently called a success.
            with self.assertRaises(Exception):
                installed_distributions()
        with patch("icarus_engine.external_research.metadata.version", return_value="1.2.3"):
            data = installed_distributions()
        self.assertTrue(data["qlib"]["metadata_present"])
        self.assertFalse(data["qlib"]["runtime_verified"])
        self.assertFalse(data["qlib"]["icarus_integrated"])

    def test_cli_probe_works_without_network(self):
        with patch("icarus_engine.external_research.metadata.version", return_value="1.2.3"):
            with patch("builtins.print") as printer:
                self.assertEqual(main(["probe"]), 0)
                printer.assert_called_once()


if __name__ == "__main__":
    unittest.main()
