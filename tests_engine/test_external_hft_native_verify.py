"""Independent read-only native HFT L2 source-to-NPY verification tests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from icarus_engine.external_hft_stage import stage_mbp_events
from icarus_engine.external_hft_numpy import pack_verified_l2
from icarus_engine.external_hft_native_verify import (
    NativeVerificationError, verify_native_l2, main,
)
from icarus_engine.external_hft_verify import L2VerificationError

HEADER = "sequence,contract_id,kind,side,exchange_ts_ns,local_ts_ns,price,quantity\n"
ROWS = (
    "1,NQH2026,depth_update,bid,1700000000000000000,1700000000000001000,15000.25,2\n"
    "2,NQH2026,depth_update,ask,1700000000000000100,1700000000000001200,15000.50,0\n"
    "3,NQH2026,trade,buy,1700000000000000200,1700000000000001300,15000.50,1\n"
)


class NativeConsumerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "original.csv"
        self.source.write_text(HEADER + ROWS, encoding="utf-8")
        self.staging = self.root / "stage"
        self.native = self.root / "native"
        self.anchor = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.build()

    def args(self):
        return dict(expected_contract_id="NQH2026",
                    expected_source_id="approved_vendor",
                    expected_input_sha256=self.anchor,
                    expected_tick_size="0.25", expected_lot_size="1")

    def build(self):
        stage_mbp_events(self.source, self.staging,
                         contract_id="NQH2026", source_id="approved_vendor",
                         tick_size="0.25", lot_size="1")
        pack_verified_l2(self.source, self.staging, self.native, **self.args())

    def go(self, **kwargs):
        options = self.args()
        options.update(kwargs)
        return verify_native_l2(self.source, self.staging, self.native, **options)

    def manifest(self):
        return self.native / "native_manifest.json"

    def mutate_manifest(self, key, value):
        obj = json.loads(self.manifest().read_text())
        obj[key] = value
        self.manifest().write_text(json.dumps(obj))

    def test_independent_complete_readback_receipt(self):
        r = self.go()
        self.assertEqual(r["status"], "STRUCTURALLY_VERIFIED_QUARANTINED")
        self.assertEqual(r["rows"], 3)
        self.assertEqual(r["record_size_bytes"], 64)
        self.assertTrue(r["native_byte_parity_verified"])
        self.assertEqual(r["native_sha256"], hashlib.sha256(
            (self.native / "hft-events.npy").read_bytes()).hexdigest())
        for key in ("source_authenticity_verified", "entitlement_verified",
                    "hftbacktest_runtime_verified", "queue_and_latency_calibrated",
                    "empirical_fill_quality_verified", "training_approved",
                    "execution_authorized"):
            self.assertIs(r[key], False)
        self.assertEqual(r["authority_granted"], "NONE")

    def test_wrong_independent_source_anchor_refused(self):
        with self.assertRaises(L2VerificationError):
            self.go(expected_input_sha256="0" * 64)

    def test_original_source_mutation_refused(self):
        self.source.write_text(HEADER + ROWS.replace("15000.25", "15000.75"))
        with self.assertRaises(L2VerificationError):
            self.go()

    def test_staged_csv_mutation_refused_even_if_rehashed(self):
        staged = self.staging / "hft-events.csv"
        staged.write_text(staged.read_text().replace("15000.25", "15000.75"))
        obj = json.loads((self.staging / "manifest.json").read_text())
        obj["export_sha256"] = hashlib.sha256(staged.read_bytes()).hexdigest()
        (self.staging / "manifest.json").write_text(json.dumps(obj))
        with self.assertRaises(L2VerificationError):
            self.go()

    def test_native_payload_mutation_refused_even_if_manifest_rehashed(self):
        binary = self.native / "hft-events.npy"
        data = bytearray(binary.read_bytes())
        data[-64 + 24] ^= 1
        binary.write_bytes(data)
        self.mutate_manifest("npy_sha256", hashlib.sha256(data).hexdigest())
        with self.assertRaisesRegex(NativeVerificationError, "native record"):
            self.go()

    def test_truncated_native_payload_refused(self):
        binary = self.native / "hft-events.npy"
        binary.write_bytes(binary.read_bytes()[:-64])
        with self.assertRaisesRegex(NativeVerificationError, "native record"):
            self.go()

    def test_trailing_native_payload_refused(self):
        binary = self.native / "hft-events.npy"
        binary.write_bytes(binary.read_bytes() + b"malicious")
        with self.assertRaisesRegex(NativeVerificationError, "trailing"):
            self.go()

    def test_wrong_native_manifest_authority_refused(self):
        for key in ("execution_authorized", "training_approved",
                    "hftbacktest_runtime_verified", "entitlement_verified"):
            with self.subTest(key=key):
                original = self.manifest().read_bytes()
                self.mutate_manifest(key, True)
                with self.assertRaisesRegex(NativeVerificationError, "unsafe authority"):
                    self.go()
                self.manifest().write_bytes(original)

    def test_wrong_dtype_and_record_size_refused(self):
        for key, value in (("dtype", [["ev", "<i8"]]),
                           ("record_size_bytes", 56),
                           ("upstream_hftbacktest_revision", "0" * 40),
                           ("actual_contract_id", "NQM2026"),
                           ("status", "ACCEPTED")):
            with self.subTest(key=key):
                original = self.manifest().read_bytes()
                self.mutate_manifest(key, value)
                with self.assertRaisesRegex(NativeVerificationError, "manifest"):
                    self.go()
                self.manifest().write_bytes(original)

    def test_duplicate_manifest_keys_refused(self):
        obj = self.manifest().read_text()
        self.manifest().write_text(obj.replace(
            '"status": "QUARANTINED",',
            '"status": "QUARANTINED", "status": "ACCEPTED",'))
        with self.assertRaisesRegex(NativeVerificationError, "duplicate"):
            self.go()

    def test_native_header_dtype_corruption_refused(self):
        binary = self.native / "hft-events.npy"
        data = binary.read_bytes()
        self.assertIn(b"<u8", data[:256])
        binary.write_bytes(data.replace(b"<u8", b"<i8", 1))
        self.mutate_manifest("npy_sha256", hashlib.sha256(binary.read_bytes()).hexdigest())
        with self.assertRaisesRegex(NativeVerificationError, "dtype"):
            self.go()

    def test_native_header_magic_corruption_refused(self):
        binary = self.native / "hft-events.npy"
        data = bytearray(binary.read_bytes())
        data[0] = 0
        binary.write_bytes(data)
        with self.assertRaisesRegex(NativeVerificationError, "magic"):
            self.go()

    def test_symlinked_native_file_refused(self):
        binary = self.native / "hft-events.npy"
        target = self.root / "original-npy"
        binary.rename(target)
        try:
            binary.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        with self.assertRaisesRegex(NativeVerificationError, "symlink"):
            self.go()

    def test_extra_native_artifact_refused(self):
        (self.native / "unexpected").write_text("not an event")
        with self.assertRaisesRegex(NativeVerificationError, "unexpected"):
            self.go()

    def test_duplicate_npy_header_keys_refused(self):
        binary = self.native / "hft-events.npy"
        data = binary.read_bytes()
        size = struct.unpack("<H", data[8:10])[0]
        header = data[10:10 + size].decode("ascii")
        # Modify a same-length key into an existing one in an otherwise valid header.
        self.assertIn("'shape'", header)
        altered = header.replace("'shape'", "'descr'")
        binary.write_bytes(data[:10] + altered.encode("ascii") + data[10 + size:])
        self.mutate_manifest("npy_sha256", hashlib.sha256(binary.read_bytes()).hexdigest())
        with self.assertRaisesRegex(NativeVerificationError, "duplicate"):
            self.go()

    def test_large_feed_full_native_byte_parity_no_sample_cap(self):
        self.staging.joinpath("hft-events.csv").unlink()
        self.staging.joinpath("manifest.json").unlink()
        self.staging.rmdir()
        self.native.joinpath("hft-events.npy").unlink()
        self.native.joinpath("native_manifest.json").unlink()
        self.native.rmdir()
        with self.source.open("w", encoding="utf-8") as f:
            f.write(HEADER)
            for index in range(1, 10021):
                t = 1700000000000000000 + index * 1000
                f.write(f"{index},NQH2026,depth_update,bid,{t},{t+100},15000.25,2\n")
        self.anchor = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.build()
        self.assertEqual(self.go()["rows"], 10020)

    def test_cli_read_only_receipt(self):
        before = {p.name: p.read_bytes() for p in self.native.iterdir()}
        with patch("builtins.print") as output:
            self.assertEqual(main([
                "--source", str(self.source), "--staging", str(self.staging),
                "--native-dir", str(self.native), "--contract-id", "NQH2026",
                "--source-id", "approved_vendor",
                "--expected-input-sha256", self.anchor,
                "--tick-size", "0.25", "--lot-size", "1",
            ]), 0)
            output.assert_called_once()
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.native.iterdir()})


if __name__ == "__main__":
    unittest.main()
