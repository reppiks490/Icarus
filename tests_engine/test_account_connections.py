"""Account isolation and policy gates; transports use synthetic responses only."""
import json
import os
import time

import pytest

from icarus_engine.account_connections import ConnectionManager, evaluate_rules


def test_nested_private_store_corruption_never_enters_public_account_status(tmp_path):
    manager = ConnectionManager(tmp_path, env={})
    manager.upsert(record())
    path = manager.root / "connections.json"
    rows = json.loads(path.read_text())
    rows["paper_one"]["readback"] = {"api_key": "PRIVATE_NESTED_MARKER"}
    path.write_text(json.dumps(rows))
    with pytest.raises(ValueError, match="account store unavailable"):
        manager.snapshot()


def test_stored_credential_references_cannot_be_rebound_to_other_secrets(tmp_path):
    manager = ConnectionManager(tmp_path, env={"OTHER_PRIVATE_SECRET": "PRIVATE_MARKER"})
    manager.upsert(record())
    path = manager.root / "connections.json"
    rows = json.loads(path.read_text())
    rows["paper_one"]["credential_refs"]["api_key"] = "OTHER_PRIVATE_SECRET"
    path.write_text(json.dumps(rows))
    with pytest.raises(ValueError, match="account store unavailable"):
        manager.snapshot()


def test_failed_configuration_save_preserves_previously_encrypted_credentials(tmp_path, monkeypatch):
    import base64
    calls = []
    def fetch(method, url, headers, payload):
        calls.append(headers)
        return {"id": "fixture-account", "status": "ACTIVE", "currency": "USD", "equity": "100", "cash": "100"}
    manager = ConnectionManager(tmp_path, env={"ICARUS_CONNECTION_STORE_KEY": base64.b64encode(b"x" * 32).decode()}, transport=fetch)
    body = record()
    body["credential_refs"] = {}
    body["credentials"] = {"api_key": "ORIGINAL_FIXTURE_KEY", "secret_key": "ORIGINAL_FIXTURE_SECRET"}
    manager.upsert(body)
    replacement = {**body, "credentials": {"api_key": "REPLACEMENT_FIXTURE_KEY", "secret_key": "REPLACEMENT_FIXTURE_SECRET"}}
    with monkeypatch.context() as patch:
        patch.setattr(manager, "_save", lambda: (_ for _ in ()).throw(OSError("fixture save failure")))
        with pytest.raises(OSError):
            manager.upsert(replacement)
    assert manager.connect("paper_one")["status"] == "CONNECTED_READ_ONLY"
    assert calls[0]["APCA-API-KEY-ID"] == "ORIGINAL_FIXTURE_KEY"


def test_failed_initial_configuration_save_leaves_no_orphan_secret(tmp_path, monkeypatch):
    import base64
    manager = ConnectionManager(tmp_path, env={"ICARUS_CONNECTION_STORE_KEY": base64.b64encode(b"x" * 32).decode()})
    body = record()
    body["credential_refs"] = {}
    body["credentials"] = {"api_key": "FIXTURE_KEY", "secret_key": "FIXTURE_SECRET"}
    monkeypatch.setattr(manager, "_save", lambda: (_ for _ in ()).throw(OSError("fixture save failure")))
    with pytest.raises(OSError):
        manager.upsert(body)
    assert not list(manager.root.glob("*.enc"))
    assert manager.snapshot()["connections"] == []


def record(**changes):
    return dict(id="paper_one", alias="Paper one", platform="alpaca_paper",
                environment="paper", firm="independent", program="paper",
                credential_refs={"api_key": "ALPACA_API_KEY", "secret_key": "ALPACA_SECRET_KEY"}, **changes)


def test_configuration_is_not_connection_and_secrets_never_enter_metadata(tmp_path):
    env = {"ALPACA_API_KEY": "PRIVATE_KEY", "ALPACA_SECRET_KEY": "PRIVATE_SECRET"}
    m = ConnectionManager(tmp_path, env=env, transport=lambda *a: pytest.fail("no implicit request"))
    first = m.upsert(record())
    assert first["status"] == "CONFIGURED"
    assert first["execution_authorized"] is False
    assert m.upsert(record())["revision"] == first["revision"]
    public = json.dumps(m.snapshot())
    assert "PRIVATE_KEY" not in public and "PRIVATE_SECRET" not in public
    assert not any("PRIVATE_" in p.read_text() for p in tmp_path.rglob("*.json"))


def test_actual_readback_is_required_and_account_identifiers_are_masked(tmp_path):
    calls = []
    def fetch(method, url, headers, payload):
        calls.append((method, url, headers, payload))
        return {"id": "FULL_ACCOUNT_IDENTIFIER", "status": "ACTIVE", "currency": "USD",
                "equity": "101.25", "cash": "98", "trading_blocked": False}
    m = ConnectionManager(tmp_path, env={"ALPACA_API_KEY": "key", "ALPACA_SECRET_KEY": "secret"}, transport=fetch, clock=lambda: 1000)
    m.upsert(record())
    result = m.connect("paper_one")
    assert result["status"] == "CONNECTED_READ_ONLY"
    assert result["readback"]["equity"] == 101.25
    assert result["execution_authorized"] is False
    assert "FULL_ACCOUNT_IDENTIFIER" not in json.dumps(result)
    assert calls[0][0:2] == ("GET", "https://paper-api.alpaca.markets/v2/account")
    assert calls[0][3] is None
    assert "FULL_ACCOUNT_IDENTIFIER" not in "".join(p.read_text() for p in tmp_path.rglob("*.json"))


def test_missing_credentials_and_unsupported_platform_make_no_requests(tmp_path):
    m = ConnectionManager(tmp_path, env={}, transport=lambda *a: pytest.fail("must not request"))
    m.upsert(record())
    assert m.connect("paper_one")["status"] == "MISSING_CREDENTIALS"
    m.upsert(dict(record(), id="other", platform="rithmic", credential_refs={}))
    assert m.connect("other")["status"] == "UNSUPPORTED"


@pytest.mark.parametrize("changes", [{"url": "https://attacker.example"}, {"environment": "live"},
    {"id": "../secret"}, {"credential_refs": {"api_key": "PATH"}},
    {"credential_refs": {"api_key": "ALPACA_SECRET_KEY"}}, {"alias": "x" * 201}])
def test_invalid_configuration_cannot_change_hosts_or_secret_sources(tmp_path, changes):
    m = ConnectionManager(tmp_path)
    with pytest.raises(ValueError):
        m.upsert(dict(record(), **changes))


def test_errors_never_echo_transport_tokens_or_old_balances(tmp_path):
    def fail(*args): raise RuntimeError("PRIVATE_PROVIDER_TOKEN")
    m = ConnectionManager(tmp_path, env={"ALPACA_API_KEY": "key", "ALPACA_SECRET_KEY": "secret"}, transport=fail)
    m.upsert(record())
    result = m.connect("paper_one")
    assert result["status"] == "READBACK_FAILED"
    assert result["readback"] is None
    assert "PRIVATE_PROVIDER_TOKEN" not in json.dumps(result)


def test_connection_state_is_account_scoped_and_expires(tmp_path):
    now = [1000]
    m = ConnectionManager(tmp_path, env={"ALPACA_API_KEY": "key", "ALPACA_SECRET_KEY": "secret"},
        clock=lambda: now[0], transport=lambda *a: {"id": "one", "status": "ACTIVE", "equity": "10", "cash": "10", "currency": "USD"})
    m.upsert(record())
    m.upsert(dict(record(), id="paper_two"))
    m.connect("paper_one")
    rows = {r["id"]: r for r in m.snapshot()["connections"]}
    assert rows["paper_two"]["status"] == "CONFIGURED"
    now[0] += 61
    assert m.snapshot()["connections"][0]["status"] == "STALE_READBACK"


def test_switching_external_account_rejects_rebinding(tmp_path):
    accounts = iter(("one", "two"))
    m = ConnectionManager(tmp_path, env={"ALPACA_API_KEY": "key", "ALPACA_SECRET_KEY": "secret"},
        transport=lambda *a: {"id": next(accounts), "status": "ACTIVE", "equity": "10", "cash": "10", "currency": "USD"})
    m.upsert(record())
    assert m.connect("paper_one")["status"] == "CONNECTED_READ_ONLY"
    assert m.connect("paper_one")["status"] == "ACCOUNT_IDENTITY_MISMATCH"


def test_duplicate_external_account_cannot_be_connected_twice(tmp_path):
    m = ConnectionManager(tmp_path, env={"ALPACA_API_KEY": "key", "ALPACA_SECRET_KEY": "secret"},
        transport=lambda *a: {"id": "same-account", "status": "ACTIVE", "equity": "10", "cash": "10", "currency": "USD"})
    m.upsert(record())
    m.upsert(dict(record(), id="paper_two"))
    assert m.connect("paper_one")["status"] == "CONNECTED_READ_ONLY"
    duplicate = m.connect("paper_two")
    assert duplicate["status"] == "DUPLICATE_ACCOUNT"
    assert duplicate["readback"] is None


def test_tampered_local_metadata_never_becomes_a_secret_status_response(tmp_path):
    m = ConnectionManager(tmp_path)
    m.upsert(record())
    path = tmp_path / ".account_connections" / "connections.json"
    saved = json.loads(path.read_text())
    saved["paper_one"]["credentials"] = {"secret": "LEAK_MARKER"}
    path.write_text(json.dumps(saved))
    with pytest.raises(ValueError): m.snapshot()


@pytest.mark.parametrize("field,value", [("equity", "nan"), ("cash", True), ("currency", "SECRET_DATA"), ("id", "")])
def test_invalid_account_response_never_establishes_connection(tmp_path, field, value):
    response = dict(id="one", status="ACTIVE", equity="10", cash="10", currency="USD")
    response[field] = value
    m = ConnectionManager(tmp_path, env={"ALPACA_API_KEY": "key", "ALPACA_SECRET_KEY": "secret"}, transport=lambda *a: response)
    m.upsert(record())
    assert m.connect("paper_one")["status"] == "READBACK_FAILED"


def test_direct_transport_has_no_order_or_host_override_surface():
    from icarus_engine.account_connections import _transport
    for method, url in [("POST", "https://paper-api.alpaca.markets/v2/orders"), ("GET", "https://attacker.example/v2/account")]:
        with pytest.raises(ValueError): _transport(method, url, {}, None)


def test_stale_readback_survives_reload_as_stale_not_new_connection(tmp_path):
    m = ConnectionManager(tmp_path, env={"ALPACA_API_KEY": "key", "ALPACA_SECRET_KEY": "secret"}, clock=lambda: 1000,
        transport=lambda *a: dict(id="one", status="ACTIVE", equity="10", cash="10", currency="USD"))
    m.upsert(record())
    m.connect("paper_one")
    assert ConnectionManager(tmp_path, clock=lambda: 1061).snapshot()["connections"][0]["status"] == "STALE_READBACK"


def test_ui_uses_ephemeral_bearer_for_authenticated_gets():
    from pathlib import Path
    script = Path(__file__).parents[1] / "icarus_engine" / "connections-ui.js"
    text = script.read_text()
    assert "innerHTML" not in text and "localStorage" not in text and "sessionStorage" not in text
    assert "request('/api/account-connections', {headers: auth()})" in text


def test_plaintext_owner_credentials_require_secure_key_and_never_persist(tmp_path):
    m = ConnectionManager(tmp_path, env={})
    body = dict(record(), credential_refs={}, credentials={"api_key": "OWNER_PRIVATE", "secret_key": "OWNER_SECRET"})
    with pytest.raises(ValueError): m.upsert(body)
    assert not list(tmp_path.rglob("*.enc"))
    assert "OWNER_PRIVATE" not in json.dumps(m.snapshot())


def test_encrypted_owner_credentials_roundtrip_without_plaintext_files(tmp_path):
    pytest.importorskip("cryptography")
    import base64
    env = {"ICARUS_CONNECTION_STORE_KEY": base64.b64encode(b"k" * 32).decode()}
    seen = []
    def fetch(method, url, headers, payload):
        seen.append(headers["APCA-API-KEY-ID"])
        return {"id": "one", "status": "ACTIVE", "equity": "10", "cash": "10", "currency": "USD"}
    m = ConnectionManager(tmp_path, env=env, transport=fetch)
    m.upsert(dict(record(), credential_refs={}, credentials={"api_key": "OWNER_PRIVATE", "secret_key": "OWNER_SECRET"}))
    assert m.connect("paper_one")["status"] == "CONNECTED_READ_ONLY"
    assert seen == ["OWNER_PRIVATE"]
    assert all(b"OWNER_PRIVATE" not in p.read_bytes() for p in tmp_path.rglob("*") if p.is_file())
    assert all(p.stat().st_mode & 0o077 == 0 for p in tmp_path.rglob("*") if p.is_file())


def policy():
    return {"status": "VERIFIED", "verified_at": 900, "expires_at": 2000,
        "sources": ["https://official.example/faq"], "unsupported_clauses": [], "unknown_clauses": [],
        "connection_id": "paper_one", "quantity_basis": "weighted_contracts",
        "daily_loss_limit": 100, "drawdown_limit": 200, "max_contracts": 5,
        "allowed_assets": ["MNQ"], "contract_weights": {"MNQ": 1},
        "session_timezone": "UTC", "session_weekdays": [3], "session_start": "00:00", "session_end": "23:59",
        "news_before_seconds": 60, "news_after_seconds": 60, "consistency_max_ratio": .5,
        "faq_coverage_complete": True, "loss_basis": "realized_plus_unrealized_after_fees",
        "drawdown_basis": "intraday_high_water_equity"}


def state():
    return {"connection_id": "paper_one", "observed_at": 1000, "daily_realized": 0, "unrealized": 0,
        "fees": 0, "equity": 1000, "high_water_equity": 1000, "positions": {},
        "news_coverage_from": 900, "news_coverage_until": 1100, "news_events": [],
        "best_day_profit": 0, "total_profit": 0}


def test_unknown_bundled_firm_rules_block_all_new_intents(tmp_path):
    m = ConnectionManager(tmp_path)
    assert m.snapshot()["rules"]
    assert all(r["status"] == "UNVERIFIED" for r in m.snapshot()["rules"])
    for r in m.snapshot()["rules"]:
        assert evaluate_rules(r, {}, {}, now=1000)["new_intent_allowed"] is False


def test_complete_fresh_policy_allows_only_a_paper_preflight():
    result = evaluate_rules(policy(), state(), {"connection_id": "paper_one", "symbol": "MNQ", "quantity": 5}, now=1000)
    assert result["new_intent_allowed"] is True
    assert result["execution_authorized"] is False


@pytest.mark.parametrize("update,reason", [({"daily_realized": -100}, "DAILY_LOSS_LIMIT"),
    ({"equity": 800}, "DRAWDOWN_LIMIT"), ({"observed_at": 939}, "STALE_ACCOUNT_STATE"),
    ({"fees": float("nan")}, "INVALID_ACCOUNT_STATE"), ({"connection_id": "other"}, "ACCOUNT_SCOPE_MISMATCH"),
    ({"news_events": [1000]}, "NEWS_RESTRICTION"), ({"news_coverage_until": 1001}, "UNKNOWN_NEWS_COVERAGE"),
    ({"best_day_profit": 60, "total_profit": 100}, "CONSISTENCY_LIMIT")])
def test_policy_boundaries_fail_closed(update, reason):
    result = evaluate_rules(policy(), dict(state(), **update), {"connection_id": "paper_one", "symbol": "MNQ", "quantity": 1}, now=1000)
    assert result["new_intent_allowed"] is False and reason in result["blockers"]


@pytest.mark.parametrize("update", [{"status": "UNVERIFIED"}, {"expires_at": 999}, {"verified_at": 1001},
    {"unknown_clauses": ["payout"]}, {"unsupported_clauses": ["overnight"]}, {"faq_coverage_complete": False},
    {"drawdown_basis": "guessed"}, {"max_contracts": True}, {"sources": []}])
def test_missing_stale_or_unsupported_policy_never_grants_a_pass(update):
    assert evaluate_rules(dict(policy(), **update), state(), {"connection_id": "paper_one", "symbol": "MNQ", "quantity": 1}, now=1000)["new_intent_allowed"] is False
