"""Offline adversarial regression tests for independent L2 staging consumer."""
from __future__ import annotations

import csv
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from icarus_engine.external_hft_verify import (
    L2VerificationError, verify_hft_l2, main,
)

HEADER = "sequence,contract_id,kind,side,exchange_ts_ns,local_ts_ns,price,quantity\n"
ROWS = (
    "1,NQH2026,depth_update,bid,1700000000000000000,1700000000000001000,15000.25,2\n"
    "2,NQH2026,depth_update,ask,1700000000000000100,1700000000000001200,15000.50,0\n"
    "3,NQH2026,trade,buy,1700000000000000200,1700000000000001300,15000.50,1\n"
)


def fixture(source, staging):
    """Independently construct synthetic event CSV/manifest, never use verifier."""
    staging.mkdir()
    with source.open(newline="", encoding="utf-8") as incoming, (
            staging / "hft-events.csv").open("w", newline="", encoding="utf-8") as outgoing:
        reader = csv.DictReader(incoming)
        writer = csv.writer(outgoing, lineterminator="\n")
        writer.writerow(["ev", "exch_ts", "local_ts", "px", "qty", "order_id", "ival", "fval"])
        count = depth = trades = 0
        first_exch = first_local = last_exch = last_local = None
        for row in reader:
            count += 1
            if row["kind"] == "depth_update":
                kind, side = 1, (1 << 29 if row["side"] == "bid" else 1 << 28)
                depth += 1
            else:
                kind, side = 2, (1 << 29 if row["side"] == "buy" else 1 << 28)
                trades += 1
            exch, local = int(row["exchange_ts_ns"]), int(row["local_ts_ns"])
            first_exch = exch if first_exch is None else first_exch
            first_local = local if first_local is None else first_local
            last_exch, last_local = exch, local
            writer.writerow([kind | side | (1 << 31) | (1 << 30), exch, local,
                             repr(float(Decimal(row["price"]))),
                             repr(float(Decimal(row["quantity"]))), 0, 0, "0.0"])
    manifest = {
        "schema_version": "icarus-hftbacktest-l2-csv-v1",
        "format": "hftbacktest_event_csv_staging_not_numpy",
        "actual_contract_id": "NQH2026", "source_id": "approved_vendor",
        "feed_kind": "MBP_L2_depth_updates_and_trades",
        "tick_size": "0.25", "lot_size": "1",
        "exchange_clock_unit": "unix_epoch_nanoseconds",
        "arrival_clock_unit": "unix_epoch_nanoseconds",
        "input_sha256": sha256(source.read_bytes()).hexdigest(),
        "export_sha256": sha256((staging / "hft-events.csv").read_bytes()).hexdigest(),
        "rows": count, "depth_updates": depth, "trades": trades,
        "first_exchange_ns": first_exch, "last_exchange_ns": last_exch,
        "first_local_ns": first_local, "last_local_ns": last_local,
        "vendor_authenticity_verified": False, "entitlement_verified": False,
        "clock_sync_verified": False, "book_snapshot_verified": False,
        "mbo_order_ids_available": False, "queue_position_validated": False,
        "hftbacktest_runtime_verified": False, "backtest_fills_verified": False,
        "execution_authorized": False}
    (staging / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


class L2ConsumerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source.csv"
        self.source.write_text(HEADER + ROWS, encoding="utf-8")
        self.staging = self.root / "staging"
        fixture(self.source, self.staging)
        self.anchor = sha256(self.source.read_bytes()).hexdigest()

    def verify(self, **overrides):
        args = dict(expected_contract_id="NQH2026", expected_source_id="approved_vendor",
                    expected_input_sha256=self.anchor, expected_tick_size="0.25",
                    expected_lot_size="1")
        args.update(overrides)
        return verify_hft_l2(self.source, self.staging, **args)

    def manifest(self):
        return json.loads((self.staging / "manifest.json").read_text())

    def write_manifest(self, value):
        (self.staging / "manifest.json").write_text(json.dumps(value, indent=2) + "\n")

    def rehash_export(self):
        manifest = self.manifest()
        manifest["export_sha256"] = sha256((self.staging / "hft-events.csv").read_bytes()).hexdigest()
        self.write_manifest(manifest)

    def test_full_readonly_receipt(self):
        before = [(p.name, sha256(p.read_bytes()).hexdigest()) for p in self.staging.iterdir()]
        result = self.verify()
        self.assertEqual(result["status"], "STRUCTURALLY_VERIFIED_QUARANTINED")
        self.assertEqual((result["rows"], result["depth_updates"], result["trades"]), (3, 2, 1))
        self.assertEqual(result["input_sha256"], self.anchor)
        for flag in ("vendor_authenticity_verified", "entitlement_verified",
                     "clock_sync_verified", "book_snapshot_verified",
                     "native_hftbacktest_replay_verified", "empirical_fill_quality_verified",
                     "training_approved", "execution_authorized"):
            self.assertIs(result[flag], False)
        self.assertEqual(before, [(p.name, sha256(p.read_bytes()).hexdigest())
                                  for p in self.staging.iterdir()])

    def test_bad_independent_anchor(self):
        with self.assertRaisesRegex(L2VerificationError, "independent anchor"):
            self.verify(expected_input_sha256="0" * 64)

    def test_tampered_original_source(self):
        self.source.write_text(HEADER + ROWS.replace("15000.25,2", "15000.75,2"))
        with self.assertRaises(L2VerificationError):
            self.verify()

    def test_rehashed_semantic_tampering(self):
        path = self.staging / "hft-events.csv"
        path.write_text(path.read_text().replace("15000.25", "15000.75"))
        self.rehash_export()
        with self.assertRaisesRegex(L2VerificationError, "differs from source"):
            self.verify()

    def test_forged_order_id(self):
        path = self.staging / "hft-events.csv"
        path.write_text(path.read_text().replace(",0,0,0.0", ",999,0,0.0"))
        self.rehash_export()
        with self.assertRaisesRegex(L2VerificationError, "differs from source"):
            self.verify()

    def test_forged_event_flags(self):
        path = self.staging / "hft-events.csv"
        path.write_text(path.read_text().replace("3758096385", "3758096386"))
        self.rehash_export()
        with self.assertRaisesRegex(L2VerificationError, "differs from source"):
            self.verify()

    def test_wrong_contract_and_source(self):
        for field, value in (("expected_contract_id", "NQM2026"),
                             ("expected_source_id", "other_source")):
            with self.subTest(field=field), self.assertRaisesRegex(L2VerificationError, "mismatch"):
                self.verify(**{field: value})

    def test_tick_lot_mismatch(self):
        for field, value in (("expected_tick_size", "0.5"),
                             ("expected_lot_size", "0.25")):
            with self.subTest(field=field), self.assertRaisesRegex(L2VerificationError, "contract mismatch"):
                self.verify(**{field: value})

    def test_authority_flag_true(self):
        for flag in ("execution_authorized", "vendor_authenticity_verified",
                     "hftbacktest_runtime_verified"):
            with self.subTest(flag=flag):
                manifest = self.manifest()
                manifest[flag] = True
                self.write_manifest(manifest)
                with self.assertRaisesRegex(L2VerificationError, "must be false"):
                    self.verify()
                manifest[flag] = False
                self.write_manifest(manifest)

    def test_duplicate_json_keys(self):
        path = self.staging / "manifest.json"
        raw = path.read_text()
        path.write_text(raw.replace('"execution_authorized": false',
                                    '"execution_authorized": false, "execution_authorized": false'))
        with self.assertRaisesRegex(L2VerificationError, "duplicate JSON"):
            self.verify()

    def test_extra_manifest_authority(self):
        manifest = self.manifest()
        manifest["training_approved"] = True
        self.write_manifest(manifest)
        with self.assertRaisesRegex(L2VerificationError, "unexpected/missing"):
            self.verify()

    def test_manifest_counts_and_clock_bounds(self):
        baseline = self.manifest()
        for field, value in (("rows", 100), ("depth_updates", 99),
                             ("first_local_ns", 1700000000000000999),
                             ("last_exchange_ns", 1700000000000000900)):
            with self.subTest(field=field):
                manifest = dict(baseline)
                manifest[field] = value
                self.write_manifest(manifest)
                with self.assertRaises(L2VerificationError):
                    self.verify()
                self.write_manifest(baseline)

    def test_extra_staged_file(self):
        (self.staging / "injected.py").write_text("print('not executed')")
        with self.assertRaisesRegex(L2VerificationError, "unexpected files"):
            self.verify()

    def test_symlinked_export(self):
        export = self.staging / "hft-events.csv"
        target = self.root / "target.csv"
        export.rename(target)
        export.symlink_to(target)
        with self.assertRaisesRegex(L2VerificationError, "symlink"):
            self.verify()

    def test_extra_export_row(self):
        export = self.staging / "hft-events.csv"
        export.write_text(export.read_text() + export.read_text().splitlines(keepends=True)[-1])
        self.rehash_export()
        with self.assertRaisesRegex(L2VerificationError, "missing/extra CSV"):
            self.verify()

    def _mutate_source_and_anchor(self, new_rows):
        self.source.write_text(HEADER + new_rows)
        self.anchor = sha256(self.source.read_bytes()).hexdigest()
        manifest = self.manifest()
        manifest["input_sha256"] = self.anchor
        self.write_manifest(manifest)

    def test_duplicate_source_sequence(self):
        self._mutate_source_and_anchor(ROWS.replace("2,NQH2026", "1,NQH2026"))
        with self.assertRaisesRegex(L2VerificationError, "sequence"):
            self.verify()

    def test_negative_arrival_latency(self):
        self._mutate_source_and_anchor(ROWS.replace(
            "1700000000000000100,1700000000000001200",
            "1700000000000000100,1700000000000000000"))
        with self.assertRaisesRegex(L2VerificationError, "clock"):
            self.verify()

    def test_off_grid_source(self):
        self._mutate_source_and_anchor(ROWS.replace("15000.25,2", "15000.26,2"))
        with self.assertRaisesRegex(L2VerificationError, "off grid"):
            self.verify()

    def test_oversized_sequence(self):
        self._mutate_source_and_anchor(ROWS.replace("1,NQH2026", "9" * 6000 + ",NQH2026"))
        with self.assertRaisesRegex(L2VerificationError, "sequence"):
            self.verify()

    def test_empty_depth_context(self):
        manifest = self.manifest()
        manifest["depth_updates"] = 0
        self.write_manifest(manifest)
        with self.assertRaisesRegex(L2VerificationError, "empty depth"):
            self.verify()

    def test_cli_success_without_provider(self):
        with patch("builtins.print") as printed:
            rc = main(["--source", str(self.source), "--staging", str(self.staging),
                       "--contract-id", "NQH2026", "--source-id", "approved_vendor",
                       "--expected-input-sha256", self.anchor,
                       "--tick-size", "0.25", "--lot-size", "1"])
        self.assertEqual(rc, 0)
        printed.assert_called_once()

    def test_no_arbitrary_sample_cap(self):
        with self.source.open("w") as file:
            file.write(HEADER)
            for i in range(1, 10015):
                ts = 1700000000000000000 + i * 1000
                file.write(f"{i},NQH2026,depth_update,bid,{ts},{ts+100},15000.25,2\n")
        for path in self.staging.iterdir():
            path.unlink()
        self.staging.rmdir()
        fixture(self.source, self.staging)
        self.anchor = sha256(self.source.read_bytes()).hexdigest()
        self.assertEqual(self.verify()["rows"], 10014)

    def test_real_producer_roundtrip(self):
        # This must execute on CI against the real #486 producer.
        from icarus_engine.external_hft_stage import stage_mbp_events
        producer_dir = self.root / "producer"
        stage_mbp_events(self.source, producer_dir, contract_id="NQH2026",
                         source_id="approved_vendor", tick_size="0.25", lot_size="1")
        receipt = verify_hft_l2(self.source, producer_dir,
                                expected_contract_id="NQH2026",
                                expected_source_id="approved_vendor",
                                expected_input_sha256=self.anchor,
                                expected_tick_size="0.25", expected_lot_size="1")
        self.assertEqual(receipt["rows"], 3)


if __name__ == "__main__":
    unittest.main()
