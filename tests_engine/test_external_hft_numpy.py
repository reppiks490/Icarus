"""Offline independent native NumPy readback for the ICARUS L2 research bridge."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from icarus_engine.external_hft_stage import stage_mbp_events
from icarus_engine.external_hft_verify import L2VerificationError, verify_hft_l2
from icarus_engine.external_hft_numpy import (
    DTYPE, L2NpyError, MAGIC, RECORD, pack_verified_l2, main,
)

HEADER = "sequence,contract_id,kind,side,exchange_ts_ns,local_ts_ns,price,quantity\n"
ROWS = (
    "1,NQH2026,depth_update,bid,1700000000000000000,1700000000000001000,15000.25,2\n"
    "2,NQH2026,depth_update,ask,1700000000000000100,1700000000000001200,15000.50,0\n"
    "3,NQH2026,trade,buy,1700000000000000200,1700000000000001300,15000.50,1\n"
)


class NativeL2Tests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root / "original.csv"
        self.source.write_text(HEADER + ROWS, encoding="utf-8")
        self.staging = self.root / "stage"
        stage_mbp_events(self.source, self.staging, contract_id="NQH2026",
                         source_id="approved_vendor", tick_size="0.25", lot_size="1")
        self.output = self.root / "binary"
        self.anchor = hashlib.sha256(self.source.read_bytes()).hexdigest()

    def go(self, **overrides):
        args = {
            "expected_contract_id": "NQH2026",
            "expected_source_id": "approved_vendor",
            "expected_input_sha256": self.anchor,
            "expected_tick_size": "0.25",
            "expected_lot_size": "1",
        }
        args.update(overrides)
        return pack_verified_l2(self.source, self.staging, self.output, **args)

    def test_native_numpy_readback_matches_original_events(self):
        manifest = self.go()
        array = np.load(self.output / "hft-events.npy", allow_pickle=False)
        self.assertEqual(array.shape, (3,))
        self.assertEqual(array.dtype.itemsize, 64)
        self.assertEqual(array.dtype.names, tuple(name for name, _ in DTYPE))
        self.assertEqual(array.dtype.descr, list(DTYPE))
        self.assertEqual(array["px"].tolist(), [15000.25, 15000.50, 15000.50])
        self.assertEqual(array["qty"].tolist(), [2.0, 0.0, 1.0])
        self.assertEqual(array["order_id"].tolist(), [0, 0, 0])
        self.assertEqual(array["exch_ts"][0], 1700000000000000000)
        self.assertEqual(array["local_ts"][-1], 1700000000000001300)
        self.assertEqual(manifest["rows"], 3)
        self.assertEqual(manifest["depth_updates"], 2)
        self.assertEqual(manifest["trades"], 1)
        self.assertEqual(manifest["authority_granted"], "NONE")
        self.assertEqual(manifest["status"], "QUARANTINED")
        self.assertEqual(manifest["npy_sha256"], hashlib.sha256(
            (self.output / "hft-events.npy").read_bytes()).hexdigest())
        self.assertEqual(manifest, json.loads((self.output / "native_manifest.json").read_text()))
        for key in ("source_authenticity_verified", "entitlement_verified",
                    "clock_sync_verified", "complete_book_verified",
                    "mbo_order_ids_available", "numpy_independent_readback_verified",
                    "hftbacktest_runtime_verified", "queue_and_latency_calibrated",
                    "empirical_fill_quality_verified", "training_approved",
                    "execution_authorized"):
            self.assertIs(manifest[key], False)

    def test_numpy_v1_header_and_record_binary_layout(self):
        self.go()
        binary = (self.output / "hft-events.npy").read_bytes()
        self.assertEqual(binary[:8], MAGIC)
        header_length = struct.unpack("<H", binary[8:10])[0]
        self.assertEqual((10 + header_length) % 16, 0)
        self.assertEqual(len(binary), 10 + header_length + 3 * 64)
        first = RECORD.unpack_from(binary, 10 + header_length)
        self.assertEqual(first, (
            1 | (1 << 29) | (1 << 30) | (1 << 31),
            1700000000000000000, 1700000000000001000,
            15000.25, 2.0, 0, 0, 0.0,
        ))
        self.assertEqual(binary[-64:], RECORD.pack(
            2 | (1 << 29) | (1 << 30) | (1 << 31),
            1700000000000000200, 1700000000000001300,
            15000.5, 1.0, 0, 0, 0.0,
        ))

    def test_untrusted_source_digest_fails_without_output(self):
        with self.assertRaisesRegex(L2VerificationError, "anchor"):
            self.go(expected_input_sha256="0" * 64)
        self.assertFalse(self.output.exists())

    def test_source_tamper_fails_without_output(self):
        self.source.write_text(HEADER + ROWS.replace("15000.25", "15000.75"))
        with self.assertRaises(L2VerificationError):
            self.go()
        self.assertFalse(self.output.exists())

    def test_forged_staged_csv_and_rehashed_manifest_fail(self):
        path = self.staging / "hft-events.csv"
        path.write_text(path.read_text().replace("15000.25", "15000.75"))
        manifest_file = self.staging / "manifest.json"
        manifest = json.loads(manifest_file.read_text())
        manifest["export_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest_file.write_text(json.dumps(manifest))
        with self.assertRaises(L2VerificationError):
            self.go()
        self.assertFalse(self.output.exists())

    def test_promoted_manifest_flag_refused(self):
        manifest_file = self.staging / "manifest.json"
        manifest = json.loads(manifest_file.read_text())
        manifest["execution_authorized"] = True
        manifest_file.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(L2VerificationError, "must be false"):
            self.go()
        self.assertFalse(self.output.exists())

    def test_existing_output_preserved(self):
        self.output.mkdir()
        (self.output / "preserve.txt").write_text("never overwrite")
        with self.assertRaisesRegex(L2NpyError, "already exists"):
            self.go()
        self.assertEqual((self.output / "preserve.txt").read_text(), "never overwrite")

    def test_output_symlink_refused(self):
        target = self.root / "other"
        target.mkdir()
        self.output.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(L2NpyError, "symlink"):
            self.go()
        self.assertEqual(list(target.iterdir()), [])

    def test_stage_mutation_after_verification_is_caught(self):
        def mutate(*args, **kwargs):
            receipt = verify_hft_l2(*args, **kwargs)
            path = self.staging / "hft-events.csv"
            path.write_text(path.read_text().replace("15000.25", "15000.75"))
            return receipt
        with patch("icarus_engine.external_hft_numpy.verify_hft_l2", side_effect=mutate):
            with self.assertRaisesRegex(L2NpyError, "changed after independent"):
                self.go()
        self.assertFalse(self.output.exists())

    def test_source_mutation_after_verification_is_caught(self):
        def mutate(*args, **kwargs):
            receipt = verify_hft_l2(*args, **kwargs)
            self.source.write_text(HEADER + ROWS.replace("15000.25", "15000.75"))
            return receipt
        with patch("icarus_engine.external_hft_numpy.verify_hft_l2", side_effect=mutate):
            with self.assertRaisesRegex(L2NpyError, "original source changed"):
                self.go()
        self.assertFalse(self.output.exists())

    def test_large_feed_no_sample_ceiling(self):
        with self.source.open("w", encoding="utf-8") as file:
            file.write(HEADER)
            for index in range(1, 10021):
                t = 1700000000000000000 + index * 1000
                file.write(f"{index},NQH2026,depth_update,bid,{t},{t+100},15000.25,2\n")
        for item in self.staging.iterdir():
            item.unlink()
        self.staging.rmdir()
        stage_mbp_events(self.source, self.staging, contract_id="NQH2026",
                         source_id="approved_vendor", tick_size="0.25", lot_size="1")
        self.anchor = hashlib.sha256(self.source.read_bytes()).hexdigest()
        manifest = self.go()
        array = np.load(self.output / "hft-events.npy", allow_pickle=False, mmap_mode="r")
        self.assertEqual(manifest["rows"], 10020)
        self.assertEqual(array.shape, (10020,))
        self.assertEqual(array["qty"][-1], 2.0)

    def test_cli_produces_only_research_artifacts(self):
        with patch("builtins.print") as output:
            self.assertEqual(main([
                "--source", str(self.source), "--staging", str(self.staging),
                "--output", str(self.output), "--contract-id", "NQH2026",
                "--source-id", "approved_vendor",
                "--expected-input-sha256", self.anchor,
                "--tick-size", "0.25", "--lot-size", "1",
            ]), 0)
            output.assert_called_once()
        self.assertEqual({x.name for x in self.output.iterdir()},
                         {"hft-events.npy", "native_manifest.json"})


if __name__ == "__main__":
    unittest.main()
