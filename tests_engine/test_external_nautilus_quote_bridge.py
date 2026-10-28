"""Synthetic-only regression coverage for the quarantined NautilusTrader quote bridge."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path
import tempfile
import unittest

from icarus_engine.external_nautilus_quote_bridge import (
    QuoteAdmissionError, stage_quotes, verify_native, VERSION,
)

HEADER = ("sequence,instrument_id,event_ts_ns,arrival_ts_ns,"
          "bid_price,ask_price,bid_size,ask_size\n")
ROWS = (
    "1,NQH2026.CME,1700000000000000000,1700000000000001000,15000.25,15000.50,2,3\n"
    "2,NQH2026.CME,1700000000000000100,1700000000000001100,15000.50,15000.75,4,5\n"
    "3,NQH2026.CME,1700000000000000200,1700000000000001200,15000.25,15000.50,2,1\n"
)
REV = "a" * 40
try:
    NATIVE_AVAILABLE = importlib.metadata.version("nautilus_trader") == VERSION
except importlib.metadata.PackageNotFoundError:
    NATIVE_AVAILABLE = False


class QuoteBridgeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "authorized_quotes.csv"
        self.staging = self.root / "staging"
        self.source.write_text(HEADER + ROWS, encoding="utf-8")

    def stage(self, **overrides):
        params = {
            "instrument_id": "NQH2026.CME",
            "source_id": "independent_receipt",
            "producer_revision": REV,
            "tick_size": "0.25",
            "lot_size": "1",
        }
        params.update(overrides)
        return stage_quotes(self.source, self.staging, **params)

    def verify(self, result, **overrides):
        params = {
            "instrument_id": "NQH2026.CME",
            "source_id": "independent_receipt",
            "producer_revision": REV,
            "expected_source_sha256": result["manifest"]["source_sha256"],
            "expected_export_sha256": result["manifest"]["export_sha256"],
            "expected_manifest_sha256": result["manifest_sha256"],
        }
        params.update(overrides)
        return verify_native(self.source, self.staging, **params)

    def test_manifest_hashes_and_denied_authority(self):
        result = self.stage()
        m = result["manifest"]
        self.assertEqual(m["rows"], 3)
        self.assertEqual(m["instrument_id"], "NQH2026.CME")
        self.assertEqual(m["source_sha256"], hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual(m["export_sha256"], hashlib.sha256(
            (self.staging / "quotes.jsonl").read_bytes()).hexdigest())
        self.assertEqual(result["manifest_sha256"], hashlib.sha256(
            (self.staging / "manifest.json").read_bytes()).hexdigest())
        for key in ("source_authenticity_verified", "license_verified",
                    "initial_book_snapshot_verified", "fill_parity_verified",
                    "training_approved", "execution_authorized"):
            self.assertIs(m[key], False)
        self.assertEqual(len((self.staging / "quotes.jsonl").read_text().splitlines()), 3)

    def test_reject_duplicate_sequence(self):
        self.source.write_text(HEADER + ROWS.replace("2,NQH2026", "1,NQH2026"))
        with self.assertRaisesRegex(QuoteAdmissionError, "sequence"):
            self.stage()
        self.assertFalse(self.staging.exists())

    def test_reject_reordered_event_clock(self):
        self.source.write_text(HEADER + ROWS.replace(
            "1700000000000000100,1700000000000001100",
            "1699999999999999000,1700000000000001100"))
        with self.assertRaisesRegex(QuoteAdmissionError, "nonmonotonic"):
            self.stage()

    def test_reject_reordered_arrival_clock(self):
        self.source.write_text(HEADER + ROWS.replace(
            "1700000000000000100,1700000000000001100",
            "1700000000000000100,1700000000000000500"))
        with self.assertRaisesRegex(QuoteAdmissionError, "nonmonotonic"):
            self.stage()

    def test_reject_negative_latency(self):
        self.source.write_text(HEADER + ROWS.replace(
            "1700000000000001000,15000.25",
            "1699999999999999999,15000.25"))
        with self.assertRaisesRegex(QuoteAdmissionError, "latency"):
            self.stage()

    def test_reject_mixed_contract(self):
        self.source.write_text(HEADER + ROWS.replace("2,NQH2026.CME", "2,NQM2026.CME"))
        with self.assertRaisesRegex(QuoteAdmissionError, "contracts"):
            self.stage()

    def test_reject_continuous_futures_alias(self):
        with self.assertRaisesRegex(QuoteAdmissionError, "physical"):
            self.stage(instrument_id="NQ1!.CME")

    def test_reject_crossed_quote(self):
        self.source.write_text(HEADER + ROWS.replace("15000.25,15000.50", "15000.75,15000.50"))
        with self.assertRaisesRegex(QuoteAdmissionError, "crossed"):
            self.stage()

    def test_reject_off_tick_price(self):
        self.source.write_text(HEADER + ROWS.replace("15000.25", "15000.26"))
        with self.assertRaisesRegex(QuoteAdmissionError, "grid"):
            self.stage()

    def test_reject_off_lot_size(self):
        with self.assertRaisesRegex(QuoteAdmissionError, "grid"):
            self.stage(lot_size="3")

    def test_reject_negative_nan_and_scientific(self):
        for price in ("-1.00", "NaN", "Infinity", "1e9", "0.00"):
            with self.subTest(price=price):
                self.source.write_text(HEADER + ROWS.replace("15000.25", price))
                with self.assertRaises(QuoteAdmissionError):
                    self.stage()
                self.assertFalse(self.staging.exists())

    def test_reject_native_fixed_point_overflow(self):
        self.source.write_text(HEADER + ROWS.replace("15000.25,15000.50", "9999999999999999.25,9999999999999999.50"))
        with self.assertRaisesRegex(QuoteAdmissionError, "fixed-point range"):
            self.stage()
        self.assertFalse(self.staging.exists())

    def test_reject_mismatched_price_precision(self):
        self.source.write_text(HEADER + ROWS.replace("15000.50", "15000.5"))
        with self.assertRaisesRegex(QuoteAdmissionError, "precision"):
            self.stage()

    def test_reject_mismatched_size_precision(self):
        self.source.write_text(HEADER + ROWS.replace(",2,3\n", ",2.0,3\n"))
        with self.assertRaisesRegex(QuoteAdmissionError, "precision"):
            self.stage()

    def test_reject_oversized_single_line_without_row_cap(self):
        self.source.write_text(HEADER + "9" * 5000 + "\n")
        with self.assertRaisesRegex(QuoteAdmissionError, "oversized physical CSV line"):
            self.stage()
        self.assertFalse(self.staging.exists())

    def test_reject_empty_source(self):
        self.source.write_text(HEADER)
        with self.assertRaisesRegex(QuoteAdmissionError, "empty"):
            self.stage()

    def test_reject_overwrite(self):
        self.staging.mkdir()
        (self.staging / "keep").write_text("safe")
        with self.assertRaisesRegex(QuoteAdmissionError, "already exists"):
            self.stage()
        self.assertEqual((self.staging / "keep").read_text(), "safe")

    def test_reject_symlinked_source(self):
        linked = self.root / "linked.csv"
        linked.symlink_to(self.source)
        with self.assertRaisesRegex(QuoteAdmissionError, "symlink"):
            stage_quotes(linked, self.staging, instrument_id="NQH2026.CME",
                         source_id="independent_receipt", producer_revision=REV,
                         tick_size="0.25", lot_size="1")

    def test_streams_more_than_ten_thousand_records(self):
        with self.source.open("w", encoding="utf-8") as handle:
            handle.write(HEADER)
            for n in range(1, 10022):
                ts = 1700000000000000000 + n * 1000
                handle.write(f"{n},NQH2026.CME,{ts},{ts+500},"
                             "15000.25,15000.50,2,3\n")
        result = self.stage()
        self.assertEqual(result["manifest"]["rows"], 10021)

    @unittest.skipUnless(NATIVE_AVAILABLE, "native NautilusTrader 1.221.0 not installed")
    def test_native_roundtrip_all_records(self):
        result = self.stage()
        receipt = self.verify(result)
        self.assertEqual(receipt["rows_verified"], 3)
        self.assertEqual(receipt["status"], "NATIVE_QUOTE_ROUNDTRIP_STRUCTURAL_ONLY")
        self.assertFalse(receipt["native_backtest_executed"])
        self.assertFalse(receipt["fills_verified"])
        self.assertFalse(receipt["execution_authorized"])

    @unittest.skipUnless(NATIVE_AVAILABLE, "native NautilusTrader 1.221.0 not installed")
    def test_native_readback_exceeds_ten_thousand_records(self):
        with self.source.open("w", encoding="utf-8") as handle:
            handle.write(HEADER)
            for n in range(1, 10022):
                ts = 1700000000000000000 + n * 1000
                handle.write(f"{n},NQH2026.CME,{ts},{ts+500},"
                             "15000.25,15000.50,2,3\n")
        receipt = self.verify(self.stage())
        self.assertEqual(receipt["rows_verified"], 10021)

    @unittest.skipUnless(NATIVE_AVAILABLE, "native NautilusTrader 1.221.0 not installed")
    def test_reject_tampered_source(self):
        result = self.stage()
        self.source.write_text(HEADER + ROWS.replace("15000.25", "15000.00"))
        with self.assertRaisesRegex(QuoteAdmissionError, "source SHA"):
            self.verify(result)

    @unittest.skipUnless(NATIVE_AVAILABLE, "native NautilusTrader 1.221.0 not installed")
    def test_reject_tampered_export(self):
        result = self.stage()
        export = self.staging / "quotes.jsonl"
        export.write_text(export.read_text().replace("15000.25", "15000.00"))
        with self.assertRaisesRegex(QuoteAdmissionError, "export SHA"):
            self.verify(result)

    @unittest.skipUnless(NATIVE_AVAILABLE, "native NautilusTrader 1.221.0 not installed")
    def test_reject_forged_authority_even_with_repin(self):
        result = self.stage()
        manifest_file = self.staging / "manifest.json"
        m = json.loads(manifest_file.read_text())
        m["execution_authorized"] = True
        manifest_file.write_text(json.dumps(m, sort_keys=True))
        forged = hashlib.sha256(manifest_file.read_bytes()).hexdigest()
        with self.assertRaisesRegex(QuoteAdmissionError, "authority"):
            self.verify(result, expected_manifest_sha256=forged)

    @unittest.skipUnless(NATIVE_AVAILABLE, "native NautilusTrader 1.221.0 not installed")
    def test_reject_unexpected_staging_files(self):
        result = self.stage()
        (self.staging / "extra.json").write_text("{}")
        with self.assertRaisesRegex(QuoteAdmissionError, "unexpected"):
            self.verify(result)

    @unittest.skipUnless(NATIVE_AVAILABLE, "native NautilusTrader 1.221.0 not installed")
    def test_reject_untrusted_manifest_pin(self):
        result = self.stage()
        with self.assertRaisesRegex(QuoteAdmissionError, "manifest digest"):
            self.verify(result, expected_manifest_sha256="0" * 64)


if __name__ == "__main__":
    unittest.main()
