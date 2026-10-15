"""Explicit-account IBKR PAPER adapter and optional TWS/IB Gateway transport.

The venue owns validation and normalization between :mod:`icarus_futures` and the
callback-normalized TWS/IB Gateway session below. Unit tests use a fake client and never
open a socket. A PAPER session must identify itself as ``PAPER`` and expose the selected
``DU...`` account; the venue has no LIVE mode or live-submit method and is deliberately
incompatible with ``ExecutionEngine(mode="LIVE")``.

The optional transport uses IBKR's official ``ibapi`` package. It only accepts loopback
TWS/IB Gateway paper ports and ``DU...`` accounts. It does not create or manage
credentials or claim sandbox/account verification.
"""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Protocol

from .contracts import MONTH_CODES, SPECS


_PAPER_ACCOUNT = re.compile(r"^DU[0-9]+$")
_DATED_FUTURE = re.compile(r"^([A-Z]+)([FGHJKMNQUVXZ])(\d{2})$")
_VALID_ORDER_KINDS = {"MARKET": "MKT", "LIMIT": "LMT", "STOP": "STP"}
_ERROR_CODES = {
    "103": "INVALID_ORDER",  # duplicate order id
    "110": "INVALID_ORDER",  # price does not conform to contract increment
    "201": "INVALID_ORDER",  # order rejected
}


class IbkrPaperGateway(Protocol):
    """Narrow normalized boundary implemented by the local IB API session owner.

    Every account-sensitive method takes ``account_id`` explicitly.  The session
    normalizes TWS callbacks to the records consumed below and must never discard an
    IBKR ``orderRef``; it must search all retained order states when reconciling it.
    """

    environment: str

    def is_connected(self) -> bool: ...
    def managed_accounts(self) -> list[str]: ...
    def place_order(self, account_id: str, contract: dict, order: dict) -> dict: ...
    def find_order_by_ref(self, account_id: str, order_ref: str) -> dict | None: ...
    def cancel_order(self, account_id: str, broker_id: str) -> dict: ...
    def modify_order(self, account_id: str, broker_id: str, order: dict) -> dict: ...
    def open_orders(self, account_id: str) -> list[dict]: ...
    def positions(self, account_id: str) -> list[dict]: ...
    def poll_events(self, account_id: str) -> list[dict]: ...


class IbkrTwsPaperGateway:
    """Optional loopback TWS/IB Gateway transport using IBKR's ``ibapi`` client.

    The connection is opened only by an explicit :meth:`connect` call. The transport
    permits the documented default TWS/IB Gateway paper ports (7497/4002), requires a
    loopback host and a ``DU...`` paper account, and never exposes a live mode. Passing
    ``api_client`` and the value factories is a test seam for callback behavior.
    """

    environment = "PAPER"
    PAPER_PORTS = frozenset({7497, 4002})

    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 71,
                 timeout_s: float = 5.0, *, api_client=None, contract_factory=None,
                 order_factory=None):
        import ipaddress

        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = host.lower() == "localhost"
        if not loopback:
            raise ValueError("IBKR PAPER transport accepts loopback hosts only")
        if port not in self.PAPER_PORTS:
            raise ValueError("IBKR PAPER transport accepts TWS 7497 or IB Gateway 4002 only")
        if isinstance(client_id, bool) or not isinstance(client_id, int) or client_id < 0:
            raise ValueError("client_id must be a non-negative integer")
        self.host, self.port, self.client_id = host, port, client_id
        self.timeout_s = float(timeout_s)
        if self.timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self._lock = threading.RLock()
        self._cv = threading.Condition(self._lock)
        self._ready = threading.Event()
        self._accounts_ready = threading.Event()
        self._open_orders_ready = threading.Event()
        self._completed_orders_ready = threading.Event()
        self._positions_ready = threading.Event()
        self._next_order_id: int | None = None
        self._accounts: list[str] = []
        self._records: dict[str, dict] = {}
        self._pending_refs: dict[str, str] = {}
        self._pending_replacements: dict[str, dict] = {}
        self._errors: dict[str, str] = {}
        self._events: list[dict] = []
        self._positions: list[dict] = []
        self._collecting_open = False
        self._open_snapshot: set[str] = set()
        self._collecting_completed = False
        self._completed_snapshot: set[str] = set()
        self._thread: threading.Thread | None = None
        if api_client is None:
            self._client, self._contract_factory, self._order_factory = self._make_ibapi_client()
        else:
            if contract_factory is None or order_factory is None:
                raise ValueError("fake api_client requires contract_factory and order_factory")
            self._client = api_client
            self._contract_factory = contract_factory
            self._order_factory = order_factory
            set_callback = getattr(api_client, "set_callback", None)
            if set_callback:
                set_callback(self)

    def _make_ibapi_client(self):
        try:
            from ibapi.client import EClient
            from ibapi.contract import Contract
            from ibapi.order import Order
            from ibapi.wrapper import EWrapper
        except ImportError as exc:
            raise RuntimeError("install the optional `ibkr` extra to use TWS/IB Gateway transport") from exc

        owner = self

        class _IbApp(EWrapper, EClient):
            def __init__(self):
                EClient.__init__(self, self)

            def nextValidId(self, orderId):
                owner.nextValidId(orderId)

            def managedAccounts(self, accountsList):
                owner.managedAccounts(accountsList)

            def openOrder(self, orderId, contract, order, orderState):
                owner.openOrder(orderId, contract, order, orderState)

            def openOrderEnd(self):
                owner.openOrderEnd()

            def orderStatus(self, orderId, status, filled, remaining, avgFillPrice,
                            permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice=0.0):
                owner.orderStatus(orderId, status, filled, remaining, avgFillPrice,
                                  permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice)

            def execDetails(self, reqId, contract, execution):
                owner.execDetails(reqId, contract, execution)

            def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
                owner.error(reqId, errorCode, errorString, advancedOrderRejectJson)

            def position(self, account, contract, position, avgCost):
                owner.position(account, contract, position, avgCost)

            def positionEnd(self):
                owner.positionEnd()

            def completedOrder(self, contract, order, orderState):
                owner.completedOrder(contract, order, orderState)

            def completedOrdersEnd(self):
                owner.completedOrdersEnd()

            def connectionClosed(self):
                owner.connectionClosed()

        return _IbApp(), Contract, Order

    def connect(self) -> None:
        """Connect to the configured local PAPER endpoint and await API identity."""
        if self.is_connected() and self._ready.is_set():
            return
        self._ready.clear()
        self._accounts_ready.clear()
        self._client.connect(self.host, self.port, self.client_id)
        run = getattr(self._client, "run", None)
        if run and (self._thread is None or not self._thread.is_alive()):
            self._thread = threading.Thread(target=run, name="ibkr-paper-api", daemon=True)
            self._thread.start()
        if not self._ready.wait(self.timeout_s) or not self._accounts_ready.wait(self.timeout_s):
            try:
                self._client.disconnect()
            finally:
                raise TimeoutError("IBKR PAPER API handshake did not complete")

    def disconnect(self) -> None:
        self._client.disconnect()
        self.connectionClosed()

    def is_connected(self) -> bool:
        try:
            return bool(self._client.isConnected())
        except Exception:
            return False

    def managed_accounts(self) -> list[str]:
        with self._lock:
            return list(self._accounts)

    def _require_account(self, account_id: str) -> None:
        if not _PAPER_ACCOUNT.fullmatch(str(account_id)):
            raise PermissionError("IBKR PAPER transport requires an explicit DU... paper account")
        if not self.is_connected() or not self._ready.is_set():
            raise ConnectionError("IBKR PAPER session is disconnected")
        if account_id not in self.managed_accounts():
            raise PermissionError("selected paper account is not managed by this session")

    @staticmethod
    def _contract_record(contract) -> dict:
        return {"conId": getattr(contract, "conId", 0),
                "symbol": getattr(contract, "symbol", ""),
                "secType": getattr(contract, "secType", ""),
                "exchange": getattr(contract, "exchange", ""),
                "currency": getattr(contract, "currency", ""),
                "lastTradeDateOrContractMonth": getattr(contract, "lastTradeDateOrContractMonth", ""),
                "localSymbol": getattr(contract, "localSymbol", ""),
                "multiplier": getattr(contract, "multiplier", "")}

    @staticmethod
    def _order_record(order) -> dict:
        record = {"account": getattr(order, "account", ""),
                  "action": getattr(order, "action", ""),
                  "totalQuantity": int(getattr(order, "totalQuantity", 0)),
                  "orderType": getattr(order, "orderType", ""),
                  "tif": getattr(order, "tif", "DAY"),
                  "orderRef": getattr(order, "orderRef", ""),
                  "outsideRth": bool(getattr(order, "outsideRth", False))}
        for field in ("lmtPrice", "auxPrice"):
            value = getattr(order, field, None)
            if value not in (None, 0, 0.0):
                record[field] = float(value)
        return record

    def _emit(self, event: dict) -> None:
        with self._cv:
            self._events.append(event)
            self._cv.notify_all()

    def nextValidId(self, orderId):
        with self._cv:
            self._next_order_id = max(int(orderId), self._next_order_id or int(orderId))
            self._ready.set()
            self._cv.notify_all()

    def managedAccounts(self, accountsList):
        with self._cv:
            self._accounts = [a.strip() for a in str(accountsList).split(",") if a.strip()]
            self._accounts_ready.set()
            self._cv.notify_all()

    def openOrder(self, orderId, contract, order, orderState):
        broker_id = str(orderId)
        contract_record = self._contract_record(contract)
        order_record = self._order_record(order)
        account_id = order_record["account"]
        status = str(getattr(orderState, "status", "Submitted"))
        record = {"account_id": account_id, "broker_id": broker_id,
                  "client_id": order_record["orderRef"], "contract": contract_record,
                  "order": order_record, "status": status, "filled": 0}
        with self._cv:
            old = self._records.get(broker_id)
            if old:
                record["filled"] = max(int(old.get("filled", 0)), int(record["filled"]))
                if old.get("fills"):
                    record["fills"] = list(old["fills"])
            self._records[broker_id] = record
            pending_replace = self._pending_replacements.get(broker_id)
            replacement_confirmed = bool(
                pending_replace
                and all(record["order"].get(field) == value
                        for field, value in pending_replace["order"].items())
            )
            if replacement_confirmed:
                self._pending_replacements.pop(broker_id, None)
            if self._collecting_open:
                self._open_snapshot.add(broker_id)
            if order_record["orderRef"]:
                self._pending_refs[broker_id] = order_record["orderRef"]
            self._cv.notify_all()
        if order_record["orderRef"]:
            if replacement_confirmed:
                self._emit({"type": "replace_ack", "account_id": account_id,
                            "client_id": order_record["orderRef"], "broker_id": broker_id,
                            "price": pending_replace["price"]})
            else:
                self._emit({"type": "ack", "account_id": account_id,
                            "client_id": order_record["orderRef"], "broker_id": broker_id})

    def openOrderEnd(self):
        with self._lock:
            self._collecting_open = False
        self._open_orders_ready.set()

    def orderStatus(self, orderId, status, filled, remaining, avgFillPrice,
                    permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice=0.0):
        broker_id = str(orderId)
        with self._cv:
            record = self._records.get(broker_id)
            if record:
                record["status"] = str(status)
                # orderStatus is cumulative; execDetails is an individual fill.
                record["filled"] = max(int(record.get("filled", 0)), int(float(filled)))
                record["remaining"] = int(float(remaining))
            client_ref = self._pending_refs.get(broker_id) or (record or {}).get("client_id")
            account_id = (record or {}).get("account_id", "")
            self._cv.notify_all()
        normalized = str(status).lower()
        if client_ref and normalized in {"pendingsubmit", "presubmitted", "submitted", "partiallyfilled", "filled"}:
            self._emit({"type": "ack", "account_id": account_id,
                        "client_id": client_ref, "broker_id": broker_id})
        elif client_ref and normalized in {"cancelled", "apicancelled", "canceled"}:
            self._emit({"type": "cancel_ack", "account_id": account_id,
                        "client_id": client_ref, "broker_id": broker_id})
        elif client_ref and normalized == "inactive":
            self._emit({"type": "reject", "account_id": account_id,
                        "client_id": client_ref, "code": "UNKNOWN"})

    def execDetails(self, reqId, contract, execution):
        broker_id = str(getattr(execution, "orderId", ""))
        with self._cv:
            record = self._records.get(broker_id)
            client_ref = (getattr(execution, "orderRef", "") or
                          self._pending_refs.get(broker_id) or (record or {}).get("client_id"))
            account_id = (record or {}).get("account_id", "")
            fill = {"fill_id": str(getattr(execution, "execId", "")),
                    "qty": int(float(getattr(execution, "shares", 0))),
                    "price": float(getattr(execution, "price", 0))}
            if record is not None:
                record.setdefault("fills", []).append(fill)
                record["filled"] = max(int(record.get("filled", 0)),
                                        sum(int(item["qty"]) for item in record["fills"]))
            self._cv.notify_all()
        if client_ref:
            self._emit({"type": "fill", "account_id": account_id,
                        "client_id": str(client_ref), "broker_id": broker_id, **fill})

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        broker_id = str(reqId)
        code = str(errorCode)
        rejection = _ERROR_CODES.get(code)
        with self._cv:
            record = self._records.get(broker_id)
            client_ref = self._pending_refs.get(broker_id) or (record or {}).get("client_id")
            account_id = (record or {}).get("account_id", "")
            # IBKR sends informational and warning callbacks through this same
            # method. Only known order-rejection codes can override status
            # readback; unknown callbacks leave the submit ambiguous until the
            # normal order-state callback arrives or the request times out.
            if rejection is not None:
                self._errors[broker_id] = rejection
            self._cv.notify_all()
        # Do not retain or emit errorString or advancedOrderRejectJson; they can contain
        # account details, provider diagnostics, or other sensitive payloads.
        if client_ref and rejection is not None:
            self._emit({"type": "reject", "account_id": account_id,
                        "client_id": str(client_ref), "code": rejection})

    def position(self, account, contract, position, avgCost):
        record = {"account_id": str(account), "contract": self._contract_record(contract),
                  "position": int(float(position))}
        with self._lock:
            self._positions.append(record)

    def positionEnd(self):
        self._positions_ready.set()

    def completedOrder(self, contract, order, orderState):
        order_record = self._order_record(order)
        broker_id = str(getattr(order, "orderId", ""))
        if not broker_id:
            return
        record = {"account_id": order_record["account"], "broker_id": broker_id,
                  "client_id": order_record["orderRef"], "contract": self._contract_record(contract),
                  "order": order_record, "status": str(getattr(orderState, "status", "")),
                  "filled": 0}
        with self._cv:
            old = self._records.get(broker_id)
            if old:
                record["filled"] = max(int(old.get("filled", 0)), int(record["filled"]))
                if old.get("fills"):
                    record["fills"] = list(old["fills"])
            self._records[broker_id] = record
            if self._collecting_completed:
                self._completed_snapshot.add(broker_id)
            self._pending_refs[broker_id] = order_record["orderRef"]
            self._cv.notify_all()

    def completedOrdersEnd(self):
        with self._lock:
            self._collecting_completed = False
        self._completed_orders_ready.set()

    def connectionClosed(self):
        self._ready.clear()

    def _make_contract(self, values: dict):
        contract = self._contract_factory()
        for key, value in values.items():
            setattr(contract, key, value)
        return contract

    def _make_order(self, values: dict):
        order = self._order_factory()
        for key, value in values.items():
            setattr(order, key, value)
        return order

    def place_order(self, account_id: str, contract: dict, order: dict) -> dict:
        self._require_account(account_id)
        with self._cv:
            if self._next_order_id is None:
                return {"status": "timeout"}
            broker_id = str(self._next_order_id)
            self._next_order_id += 1
            self._pending_refs[broker_id] = str(order["orderRef"])
            self._records[broker_id] = {"account_id": account_id, "broker_id": broker_id,
                                        "client_id": str(order["orderRef"]),
                                        "contract": dict(contract), "order": dict(order),
                                        "status": "PendingSubmit", "filled": 0}
            self._errors.pop(broker_id, None)
        try:
            self._client.placeOrder(int(broker_id), self._make_contract(contract), self._make_order(order))
        except (ConnectionError, OSError, TimeoutError):
            return {"status": "timeout"}
        deadline = time.monotonic() + self.timeout_s
        with self._cv:
            while time.monotonic() < deadline:
                code = self._errors.get(broker_id)
                if code:
                    return {"status": "rejected", "code": code}
                record = self._records.get(broker_id, {})
                if record.get("status", "").lower() in {
                    "pendingsubmit", "presubmitted", "submitted", "partiallyfilled", "filled"
                } and record.get("status") != "PendingSubmit":
                    return {"status": "ack", "broker_id": broker_id}
                self._cv.wait(max(0, deadline - time.monotonic()))
        return {"status": "timeout"}

    def find_order_by_ref(self, account_id: str, order_ref: str) -> dict | None:
        self._require_account(account_id)
        self.open_orders(account_id)
        self._completed_orders_ready.clear()
        with self._lock:
            self._collecting_completed = True
            self._completed_snapshot = set()
        try:
            self._client.reqCompletedOrders(False)
            completed = self._completed_orders_ready.wait(self.timeout_s)
        except (AttributeError, ConnectionError, OSError, TimeoutError):
            # Current open-order readback still prevents a blind retry when present.
            completed = False
        finally:
            with self._lock:
                self._collecting_completed = False
        with self._lock:
            matches = [dict(row) for row in self._records.values()
                       if row.get("account_id") == account_id and row.get("client_id") == order_ref]
        if not matches:
            # A completed-order request can time out or report only API orders. If this
            # adapter previously attempted the ref, absence is ambiguous, never proof
            # that it is safe to submit it a second time.
            if not completed:
                return {"account_id": account_id, "broker_id": "", "client_id": order_ref,
                        "status": "Unknown"}
            return None
        current = [row for row in matches
                   if row.get("broker_id") in self._open_snapshot | self._completed_snapshot]
        if current:
            return current[-1]
        # The ref has existed but neither current-open nor completed-order readback
        # resolves it. Tell the adapter to remain ambiguous; never treat it as new.
        stale = dict(matches[-1])
        stale["status"] = "Unknown"
        return stale

    def cancel_order(self, account_id: str, broker_id: str) -> dict:
        self._require_account(account_id)
        with self._lock:
            record = self._records.get(str(broker_id))
        if record is None or record.get("account_id") != account_id:
            return {"status": "not_found"}
        try:
            self._client.cancelOrder(int(broker_id))
        except (ConnectionError, OSError, TimeoutError):
            return {"status": "timeout"}
        return {"status": "ok"}

    def modify_order(self, account_id: str, broker_id: str, order: dict) -> dict:
        self._require_account(account_id)
        with self._lock:
            record = self._records.get(str(broker_id))
        if record is None or record.get("account_id") != account_id:
            return {"status": "not_found"}
        if order.get("account") != account_id or order.get("orderRef") != record.get("client_id"):
            raise PermissionError("IBKR replace must preserve selected paper account and orderRef")
        price_field = "lmtPrice" if order.get("orderType") == "LMT" else "auxPrice"
        if price_field not in order:
            raise ValueError("IBKR replace must include the updated order price")
        with self._cv:
            self._pending_replacements[str(broker_id)] = {
                "order": dict(order), "price": float(_decimal(order[price_field], "replace price")),
            }
        try:
            self._client.placeOrder(int(broker_id), self._make_contract(record["contract"]),
                                    self._make_order(order))
        except (ConnectionError, OSError, TimeoutError):
            return {"status": "timeout"}
        return {"status": "ok"}

    def open_orders(self, account_id: str) -> list[dict]:
        self._require_account(account_id)
        self._open_orders_ready.clear()
        with self._lock:
            self._collecting_open = True
            self._open_snapshot = set()
        self._client.reqAllOpenOrders()
        if not self._open_orders_ready.wait(self.timeout_s):
            with self._lock:
                self._collecting_open = False
            raise TimeoutError("IBKR open-order readback timed out")
        with self._lock:
            return [dict(self._records[broker_id]) for broker_id in self._open_snapshot
                    if broker_id in self._records and
                    self._records[broker_id].get("account_id") == account_id and
                    self._records[broker_id].get("status", "").lower() not in {"filled", "cancelled", "canceled", "apicancelled", "inactive", "rejected", "expired"}]

    def positions(self, account_id: str) -> list[dict]:
        self._require_account(account_id)
        self._positions_ready.clear()
        with self._lock:
            self._positions = []
        self._client.reqPositions()
        if not self._positions_ready.wait(self.timeout_s):
            raise TimeoutError("IBKR position readback timed out")
        try:
            self._client.cancelPositions()
        except AttributeError:
            pass
        with self._lock:
            return [dict(row) for row in self._positions if row["account_id"] == account_id]

    def poll_events(self, account_id: str) -> list[dict]:
        with self._lock:
            selected = [event for event in self._events if event.get("account_id") == account_id]
            self._events = [event for event in self._events if event.get("account_id") != account_id]
        return [{key: value for key, value in event.items() if key != "account_id"}
                for event in selected]


def _decimal(value: Any, field: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{field} must be a finite decimal") from exc
    if not number.is_finite():
        raise ValueError(f"{field} must be a finite decimal")
    return number


@dataclass(frozen=True)
class ContractMapping:
    """A reviewed, immutable mapping for one exact futures month on IBKR."""

    symbol: str
    con_id: int
    local_symbol: str
    contract_month: str  # IBKR format YYYYMM; exact contract only
    exchange: str
    currency: str
    multiplier: Decimal
    tick_size: Decimal

    def __post_init__(self):
        match = _DATED_FUTURE.fullmatch(self.symbol)
        if not match:
            raise ValueError("contract mapping symbol must be an exact dated futures code")
        root, month_code, year_suffix = match.groups()
        if root not in SPECS:
            raise ValueError(f"unsupported futures root: {root}")
        spec = SPECS[root]
        if len(self.contract_month) != 6 or not self.contract_month.isdigit():
            raise ValueError("contract_month must be an exact YYYYMM value")
        year, month = int(self.contract_month[:4]), int(self.contract_month[4:])
        if not 1 <= month <= 12 or MONTH_CODES[month - 1] != month_code or year % 100 != int(year_suffix):
            raise ValueError("symbol and exact contract_month do not identify the same contract")
        if self.con_id <= 0 or not self.local_symbol.strip():
            raise ValueError("mapping requires a positive conId and explicit localSymbol")
        if self.exchange != spec.exchange:
            raise ValueError(f"exchange for {root} must be {spec.exchange}")
        if self.currency != "USD":
            raise ValueError("only explicitly reviewed USD CME futures mappings are supported")
        if _decimal(self.tick_size, "tick_size") != _decimal(str(spec.tick_size), "tick_size"):
            raise ValueError(f"tick_size for {root} must match the checked futures specification")
        if _decimal(self.multiplier, "multiplier") != _decimal(str(spec.point_value), "multiplier"):
            raise ValueError(f"multiplier for {root} must match the checked futures specification")
        object.__setattr__(self, "multiplier", _decimal(self.multiplier, "multiplier"))
        object.__setattr__(self, "tick_size", _decimal(self.tick_size, "tick_size"))

    @property
    def root(self) -> str:
        return _DATED_FUTURE.fullmatch(self.symbol).group(1)

    def ib_contract(self) -> dict:
        return {
            "conId": self.con_id,
            "symbol": self.root,
            "secType": "FUT",
            "exchange": self.exchange,
            "currency": self.currency,
            "lastTradeDateOrContractMonth": self.contract_month,
            "localSymbol": self.local_symbol,
            "multiplier": format(self.multiplier, "f"),
            "includeExpired": False,
        }


class IbkrPaperVenue:
    """IBKR TWS/IB Gateway PAPER adapter with one fixed account and exact mappings."""

    name = "ibkr_tws_paper"
    kind = "PAPER"

    def __init__(self, gateway: IbkrPaperGateway, account_id: str,
                 contracts: Mapping[str, ContractMapping]):
        if not isinstance(account_id, str) or not _PAPER_ACCOUNT.fullmatch(account_id):
            raise PermissionError("an explicit DU... paper account is required")
        if str(getattr(gateway, "environment", "")).upper() != "PAPER":
            raise PermissionError("IBKR gateway session must identify as PAPER")
        if not gateway.is_connected():
            raise ConnectionError("IBKR PAPER session is disconnected")
        if account_id not in gateway.managed_accounts():
            raise PermissionError("selected paper account is not managed by this session")
        if not contracts:
            raise ValueError("at least one explicit dated futures contract mapping is required")
        normalized: dict[str, ContractMapping] = {}
        for key, mapping in contracts.items():
            if key != mapping.symbol:
                raise ValueError("mapping key must equal its exact dated contract symbol")
            if key in normalized:
                raise ValueError(f"duplicate futures mapping: {key}")
            normalized[key] = mapping
        con_ids = [mapping.con_id for mapping in normalized.values()]
        local_symbols = [mapping.local_symbol for mapping in normalized.values()]
        if len(con_ids) != len(set(con_ids)):
            raise ValueError("each dated futures mapping must use a unique IBKR conId")
        if len(local_symbols) != len(set(local_symbols)):
            raise ValueError("each dated futures mapping must use a unique IBKR localSymbol")
        self.gateway = gateway
        self.account_id = account_id
        self.contracts = normalized
        self._by_con_id = {m.con_id: m.symbol for m in normalized.values()}
        self._by_local_symbol = {m.local_symbol: m.symbol for m in normalized.values()}
        self._attempted_refs: set[str] = set()
        self._broker_to_client: dict[str, str] = {}
        self._events: list[dict] = []

    def _connected(self) -> bool:
        try:
            return bool(self.gateway.is_connected())
        except Exception:
            return False

    def _mapping(self, symbol: str) -> ContractMapping:
        if symbol not in self.contracts:
            raise ValueError(f"futures contract is not explicitly mapped: {symbol!r}")
        return self.contracts[symbol]

    @staticmethod
    def _order_ref(order_id: str) -> str:
        if not isinstance(order_id, str) or not order_id or len(order_id) > 64:
            raise ValueError("client order reference must be 1 to 64 characters")
        if not order_id.isascii():
            raise ValueError("client order reference must be ASCII")
        return order_id

    @staticmethod
    def _price(mapping: ContractMapping, value: Any, *, required: bool) -> Decimal | None:
        if value is None:
            if required:
                raise ValueError("limit/stop order requires a price")
            return None
        price = _decimal(value, "price")
        if price <= 0:
            raise ValueError("price must be greater than zero")
        ticks = price / mapping.tick_size
        if ticks != ticks.to_integral_value():
            raise ValueError(f"price must align to {mapping.tick_size} tick")
        return price

    def _build_order(self, mapping: ContractMapping, order_ref: str, side: str,
                     qty: int, kind: str, price: Any) -> dict:
        side = str(side).upper()
        if side not in ("BUY", "SELL"):
            raise ValueError("side must be BUY or SELL")
        if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
            raise ValueError("futures quantity must be a positive whole-contract quantity")
        kind = str(kind).upper()
        if kind not in _VALID_ORDER_KINDS:
            raise ValueError(f"unsupported order kind: {kind}")
        normalized_price = self._price(mapping, price, required=kind != "MARKET")
        if kind == "MARKET" and normalized_price is not None:
            raise ValueError("market order must not carry a limit or stop price")
        request = {
            "account": self.account_id,
            "action": side,
            "totalQuantity": qty,
            "orderType": _VALID_ORDER_KINDS[kind],
            "tif": "DAY",
            "orderRef": order_ref,
            "outsideRth": False,
        }
        if normalized_price is not None:
            request["lmtPrice" if kind == "LIMIT" else "auxPrice"] = float(normalized_price)
        return request

    def _normalize_found_order(self, record: dict, order_ref: str) -> dict:
        account_id = record.get("account_id") or record.get("order", {}).get("account")
        client_ref = record.get("client_id") or record.get("order", {}).get("orderRef")
        if account_id != self.account_id:
            raise PermissionError("IBKR order readback is outside the selected paper account")
        if client_ref != order_ref:
            raise ValueError("IBKR order readback does not match the requested orderRef")
        status = str(record.get("status", "")).lower()
        broker_id = str(record.get("broker_id", ""))
        if not broker_id:
            return {"status": "timeout"}
        self._broker_to_client[broker_id] = order_ref
        if status in {"rejected", "inactive"}:
            self._events.append({"type": "reject", "client_id": order_ref, "code": "UNKNOWN"})
            return {"status": "rejected", "code": "UNKNOWN"}
        if status not in {"pendingsubmit", "presubmitted", "submitted", "partiallyfilled",
                          "filled", "cancelled", "canceled", "apicancelled", "expired"}:
            return {"status": "timeout"}
        fills = record.get("fills", [])
        filled = int(record.get("filled", 0))
        if (filled or status in {"partiallyfilled", "filled"}) and not fills:
            # The ref proves the order exists, but a position-changing partial/full
            # execution must also be rebuilt before it can be called reconciled.
            return {"status": "timeout"}
        self._events.append({"type": "ack", "client_id": order_ref, "broker_id": broker_id})
        for fill in fills:
            self._events.append({"type": "fill", "client_id": order_ref, "broker_id": broker_id,
                                 "fill_id": str(fill["fill_id"]), "qty": int(fill["qty"]),
                                 "price": float(_decimal(fill["price"], "fill price"))})
        if status in {"cancelled", "canceled", "apicancelled"}:
            self._events.append({"type": "cancel_ack", "client_id": order_ref,
                                 "broker_id": broker_id})
        elif status == "expired":
            self._events.append({"type": "expire", "client_id": order_ref,
                                 "broker_id": broker_id})
        return {"status": "ack", "broker_id": broker_id}

    def submit(self, order_id: str, symbol: str, side: str, qty: int, kind: str,
               price: float | None) -> dict:
        order_ref = self._order_ref(order_id)
        mapping = self._mapping(symbol)
        request = self._build_order(mapping, order_ref, side, qty, kind, price)
        if not self._connected():
            return {"status": "timeout"}
        attempted_before = order_ref in self._attempted_refs
        try:
            found = self.gateway.find_order_by_ref(self.account_id, order_ref)
        except (ConnectionError, TimeoutError, OSError):
            return {"status": "timeout"}
        if found:
            return self._normalize_found_order(found, order_ref)
        if attempted_before:
            # Readback must be conclusive before retrying. A callback timeout or
            # incomplete completed-order snapshot leaves execution ambiguous.
            return {"status": "timeout"}
        # A client ref whose submit outcome is unknown may only be resolved by readback.
        # It is never submitted twice by this adapter instance.
        if order_ref in self._attempted_refs:
            return {"status": "timeout"}
        self._attempted_refs.add(order_ref)
        try:
            result = self.gateway.place_order(self.account_id, mapping.ib_contract(), request)
        except (ConnectionError, TimeoutError, OSError):
            return {"status": "timeout"}
        status = str(result.get("status", "")).lower()
        if status == "ack" and result.get("broker_id") is not None:
            broker_id = str(result["broker_id"])
            self._broker_to_client[broker_id] = order_ref
            self._events.append({"type": "ack", "client_id": order_ref, "broker_id": broker_id})
            return {"status": "ack", "broker_id": broker_id}
        if status in {"timeout", "unknown", "ambiguous"}:
            return {"status": "timeout"}
        if status == "rejected":
            raw_code = str(result.get("code", ""))
            code = raw_code if raw_code in _ERROR_CODES.values() else _ERROR_CODES.get(raw_code, "UNKNOWN")
            self._events.append({"type": "reject", "client_id": order_ref, "code": code})
            return {"status": "rejected", "code": code}
        return {"status": "timeout"}

    def _record_symbol(self, record: dict) -> str:
        contract = record.get("contract", {})
        symbol = contract.get("canonical_symbol") or contract.get("symbol")
        if symbol in self.contracts:
            return symbol
        con_id = contract.get("conId", contract.get("con_id"))
        local = contract.get("localSymbol", contract.get("local_symbol"))
        mapped = self._by_con_id.get(con_id) or self._by_local_symbol.get(local)
        if mapped is None:
            raise ValueError("IBKR readback contains a contract without an explicit mapping")
        return mapped

    def _record_client(self, record: dict) -> str:
        client = record.get("client_id") or record.get("order", {}).get("orderRef")
        if client:
            return str(client)
        broker_id = str(record.get("broker_id", ""))
        if broker_id in self._broker_to_client:
            return self._broker_to_client[broker_id]
        raise ValueError("IBKR order readback omitted orderRef")

    def _normalized_open_order(self, record: dict) -> dict:
        account_id = record.get("account_id") or record.get("order", {}).get("account")
        if account_id != self.account_id:
            raise PermissionError("IBKR open-order readback is outside the selected paper account")
        symbol = self._record_symbol(record)
        client_id = self._record_client(record)
        broker_id = str(record.get("broker_id", ""))
        if not broker_id:
            raise ValueError("IBKR open order readback omitted broker order id")
        order = record.get("order", {})
        quantity = int(order.get("totalQuantity", record.get("quantity", 0)))
        filled = int(record.get("filled", 0))
        if quantity <= 0 or filled < 0 or filled > quantity:
            raise ValueError("IBKR open order readback has invalid quantity")
        action = str(order.get("action", record.get("side", ""))).upper()
        if action not in {"BUY", "SELL"}:
            raise ValueError("IBKR open order readback has invalid side")
        order_type = str(order.get("orderType", "")).upper()
        if order_type == "LMT":
            price = order.get("lmtPrice")
        elif order_type == "STP":
            price = order.get("auxPrice")
        else:
            price = None
        self._broker_to_client[broker_id] = client_id
        return {"broker_id": broker_id, "client_id": client_id, "symbol": symbol,
                "side": action, "remaining": quantity - filled, "price": price}

    def open_orders(self) -> list[dict]:
        if not self._connected():
            raise ConnectionError("IBKR PAPER session is disconnected")
        return [self._normalized_open_order(row)
                for row in self.gateway.open_orders(self.account_id)]

    def positions(self) -> dict[str, int]:
        if not self._connected():
            raise ConnectionError("IBKR PAPER session is disconnected")
        positions: dict[str, int] = {}
        for row in self.gateway.positions(self.account_id):
            if row.get("account_id") != self.account_id:
                raise PermissionError("IBKR position readback is outside the selected paper account")
            symbol = row.get("symbol") or self._record_symbol({"contract": row.get("contract", {})})
            if symbol not in self.contracts:
                raise ValueError("IBKR position readback contains a contract without an explicit mapping")
            quantity = row.get("position")
            if isinstance(quantity, bool) or not isinstance(quantity, int):
                raise ValueError("IBKR futures position must be a whole-contract integer")
            positions[symbol] = positions.get(symbol, 0) + quantity
        return {symbol: quantity for symbol, quantity in positions.items() if quantity}

    def cancel(self, broker_id: str, client_id: str | None = None) -> dict:
        if client_id is None:
            raise ValueError("IBKR cancellation requires the originating client order ID")
        client_id = self._order_ref(client_id)
        broker_id = str(broker_id)
        if not self._connected():
            return {"status": "timeout"}
        try:
            open_orders = self.gateway.open_orders(self.account_id)
        except (ConnectionError, TimeoutError, OSError):
            return {"status": "timeout"}
        record = next((r for r in open_orders if str(r.get("broker_id", "")) == broker_id), None)
        if record is None:
            return {"status": "not_found"}
        self._normalized_open_order(record)  # reject unmapped/foreign readback
        if self._record_client(record) != client_id:
            return {"status": "not_found"}
        try:
            result = self.gateway.cancel_order(self.account_id, broker_id)
        except (ConnectionError, TimeoutError, OSError):
            return {"status": "timeout"}
        return {"status": str(result.get("status", "timeout")).lower()}

    def replace(self, broker_id: str, new_price: float, client_id: str | None = None) -> dict:
        if client_id is None:
            raise ValueError("IBKR replace requires the originating client order ID")
        client_id = self._order_ref(client_id)
        broker_id = str(broker_id)
        if not self._connected():
            return {"status": "timeout"}
        try:
            open_orders = self.gateway.open_orders(self.account_id)
        except (ConnectionError, TimeoutError, OSError):
            return {"status": "timeout"}
        record = next((r for r in open_orders if str(r.get("broker_id", "")) == broker_id), None)
        if record is None:
            return {"status": "not_found"}
        if self._record_client(record) != client_id:
            return {"status": "not_found"}
        symbol = self._record_symbol(record)
        mapping = self.contracts[symbol]
        current = record.get("order", {})
        order_type = str(current.get("orderType", "")).upper()
        if order_type not in {"LMT", "STP"}:
            return {"status": "unsupported"}
        price = self._price(mapping, new_price, required=True)
        request = dict(current)
        request["account"] = self.account_id
        request["orderRef"] = self._record_client(record)
        request["outsideRth"] = False
        request["lmtPrice" if order_type == "LMT" else "auxPrice"] = float(price)
        try:
            result = self.gateway.modify_order(self.account_id, broker_id, request)
        except (ConnectionError, TimeoutError, OSError):
            return {"status": "timeout"}
        return {"status": str(result.get("status", "timeout")).lower()}

    def poll(self) -> list[dict]:
        if not self._connected():
            raise ConnectionError("IBKR PAPER session is disconnected")
        raw_events = self.gateway.poll_events(self.account_id)
        events = list(self._events)
        for event in raw_events:
            kind = str(event.get("type", ""))
            broker_id = str(event.get("broker_id", "")) if event.get("broker_id") is not None else ""
            client_id = event.get("client_id") or self._broker_to_client.get(broker_id)
            if not client_id:
                raise ValueError("IBKR event omitted the orderRef needed for reconciliation")
            if kind == "ack":
                broker_id = str(event.get("broker_id", ""))
                if not broker_id:
                    raise ValueError("IBKR acknowledgement omitted broker order id")
                self._broker_to_client[broker_id] = str(client_id)
                events.append({"type": "ack", "client_id": str(client_id), "broker_id": broker_id})
            elif kind == "fill":
                events.append({"type": "fill", "client_id": str(client_id),
                               "broker_id": broker_id or None,
                               "fill_id": str(event["fill_id"]), "qty": int(event["qty"]),
                               "price": float(_decimal(event["price"], "fill price"))})
            elif kind in {"cancel_ack", "expire"}:
                events.append({"type": kind, "client_id": str(client_id),
                               **({"broker_id": broker_id} if broker_id else {})})
            elif kind == "replace_ack":
                events.append({"type": kind, "client_id": str(client_id),
                               "price": float(_decimal(event["price"], "replace price"))})
            elif kind == "reject":
                code = _ERROR_CODES.get(str(event.get("code", "")), "UNKNOWN")
                events.append({"type": "reject", "client_id": str(client_id), "code": code})
            else:
                raise ValueError(f"unsupported normalized IBKR event type: {kind!r}")
        self._events = []
        unique = []
        seen = set()
        for event in events:
            identity = (event.get("type"), event.get("client_id"), event.get("broker_id"),
                        event.get("fill_id"), event.get("code"), event.get("price"))
            if identity not in seen:
                seen.add(identity)
                unique.append(event)
        return unique
