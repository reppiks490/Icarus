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


def test_interrupted_secret_rotation_preserves_committed_credentials_after_restart(tmp_path, monkeypatch):
    import base64
    env = {"ICARUS_CONNECTION_STORE_KEY": base64.b64encode(b"x" * 32).decode()}
    seen = []
    def fetch(method, url, headers, payload):
        seen.append(headers["APCA-API-KEY-ID"])
        return dict(id="one", status="ACTIVE", equity="10", cash="10", currency="USD")
    manager = ConnectionManager(tmp_path, env=env)
    body = dict(record(), credential_refs={}, credentials={"api_key": "COMMITTED", "secret_key": "ORIGINAL"})
    manager.upsert(body)
    with monkeypatch.context() as patch:
        patch.setattr(manager, "_save", lambda: (_ for _ in ()).throw(KeyboardInterrupt()))
        with pytest.raises(KeyboardInterrupt):
            manager.upsert(dict(body, credentials={"api_key": "UNCOMMITTED", "secret_key": "NEW"}))
    restarted = ConnectionManager(tmp_path, env=env, transport=fetch)
    assert restarted.connect("paper_one")["status"] == "CONNECTED_READ_ONLY"
    assert seen == ["COMMITTED"]
    assert "secret_ref" not in restarted.snapshot()["connections"][0]


@pytest.mark.parametrize("changes", [
    {"status": "CONNECTED_READ_ONLY", "last_read_at": 1000},
    {"environment": "funded"},
])
def test_inconsistent_stored_connection_state_is_rejected(tmp_path, changes):
    manager = ConnectionManager(tmp_path)
    manager.upsert(record())
    path = manager.root / "connections.json"
    rows = json.loads(path.read_text())
    rows["paper_one"].update(changes)
    path.write_text(json.dumps(rows))
    with pytest.raises(ValueError): manager.snapshot()


@pytest.mark.parametrize("quantity,positions", [(0.25, {}), (1, {"MNQ": 0.5})])
def test_fractional_contract_quantities_never_pass_preflight(quantity, positions):
    result = evaluate_rules(policy(), dict(state(), positions=positions),
        {"connection_id": "paper_one", "symbol": "MNQ", "quantity": quantity}, now=1000)
    assert result["new_intent_allowed"] is False


def record(**changes):
    return dict(id="paper_one", alias="Paper one", platform="alpaca_paper",
                environment="paper", firm="independent", program="paper",
                credential_refs={"api_key": "ALPACA_API_KEY", "secret_key": "ALPACA_SECRET_KEY"}, **changes)


def projectx_record():
    import hashlib
    return dict(id="topstep_one", alias="Topstep evaluation", platform="projectx_topstep",
        environment="evaluation", firm="Topstep", program="unverified-program",
        account_selector=hashlib.sha256(b"projectx_topstep:123").hexdigest(),
        credential_refs={"api_key": "PROJECTX_API_KEY", "username": "PROJECTX_USERNAME"})


def test_projectx_login_and_explicit_account_readback_never_submit_orders(tmp_path):
    calls = []
    def transport(method, url, headers, payload):
        calls.append((method, url, headers, payload))
        if url.endswith("/Auth/loginKey"):
            return {"success": True, "errorCode": 0, "token": "PRIVATE_SESSION"}
        return {"success": True, "errorCode": 0, "accounts": [
            {"id": 999, "name": "DO_NOT_PICK_FIRST", "balance": 9999, "canTrade": True, "isVisible": True},
            {"id": 123, "name": "PRIVATE_ACCOUNT_NAME", "balance": 123.45, "canTrade": False, "isVisible": True}]}
    manager = ConnectionManager(tmp_path, env={"PROJECTX_API_KEY": "API_PRIVATE", "PROJECTX_USERNAME": "USER_PRIVATE"}, transport=transport, clock=lambda: 1000)
    manager.upsert(projectx_record())
    result = manager.connect("topstep_one")
    assert result["status"] == "CONNECTED_READ_ONLY"
    assert result["readback"]["balance"] == 123.45
    assert result["readback"]["currency"] is None
    assert result["readback"]["trading_blocked"] is True
    assert result["execution_authorized"] is False and result["new_intents_blocked"] is True
    assert [row[0:2] for row in calls] == [("POST", "https://api.topstepx.com/api/Auth/loginKey"), ("POST", "https://api.topstepx.com/api/Account/search")]
    assert calls[0][3] == {"userName": "USER_PRIVATE", "apiKey": "API_PRIVATE"}
    assert calls[1][3] == {"onlyActiveAccounts": True}
    assert calls[1][2]["Authorization"] == "Bearer PRIVATE_SESSION"
    manager.connect("topstep_one")
    assert len(calls) == 3  # Session token reused; only account search repeated.
    public = json.dumps(manager.snapshot())
    assert all(value not in public for value in ("API_PRIVATE", "USER_PRIVATE", "PRIVATE_SESSION", "PRIVATE_ACCOUNT_NAME", "DO_NOT_PICK_FIRST"))
    assert all(b"PRIVATE_SESSION" not in p.read_bytes() for p in manager.root.rglob("*") if p.is_file())


@pytest.mark.parametrize("code,status", [(9, "SUBSCRIPTION_REQUIRED"), (7, "AGREEMENTS_REQUIRED"), (3, "AUTHENTICATION_FAILED"), (10, "API_ACCESS_DISABLED")])
def test_projectx_http_success_does_not_override_denial_or_buy_access(tmp_path, code, status):
    calls = []
    def transport(*args):
        calls.append(args)
        return {"success": False, "errorCode": code, "errorMessage": "PRIVATE_DETAIL"}
    manager = ConnectionManager(tmp_path, env={"PROJECTX_API_KEY": "key", "PROJECTX_USERNAME": "user"}, transport=transport)
    manager.upsert(projectx_record())
    result = manager.connect("topstep_one")
    assert result["status"] == status and result["readback"] is None
    assert len(calls) == 1 and "PRIVATE_DETAIL" not in json.dumps(result)


@pytest.mark.parametrize("change", [{"account_selector": None}, {"account_selector": "123"}, {"environment": "funded"}, {"firm": "another-firm"}])
def test_projectx_requires_exact_account_and_supported_firm_environment(tmp_path, change):
    manager = ConnectionManager(tmp_path, env={}, transport=lambda *a: pytest.fail("no transport"))
    with pytest.raises(ValueError): manager.upsert(dict(projectx_record(), **change))


def test_projectx_never_selects_an_unmatched_or_invisible_account(tmp_path):
    def transport(method, url, headers, payload):
        if url.endswith("loginKey"): return {"success": True, "errorCode": 0, "token": "token"}
        return {"success": True, "errorCode": 0, "accounts": [{"id": 456, "balance": 1, "isVisible": True, "canTrade": True}]}
    manager = ConnectionManager(tmp_path, env={"PROJECTX_API_KEY": "key", "PROJECTX_USERNAME": "user"}, transport=transport)
    manager.upsert(projectx_record())
    assert manager.connect("topstep_one")["status"] == "READBACK_FAILED"


@pytest.mark.parametrize("change", [{"isVisible": False}, {"canTrade": "true"}, {"balance": "nan"}, {"id": True}])
def test_projectx_invalid_selected_account_cannot_establish_readback(tmp_path, change):
    account = dict(id=123, balance=100, isVisible=True, canTrade=True)
    account.update(change)
    def transport(method, url, headers, payload):
        if url.endswith("loginKey"): return {"success": True, "errorCode": 0, "token": "token"}
        return {"success": True, "errorCode": 0, "accounts": [account]}
    manager = ConnectionManager(tmp_path, env={"PROJECTX_API_KEY": "key", "PROJECTX_USERNAME": "user"}, transport=transport)
    manager.upsert(projectx_record())
    assert manager.connect("topstep_one")["status"] == "READBACK_FAILED"


def test_projectx_session_expiry_reauthenticates_without_persisting_token(tmp_path):
    now, methods = [1000], []
    def transport(method, url, headers, payload):
        methods.append(url)
        if url.endswith("loginKey"): return {"success": True, "errorCode": 0, "token": "token"}
        return {"success": True, "errorCode": 0, "accounts": [dict(id=123, balance=100, isVisible=True, canTrade=True)]}
    manager = ConnectionManager(tmp_path, env={"PROJECTX_API_KEY": "key", "PROJECTX_USERNAME": "user"}, transport=transport, clock=lambda: now[0])
    manager.upsert(projectx_record())
    manager.connect("topstep_one")
    now[0] += 86400
    assert manager.connect("topstep_one")["status"] == "CONNECTED_READ_ONLY"
    assert sum(url.endswith("loginKey") for url in methods) == 2


def test_projectx_order_and_enrollment_operations_are_not_transport_capabilities():
    from icarus_engine.account_connections import _transport
    for path in ("/api/Order/place", "/api/Order/cancel", "/api/Position/closeContract", "/api/Subscription/create"):
        with pytest.raises(ValueError): _transport("POST", "https://api.topstepx.com" + path, {}, {})


def test_projectx_missing_keys_do_not_trigger_login_or_subscription(tmp_path):
    manager = ConnectionManager(tmp_path, env={}, transport=lambda *a: pytest.fail("no account keys"))
    manager.upsert(projectx_record())
    assert manager.connect("topstep_one")["status"] == "MISSING_CREDENTIALS"


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
    # Windows mode bits do not attest file ACLs; keep encryption and redaction
    # coverage above active on every platform. ACL privacy is not claimed here.
    import os
    if os.name == "posix":
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


def test_projectx_rotating_resolved_credentials_cannot_reuse_previous_users_session(tmp_path):
    env = {'PROJECTX_API_KEY': 'OLD_FIXTURE_KEY', 'PROJECTX_USERNAME': 'old-user'}
    calls = []
    def transport(method, url, headers, payload):
        calls.append((url, headers, payload))
        if url.endswith('loginKey'):
            if payload['userName'] != 'old-user':
                return dict(success=False, errorCode=3)
            return dict(success=True, errorCode=0, token='OLD_FIXTURE_SESSION')
        return dict(success=True, errorCode=0, accounts=[dict(id=123, balance=100, isVisible=True, canTrade=False)])
    manager = ConnectionManager(tmp_path, env=env, transport=transport, clock=lambda: 1000)
    manager.upsert(projectx_record())
    assert manager.connect('topstep_one')['status'] == 'CONNECTED_READ_ONLY'
    env.update(PROJECTX_API_KEY='NEW_FIXTURE_KEY', PROJECTX_USERNAME='new-user')
    result = manager.connect('topstep_one')
    assert result['status'] == 'AUTHENTICATION_FAILED'
    assert result['readback'] is None
    assert sum(url.endswith('loginKey') for url, _, _ in calls) == 2
    assert len(calls) == 3  # Failed replacement authentication must not search accounts.
    assert manager._tokens == {}


def test_projectx_missing_credentials_clear_session_before_restoring_same_pair(tmp_path):
    env = {'PROJECTX_API_KEY': 'FIXTURE_KEY', 'PROJECTX_USERNAME': 'fixture-user'}
    calls = []
    def transport(method, url, headers, payload):
        calls.append(url)
        if url.endswith('loginKey'):
            return dict(success=True, errorCode=0, token='FIXTURE_SESSION')
        return dict(success=True, errorCode=0, accounts=[dict(id=123, balance=100, isVisible=True, canTrade=False)])
    manager = ConnectionManager(tmp_path, env=env, transport=transport, clock=lambda: 1000)
    manager.upsert(projectx_record())
    manager.connect('topstep_one')
    env.pop('PROJECTX_API_KEY')
    assert manager.connect('topstep_one')['status'] == 'MISSING_CREDENTIALS'
    assert manager._tokens == {}
    env['PROJECTX_API_KEY'] = 'FIXTURE_KEY'
    assert manager.connect('topstep_one')['status'] == 'CONNECTED_READ_ONLY'
    assert sum(url.endswith('loginKey') for url in calls) == 2


def test_projectx_successful_configuration_revision_invalidates_session_immediately(tmp_path):
    def transport(method, url, headers, payload):
        if url.endswith('loginKey'):
            return dict(success=True, errorCode=0, token='FIXTURE_SESSION')
        return dict(success=True, errorCode=0, accounts=[dict(id=123, balance=100, isVisible=True, canTrade=False)])
    manager = ConnectionManager(tmp_path, env={'PROJECTX_API_KEY': 'key', 'PROJECTX_USERNAME': 'user'}, transport=transport)
    manager.upsert(projectx_record())
    manager.connect('topstep_one')
    assert manager._tokens
    manager.upsert(dict(projectx_record(), alias='Updated display label'))
    assert manager._tokens == {}


def test_projectx_credential_digest_is_ephemeral_and_each_key_change_reauthenticates(tmp_path):
    import hashlib
    from icarus_engine.account_connections import _json
    env = {'PROJECTX_API_KEY': 'PRIVATE_FIXTURE_KEY', 'PROJECTX_USERNAME': 'private-fixture-user'}
    calls = []
    def transport(method, url, headers, payload):
        calls.append((url, payload))
        if url.endswith('loginKey'):
            return dict(success=True, errorCode=0, token='PRIVATE_FIXTURE_SESSION')
        return dict(success=True, errorCode=0, accounts=[dict(id=123, balance=100, isVisible=True, canTrade=False)])
    manager = ConnectionManager(tmp_path, env=env, transport=transport)
    manager.upsert(projectx_record())
    manager.connect('topstep_one')
    digest = hashlib.sha256(_json({'api_key': env['PROJECTX_API_KEY'], 'username': env['PROJECTX_USERNAME']})).hexdigest()
    env['PROJECTX_API_KEY'] = 'ROTATED_PRIVATE_FIXTURE_KEY'
    assert manager.connect('topstep_one')['status'] == 'CONNECTED_READ_ONLY'
    assert sum(url.endswith('loginKey') for url, _ in calls) == 2
    current_digest = hashlib.sha256(_json({'api_key': env['PROJECTX_API_KEY'], 'username': env['PROJECTX_USERNAME']})).hexdigest()
    public = json.dumps(manager.snapshot())
    persisted = b''.join(path.read_bytes() for path in manager.root.rglob('*') if path.is_file())
    for value in (digest, current_digest, 'PRIVATE_FIXTURE_KEY', 'private-fixture-user', 'PRIVATE_FIXTURE_SESSION'):
        assert value not in public and value.encode() not in persisted


def test_eight_prop_firms_have_free_local_inventory_all_documented_types_and_no_execution(tmp_path):
    manager = ConnectionManager(tmp_path, env={}, transport=lambda *args: pytest.fail('No remote calls for local records'))
    snapshot = manager.snapshot()
    assert len(snapshot['firms']) == 8
    assert {firm['id'] for firm in snapshot['firms']} == {'apex','lucid','myfundedfutures','goat','tradeify','takeprofittrader','earn2trade','bulenox'}
    for firm in snapshot['firms']:
        assert firm['local_integration_cost_usd'] == 0
        assert firm['free_account_or_api_verified'] is False
        assert firm['execution_authorized'] is False
        assert firm['account_types'] and firm['source_review']
        for program in firm['account_types']:
            assert program['stages'] and program['source_refs']
    for i, firm in enumerate(snapshot['firms']):
        program = firm['account_types'][0]
        record = manager.upsert(dict(id=f'firm_{i}', alias=firm['name'], platform='manual_inventory',
            environment='evaluation', firm=firm['name'], program=program['name'], credential_refs={}))
        assert record['status'] == 'INVENTORY_ONLY'
        assert manager.connect(record['id'])['status'] == 'INVENTORY_ONLY'
        assert record['readback'] is None and record['new_intents_blocked'] is True
    assert all(row['readback'] is None for row in ConnectionManager(tmp_path, env={}).snapshot()['connections'])
    assert next(p for p in snapshot['platforms'] if p['id'] == 'projectx_topstep')['configuration_phase'] == 'LATER'


def test_projectx_rejected_cached_session_is_evicted_before_retry(tmp_path):
    calls = []
    reject = [False]
    def transport(method, url, headers, payload):
        calls.append(url)
        if url.endswith('loginKey'):
            return dict(success=True,errorCode=0,token='FIXTURE_TOKEN')
        if reject[0]:
            return dict(success=False,errorCode=3)
        return dict(success=True,errorCode=0,accounts=[dict(id=123,balance=100,isVisible=True,canTrade=False)])
    manager = ConnectionManager(tmp_path,env={'PROJECTX_API_KEY':'key','PROJECTX_USERNAME':'user'},transport=transport)
    manager.upsert(projectx_record())
    manager.connect('topstep_one')
    reject[0] = True
    assert manager.connect('topstep_one')['status'] == 'AUTHENTICATION_FAILED'
    assert manager._tokens == {}
    reject[0] = False
    assert manager.connect('topstep_one')['status'] == 'CONNECTED_READ_ONLY'
    assert sum(url.endswith('loginKey') for url in calls) == 2
