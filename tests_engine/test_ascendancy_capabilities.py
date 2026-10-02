from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from icarus_engine.ascendancy.capabilities import capability_contract, capability_snapshot
from icarus_engine.runtime import Journal, Portfolio
from icarus_engine.server import serve


REQUIRED_PROVIDERS = {
    "github", "superpowers", "akinator", "astral-orchestrator",
    "adaptive-codex-orchestrator", "baton-pass", "agent-reach",
    "firecrawl", "parallel-search", "scite", "transcriptor", "figma",
    "prompt-perfect", "massive", "twelve-data", "fmp", "bybit",
    "blockscout", "bigdata", "the-fly", "zacks", "us-gold-bureau",
    "stackerscan",
}


def test_capability_snapshot_has_required_providers_and_no_authority():
    out = capability_snapshot()
    ids = {row["id"] for row in out["providers"]}
    assert REQUIRED_PROVIDERS <= ids
    assert out["execution_authorized"] is False
    assert out["production_decision_authorized"] is False
    assert out["schema_version"] == "icarus-ascendancy-capabilities-v1"


def test_blocked_and_unprobed_states_are_truthful():
    rows = {row["id"]: row for row in capability_snapshot()["providers"]}
    assert rows["scite"]["observed_status"] == "BLOCKED_SUBSCRIPTION"
    assert rows["us-gold-bureau"]["observed_status"] == "BLOCKED_NETWORK_POLICY"
    assert rows["prompt-perfect"]["observed_status"] == "VERIFIED"


def test_market_and_chain_truth_boundaries_are_explicit():
    massive = capability_contract("massive")
    bybit = capability_contract("bybit")
    blockscout = capability_contract("blockscout")
    assert {"futures_trades", "futures_quotes", "futures_snapshots"} <= set(massive["claims_allowed"])
    assert "crypto_orderbook" in bybit["claims_allowed"]
    assert "place_orders" in bybit["claims_forbidden"]
    assert "onchain_transactions" in blockscout["claims_allowed"]
    assert "exchange_order_flow" in blockscout["claims_forbidden"]


def test_committed_capability_rows_are_public_contract_only():
    out = capability_snapshot()
    assert all(row["public_contract_only"] is True for row in out["providers"])


def test_unknown_provider_fails_closed():
    assert capability_contract("does-not-exist") is None


@pytest.fixture
def ascendancy_http(tmp_path):
    port = Portfolio(Journal(":memory:"), str(tmp_path))
    srv = serve(port, 0, token="ascendancy-token", start=False)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def request(route: str, *, auth: bool = True):
        headers = {}
        if auth:
            headers["Authorization"] = "Bearer ascendancy-token"
        req = urllib.request.Request(base + route, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as reply:
                return reply.status, json.load(reply)
        except urllib.error.HTTPError as ex:
            return ex.code, json.load(ex)

    yield request
    srv.shutdown()
    srv.server_close()
    thread.join(5)
    port.journal.con.close()


def test_ascendancy_capability_api_is_authenticated_and_truthful(ascendancy_http):
    status, body = ascendancy_http("/api/ascendancy/capabilities", auth=False)
    assert status == 401
    assert "admin token" in body["detail"]

    status, body = ascendancy_http("/api/ascendancy/capabilities")
    assert status == 200
    assert body["schema_version"] == "icarus-ascendancy-capabilities-v1"
    assert body["provider_count"] >= len(REQUIRED_PROVIDERS)
    assert body["blocked_count"] >= 2
    assert body["execution_authorized"] is False
    assert body["production_decision_authorized"] is False
