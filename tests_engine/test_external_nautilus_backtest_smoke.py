"""Synthetic-only native BacktestEngine smoke regressions."""
from __future__ import annotations

import importlib.metadata
from pathlib import Path
import tempfile
import unittest

from icarus_engine.external_nautilus_backtest_smoke import run_verified_synthetic_backtest
from icarus_engine.external_nautilus_quote_bridge import (
    QuoteAdmissionError,
    VERSION,
    stage_quotes,
)

HEADER = "sequence,instrument_id,event_ts_ns,arrival_ts_ns,bid_price,ask_price,bid_size,ask_size\n"
BASE = 1_700_000_000_000_000_000
REV = "c" * 40
try:
    NATIVE = importlib.metadata.version("nautilus_trader") == VERSION
except importlib.metadata.PackageNotFoundError:
    NATIVE = False


def row(i: int, bid: str = "15000.25", ask: str = "15000.50") -> str:
    event = BASE + (i - 1) * 100
    arrival = event + 1_000
    return f"{i},NQH2026.CME,{event},{arrival},{bid},{ask},2,3\n"


@unittest.skipUnless(NATIVE, "pinned NautilusTrader wheel required")
class NativeBacktestSmokeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root / "quotes.csv"
        self.staging = self.root / "staging"
        self.source.write_text(HEADER + row(1) + row(2, "15000.50", "15000.75") + row(3))
        self._stage()

    def _stage(self):
        receipt = stage_quotes(
            self.source,
            self.staging,
            instrument_id="NQH2026.CME",
            source_id="synthetic_native_backtest",
            producer_revision=REV,
            tick_size="0.25",
            lot_size="1",
        )
        self.manifest = receipt["manifest"]
        self.manifest_sha = receipt["manifest_sha256"]

    def _run(self):
        return run_verified_synthetic_backtest(
            self.source,
            self.staging,
            instrument_id="NQH2026.CME",
            source_id="synthetic_native_backtest",
            producer_revision=REV,
            expected_source_sha256=self.manifest["source_sha256"],
            expected_export_sha256=self.manifest["export_sha256"],
            expected_manifest_sha256=self.manifest_sha,
        )

    def test_actual_backtestengine_processes_all_quotes_with_zero_trading_state(self):
        result = self._run()
        self.assertEqual(result["status"], "NATIVE_BACKTESTENGINE_SYNTHETIC_ZERO_ORDER_SMOKE_ONLY")
        self.assertEqual(result["records_replayed"], 3)
        self.assertEqual(result["first_run"]["iterations"], 3)
        self.assertEqual(result["first_run"]["orders_total"], 0)
        self.assertEqual(result["first_run"]["positions_total"], 0)
        self.assertEqual(result["reset_run"], result["first_run"])
        self.assertTrue(result["deterministic_reset_replay"])

    def test_every_authority_and_empirical_gate_stays_false(self):
        result = self._run()
        for key in (
            "source_authenticity_verified",
            "license_verified",
            "instrument_economics_verified",
            "exchange_clock_synchronized",
            "initial_book_snapshot_verified",
            "queue_model_calibrated",
            "latency_model_calibrated",
            "fill_parity_verified",
            "empirical_edge_verified",
            "training_approved",
            "brain_admission_approved",
            "execution_authorized",
            "live_broker_connected",
        ):
            self.assertIs(result[key], False)

    def test_rejects_staging_tamper_before_backtest(self):
        target = self.staging / "quotes.jsonl"
        target.write_bytes(target.read_bytes().replace(b"15000.25", b"15001.25", 1))
        with self.assertRaises(QuoteAdmissionError):
            self._run()

    def test_rejects_original_source_tamper_before_backtest(self):
        self.source.write_text(self.source.read_text().replace("15000.25", "15001.25", 1))
        with self.assertRaises(QuoteAdmissionError):
            self._run()

    def test_rejects_mismatched_contract_identity(self):
        with self.assertRaises(QuoteAdmissionError):
            run_verified_synthetic_backtest(
                self.source,
                self.staging,
                instrument_id="NQM2026.CME",
                source_id="synthetic_native_backtest",
                producer_revision=REV,
                expected_source_sha256=self.manifest["source_sha256"],
                expected_export_sha256=self.manifest["export_sha256"],
                expected_manifest_sha256=self.manifest_sha,
            )

    def test_actual_engine_replays_more_than_ten_thousand_records(self):
        self.staging.rename(self.root / "old_staging")
        self.source.write_text(HEADER + "".join(row(i) for i in range(1, 10022)))
        self._stage()
        result = self._run()
        self.assertEqual(result["records_replayed"], 10021)
        self.assertEqual(result["first_run"]["iterations"], 10021)
        self.assertEqual(result["first_run"]["orders_total"], 0)
        self.assertEqual(result["first_run"], result["reset_run"])


if __name__ == "__main__":
    unittest.main()
