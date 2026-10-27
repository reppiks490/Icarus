"""No-network / no-provider validation of HFTBacktest MBP L2 event staging."""
from __future__ import annotations

import csv
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from icarus_engine.external_hft_stage import (
    DepthAdmissionError, FLAG_EXCH, FLAG_LOCAL, FLAG_BUY, FLAG_SELL,
    DEPTH_EVENT, TRADE_EVENT, stage_mbp_events, main,
)

HEAD = "sequence,contract_id,kind,side,exchange_ts_ns,local_ts_ns,price,quantity\n"
DATA = (
    "1,NQH2026,depth_update,bid,1700000000000000000,1700000000000001000,15000.25,2\n"
    "2,NQH2026,depth_update,ask,1700000000000000100,1700000000000001200,15000.50,0\n"
    "3,NQH2026,trade,buy,1700000000000000200,1700000000000001300,15000.50,1\n"
)


class HftStageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "input.csv"
        self.output = self.root / "staging"
        self.source.write_text(HEAD + DATA, encoding="utf-8")

    def go(self, **kwargs):
        args = dict(contract_id="NQH2026", source_id="approved_vendor",
                    tick_size="0.25", lot_size="1")
        args.update(kwargs)
        return stage_mbp_events(self.source, self.output, **args)

    def test_contract_safe_hftbacktest_event_column_mapping(self):
        m = self.go()
        with (self.output / "hft-events.csv").open(newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 3)
        self.assertEqual(list(rows[0]), ["ev","exch_ts","local_ts","px","qty",
                                         "order_id","ival","fval"])
        self.assertEqual(int(rows[0]["ev"]),
                         DEPTH_EVENT | FLAG_BUY | FLAG_EXCH | FLAG_LOCAL)
        self.assertEqual(int(rows[1]["ev"]),
                         DEPTH_EVENT | FLAG_SELL | FLAG_EXCH | FLAG_LOCAL)
        self.assertEqual(int(rows[2]["ev"]),
                         TRADE_EVENT | FLAG_BUY | FLAG_EXCH | FLAG_LOCAL)
        self.assertEqual(rows[1]["qty"], "0.0")
        self.assertTrue(all(row["order_id"] == "0" for row in rows))
        self.assertEqual(m["input_sha256"], sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual(m["export_sha256"],
                         sha256((self.output / "hft-events.csv").read_bytes()).hexdigest())
        self.assertEqual(m["rows"], 3)
        self.assertEqual(m["depth_updates"], 2)
        self.assertEqual(m["trades"], 1)
        for field in ("vendor_authenticity_verified", "entitlement_verified",
                      "clock_sync_verified", "book_snapshot_verified",
                      "mbo_order_ids_available", "queue_position_validated",
                      "hftbacktest_runtime_verified", "backtest_fills_verified",
                      "execution_authorized"):
            self.assertIs(m[field], False)

    def test_duplicate_sequence_is_refused(self):
        self.source.write_text(HEAD + DATA.replace("2,NQH2026,", "1,NQH2026,"))
        with self.assertRaisesRegex(DepthAdmissionError, "sequence"):
            self.go()
        self.assertFalse(self.output.exists())

    def test_sequence_out_of_order_is_refused(self):
        self.source.write_text(HEAD + DATA.replace("3,NQH2026,", "0,NQH2026,"))
        with self.assertRaisesRegex(DepthAdmissionError, "sequence"):
            self.go()
        self.assertFalse(self.output.exists())

    def test_mixed_actual_futures_contract_is_refused(self):
        self.source.write_text(HEAD + DATA.replace("2,NQH2026,", "2,NQM2026,"))
        with self.assertRaisesRegex(DepthAdmissionError, "contracts"):
            self.go()
        self.assertFalse(self.output.exists())

    def test_local_clock_before_exchange_is_refused(self):
        self.source.write_text(HEAD + DATA.replace(
            "1700000000000001000,15000.25", "1699999999999999999,15000.25"))
        with self.assertRaisesRegex(DepthAdmissionError, "latency"):
            self.go()

    def test_exchange_clock_ordering_is_refused(self):
        self.source.write_text(HEAD + DATA.replace(
            "1700000000000000100,1700000000000001200",
            "1699999999999999000,1700000000000001200"))
        with self.assertRaisesRegex(DepthAdmissionError, "clocks"):
            self.go()

    def test_local_arrival_clock_ordering_is_refused(self):
        self.source.write_text(HEAD + DATA.replace(
            "1700000000000000100,1700000000000001200",
            "1700000000000000100,1700000000000000500"))
        with self.assertRaisesRegex(DepthAdmissionError, "clocks"):
            self.go()

    def test_off_tick_grid_is_refused(self):
        self.source.write_text(HEAD + DATA.replace("15000.25", "15000.26"))
        with self.assertRaisesRegex(DepthAdmissionError, "tick/lot"):
            self.go()

    def test_off_lot_grid_is_refused(self):
        with self.assertRaisesRegex(DepthAdmissionError, "tick/lot"):
            self.go(lot_size="0.7")

    def test_negative_and_nonfinite_values_rejected(self):
        for mutant in (DATA.replace("15000.25", "NaN"),
                       DATA.replace("15000.25", "Infinity"),
                       DATA.replace("15000.25,2", "15000.25,-2")):
            with self.subTest(data=mutant):
                self.source.write_text(HEAD + mutant)
                with self.assertRaises(DepthAdmissionError):
                    self.go()
                self.assertFalse(self.output.exists())

    def test_zero_trade_qty_forbidden_zero_depth_qty_allowed(self):
        self.source.write_text(HEAD + DATA.replace("15000.50,1\n", "15000.50,0\n"))
        with self.assertRaisesRegex(DepthAdmissionError, "quantity"):
            self.go()

    def test_mbo_add_cancel_and_fake_snapshot_claims_are_forbidden(self):
        for kind in ("add_order", "cancel_order", "depth_snapshot"):
            with self.subTest(kind=kind):
                self.source.write_text(HEAD + DATA.replace("depth_update,bid",
                                                           f"{kind},bid"))
                with self.assertRaisesRegex(DepthAdmissionError, "unsupported"):
                    self.go()
                self.assertFalse(self.output.exists())

    def test_missing_header_or_extra_column_refused(self):
        self.source.write_text(HEAD.replace("quantity\n","quantity,order_id\n") +
                               DATA.replace("\n", ",0\n"))
        with self.assertRaisesRegex(DepthAdmissionError, "columns"):
            self.go()

    def test_empty_feed_cannot_claim_research_evidence(self):
        self.source.write_text(HEAD)
        with self.assertRaisesRegex(DepthAdmissionError, "nonempty"):
            self.go()

    def test_only_trades_cannot_claim_depth_context(self):
        self.source.write_text(HEAD + DATA.splitlines(keepends=True)[-1])
        with self.assertRaisesRegex(DepthAdmissionError, "depth-update"):
            self.go()

    def test_unsafe_output_overwrite_is_refused(self):
        self.output.mkdir()
        (self.output / "preserve").write_text("unchanged")
        with self.assertRaisesRegex(DepthAdmissionError, "already exists"):
            self.go()
        self.assertEqual((self.output / "preserve").read_text(), "unchanged")

    def test_large_feed_is_streamed_with_no_sample_cap(self):
        with self.source.open("w", newline="", encoding="utf-8") as f:
            f.write(HEAD)
            for index in range(1, 10021):
                base = 1700000000000000000 + index * 1000
                f.write(f"{index},NQH2026,depth_update,bid,{base},"
                        f"{base + 1000},15000.25,2\n")
        m = self.go()
        self.assertEqual(m["rows"], 10020)
        self.assertEqual(m["depth_updates"], 10020)

    def test_cli_never_runs_external_framework(self):
        with patch("builtins.print") as out:
            self.assertEqual(main(["--input",str(self.source),"--output",str(self.output),
                                   "--contract-id","NQH2026","--source-id","approved_vendor",
                                   "--tick-size","0.25","--lot-size","1"]),0)
            out.assert_called_once()


if __name__ == "__main__":
    unittest.main()
