import unittest
import json
import threading
import urllib.error
import urllib.request
from types import SimpleNamespace
from tempfile import TemporaryDirectory

from icarus_engine.assets import resolve
from icarus_engine.execution_costs import (
    FeeSchedule,
    estimate_book_sweep,
    reconcile_fills,
    summarize_book_sweep_window,
)
from icarus_engine.runtime import Journal, Portfolio
from icarus_engine.server import serve


def snapshot(received, sequence=1, bids=((99.0, 2), (98.0, 3)), asks=((101.0, 2), (102.0, 3))):
    levels = []
    for i in range(max(len(bids), len(asks))):
        bid = bids[i] if i < len(bids) else (None, 0)
        ask = asks[i] if i < len(asks) else (None, 0)
        levels.append({"bid_px": bid[0], "bid_sz": bid[1], "ask_px": ask[0], "ask_sz": ask[1]})
    return {"schema": "mbp-10", "ts_recv_ns": received, "ts_event_ns": received - 1,
            "sequence": sequence, "levels": levels}


class ExecutionCostTests(unittest.TestCase):
    def setUp(self):
        self.fees = FeeSchedule(broker_per_contract=0.5, exchange_per_contract=0.25,
                                per_order=1.0, source="fixture rate card")

    def test_sweep_cost_splits_spread_impact_and_fees(self):
        result = estimate_book_sweep([snapshot(100)], side="buy", quantity=3,
                                     tick_size=1, point_value=20, fee_schedule=self.fees)
        self.assertEqual(result["estimated_filled_contracts"], 3)
        self.assertTrue(result["complete_book_coverage"])
        self.assertEqual(result["sweep_vwap"], (101 * 2 + 102) / 3)
        self.assertAlmostEqual(result["spread_cost_currency"], 60)
        self.assertAlmostEqual(result["displayed_depth_impact_currency"], 20)
        self.assertAlmostEqual(result["estimated_slippage_currency"], 80)
        self.assertEqual(result["fees_one_side_for_estimated_fills"]["total_one_side"], 3.25)
        self.assertFalse(result["actual_costs_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_shallow_book_does_not_extrapolate(self):
        result = estimate_book_sweep([snapshot(100, asks=((101.0, 1),))], side="buy", quantity=2,
                                     tick_size=1, point_value=20, fee_schedule=self.fees)
        self.assertEqual(result["estimated_filled_contracts"], 1)
        self.assertEqual(result["unpriced_contracts"], 1)
        self.assertIsNone(result["estimated_complete_order_slippage_currency"])
        self.assertIsNone(result["estimated_complete_one_side_cost_currency"])

    def test_rejects_bad_schedules_quantities_and_crossed_books(self):
        with self.assertRaisesRegex(ValueError, "source is required"):
            FeeSchedule.from_mapping({"broker_per_contract": 1})
        with self.assertRaisesRegex(ValueError, "finite non-negative"):
            FeeSchedule.from_mapping({"source": "card", "per_order": float("nan")})
        with self.assertRaisesRegex(ValueError, "positive integer"):
            estimate_book_sweep([snapshot(100)], side="buy", quantity=True,
                                tick_size=1, point_value=20, fee_schedule=self.fees)
        with self.assertRaisesRegex(ValueError, "crossed or locked"):
            estimate_book_sweep([snapshot(100, bids=((101, 1),), asks=((101, 1),))], side="buy", quantity=1,
                                tick_size=1, point_value=20, fee_schedule=self.fees)

    def test_distribution_is_update_weighted_and_excludes_incomplete_samples(self):
        events = [snapshot(100), snapshot(200, sequence=2, asks=((101, 1),))]
        result = summarize_book_sweep_window(events, side="buy", quantity=2,
                                             tick_size=1, point_value=20, fee_schedule=self.fees)
        self.assertEqual(result["sampled_book_updates"], 2)
        self.assertEqual(result["complete_order_samples"], 1)
        self.assertEqual(result["incomplete_depth_samples"], 1)
        self.assertEqual(result["complete_order_slippage_currency"]["p50"], 40)

    def test_fill_reconciliation_uses_preceding_book_and_supplied_fees(self):
        events = [snapshot(100), snapshot(200, sequence=2)]
        fills = [{"fill_id": "f1", "timestamp_ns": 250, "side": "buy", "quantity": 1,
                  "price": 102, "actual_fee": 2.0}]
        result = reconcile_fills(events, fills, tick_size=1, point_value=20, fee_schedule=self.fees)
        self.assertEqual(result[0]["status"], "MATCHED")
        self.assertEqual(result[0]["book_received_ns"], 200)
        self.assertEqual(result[0]["actual_slippage_currency_vs_preceding_midpoint"], 40)
        self.assertEqual(result[0]["actual_minus_modeled_fee_currency"], 0.25)
        self.assertFalse(result[0]["actual_fee_verified"])

    def test_fill_without_preceding_book_is_not_invented(self):
        result = reconcile_fills([snapshot(200)], [{"timestamp_ns": 100, "side": "buy", "quantity": 1,
                                "price": 101}], tick_size=1, point_value=20, fee_schedule=self.fees)
        self.assertEqual(result[0]["status"], "NO_PRECEDING_BOOK_SNAPSHOT")
        self.assertIsNone(result[0]["comparison"])

    def test_http_endpoint_authenticates_and_returns_read_only_estimate(self):
        class Feed:
            failure = None

            def depth_events(self, symbol, *, schema, limit):
                self.request = (symbol, schema, limit)
                if self.failure is not None:
                    raise self.failure
                return [snapshot(1_800_000_000_000_000_000)]

        with TemporaryDirectory() as directory:
            port = Portfolio(Journal(":memory:"), directory)
            feed = Feed()
            spec = resolve("NQ")
            port.runners["NQ"] = SimpleNamespace(
                symbol="NQ", spec=spec, feed=feed)
            server = serve(port, 0, token="cost-test-token", start=False)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f"http://127.0.0.1:{server.server_address[1]}/admin/execution-cost/estimate"

            def request(payload, auth=True):
                headers = {"Content-Type": "application/json"}
                if auth:
                    headers["Authorization"] = "Bearer cost-test-token"
                req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=30) as response:
                        return response.status, json.load(response)
                except urllib.error.HTTPError as error:
                    return error.code, json.load(error)

            try:
                status, denied = request({}, auth=False)
                self.assertEqual(status, 401)
                payload = {"asset": "NQ", "side": "buy", "quantity": 1,
                           "fee_schedule": {"source": "fixture rate card"}}
                status, result = request(payload)
                self.assertEqual(status, 200, result)
                self.assertEqual(result["asset"], "NQ")
                self.assertFalse(result["execution_authorized"])
                self.assertEqual(feed.request, (spec.ticker, "mbp-10", 1000))
                status, invalid = request({"asset": "NQ"})
                self.assertEqual(status, 400)
                self.assertIn("missing", invalid["detail"])
                secret = "credential=private-provider-token"
                feed.failure = RuntimeError(secret)
                status, unavailable = request(payload)
                self.assertEqual(status, 502)
                self.assertEqual(unavailable["detail"], "Databento depth is temporarily unavailable")
                self.assertNotIn(secret, json.dumps(unavailable))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(5)
                port.journal.con.close()


if __name__ == "__main__":
    unittest.main()
