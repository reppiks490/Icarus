from decimal import Decimal
from tempfile import TemporaryDirectory
import unittest
from types import SimpleNamespace

from icarus_futures.engine import ExecutionEngine
from icarus_futures.ibkr_paper import (
    ContractMapping,
    IbkrPaperVenue,
    IbkrTwsPaperGateway,
)
from icarus_futures.journal import Journal
from icarus_futures.orders import Intent, S
from icarus_futures.risk import RiskGovernor
from icarus_futures.venue import SimVenue


def mapping():
    return ContractMapping(
        symbol="MNQZ26",
        con_id=123456,
        local_symbol="MNQZ6",
        contract_month="202612",
        exchange="CME",
        currency="USD",
        multiplier=Decimal("2"),
        tick_size=Decimal("0.25"),
    )


class FakeTwsGateway:
    """The callback-normalized boundary expected from an IB API session."""

    environment = "PAPER"

    def __init__(self, accounts=("DU12345",)):
        self.accounts = list(accounts)
        self.connected = True
        self.orders = {}
        self.next_id = 900
        self.placed = []
        self.cancelled = []
        self.modified = []
        self.events = []
        self.positions_snapshot = []
        self.place_outcome = None

    def is_connected(self):
        return self.connected

    def managed_accounts(self):
        return self.accounts

    def place_order(self, account_id, contract, order):
        self.placed.append((account_id, contract, order))
        if self.place_outcome == "reject":
            self.place_outcome = None
            return {"status": "rejected", "code": "201"}
        self.next_id += 1
        broker_id = str(self.next_id)
        record = {"account_id": account_id, "broker_id": broker_id,
                  "client_id": order["orderRef"], "contract": contract,
                  "order": dict(order), "status": "Submitted"}
        self.orders[broker_id] = record
        if self.place_outcome == "timeout_after_accept":
            self.place_outcome = None
            return {"status": "timeout"}
        return {"status": "ack", "broker_id": broker_id}

    def find_order_by_ref(self, account_id, order_ref):
        return next((dict(o) for o in self.orders.values()
                     if o["account_id"] == account_id and o["client_id"] == order_ref), None)

    def cancel_order(self, account_id, broker_id):
        self.cancelled.append((account_id, broker_id))
        record = self.orders.get(str(broker_id))
        if not record or record["account_id"] != account_id:
            return {"status": "not_found"}
        self.events.append({"type": "cancel_ack", "client_id": record["client_id"],
                            "broker_id": str(broker_id)})
        del self.orders[str(broker_id)]
        return {"status": "ok"}

    def modify_order(self, account_id, broker_id, order):
        self.modified.append((account_id, broker_id, dict(order)))
        record = self.orders.get(str(broker_id))
        if not record or record["account_id"] != account_id:
            return {"status": "not_found"}
        record["order"] = dict(order)
        self.events.append({"type": "replace_ack", "client_id": record["client_id"],
                            "broker_id": str(broker_id), "price": order.get("lmtPrice")})
        return {"status": "ok"}

    def open_orders(self, account_id):
        return [dict(o) for o in self.orders.values() if o["account_id"] == account_id]

    def positions(self, account_id):
        return [dict(p) for p in self.positions_snapshot if p["account_id"] == account_id]

    def poll_events(self, account_id):
        events, self.events = self.events, []
        return events


class FakeIbapiClient:
    """Simulates the official EClient calls and EWrapper callback ordering."""

    def __init__(self):
        self.callback = None
        self.connected = False
        self.orders = {}
        self.positions_rows = []
        self.placed = []
        self.completed_orders = []
        self.complete_readback = True
        self.error_on_place = None

    def set_callback(self, callback):
        self.callback = callback

    def connect(self, host, port, clientId):
        self.connected = True
        self.callback.nextValidId(900)
        self.callback.managedAccounts("DU12345")

    def isConnected(self):
        return self.connected

    def disconnect(self):
        self.connected = False
        self.callback.connectionClosed()

    def placeOrder(self, orderId, contract, order):
        self.placed.append((orderId, contract, order))
        if self.error_on_place is not None:
            code = self.error_on_place
            self.error_on_place = None
            self.callback.error(orderId, code, "private broker diagnostic")
            if code == 201:
                return
        self.orders[str(orderId)] = (contract, order, "Submitted")
        self.callback.openOrder(orderId, contract, order, SimpleNamespace(status="Submitted"))
        self.callback.orderStatus(orderId, "Submitted", 0, order.totalQuantity, 0.0,
                                  0, 0, 0.0, 71, "", 0.0)

    def reqAllOpenOrders(self):
        for order_id, (contract, order, status) in self.orders.items():
            if status.lower() not in {"cancelled", "filled", "inactive", "rejected"}:
                self.callback.openOrder(int(order_id), contract, order, SimpleNamespace(status=status))
        self.callback.openOrderEnd()

    def reqCompletedOrders(self, apiOnly):
        for contract, order, status in self.completed_orders:
            self.callback.completedOrder(contract, order, SimpleNamespace(status=status))
        if self.complete_readback:
            self.callback.completedOrdersEnd()
        self.callback.completedOrdersEnd()

    def reqPositions(self):
        for account, contract, position in self.positions_rows:
            self.callback.position(account, contract, position, 0.0)
        self.callback.positionEnd()

    def cancelPositions(self):
        return None

    def cancelOrder(self, orderId):
        contract, order, _ = self.orders[str(orderId)]
        self.orders[str(orderId)] = (contract, order, "Cancelled")
        self.callback.orderStatus(orderId, "Cancelled", 0, order.totalQuantity, 0.0,
                                  0, 0, 0.0, 71, "", 0.0)

    def order_fill(self, order_id, qty, price, exec_id):
        contract, order, status = self.orders[str(order_id)]
        execution = SimpleNamespace(orderId=order_id, orderRef=order.orderRef,
                                    shares=qty, price=price, execId=exec_id)
        self.callback.execDetails(1, contract, execution)
        self.orders[str(order_id)] = (contract, order, status)
        self.callback.orderStatus(order_id, "PartiallyFilled", qty, order.totalQuantity - qty, price,
                                  0, 0, price, 71, "", 0.0)


class FakeApiRecord:
    pass


def venue(gateway=None):
    gateway = gateway or FakeTwsGateway()
    return IbkrPaperVenue(gateway=gateway, account_id="DU12345", contracts={"MNQZ26": mapping()}), gateway


class IbkrPaperVenueTests(unittest.TestCase):
  def test_maps_exact_dated_cme_contract_and_normalizes_limit_request(self):
    adapter, gateway = venue()

    result = adapter.submit("ci-abc123", "MNQZ26", "buy", 2, "limit", 19888.25)

    assert result == {"status": "ack", "broker_id": "901"}
    account, contract, order = gateway.placed[0]
    assert account == "DU12345"
    assert contract == {
        "conId": 123456, "symbol": "MNQ", "secType": "FUT", "exchange": "CME",
        "currency": "USD", "lastTradeDateOrContractMonth": "202612",
        "localSymbol": "MNQZ6", "multiplier": "2", "includeExpired": False,
    }
    assert order == {
        "account": "DU12345", "action": "BUY", "totalQuantity": 2,
        "orderType": "LMT", "tif": "DAY", "orderRef": "ci-abc123",
        "outsideRth": False, "lmtPrice": 19888.25,
    }
    assert adapter.kind == "PAPER"
    assert adapter.poll() == [{"type": "ack", "client_id": "ci-abc123", "broker_id": "901"}]

    stop = adapter.submit("ci-stop", "MNQZ26", "SELL", 1, "STOP", 19888.50)
    assert stop["status"] == "ack"
    assert gateway.placed[-1][2]["orderType"] == "STP"
    assert gateway.placed[-1][2]["auxPrice"] == 19888.50


  def test_off_tick_prices_and_fractional_futures_quantity_are_rejected_before_submit(self):
    adapter, gateway = venue()

    with self.assertRaisesRegex(ValueError, "tick"):
        adapter.submit("ci-off-tick", "MNQZ26", "BUY", 1, "LIMIT", 19888.10)
    with self.assertRaisesRegex(ValueError, "quantity"):
        adapter.submit("ci-fraction", "MNQZ26", "BUY", 1.5, "MARKET", None)

    assert gateway.placed == []

  def test_contract_mapping_rejects_wrong_month_or_economic_precision(self):
    with self.assertRaisesRegex(ValueError, "same contract"):
        ContractMapping("MNQZ26", 123456, "MNQZ6", "202609", "CME", "USD",
                        Decimal("2"), Decimal("0.25"))
    with self.assertRaisesRegex(ValueError, "tick_size"):
        ContractMapping("MNQZ26", 123456, "MNQZ6", "202612", "CME", "USD",
                        Decimal("2"), Decimal("0.10"))

  def test_contract_mapping_indexes_reject_duplicate_ibkr_identity(self):
    gateway = FakeTwsGateway()
    same_con_id = ContractMapping("MNQH27", 123456, "MNQH7", "202703", "CME", "USD",
                                  Decimal("2"), Decimal("0.25"))
    same_local_symbol = ContractMapping("MNQH27", 123457, "MNQZ6", "202703", "CME", "USD",
                                        Decimal("2"), Decimal("0.25"))

    with self.assertRaisesRegex(ValueError, "unique IBKR conId"):
      IbkrPaperVenue(gateway, "DU12345", {
          "MNQZ26": mapping(), "MNQH27": same_con_id,
      })
    with self.assertRaisesRegex(ValueError, "unique IBKR localSymbol"):
      IbkrPaperVenue(gateway, "DU12345", {
          "MNQZ26": mapping(), "MNQH27": same_local_symbol,
      })

  def test_optional_tws_session_uses_paper_loopback_callbacks_and_readback(self):
    api = FakeIbapiClient()
    gateway = IbkrTwsPaperGateway(api_client=api, contract_factory=FakeApiRecord,
                                  order_factory=FakeApiRecord, timeout_s=0.05)
    with self.assertRaisesRegex(ValueError, "loopback"):
        IbkrTwsPaperGateway(host="broker.example", api_client=api,
                            contract_factory=FakeApiRecord, order_factory=FakeApiRecord)
    with self.assertRaisesRegex(ValueError, "7497"):
        IbkrTwsPaperGateway(port=7496, api_client=api,
                            contract_factory=FakeApiRecord, order_factory=FakeApiRecord)

    gateway.connect()
    adapter = IbkrPaperVenue(gateway, "DU12345", {"MNQZ26": mapping()})
    submitted = adapter.submit("ci-session", "MNQZ26", "BUY", 1, "LIMIT", 19888.25)
    assert submitted == {"status": "ack", "broker_id": "900"}
    assert len(api.placed) == 1
    open_order = adapter.open_orders()[0]
    assert open_order["symbol"] == "MNQZ26" and open_order["client_id"] == "ci-session"
    assert open_order["price"] == 19888.25
    assert open_order["quantity"] == 1 and open_order["kind"] == "LIMIT"

    api.positions_rows = [("DU12345", api.orders["900"][0], -1)]
    assert adapter.positions() == {"MNQZ26": -1}
    assert adapter.replace("900", 19888.50, client_id="ci-session") == {"status": "ok"}
    replacement_events = adapter.poll()
    assert {event["type"] for event in replacement_events} >= {"replace_ack"}
    assert next(event["price"] for event in replacement_events
                if event["type"] == "replace_ack") == 19888.50
    assert api.placed[-1][0] == 900  # amend reuses the broker order id
    assert api.placed[-1][2].lmtPrice == 19888.50
    assert adapter.cancel("900", client_id="ci-session") == {"status": "ok"}
    assert adapter.open_orders() == []
    gateway.disconnect()


  def test_ibkr_order_warning_does_not_override_submitted_order_status(self):
    api = FakeIbapiClient()
    gateway = IbkrTwsPaperGateway(api_client=api, contract_factory=FakeApiRecord,
                                  order_factory=FakeApiRecord, timeout_s=0.05)
    gateway.connect()
    adapter = IbkrPaperVenue(gateway, "DU12345", {"MNQZ26": mapping()})
    api.error_on_place = 2109  # nonfatal order attribute warning

    submitted = adapter.submit("ci-warning", "MNQZ26", "BUY", 1, "LIMIT", 19888.25)

    assert submitted == {"status": "ack", "broker_id": "900"}
    assert all(event.get("type") != "reject" for event in adapter.poll())
    gateway.disconnect()


  def test_ibkr_known_rejection_callback_remains_definitive_and_sanitized(self):
    api = FakeIbapiClient()
    gateway = IbkrTwsPaperGateway(api_client=api, contract_factory=FakeApiRecord,
                                  order_factory=FakeApiRecord, timeout_s=0.05)
    gateway.connect()
    adapter = IbkrPaperVenue(gateway, "DU12345", {"MNQZ26": mapping()})
    api.error_on_place = 201

    rejected = adapter.submit("ci-reject-callback", "MNQZ26", "BUY", 1, "LIMIT", 19888.25)

    assert rejected == {"status": "rejected", "code": "INVALID_ORDER"}
    assert "private broker diagnostic" not in repr(rejected)
    gateway.disconnect()


  def test_engine_cancel_remains_compatible_with_legacy_one_argument_venue(self):
    venue = SimVenue()
    original_cancel = venue.cancel
    cancelled = []

    def legacy_cancel(broker_id):
      cancelled.append(broker_id)
      return original_cancel(broker_id)

    venue.cancel = legacy_cancel
    intent = Intent("test", "MNQZ26", "BUY", 1, "LIMIT", 19888.25)
    submitted = venue.submit(intent.intent_id, intent.symbol, intent.side, intent.qty,
                             intent.kind, intent.price)
    venue.poll()  # consume the direct venue ack before attaching the engine
    engine = ExecutionEngine(venue, RiskGovernor(), Journal(":memory:"), mode="SIM")
    order, _created = engine.book.add(intent)
    order.state = S.WORKING
    order.broker_id = submitted["broker_id"]

    assert engine.cancel(order.id) is True
    assert cancelled == [submitted["broker_id"]]
    assert order.state is S.CANCELLED


  def test_callback_readback_preserves_partial_fill_and_cumulative_quantity(self):
    api = FakeIbapiClient()
    gateway = IbkrTwsPaperGateway(api_client=api, contract_factory=FakeApiRecord,
                                  order_factory=FakeApiRecord, timeout_s=0.05)
    gateway.connect()
    adapter = IbkrPaperVenue(gateway, "DU12345", {"MNQZ26": mapping()})
    assert adapter.submit("ci-partial", "MNQZ26", "BUY", 2, "LIMIT", 19888.25)["status"] == "ack"
    api.order_fill(900, 1, 19888.25, "exec-1")
    events = adapter.poll()
    assert [event["type"] for event in events].count("fill") == 1
    open_order = adapter.open_orders()[0]
    assert open_order["remaining"] == 1
    api.completed_orders = [(api.orders["900"][0], api.orders["900"][1], "PartiallyFilled")]
    found = gateway.find_order_by_ref("DU12345", "ci-partial")
    assert found["filled"] == 1
    assert found["fills"] == [{"fill_id": "exec-1", "qty": 1, "price": 19888.25}]
    gateway.disconnect()


  def test_uncertain_completed_order_readback_keeps_submit_ambiguous(self):
    api = FakeIbapiClient()
    gateway = IbkrTwsPaperGateway(api_client=api, contract_factory=FakeApiRecord,
                                  order_factory=FakeApiRecord, timeout_s=0.01)
    gateway.connect()
    adapter = IbkrPaperVenue(gateway, "DU12345", {"MNQZ26": mapping()})
    assert adapter.submit("ci-lost", "MNQZ26", "BUY", 1, "MARKET", None)["status"] == "ack"
    api.orders.clear()  # Simulate an absent open-order response with lost completed readback.
    api.complete_readback = False
    assert adapter.submit("ci-lost", "MNQZ26", "BUY", 1, "MARKET", None) == {"status": "timeout"}
    assert len(api.placed) == 1
    gateway.disconnect()


  def test_ambiguous_submit_is_reconciled_by_order_ref_without_second_placement(self):
    adapter, gateway = venue()
    gateway.place_outcome = "timeout_after_accept"

    first = adapter.submit("ci-same", "MNQZ26", "BUY", 1, "MARKET", None)
    second = adapter.submit("ci-same", "MNQZ26", "BUY", 1, "MARKET", None)

    assert first == {"status": "timeout"}
    assert second == {"status": "ack", "broker_id": "901"}
    assert len(gateway.placed) == 1
    assert adapter.open_orders() == [{
        "broker_id": "901", "client_id": "ci-same", "symbol": "MNQZ26", "side": "BUY",
        "quantity": 1, "kind": "MARKET", "remaining": 1, "price": None,
    }]


  def test_engine_keeps_mismatched_ibkr_readback_ambiguous(self):
    adapter, gateway = venue()
    intent = Intent("test-replay", "MNQZ26", "BUY", 1, "MARKET")
    order_ref = adapter._order_ref(intent.intent_id)
    request = {
        "account": "DU12345", "action": "SELL", "totalQuantity": 1,
        "orderType": "MKT", "tif": "DAY", "orderRef": order_ref,
        "outsideRth": False,
    }
    gateway.orders["901"] = {
        "account_id": "DU12345", "broker_id": "901", "client_id": order_ref,
        "contract": mapping().ib_contract(), "order": request,
        "status": "Submitted", "filled": 0,
    }
    with TemporaryDirectory() as temp:
      engine = ExecutionEngine(adapter, RiskGovernor(), Journal(f"{temp}/journal.jsonl"), mode="PAPER")
      engine.state.data_age_s["MNQZ26"] = 0
      engine.state.marks["MNQZ26"] = 19888.25

      result = engine.submit(intent)

      assert result == {"status": S.AMBIGUOUS.value, "order_id": intent.intent_id}
      assert engine.book.orders[intent.intent_id].state is S.AMBIGUOUS
      assert engine.snapshot()["health"] == "BLOCKED"

      reconciliation = engine.reconcile()
      assert intent.intent_id not in reconciliation["resolved"]
      assert reconciliation["mismatched_orders"][intent.intent_id] == ["side"]
      assert engine.book.orders[intent.intent_id].state is S.AMBIGUOUS
      assert engine.snapshot()["health"] == "BLOCKED"
    assert gateway.placed == []


  def test_duplicate_open_order_refs_do_not_resolve_engine_ambiguity(self):
    adapter, gateway = venue()
    intent = Intent("test-duplicate-replay", "MNQZ26", "BUY", 1, "MARKET")
    order_ref = adapter._order_ref(intent.intent_id)
    matching_order = {
        "account": "DU12345", "action": "BUY", "totalQuantity": 1,
        "orderType": "MKT", "tif": "DAY", "orderRef": order_ref,
        "outsideRth": False,
    }
    gateway.connected = False
    with TemporaryDirectory() as temp:
      engine = ExecutionEngine(adapter, RiskGovernor(), Journal(f"{temp}/journal.jsonl"), mode="PAPER")
      engine.state.data_age_s["MNQZ26"] = 0
      engine.state.marks["MNQZ26"] = 19888.25
      submitted = engine.submit(intent)
      assert submitted["status"] == S.AMBIGUOUS.value
      gateway.connected = True
      for broker_id in ("901", "902"):
        gateway.orders[broker_id] = {
            "account_id": "DU12345", "broker_id": broker_id, "client_id": order_ref,
            "contract": mapping().ib_contract(), "order": dict(matching_order),
            "status": "Submitted", "filled": 0,
        }
      reconciliation = engine.reconcile()
      assert intent.intent_id not in reconciliation["resolved"]
      assert "duplicate_client_reference" in reconciliation["mismatched_orders"][intent.intent_id]
      assert engine.book.orders[intent.intent_id].state is S.AMBIGUOUS
      assert engine.snapshot()["health"] == "BLOCKED"


  def test_unmapped_ibkr_open_order_contract_cannot_clear_ambiguity(self):
    adapter, gateway = venue()
    intent = Intent("test-contract-replay", "MNQZ26", "BUY", 1, "MARKET")
    order_ref = adapter._order_ref(intent.intent_id)
    request = {
        "account": "DU12345", "action": "BUY", "totalQuantity": 1,
        "orderType": "MKT", "tif": "DAY", "orderRef": order_ref,
        "outsideRth": False,
    }
    wrong_contract = dict(mapping().ib_contract(), conId=999999)
    gateway.orders["901"] = {
        "account_id": "DU12345", "broker_id": "901", "client_id": order_ref,
        "contract": wrong_contract, "order": request,
        "status": "Submitted", "filled": 0,
    }
    with TemporaryDirectory() as temp:
      engine = ExecutionEngine(adapter, RiskGovernor(), Journal(f"{temp}/journal.jsonl"), mode="PAPER")
      engine.state.data_age_s["MNQZ26"] = 0
      engine.state.marks["MNQZ26"] = 19888.25
      submitted = engine.submit(intent)
      assert submitted["status"] == S.AMBIGUOUS.value

      reconciliation = engine.reconcile()

      assert reconciliation["resolved"] == {}
      assert reconciliation["open_order_readback_error"] == "UNAVAILABLE_OR_INVALID"
      assert engine.book.orders[intent.intent_id].state is S.AMBIGUOUS
      assert engine.snapshot()["health"] == "BLOCKED"


  def test_reused_order_ref_with_different_terms_is_rejected_not_acknowledged(self):
    adapter, gateway = venue()
    assert adapter.submit("same-ref", "MNQZ26", "BUY", 1, "MARKET", None)["status"] == "ack"

    assert adapter.submit("same-ref", "MNQZ26", "SELL", 2, "LIMIT", 19888.25) == {"status": "timeout"}

    assert len(gateway.placed) == 1
    assert gateway.placed[0][2]["action"] == "BUY"
    assert gateway.placed[0][2]["totalQuantity"] == 1


  def test_replay_rejects_matching_basic_order_with_different_ibkr_execution_terms(self):
    mismatches = (
        ("parentId", 901),
        ("ocaGroup", "unrelated-bracket"),
        ("ocaType", 1),
        ("transmit", False),
        ("allOrNone", True),
        ("minQty", 1),
        ("goodAfterTime", "20261016 09:30:00 US/Eastern"),
        ("goodTillDate", "20261016 16:00:00 US/Eastern"),
        ("conditions", [{"type": "PriceCondition", "price": 19000}]),
    )
    for field, value in mismatches:
      with self.subTest(field=field):
        adapter, gateway = venue()
        assert adapter.submit("replay-ref", "MNQZ26", "BUY", 1, "MARKET", None)["status"] == "ack"
        gateway.orders["901"]["order"][field] = value

        assert adapter.submit("replay-ref", "MNQZ26", "BUY", 1, "MARKET", None) == {"status": "timeout"}
        assert len(gateway.placed) == 1


  def test_tws_callback_readback_retains_execution_terms_for_replay_check(self):
    api = FakeIbapiClient()
    gateway = IbkrTwsPaperGateway(api_client=api, contract_factory=FakeApiRecord,
                                  order_factory=FakeApiRecord, timeout_s=0.05)
    gateway.connect()
    adapter = IbkrPaperVenue(gateway, "DU12345", {"MNQZ26": mapping()})
    order_ref = "callback-replay"
    contract = gateway._make_contract(mapping().ib_contract())
    order = gateway._make_order(adapter._build_order(mapping(), order_ref, "BUY", 1, "MARKET", None))
    order.parentId = 901
    order.ocaGroup = "unrelated-bracket"
    order.ocaType = 1
    order.transmit = False
    api.orders["901"] = (contract, order, "Submitted")

    result = adapter.submit(order_ref, "MNQZ26", "BUY", 1, "MARKET", None)

    assert result == {"status": "timeout"}
    assert api.placed == []
    gateway.disconnect()


  def test_same_order_ref_with_different_contract_is_rejected(self):
    adapter, gateway = venue()
    assert adapter.submit("same-ref", "MNQZ26", "BUY", 1, "MARKET", None)["status"] == "ack"
    original_find = gateway.find_order_by_ref

    def wrong_contract(account_id, order_ref):
      record = original_find(account_id, order_ref)
      record["contract"] = dict(record["contract"], conId=999999)
      return record

    gateway.find_order_by_ref = wrong_contract
    assert adapter.submit("same-ref", "MNQZ26", "BUY", 1, "MARKET", None) == {"status": "timeout"}
    assert len(gateway.placed) == 1


  def test_duplicate_ibkr_order_refs_remain_ambiguous(self):
    api = FakeIbapiClient()
    gateway = IbkrTwsPaperGateway(api_client=api, contract_factory=FakeApiRecord,
                                  order_factory=FakeApiRecord, timeout_s=0.05)
    gateway.connect()
    contract = gateway._make_contract(mapping().ib_contract())
    request = {
        "account": "DU12345", "action": "BUY", "totalQuantity": 1,
        "orderType": "MKT", "tif": "DAY", "orderRef": "duplicate-ref",
        "outsideRth": False,
    }
    first_order = gateway._make_order(request)
    second_order = gateway._make_order(request)
    api.orders["901"] = (contract, first_order, "Submitted")
    api.orders["902"] = (contract, second_order, "Submitted")
    adapter = IbkrPaperVenue(gateway, "DU12345", {"MNQZ26": mapping()})

    result = adapter.submit("duplicate-ref", "MNQZ26", "BUY", 1, "MARKET", None)

    assert result == {"status": "timeout"}
    assert len(api.placed) == 0
    gateway.disconnect()


  def test_cancel_replace_and_positions_are_scoped_to_selected_paper_account(self):
    adapter, gateway = venue()
    result = adapter.submit("ci-working", "MNQZ26", "SELL", 2, "LIMIT", 19888.25)
    assert adapter.replace(result["broker_id"], 19888.50, client_id="ci-working") == {"status": "ok"}
    assert gateway.modified[-1][0:2] == ("DU12345", "901")
    assert gateway.modified[-1][2]["lmtPrice"] == 19888.50
    assert adapter.cancel(result["broker_id"], client_id="ci-working") == {"status": "ok"}
    assert gateway.cancelled == [("DU12345", "901")]

    gateway.positions_snapshot = [{"account_id": "DU12345", "symbol": "MNQZ26", "position": -2}]
    assert adapter.positions() == {"MNQZ26": -2}
    assert adapter.open_orders() == []


  def test_cancel_and_replace_require_matching_client_order_id(self):
    api = FakeIbapiClient()
    gateway = IbkrTwsPaperGateway(api_client=api, contract_factory=FakeApiRecord,
                                  order_factory=FakeApiRecord, timeout_s=0.05)
    gateway.connect()
    adapter = IbkrPaperVenue(gateway, "DU12345", {"MNQZ26": mapping()})
    placed = adapter.submit("ci-owned", "MNQZ26", "BUY", 1, "LIMIT", 19888.25)
    broker_id = placed["broker_id"]

    with self.assertRaisesRegex(ValueError, "originating client"):
        adapter.cancel(broker_id)
    assert adapter.cancel(broker_id, client_id="ci-other") == {"status": "not_found"}
    assert adapter.replace(broker_id, 19888.50, client_id="ci-other") == {"status": "not_found"}
    assert api.orders[broker_id][1].lmtPrice == 19888.25

    assert adapter.cancel(broker_id, client_id="ci-owned") == {"status": "ok"}
    gateway.disconnect()


  def test_wrong_environment_account_or_unmapped_contract_fails_closed(self):
    gateway = FakeTwsGateway()
    gateway.environment = "LIVE"
    with self.assertRaisesRegex(PermissionError, "PAPER"):
        IbkrPaperVenue(gateway, "DU12345", {"MNQZ26": mapping()})

    with self.assertRaisesRegex(PermissionError, "paper account"):
        IbkrPaperVenue(FakeTwsGateway(accounts=("U12345",)), "U12345", {"MNQZ26": mapping()})

    adapter, gateway = venue()
    with self.assertRaisesRegex(ValueError, "explicitly mapped"):
        adapter.submit("ci-continuous", "MNQ1!", "BUY", 1, "MARKET", None)
    assert gateway.placed == []

    with TemporaryDirectory() as temp:
        with self.assertRaises(PermissionError):
            ExecutionEngine(adapter, RiskGovernor(), Journal(f"{temp}/journal.jsonl"),
                            mode="LIVE", governance_path=f"{temp}/missing.json")


  def test_account_and_order_reference_are_rechecked_on_gateway_readback(self):
    adapter, gateway = venue()
    foreign = {"account_id": "DU99999", "broker_id": "77", "client_id": "ci-x",
               "status": "Submitted", "filled": 0}
    gateway.find_order_by_ref = lambda _account, _ref: foreign
    assert adapter.submit("ci-x", "MNQZ26", "BUY", 1, "MARKET", None) == {"status": "timeout"}

    gateway.find_order_by_ref = lambda _account, _ref: {
        "account_id": "DU12345", "broker_id": "77", "client_id": "ci-other",
        "status": "Submitted", "filled": 0,
    }
    assert adapter.submit("ci-x", "MNQZ26", "BUY", 1, "MARKET", None) == {"status": "timeout"}

    gateway.open_orders = lambda _account: [{
        "account_id": "DU99999", "broker_id": "77", "client_id": "ci-x",
        "contract": mapping().ib_contract(),
        "order": {"account": "DU99999", "orderRef": "ci-x", "action": "BUY",
                  "totalQuantity": 1, "orderType": "MKT"},
    }]
    with self.assertRaisesRegex(PermissionError, "selected paper account"):
        adapter.open_orders()

    gateway.open_orders = FakeTwsGateway().open_orders
    gateway.positions = lambda _account: [
        {"account_id": "DU99999", "symbol": "MNQZ26", "position": 1}
    ]
    with self.assertRaisesRegex(PermissionError, "selected paper account"):
        adapter.positions()


  def test_disconnect_and_provider_rejects_do_not_retry_or_leak_raw_error_text(self):
    adapter, gateway = venue()
    gateway.connected = False

    assert adapter.submit("ci-disconnected", "MNQZ26", "BUY", 1, "MARKET", None) == {"status": "timeout"}
    gateway.connected = True
    assert adapter.submit("ci-disconnected", "MNQZ26", "BUY", 1, "MARKET", None)["status"] == "ack"
    assert len(gateway.placed) == 1

    gateway.place_outcome = "reject"
    rejected = adapter.submit("ci-rejected", "MNQZ26", "BUY", 1, "MARKET", None)
    assert rejected == {"status": "rejected", "code": "INVALID_ORDER"}
    assert "secret" not in repr(rejected).lower()


if __name__ == "__main__":
    unittest.main()
