"""Account-scoped, read-only connections and fail-closed policy preflight.

No order, cancel, flatten, enrollment, or live-arming method exists here. A
successful account read is neither execution authority nor verified compliance.
"""
from __future__ import annotations

import base64
import copy
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import threading
import time
import urllib.request
import uuid
from zoneinfo import ZoneInfo

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_FIELDS = {"id", "alias", "platform", "environment", "firm", "program", "credential_refs", "credentials", "account_selector"}
_REFS = {
    "alpaca_paper": {"api_key": "ALPACA_API_KEY", "secret_key": "ALPACA_SECRET_KEY"},
    "projectx_topstep": {"api_key": "PROJECTX_API_KEY", "username": "PROJECTX_USERNAME"},
}
_URL = "https://paper-api.alpaca.markets/v2/account"
_PROJECTX_AUTH = "https://api.topstepx.com/api/Auth/loginKey"
_PROJECTX_ACCOUNTS = "https://api.topstepx.com/api/Account/search"
_LOCKS = {}
_LOCK_GUARD = threading.Lock()
_LIMIT = 1_048_576
_STORED_FIELDS = (_FIELDS - {"credentials"}) | {"revision", "status", "readback", "account_fingerprint", "last_read_at", "secret_ref"}


def _validate_stored(row):
    for name, limit in (("alias", 200), ("platform", 64), ("environment", 32), ("firm", 100), ("program", 100)):
        _label(row[name], limit)
    if row["environment"] not in {"paper", "simulated", "evaluation", "funded", "demo"}:
        raise ValueError("invalid account environment")
    if row["platform"] == "alpaca_paper" and row["environment"] != "paper":
        raise ValueError("invalid Alpaca environment")
    _validate_selector(row["platform"], row["environment"], row["firm"], row["account_selector"])
    refs = row["credential_refs"]
    approved = _REFS.get(row["platform"], {})
    if not isinstance(refs, dict) or any(approved.get(k) != v for k, v in refs.items()):
        raise ValueError("invalid stored credential references")
    secret_ref = row["secret_ref"]
    if secret_ref is not None and (not isinstance(secret_ref, str) or re.fullmatch(re.escape(row["id"]) + r"\.[0-9a-f]{32}\.enc", secret_ref) is None or refs or not approved):
        raise ValueError("invalid immutable credential reference")
    if type(row["revision"]) is not int or row["revision"] < 1:
        raise ValueError("invalid account state")
    if row["status"] not in {"CONFIGURED", "UNSUPPORTED", "MISSING_CREDENTIALS", "ACCOUNT_IDENTITY_MISMATCH", "DUPLICATE_ACCOUNT", "CONNECTED_READ_ONLY", "READBACK_FAILED", "SUBSCRIPTION_REQUIRED", "AGREEMENTS_REQUIRED", "AUTHENTICATION_FAILED", "API_ACCESS_DISABLED"}:
        raise ValueError("invalid connection status")
    fingerprint = row["account_fingerprint"]
    if fingerprint is not None and (not isinstance(fingerprint, str) or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None):
        raise ValueError("invalid account fingerprint")
    if row["last_read_at"] is not None:
        _number(row["last_read_at"])
    readback = row["readback"]
    connected = row["status"] == "CONNECTED_READ_ONLY"
    if connected and (readback is None or fingerprint is None or row["last_read_at"] is None or not approved):
        raise ValueError("connected account requires complete readback")
    if connected and row["platform"] == "projectx_topstep" and fingerprint != row["account_selector"]:
        raise ValueError("connected account selector mismatch")
    if not connected and (readback is not None or row["last_read_at"] is not None):
        raise ValueError("inactive account has inconsistent readback")
    if readback is not None:
        if row["platform"] == "projectx_topstep":
            if not isinstance(readback, dict) or set(readback) != {"balance", "currency", "account_status", "trading_blocked"}:
                raise ValueError("invalid account readback")
            _number(readback["balance"])
            if readback["currency"] is not None or readback["account_status"] != "VISIBLE" or type(readback["trading_blocked"]) is not bool:
                raise ValueError("invalid account readback")
            return
        if not isinstance(readback, dict) or set(readback) != {"equity", "cash", "currency", "account_status", "trading_blocked"}:
            raise ValueError("invalid account readback")
        _number(readback["equity"])
        _number(readback["cash"])
        if (not isinstance(readback["currency"], str) or re.fullmatch(r"[A-Z]{3}", readback["currency"]) is None
                or readback["account_status"] != "ACTIVE" or type(readback["trading_blocked"]) is not bool):
            raise ValueError("invalid account readback")


def _validate_selector(platform, environment, firm, selector):
    if platform == "projectx_topstep":
        if environment not in {"evaluation", "simulated"} or not isinstance(firm, str) or firm.casefold() != "topstep":
            raise ValueError("Topstep readback supports only explicit simulated or evaluation accounts")
        if not isinstance(selector, str) or re.fullmatch(r"[0-9a-f]{64}", selector) is None:
            raise ValueError("an explicit account fingerprint is required")
    elif selector is not None:
        raise ValueError("account selector unsupported for this platform")


class _AccountFailure(Exception):
    def __init__(self, status):
        self.status = status


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("invalid numerical evidence")
    try:
        result = float(value)
    except (ValueError, OverflowError):
        raise ValueError("invalid numerical evidence") from None
    if not math.isfinite(result) or abs(result) >= 1e15:
        raise ValueError("invalid numerical evidence")
    return result


def _label(value, limit=200):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError("invalid connection label")
    return value.strip()


def _read(path):
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    try:
        details = os.fstat(fd)
        if not stat.S_ISREG(details.st_mode) or details.st_size > _LIMIT:
            raise ValueError("invalid account store")
        if os.name == "posix" and details.st_mode & 0o077:
            raise ValueError("account store permissions are not private")
        with os.fdopen(fd, "rb") as stream:
            fd = None
            raw = stream.read(_LIMIT + 1)
        if len(raw) > _LIMIT:
            raise ValueError("account store byte limit")
        return raw
    finally:
        if fd is not None:
            os.close(fd)


def _write(path, raw):
    temporary = path.with_name(".pending-" + uuid.uuid4().hex)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            fd = None
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if fd is not None:
            os.close(fd)
        temporary.unlink(missing_ok=True)


def _json(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()


def _transport(method, url, headers, payload):
    allowed = method == "GET" and url == _URL and payload is None
    if method == "POST" and isinstance(payload, dict):
        allowed = (url == _PROJECTX_AUTH and set(payload) == {"userName", "apiKey"}) or (url == _PROJECTX_ACCOUNTS and set(payload) == {"onlyActiveAccounts"} and payload["onlyActiveAccounts"] is True)
    if not allowed:
        raise ValueError("unsupported account operation")
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            raise ValueError("account redirect blocked")
    request = urllib.request.Request(url, headers=headers, method=method, data=None if payload is None else _json(payload))
    with urllib.request.build_opener(NoRedirect).open(request, timeout=8) as response:
        raw = response.read(_LIMIT + 1)
    if len(raw) > _LIMIT:
        raise ValueError("account response byte limit")
    return json.loads(raw)


class ConnectionManager:
    """Persist private metadata; inject secrets only into fixed official read calls.

    Owner-entered credentials require cryptography and a separately provisioned
    32-byte base64 ICARUS_CONNECTION_STORE_KEY. No master key is written to disk.
    Environment secret references are an alternative, not proof of key presence.
    """
    def __init__(self, base_dir, *, env=None, transport=None, clock=None):
        self.root = Path(base_dir).absolute() / ".account_connections"
        self.env = os.environ if env is None else env
        self.transport = _transport if transport is None else transport
        self.clock = time.time if clock is None else clock
        with _LOCK_GUARD:
            self.lock = _LOCKS.setdefault(str(self.root), threading.RLock())
        self._records = {}
        self._tokens = {}  # Ephemeral sessions only; never persisted or projected.
        with self.lock:
            if self.root.is_symlink():
                raise ValueError("unsafe account store")
            if self.root.exists():
                if not self.root.is_dir() or (os.name == "posix" and self.root.stat().st_mode & 0o077):
                    raise ValueError("account store directory is not private")
            else:
                self.root.mkdir(mode=0o700, parents=True)
            self._load()

    def _load(self):
        path = self.root / "connections.json"
        if path.is_symlink():
            raise ValueError("unsafe account store")
        if path.exists():
            try:
                rows = json.loads(_read(path))
                if not isinstance(rows, dict) or len(rows) > 100:
                    raise ValueError("invalid account store")
                for key, row in rows.items():
                    if (not _ID.fullmatch(key) or not isinstance(row, dict) or row.get("id") != key
                            or set(row) != _STORED_FIELDS):
                        raise ValueError("invalid account store")
                    _validate_stored(row)
                self._records = rows
            except (OSError, ValueError, TypeError, RecursionError):
                raise ValueError("account store unavailable") from None

    def _save(self):
        raw = _json(self._records)
        if len(raw) > _LIMIT:
            raise ValueError("account store capacity exceeded")
        _write(self.root / "connections.json", raw)

    def _cipher(self):
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            key = base64.b64decode(self.env.get("ICARUS_CONNECTION_STORE_KEY", ""), validate=True)
            if len(key) != 32:
                raise ValueError()
            return AESGCM(key)
        except (ImportError, ValueError, TypeError):
            raise ValueError("encrypted credential store requires a provisioned secure master key") from None

    def _public(self, row):
        result = copy.deepcopy(row)
        result.pop("secret_ref", None)
        now = _number(self.clock())
        if result["status"] == "CONNECTED_READ_ONLY":
            age = now - result.get("last_read_at", 0)
            if age < 0 or age > 60:
                result["status"] = "STALE_READBACK"
        result.update(execution_authorized=False, production_decision_authorized=False,
                      new_intents_blocked=True, policy_status="UNVERIFIED")
        return result

    def snapshot(self):
        with self.lock:
            self._load()
            rules = json.loads(Path(__file__).with_name("propfirm-rules.json").read_text())
            return {"schema_version": "icarus.account-connections/1", "read_only": True,
                    "execution_authorized": False,
                    "connections": [self._public(self._records[key]) for key in sorted(self._records)],
                    "platforms": [{"id": "alpaca_paper", "environments": ["paper"],
                        "capabilities": ["ACCOUNT_READ"], "markets": ["equities"],
                        "implementation_status": "CODED_MOCK_TESTED", "credential_refs": _REFS["alpaca_paper"]},
                        {"id": "projectx_topstep", "environments": ["evaluation", "simulated"],
                         "implementation_status": "CODED_MOCK_TESTED", "capabilities": ["AUTHENTICATE", "ACCOUNT_READ"],
                         "credential_refs": _REFS["projectx_topstep"], "explicit_account_selector_required": True,
                         "access_cost": "EXISTING_SUBSCRIPTION_REQUIRED_NO_ENROLLMENT",
                         "restrictions": ["Read-only monitoring", "No remote order operations", "No live funded API", "No purchase or subscription enrollment"]},
                        {"id": "rithmic", "implementation_status": "UNSUPPORTED"},
                        {"id": "tradovate", "implementation_status": "UNSUPPORTED"},
                        {"id": "ibkr", "implementation_status": "UNSUPPORTED"}],
                    "credential_entry": {"encrypted_local_store_available": self._store_available(),
                        "environment_references_supported": True, "plaintext_persistence": False},
                    "rules": rules["policies"]}

    def _store_available(self):
        try:
            self._cipher()
            return True
        except ValueError:
            return False

    def upsert(self, body):
        if not isinstance(body, dict) or set(body) - _FIELDS:
            raise ValueError("unsupported connection fields")
        identity = body.get("id")
        if not isinstance(identity, str) or not _ID.fullmatch(identity):
            raise ValueError("invalid connection identifier")
        platform = _label(body.get("platform"), 64)
        environment = _label(body.get("environment"), 32)
        if environment not in {"paper", "simulated", "evaluation", "funded", "demo"}:
            raise ValueError("live account connection is disabled")
        if platform == "alpaca_paper" and environment != "paper":
            raise ValueError("Alpaca connection supports paper only")
        refs = body.get("credential_refs", {})
        credentials = body.get("credentials")
        approved = _REFS.get(platform, {})
        if not isinstance(refs, dict) or any(approved.get(k) != v for k, v in refs.items()):
            raise ValueError("unapproved credential reference")
        if credentials is not None:
            if refs or not approved or not isinstance(credentials, dict) or set(credentials) != set(approved):
                raise ValueError("invalid owner credential entry")
            for value in credentials.values():
                _label(value, 4096)
            cipher = self._cipher()
        config = {"id": identity, "alias": _label(body.get("alias", identity)), "platform": platform,
                  "environment": environment, "firm": _label(body.get("firm", "unassigned"), 100),
                  "program": _label(body.get("program", "unassigned"), 100), "credential_refs": refs,
                  "account_selector": body.get("account_selector")}
        _validate_selector(platform, environment, config["firm"], config["account_selector"])
        with self.lock:
            self._load()
            prior_records = copy.deepcopy(self._records)
            old = self._records.get(identity)
            if old and credentials is None and all(old.get(k) == v for k, v in config.items()):
                return self._public(old)
            if not old and len(self._records) >= 100:
                raise ValueError("account record limit reached")
            row = dict(config, revision=(old or {}).get("revision", 0) + 1,
                       status="CONFIGURED" if platform in _REFS else "UNSUPPORTED", readback=None,
                       account_fingerprint=(old or {}).get("account_fingerprint"), last_read_at=None,
                       secret_ref=(old or {}).get("secret_ref") if not refs and (old or {}).get("platform") == platform else None)
            secret_path = None
            try:
                if credentials is not None:
                    nonce = os.urandom(12)
                    encrypted = nonce + cipher.encrypt(nonce, _json(credentials), identity.encode())
                    # A new immutable blob precedes the atomic metadata commit.
                    # An interrupted rotation can leave an orphan, but never
                    # changes bytes referenced by the previous committed record.
                    secret_ref = identity + "." + uuid.uuid4().hex + ".enc"
                    secret_path = self.root / secret_ref
                    fd = os.open(secret_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(encrypted)
                        stream.flush()
                        os.fsync(stream.fileno())
                    row["secret_ref"] = secret_ref
                self._records[identity] = row
                self._save()
                self._tokens.pop(identity, None)
            except Exception:
                self._records = prior_records
                if secret_path is not None:
                    secret_path.unlink(missing_ok=True)
                raise
            return self._public(row)

    def _projectx_read(self, row, credentials):
        now = _number(self.clock())
        cached = self._tokens.get(row["id"])
        # Bind sessions to the exact resolved credential pair, including changes
        # behind stable environment references. The digest stays in memory only.
        credential_digest = hashlib.sha256(_json(credentials)).hexdigest()
        def successful(response):
            if not isinstance(response, dict):
                raise ValueError("invalid account response")
            code = response.get("errorCode")
            if response.get("success") is not True or type(code) is not int or code != 0:
                self._tokens.pop(row["id"], None)
                status = {3: "AUTHENTICATION_FAILED", 7: "AGREEMENTS_REQUIRED", 9: "SUBSCRIPTION_REQUIRED", 10: "API_ACCESS_DISABLED"}.get(code, "READBACK_FAILED")
                raise _AccountFailure(status)
            return response
        if (cached is None or cached[0] != row["revision"] or cached[3] != credential_digest
                or not 0 <= cached[2] - now - 60 <= 86400):
            self._tokens.pop(row["id"], None)
            response = successful(self.transport("POST", _PROJECTX_AUTH,
                {"Accept": "application/json", "Content-Type": "application/json"},
                {"userName": credentials["username"], "apiKey": credentials["api_key"]}))
            token = _label(response.get("token"), 16384)
            cached = (row["revision"], token, now + 86400, credential_digest)
            self._tokens[row["id"]] = cached
        response = successful(self.transport("POST", _PROJECTX_ACCOUNTS,
            {"Accept": "application/json", "Content-Type": "application/json", "Authorization": "Bearer " + cached[1]},
            {"onlyActiveAccounts": True}))
        accounts = response.get("accounts")
        if not isinstance(accounts, list) or len(accounts) > 1000:
            raise ValueError("invalid account list")
        matches = []
        for account in accounts:
            if not isinstance(account, dict) or type(account.get("id")) is not int or account["id"] <= 0:
                raise ValueError("invalid account identity")
            fingerprint = hashlib.sha256(("projectx_topstep:" + str(account["id"])).encode()).hexdigest()
            if fingerprint == row["account_selector"]:
                matches.append(account)
        if len(matches) != 1 or matches[0].get("isVisible") is not True or type(matches[0].get("canTrade")) is not bool:
            raise ValueError("explicit account unavailable or ambiguous")
        account = matches[0]
        return row["account_selector"], {"balance": _number(account.get("balance")), "currency": None,
            "account_status": "VISIBLE", "trading_blocked": not account["canTrade"]}

    def _credentials(self, row):
        approved = _REFS[row["platform"]]
        if row.get("secret_ref"):
            raw = _read(self.root / row["secret_ref"])
            values = json.loads(self._cipher().decrypt(raw[:12], raw[12:], row["id"].encode()))
        else:
            values = {key: self.env.get(row["credential_refs"].get(key, ""), "") for key in approved}
        if not isinstance(values, dict) or set(values) != set(approved):
            raise ValueError("missing account credentials")
        for value in values.values():
            _label(value, 4096)
        return values

    def connect(self, connection_id):
        if not isinstance(connection_id, str) or not _ID.fullmatch(connection_id):
            raise ValueError("invalid connection identifier")
        with self.lock:
            self._load()
            if connection_id not in self._records:
                raise KeyError(connection_id)
            row = self._records[connection_id]
            row["readback"] = None
            row["last_read_at"] = None
            if row["platform"] not in _REFS:
                row["status"] = "UNSUPPORTED"
            else:
                try:
                    credentials = self._credentials(row)
                except Exception:
                    self._tokens.pop(row["id"], None)
                    row["status"] = "MISSING_CREDENTIALS"
                else:
                    try:
                        if row["platform"] == "projectx_topstep":
                            fingerprint, readback = self._projectx_read(row, credentials)
                        else:
                            response = self.transport("GET", _URL, {"Accept": "application/json",
                                "APCA-API-KEY-ID": credentials["api_key"],
                                "APCA-API-SECRET-KEY": credentials["secret_key"]}, None)
                            if not isinstance(response, dict) or response.get("status") != "ACTIVE":
                                raise ValueError("account not active")
                            identity = _label(response.get("id"), 200)
                            currency = response.get("currency")
                            if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
                                raise ValueError("invalid currency")
                            fingerprint = hashlib.sha256((row["platform"] + ":" + identity).encode()).hexdigest()
                            readback = {"equity": _number(response.get("equity")), "cash": _number(response.get("cash")),
                                        "currency": currency, "account_status": "ACTIVE",
                                        "trading_blocked": response.get("trading_blocked") is True}
                        if row.get("account_fingerprint") not in (None, fingerprint):
                            row["status"] = "ACCOUNT_IDENTITY_MISMATCH"
                        elif any(other["id"] != row["id"] and other.get("account_fingerprint") == fingerprint
                                 for other in self._records.values()):
                            row["status"] = "DUPLICATE_ACCOUNT"
                        else:
                            row.update(account_fingerprint=fingerprint, readback=readback,
                                       last_read_at=_number(self.clock()), status="CONNECTED_READ_ONLY")
                    except _AccountFailure as failure:
                        row["status"] = failure.status
                    except Exception:
                        self._tokens.pop(row["id"], None)
                        row["status"] = "READBACK_FAILED"
            self._save()
            return self._public(row)


def evaluate_rules(policy, state, intent, *, now=None):
    """Evaluate a complete explicit policy; never authorize broker execution.

    This generic checker does not verify FAQ source text. Bundled firm profiles
    remain UNVERIFIED until every clause has a source-backed implementation.
    """
    blockers = []
    result = {"new_intent_allowed": False, "execution_authorized": False, "blockers": blockers}
    try:
        now = _number(time.time() if now is None else now)
        if not isinstance(policy, dict) or policy.get("status") != "VERIFIED":
            blockers.append("UNVERIFIED_POLICY")
            return result
        if (policy.get("faq_coverage_complete") is not True or policy.get("unknown_clauses") != []
                or policy.get("unsupported_clauses") != [] or not isinstance(policy.get("sources"), list)
                or not policy["sources"] or not all(isinstance(v, str) and v.startswith("https://") for v in policy["sources"])):
            blockers.append("INCOMPLETE_FAQ_COVERAGE")
        verified, expires = _number(policy["verified_at"]), _number(policy["expires_at"])
        if not verified <= now <= expires or expires - verified > 7 * 86400:
            blockers.append("STALE_POLICY")
        if policy["loss_basis"] != "realized_plus_unrealized_after_fees" or policy["drawdown_basis"] != "intraday_high_water_equity" or policy["quantity_basis"] != "weighted_contracts":
            blockers.append("UNSUPPORTED_RULE_SEMANTICS")
        account = policy["connection_id"]
        if not account or state.get("connection_id") != account or intent.get("connection_id") != account:
            blockers.append("ACCOUNT_SCOPE_MISMATCH")
        observed = _number(state["observed_at"])
        if not 0 <= now - observed <= 60:
            blockers.append("STALE_ACCOUNT_STATE")
        fields = {key: _number(state[key]) for key in ("daily_realized", "unrealized", "fees", "equity", "high_water_equity", "best_day_profit", "total_profit")}
        if fields["fees"] < 0 or fields["high_water_equity"] < fields["equity"] or fields["best_day_profit"] < 0 or fields["total_profit"] < fields["best_day_profit"]:
            raise ValueError("invalid account state")
        daily_limit, drawdown_limit, maximum = (_number(policy[k]) for k in ("daily_loss_limit", "drawdown_limit", "max_contracts"))
        if min(daily_limit, drawdown_limit, maximum) <= 0:
            raise ValueError("invalid risk limits")
        if -(fields["daily_realized"] + fields["unrealized"] - fields["fees"]) >= daily_limit:
            blockers.append("DAILY_LOSS_LIMIT")
        if fields["high_water_equity"] - fields["equity"] >= drawdown_limit:
            blockers.append("DRAWDOWN_LIMIT")
        assets, weights = policy["allowed_assets"], policy["contract_weights"]
        if not isinstance(assets, list) or not assets or len(assets) != len(set(assets)) or not isinstance(weights, dict) or set(weights) != set(assets):
            raise ValueError("invalid instrument policy")
        weights = {key: _number(value) for key, value in weights.items()}
        if any(value <= 0 for value in weights.values()):
            raise ValueError("invalid contract weights")
        symbol, quantity = intent["symbol"], _number(intent["quantity"])
        positions = state["positions"]
        if not isinstance(positions, dict) or any(key not in weights for key in positions) or quantity == 0 or not quantity.is_integer():
            raise ValueError("unknown position or quantity")
        if any(not _number(value).is_integer() for value in positions.values()):
            raise ValueError("fractional contract position")
        if symbol not in assets:
            blockers.append("ASSET_NOT_ALLOWED")
        else:
            gross = sum(abs(_number(value)) * weights[key] for key, value in positions.items())
            if gross + abs(quantity) * weights[symbol] > maximum:
                blockers.append("MAX_CONTRACTS")
        local = datetime.fromtimestamp(now, ZoneInfo(policy["session_timezone"]))
        def minute(value):
            if not isinstance(value, str) or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", value):
                raise ValueError("invalid session")
            h, m = map(int, value.split(":"))
            return h * 60 + m
        start, end = minute(policy["session_start"]), minute(policy["session_end"])
        weekdays = policy["session_weekdays"]
        if not isinstance(weekdays, list) or not weekdays or any(type(v) is not int or not 0 <= v <= 6 for v in weekdays) or start == end:
            raise ValueError("invalid session")
        current = local.hour * 60 + local.minute
        day = local.weekday()
        in_session = day in weekdays and start <= current < end if start < end else ((day in weekdays and current >= start) or ((day - 1) % 7 in weekdays and current < end))
        if not in_session:
            blockers.append("SESSION_RESTRICTION")
        before, after = _number(policy["news_before_seconds"]), _number(policy["news_after_seconds"])
        if before < 0 or after < 0:
            raise ValueError("invalid news policy")
        if _number(state["news_coverage_from"]) > now - after or _number(state["news_coverage_until"]) < now + before:
            blockers.append("UNKNOWN_NEWS_COVERAGE")
        events = state["news_events"]
        if not isinstance(events, list) or len(events) > 10000:
            raise ValueError("invalid news state")
        if any(_number(event) - before <= now <= _number(event) + after for event in events):
            blockers.append("NEWS_RESTRICTION")
        ratio = _number(policy["consistency_max_ratio"])
        if not 0 < ratio <= 1:
            raise ValueError("invalid consistency policy")
        if fields["total_profit"] > 0 and fields["best_day_profit"] / fields["total_profit"] > ratio:
            blockers.append("CONSISTENCY_LIMIT")
        result["new_intent_allowed"] = not blockers
    except (KeyError, TypeError, ValueError, OverflowError, OSError):
        blockers.append("INVALID_ACCOUNT_STATE")
    return result
