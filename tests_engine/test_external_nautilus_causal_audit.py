"""Synthetic-only regressions for Nautilus native QuoteTick reception-time causality."""
from __future__ import annotations

import hashlib
import importlib.metadata
from pathlib import Path
import tempfile
import unittest

from icarus_engine.external_nautilus_quote_bridge import (
    QuoteAdmissionError, VERSION, stage_quotes,
)
from icarus_engine.external_nautilus_causal_audit import audit_quote_asof

HEADER = "sequence,instrument_id,event_ts_ns,arrival_ts_ns,bid_price,ask_price,bid_size,ask_size\n"
EPOCH = 1700000000000000000
REV = "b" * 40
try:
    NATIVE = importlib.metadata.version("nautilus_trader") == VERSION
except importlib.metadata.PackageNotFoundError:
    NATIVE = False


def quote(sequence, event, arrival, bid="15000.25", ask="15000.50"):
    return f"{sequence},NQH2026.CME,{event},{arrival},{bid},{ask},2,3\n"


@unittest.skipUnless(NATIVE, "actual pinned NautilusTrader wheel required for native parity")
class CausalAuditTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root / "quotes.csv"
        self.staging = self.root / "native_staging"
        self.records = [
            quote(1, EPOCH, EPOCH + 1000),
            quote(2, EPOCH + 100, EPOCH + 1100, "15000.50", "15000.75"),
            quote(3, EPOCH + 200, EPOCH + 1200),
        ]
        self.source.write_text(HEADER + "".join(self.records), encoding="utf-8")
        self.refresh()

    def refresh(self):
        self.stage_receipt = stage_quotes(
            self.source, self.staging,
            instrument_id="NQH2026.CME", source_id="independent_synthetic",
            producer_revision=REV, tick_size="0.25", lot_size="1",
        )
        manifest = self.stage_receipt["manifest"]
        self.arguments = dict(
            source=self.source, staging=self.staging,
            instrument_id="NQH2026.CME", source_id="independent_synthetic",
            producer_revision=REV,
            expected_source_sha256=manifest["source_sha256"],
            expected_export_sha256=manifest["export_sha256"],
            expected_manifest_sha256=self.stage_receipt["manifest_sha256"],
        )

    def audit(self, times, **kwargs):
        args = {**self.arguments, **kwargs}
        return audit_quote_asof(**args, observation_ns=times)

    def test_exchange_time_does_not_make_quote_visible_before_arrival(self):
        samples = self.audit([EPOCH, EPOCH + 999, EPOCH + 1000, EPOCH + 1099,
                              EPOCH + 1100, EPOCH + 1200])["observations"]
        self.assertEqual([s["available"] for s in samples],
                         [False, False, True, True, True, True])
        self.assertEqual(samples[2]["quote"]["bid_price"], "15000.25")
        self.assertEqual(samples[4]["quote"]["bid_price"], "15000.50")
        self.assertEqual(samples[5]["quote"]["bid_price"], "15000.25")
        self.assertLess(samples[2]["quote"]["ts_event"], samples[2]["asof_arrival_ns"])

    def test_schedule_independence_and_repeated_observations(self):
        short = self.audit([EPOCH + 1000, EPOCH + 1200])["observations"]
        long = self.audit([EPOCH, EPOCH + 1000, EPOCH + 1050, EPOCH + 1100,
                           EPOCH + 1200, EPOCH + 1200])["observations"]
        self.assertEqual(short, [long[1], long[4]])
        self.assertEqual(long[-1], long[-2])

    def test_future_edit_cannot_change_earlier_quote_observation(self):
        before = self.audit([EPOCH + 1050])["observations"]
        # This is a genuinely distinct new synthetic source, not a tampered receipt.
        self.staging.rename(self.root / "old_staging")
        self.source.write_text(
            HEADER + self.records[0] + quote(2, EPOCH + 100, EPOCH + 1100,
                                              "17000.50", "17000.75")
            + quote(3, EPOCH + 200, EPOCH + 1200, "18000.25", "18000.50"),
            encoding="utf-8",
        )
        self.refresh()
        after = self.audit([EPOCH + 1050])["observations"]
        self.assertEqual(before, after)
        self.assertNotEqual(
            self.audit([EPOCH + 1200])["observations"][0]["quote"]["bid_price"],
            "15000.25",
        )

    def test_rejects_modified_staging_even_with_previously_good_pin(self):
        path = self.staging / "quotes.jsonl"
        path.write_bytes(path.read_bytes().replace(b"15000.25", b"15001.25", 1))
        with self.assertRaisesRegex(QuoteAdmissionError, "digest"):
            self.audit([EPOCH + 1200])

    def test_rejects_forged_authority_even_if_manifest_hash_recomputed(self):
        import json
        path = self.staging / "manifest.json"
        value = json.loads(path.read_text())
        value["execution_authorized"] = True
        path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
        self.arguments["expected_manifest_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(QuoteAdmissionError, "authority"):
            self.audit([EPOCH + 1200])

    def test_untrusted_pins_or_source_revisions_rejected(self):
        with self.assertRaises(QuoteAdmissionError):
            self.audit([EPOCH + 1200], expected_source_sha256="0" * 64)
        with self.assertRaises(QuoteAdmissionError):
            self.audit([EPOCH + 1200], producer_revision="not_a_revision")

    def test_denies_nonmonotone_and_noninteger_observation_clock(self):
        for samples in ([], [EPOCH + 2000, EPOCH + 1000],
                        [True], ["1700000000000000000"], [-1], [2**64]):
            with self.subTest(samples=samples):
                with self.assertRaises(QuoteAdmissionError):
                    self.audit(samples)

    def test_research_authority_remains_denied(self):
        result = self.audit([EPOCH, EPOCH + 1200])
        self.assertEqual(result["status"], "NATIVE_QUOTE_ASOF_CAUSAL_OBSERVATION_ONLY")
        self.assertEqual(result["records_fully_scanned"], 3)
        for key in ("execution_authorized", "training_approved",
                    "fill_parity_verified", "native_backtest_executed",
                    "source_authenticity_verified", "license_verified",
                    "initial_book_snapshot_verified", "queue_model_calibrated",
                    "latency_model_calibrated", "empirical_edge_verified"):
            self.assertIs(result[key], False)

    def test_full_stream_10021_records_no_truncation(self):
        self.staging.rename(self.root / "old_staging")
        count = 10021
        self.source.write_text(
            HEADER + "".join(quote(i + 1, EPOCH + i * 100,
                                   EPOCH + 1000 + i * 100)
                             for i in range(count)),
            encoding="utf-8",
        )
        self.refresh()
        result = self.audit([EPOCH + 999, EPOCH + 1000, EPOCH + 1000 + (count-1)*100])
        self.assertEqual(result["records_fully_scanned"], count)
        self.assertFalse(result["observations"][0]["available"])
        self.assertTrue(result["observations"][-1]["available"])


if __name__ == "__main__":
    unittest.main()
