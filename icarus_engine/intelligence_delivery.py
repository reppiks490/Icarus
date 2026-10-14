"""Durable, transport-independent delivery plane for ICARUS intelligence events.

This layer owns delivery state only. It never authorizes execution or production decisions.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping

MAX_TEXT = 240
MAX_FILTER_ITEMS = 64
MAX_REASON_BYTES = 32768
MAX_LIMIT = 1000


def _text(value: Any, name: str, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    value = value.strip()
    if not value:
        raise ValueError(f"{name} is required")
    if len(value) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return value


def _optional_text(value: Any, name: str, limit: int = MAX_TEXT) -> str | None:
    return None if value is None else _text(value, name, limit)


def _positive_int(value: Any, name: str, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _time_text(value: Any, name: str) -> str:
    value = _text(value, name, 80)
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _items(values: Any, name: str, *, lower: bool = False) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must be a collection")
    try:
        values = tuple(values)
    except TypeError as exc:
        raise ValueError(f"{name} must be a collection") from exc
    if len(values) > MAX_FILTER_ITEMS:
        raise ValueError(f"{name} exceeds {MAX_FILTER_ITEMS} items")
    normalized = [_text(v, f"{name} item", 80) for v in values]
    if lower:
        normalized = [v.lower() for v in normalized]
    return tuple(sorted(set(normalized)))


def _finite_json(value: Any, name: str, max_bytes: int = MAX_REASON_BYTES) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite JSON") from exc
    if len(raw.encode()) > max_bytes:
        raise ValueError(f"{name} exceeds {max_bytes} bytes")
    return raw


def _authority(record: dict[str, Any]) -> dict[str, Any]:
    record["execution_authorized"] = False
    record["production_decision_authorized"] = False
    return record


@dataclass(frozen=True)
class SubscriptionSpec:
    subscription_id: str
    revision: int
    mode: str
    consumer_id: str | None = None
    consumer_group: str | None = None
    start_sequence: int = 1
    channel: str | None = None
    event_types: tuple[str, ...] = ()
    assets: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    source: str | None = None
    min_severity: int | None = None
    max_attempts: int = 5
    retry_delay_seconds: int = 0


def _normalize_spec(spec: SubscriptionSpec) -> dict[str, Any]:
    if not isinstance(spec, SubscriptionSpec):
        raise ValueError("spec must be SubscriptionSpec")
    mode = _text(spec.mode, "mode", 32).lower()
    if mode not in {"broadcast", "competing"}:
        raise ValueError("mode must be broadcast or competing")
    consumer_id = _optional_text(spec.consumer_id, "consumer_id")
    consumer_group = _optional_text(spec.consumer_group, "consumer_group")
    if mode == "broadcast":
        if consumer_id is None or consumer_group is not None:
            raise ValueError("broadcast requires exactly consumer_id")
        target_kind, target_id = "consumer", consumer_id
    else:
        if consumer_group is None or consumer_id is not None:
            raise ValueError("competing requires exactly consumer_group")
        target_kind, target_id = "group", consumer_group
    if spec.min_severity is not None and (
        isinstance(spec.min_severity, bool) or not isinstance(spec.min_severity, int) or not 0 <= spec.min_severity <= 5
    ):
        raise ValueError("min_severity must be an integer in [0, 5]")
    return {
        "subscription_id": _text(spec.subscription_id, "subscription_id"),
        "revision": _positive_int(spec.revision, "revision"),
        "mode": mode,
        "consumer_id": consumer_id,
        "consumer_group": consumer_group,
        "target_kind": target_kind,
        "target_id": target_id,
        "start_sequence": _positive_int(spec.start_sequence, "start_sequence"),
        "channel": _optional_text(spec.channel, "channel", 80),
        "event_types": list(_items(spec.event_types, "event_types", lower=True)),
        "assets": list(_items(spec.assets, "assets")),
        "tags": list(_items(spec.tags, "tags")),
        "source": _optional_text(spec.source, "source", 160),
        "min_severity": spec.min_severity,
        "max_attempts": _positive_int(spec.max_attempts, "max_attempts"),
        "retry_delay_seconds": _nonnegative_int(spec.retry_delay_seconds, "retry_delay_seconds"),
    }


class IntelligenceDeliveryPlane:
    def __init__(
        self,
        path_or_connection: str | sqlite3.Connection = ":memory:",
        *,
        busy_timeout_ms: int = 5000,
        token_factory: Callable[[], str] | None = None,
    ) -> None:
        if isinstance(busy_timeout_ms, bool) or not isinstance(busy_timeout_ms, int) or not 0 <= busy_timeout_ms <= 60000:
            raise ValueError("busy_timeout_ms must be an integer in [0, 60000]")
        if isinstance(path_or_connection, sqlite3.Connection):
            self._conn, self._owns_connection, file_backed = path_or_connection, False, False
        elif isinstance(path_or_connection, str):
            self._conn = sqlite3.connect(path_or_connection)
            self._owns_connection, file_backed = True, path_or_connection != ":memory:"
        else:
            raise ValueError("path_or_connection must be a SQLite path or connection")
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute(f"PRAGMA busy_timeout = {busy_timeout_ms}")
        if file_backed:
            self._conn.execute("PRAGMA journal_mode = WAL")
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(24))
        self._create_schema()

    def _create_schema(self) -> None:
        with self._conn:
            self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS fabric_consumers(
                consumer_id TEXT PRIMARY KEY, registered_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS fabric_consumer_groups(
                consumer_id TEXT NOT NULL, consumer_group TEXT NOT NULL,
                enabled INTEGER NOT NULL CHECK(enabled IN(0,1)), updated_at TEXT NOT NULL,
                PRIMARY KEY(consumer_id,consumer_group),
                FOREIGN KEY(consumer_id) REFERENCES fabric_consumers(consumer_id));
            CREATE TABLE IF NOT EXISTS fabric_subscriptions(
                subscription_id TEXT NOT NULL, revision INTEGER NOT NULL, mode TEXT NOT NULL,
                target_kind TEXT NOT NULL, target_id TEXT NOT NULL, start_sequence INTEGER NOT NULL,
                max_attempts INTEGER NOT NULL, retry_delay_seconds INTEGER NOT NULL,
                material_json TEXT NOT NULL, material_hash TEXT NOT NULL,
                enabled INTEGER NOT NULL CHECK(enabled IN(0,1)), created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(subscription_id,revision));
            CREATE TABLE IF NOT EXISTS fabric_deliveries(
                delivery_id TEXT PRIMARY KEY, subscription_id TEXT NOT NULL, revision INTEGER NOT NULL,
                target_kind TEXT NOT NULL, target_id TEXT NOT NULL, event_id TEXT NOT NULL,
                journal_sequence INTEGER NOT NULL, status TEXT NOT NULL, attempt INTEGER NOT NULL DEFAULT 0,
                lease_owner TEXT, lease_token TEXT, leased_at TEXT, lease_expires_at TEXT,
                retry_eligible_at TEXT, requeue_bonus INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL,
                UNIQUE(subscription_id,revision,target_kind,target_id,event_id),
                FOREIGN KEY(subscription_id,revision) REFERENCES fabric_subscriptions(subscription_id,revision));
            CREATE TABLE IF NOT EXISTS fabric_delivery_receipts(
                receipt_sequence INTEGER PRIMARY KEY AUTOINCREMENT, transition TEXT NOT NULL, occurred_at TEXT NOT NULL,
                subscription_id TEXT, revision INTEGER, consumer_id TEXT, consumer_group TEXT,
                delivery_id TEXT, event_id TEXT, attempt INTEGER, details_json TEXT NOT NULL DEFAULT '{}');
            CREATE INDEX IF NOT EXISTS idx_delivery_receipts_subscription
                ON fabric_delivery_receipts(subscription_id,revision,receipt_sequence);
            CREATE INDEX IF NOT EXISTS idx_deliveries_subscription
                ON fabric_deliveries(subscription_id,revision,journal_sequence);
            """)

    def _append_receipt(self, transition: str, occurred_at: str, **fields: Any) -> None:
        details = fields.pop("details", None)
        self._conn.execute(
            """INSERT INTO fabric_delivery_receipts(
            transition,occurred_at,subscription_id,revision,consumer_id,consumer_group,delivery_id,event_id,attempt,details_json)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (transition, occurred_at, fields.get("subscription_id"), fields.get("revision"), fields.get("consumer_id"),
             fields.get("consumer_group"), fields.get("delivery_id"), fields.get("event_id"), fields.get("attempt"),
             _finite_json(dict(details or {}), "receipt details")),
        )

    def register_consumer(self, consumer_id: str, *, as_of: str) -> dict[str, Any]:
        consumer_id, now = _text(consumer_id, "consumer_id"), _time_text(as_of, "as_of")
        with self._conn:
            row = self._conn.execute("SELECT registered_at FROM fabric_consumers WHERE consumer_id=?", (consumer_id,)).fetchone()
            if row is None:
                self._conn.execute("INSERT INTO fabric_consumers VALUES(?,?)", (consumer_id, now))
                self._append_receipt("CONSUMER_REGISTERED", now, consumer_id=consumer_id)
        return _authority({"consumer_id": consumer_id, "registered_at": row["registered_at"] if row else now, "idempotent": row is not None})

    def set_group_membership(self, consumer_id: str, consumer_group: str, enabled: bool, *, as_of: str) -> dict[str, Any]:
        consumer_id, consumer_group, now = _text(consumer_id, "consumer_id"), _text(consumer_group, "consumer_group"), _time_text(as_of, "as_of")
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be boolean")
        with self._conn:
            if self._conn.execute("SELECT 1 FROM fabric_consumers WHERE consumer_id=?", (consumer_id,)).fetchone() is None:
                raise ValueError("consumer must be registered before group membership")
            row = self._conn.execute("SELECT enabled FROM fabric_consumer_groups WHERE consumer_id=? AND consumer_group=?", (consumer_id, consumer_group)).fetchone()
            idempotent = row is not None and bool(row["enabled"]) is enabled
            if not idempotent:
                self._conn.execute("""INSERT INTO fabric_consumer_groups VALUES(?,?,?,?)
                    ON CONFLICT(consumer_id,consumer_group) DO UPDATE SET enabled=excluded.enabled,updated_at=excluded.updated_at""",
                    (consumer_id, consumer_group, int(enabled), now))
                self._append_receipt("GROUP_MEMBERSHIP_ENABLED" if enabled else "GROUP_MEMBERSHIP_DISABLED", now,
                                     consumer_id=consumer_id, consumer_group=consumer_group)
        return _authority({"consumer_id": consumer_id, "consumer_group": consumer_group, "enabled": enabled, "idempotent": idempotent})

    def create_subscription(self, spec: SubscriptionSpec, *, as_of: str) -> dict[str, Any]:
        material, now = _normalize_spec(spec), _time_text(as_of, "as_of")
        raw = _finite_json(material, "subscription material")
        digest = hashlib.sha256(raw.encode()).hexdigest()
        key = (material["subscription_id"], material["revision"])
        with self._conn:
            row = self._conn.execute("SELECT * FROM fabric_subscriptions WHERE subscription_id=? AND revision=?", key).fetchone()
            if row is not None:
                if row["material_hash"] != digest or row["material_json"] != raw:
                    raise ValueError("subscription revision conflict")
                return _authority({"subscription_id": key[0], "revision": key[1], "material_hash": digest,
                                   "enabled": bool(row["enabled"]), "idempotent": True,
                                   "created_at": row["created_at"], "updated_at": row["updated_at"]})
            self._conn.execute("""INSERT INTO fabric_subscriptions VALUES(?,?,?,?,?,?,?,?,?,?,1,?,?)""",
                (key[0], key[1], material["mode"], material["target_kind"], material["target_id"], material["start_sequence"],
                 material["max_attempts"], material["retry_delay_seconds"], raw, digest, now, now))
            self._append_receipt("SUBSCRIPTION_CREATED", now, subscription_id=key[0], revision=key[1],
                                 consumer_id=material["consumer_id"], consumer_group=material["consumer_group"])
        return _authority({"subscription_id": key[0], "revision": key[1], "material_hash": digest,
                           "enabled": True, "idempotent": False, "created_at": now, "updated_at": now})

    def set_subscription_enabled(self, subscription_id: str, revision: int, enabled: bool, *, as_of: str) -> dict[str, Any]:
        subscription_id, revision, now = _text(subscription_id, "subscription_id"), _positive_int(revision, "revision"), _time_text(as_of, "as_of")
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be boolean")
        with self._conn:
            row = self._conn.execute("SELECT material_hash,enabled FROM fabric_subscriptions WHERE subscription_id=? AND revision=?", (subscription_id, revision)).fetchone()
            if row is None:
                raise ValueError("unknown subscription revision")
            idempotent = bool(row["enabled"]) is enabled
            if not idempotent:
                self._conn.execute("UPDATE fabric_subscriptions SET enabled=?,updated_at=? WHERE subscription_id=? AND revision=?", (int(enabled), now, subscription_id, revision))
                self._append_receipt("SUBSCRIPTION_ENABLED" if enabled else "SUBSCRIPTION_DISABLED", now,
                                     subscription_id=subscription_id, revision=revision)
        return _authority({"subscription_id": subscription_id, "revision": revision, "material_hash": row["material_hash"],
                           "enabled": enabled, "idempotent": idempotent})

    def _subscription(self, subscription_id: str, revision: int) -> sqlite3.Row:
        row = self._conn.execute("SELECT * FROM fabric_subscriptions WHERE subscription_id=? AND revision=?",
                                 (_text(subscription_id, "subscription_id"), _positive_int(revision, "revision"))).fetchone()
        if row is None:
            raise ValueError("unknown subscription revision")
        return row

    def _candidates(self, material: Mapping[str, Any], as_of: str) -> list[sqlite3.Row]:
        clauses, params = ["e.sequence>=?", "e.received_at<=?"], [material["start_sequence"], as_of]
        for key, column in (("channel", "e.channel"), ("source", "e.source")):
            if material.get(key) is not None:
                clauses.append(f"{column}=?"); params.append(material[key])
        if material.get("min_severity") is not None:
            clauses.append("e.severity>=?"); params.append(material["min_severity"])
        types = tuple(material.get("event_types") or ())
        if types:
            clauses.append("e.event_type IN (" + ",".join("?" for _ in types) + ")"); params.extend(types)
        for key, table, col in (("assets", "fabric_assets", "asset"), ("tags", "fabric_tags", "tag")):
            vals = tuple(material.get(key) or ())
            if vals:
                clauses.append(f"EXISTS(SELECT 1 FROM {table} x WHERE x.event_id=e.event_id AND x.{col} IN (" + ",".join("?" for _ in vals) + "))")
                params.extend(vals)
        return self._conn.execute("SELECT e.* FROM fabric_events e WHERE " + " AND ".join(clauses) + " ORDER BY e.sequence", params).fetchall()

    @staticmethod
    def _verify_event(event: sqlite3.Row) -> dict[str, Any]:
        try:
            envelope = json.loads(str(event["envelope_json"]))
        except (TypeError, ValueError) as exc:
            raise ValueError("Phase 1 event integrity failure: invalid envelope JSON") from exc
        if not isinstance(envelope, dict) or envelope.get("schema_version") != "icarus-intelligence-fabric-v1":
            raise ValueError("Phase 1 event integrity failure: unsupported schema")
        if envelope.get("execution_authorized") is not False or envelope.get("production_decision_authorized") is not False:
            raise ValueError("Phase 1 event authority violation")
        canonical = _finite_json(envelope, "Phase 1 event envelope", 1_000_000)
        if hashlib.sha256(canonical.encode()).hexdigest() != str(event["event_id"]):
            raise ValueError("Phase 1 event integrity failure: event_id hash mismatch")
        return envelope

    @staticmethod
    def _delivery_id(subscription_id: str, revision: int, target_kind: str, target_id: str, event_id: str) -> str:
        raw = json.dumps([subscription_id, revision, target_kind, target_id, event_id], separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()

    def _result(self, row: sqlite3.Row, event: Mapping[str, Any] | None = None) -> dict[str, Any]:
        result = {"delivery_id": row["delivery_id"], "subscription_id": row["subscription_id"], "revision": int(row["revision"]),
                  "target_kind": row["target_kind"], "target_id": row["target_id"], "event_id": row["event_id"],
                  "journal_sequence": int(row["journal_sequence"]), "state": row["status"], "attempt": int(row["attempt"]),
                  "lease_owner": row["lease_owner"], "lease_token": row["lease_token"], "leased_at": row["leased_at"],
                  "lease_expires_at": row["lease_expires_at"], "retry_eligible_at": row["retry_eligible_at"]}
        if event is not None:
            result["event"] = dict(event)
        return _authority(result)

    @staticmethod
    def _plus_seconds(value: str, seconds: int) -> str:
        return (datetime.fromisoformat(value.replace("Z", "+00:00")) + timedelta(seconds=seconds)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def claim(self, subscription_id: str, revision: int, consumer_id: str, *, as_of: str,
              lease_seconds: int = 30, limit: int = 1) -> list[dict[str, Any]]:
        subscription_id, revision, consumer_id = _text(subscription_id, "subscription_id"), _positive_int(revision, "revision"), _text(consumer_id, "consumer_id")
        now, lease_seconds, limit = _time_text(as_of, "as_of"), _positive_int(lease_seconds, "lease_seconds"), _positive_int(limit, "limit")
        if limit > MAX_LIMIT: raise ValueError(f"limit must be <= {MAX_LIMIT}")
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            sub = self._subscription(subscription_id, revision)
            if not bool(sub["enabled"]): self._conn.commit(); return []
            if self._conn.execute("SELECT 1 FROM fabric_consumers WHERE consumer_id=?", (consumer_id,)).fetchone() is None:
                raise ValueError("consumer must be registered before claiming")
            if sub["mode"] == "broadcast":
                if sub["target_id"] != consumer_id: raise ValueError("consumer does not own broadcast subscription")
            elif sub["mode"] == "competing":
                membership = self._conn.execute("SELECT enabled FROM fabric_consumer_groups WHERE consumer_id=? AND consumer_group=?", (consumer_id, sub["target_id"])).fetchone()
                if membership is None or not bool(membership["enabled"]): raise ValueError("consumer lacks active group membership")
            else: raise ValueError("unsupported subscription mode")
            material, claimed = json.loads(sub["material_json"]), []
            for event_row in self._candidates(material, now):
                if len(claimed) >= limit: break
                envelope = self._verify_event(event_row)
                delivery_id = self._delivery_id(subscription_id, revision, sub["target_kind"], sub["target_id"], event_row["event_id"])
                row = self._conn.execute("SELECT * FROM fabric_deliveries WHERE delivery_id=?", (delivery_id,)).fetchone()
                if row is None:
                    self._conn.execute("""INSERT INTO fabric_deliveries(
                        delivery_id,subscription_id,revision,target_kind,target_id,event_id,journal_sequence,status,attempt,updated_at)
                        VALUES(?,?,?,?,?,?,?,'PENDING',0,?)""",
                        (delivery_id, subscription_id, revision, sub["target_kind"], sub["target_id"], event_row["event_id"], event_row["sequence"], now))
                    self._append_receipt("PENDING", now, subscription_id=subscription_id, revision=revision, consumer_id=consumer_id,
                                         consumer_group=sub["target_id"] if sub["mode"] == "competing" else None,
                                         delivery_id=delivery_id, event_id=event_row["event_id"], attempt=0)
                    row = self._conn.execute("SELECT * FROM fabric_deliveries WHERE delivery_id=?", (delivery_id,)).fetchone()
                if row["status"] != "PENDING" or (row["retry_eligible_at"] is not None and row["retry_eligible_at"] > now): continue
                token, attempt = _text(self._token_factory(), "lease_token", 256), int(row["attempt"]) + 1
                expiry = self._plus_seconds(now, lease_seconds)
                self._conn.execute("""UPDATE fabric_deliveries SET status='LEASED',attempt=?,lease_owner=?,lease_token=?,
                    leased_at=?,lease_expires_at=?,retry_eligible_at=NULL,updated_at=? WHERE delivery_id=?""",
                    (attempt, consumer_id, token, now, expiry, now, delivery_id))
                self._append_receipt("LEASED", now, subscription_id=subscription_id, revision=revision, consumer_id=consumer_id,
                                     consumer_group=sub["target_id"] if sub["mode"] == "competing" else None,
                                     delivery_id=delivery_id, event_id=event_row["event_id"], attempt=attempt)
                claimed.append(self._result(self._conn.execute("SELECT * FROM fabric_deliveries WHERE delivery_id=?", (delivery_id,)).fetchone(), envelope))
            self._conn.commit(); return claimed
        except Exception:
            self._conn.rollback(); raise

    def _validate_lease(self, delivery_id: str, consumer_id: str, token: str, now: str) -> sqlite3.Row:
        row = self._conn.execute("SELECT * FROM fabric_deliveries WHERE delivery_id=?", (delivery_id,)).fetchone()
        if row is None: raise ValueError("unknown delivery")
        if row["status"] != "LEASED": raise ValueError("delivery is not leased")
        if row["lease_owner"] != consumer_id: raise ValueError("consumer does not own lease")
        if row["lease_token"] != token: raise ValueError("lease token mismatch")
        if row["lease_expires_at"] is None or now >= row["lease_expires_at"]: raise ValueError("lease has expired")
        return row

    def ack(self, delivery_id: str, consumer_id: str, lease_token: str, *, as_of: str) -> dict[str, Any]:
        delivery_id, consumer_id, lease_token, now = _text(delivery_id,"delivery_id",128), _text(consumer_id,"consumer_id"), _text(lease_token,"lease_token",256), _time_text(as_of,"as_of")
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._validate_lease(delivery_id, consumer_id, lease_token, now)
            self._conn.execute("""UPDATE fabric_deliveries SET status='ACKED',lease_owner=NULL,lease_token=NULL,
                leased_at=NULL,lease_expires_at=NULL,updated_at=? WHERE delivery_id=?""", (now, delivery_id))
            self._append_receipt("ACKED", now, subscription_id=row["subscription_id"], revision=row["revision"], consumer_id=consumer_id,
                                 delivery_id=delivery_id, event_id=row["event_id"], attempt=row["attempt"])
            current = self._conn.execute("SELECT * FROM fabric_deliveries WHERE delivery_id=?", (delivery_id,)).fetchone()
            self._conn.commit(); return self._result(current)
        except Exception:
            self._conn.rollback(); raise

    def _fail(self, row: sqlite3.Row, now: str, transition: str, consumer_id: str | None, details: Mapping[str, Any] | None = None) -> sqlite3.Row:
        sub = self._subscription(row["subscription_id"], int(row["revision"]))
        budget, delay = int(sub["max_attempts"]) + int(row["requeue_bonus"]), int(sub["retry_delay_seconds"])
        group = row["target_id"] if row["target_kind"] == "group" else None
        self._append_receipt(transition, now, subscription_id=row["subscription_id"], revision=row["revision"], consumer_id=consumer_id,
                             consumer_group=group, delivery_id=row["delivery_id"], event_id=row["event_id"], attempt=row["attempt"], details=details)
        if int(row["attempt"]) >= budget:
            self._conn.execute("""UPDATE fabric_deliveries SET status='DEAD_LETTERED',lease_owner=NULL,lease_token=NULL,
                leased_at=NULL,lease_expires_at=NULL,retry_eligible_at=NULL,updated_at=? WHERE delivery_id=?""", (now,row["delivery_id"]))
            self._append_receipt("DEAD_LETTERED", now, subscription_id=row["subscription_id"], revision=row["revision"], consumer_id=consumer_id,
                                 consumer_group=group, delivery_id=row["delivery_id"], event_id=row["event_id"], attempt=row["attempt"])
        else:
            retry_at = self._plus_seconds(now, delay)
            self._conn.execute("""UPDATE fabric_deliveries SET status='PENDING',lease_owner=NULL,lease_token=NULL,
                leased_at=NULL,lease_expires_at=NULL,retry_eligible_at=?,updated_at=? WHERE delivery_id=?""", (retry_at,now,row["delivery_id"]))
            self._append_receipt("PENDING", now, subscription_id=row["subscription_id"], revision=row["revision"], consumer_id=consumer_id,
                                 consumer_group=group, delivery_id=row["delivery_id"], event_id=row["event_id"], attempt=row["attempt"],
                                 details={"retry_eligible_at":retry_at})
        return self._conn.execute("SELECT * FROM fabric_deliveries WHERE delivery_id=?", (row["delivery_id"],)).fetchone()

    def nack(self, delivery_id: str, consumer_id: str, lease_token: str, *, as_of: str,
             reason: Mapping[str, Any] | None = None) -> dict[str, Any]:
        delivery_id, consumer_id, lease_token, now = _text(delivery_id,"delivery_id",128), _text(consumer_id,"consumer_id"), _text(lease_token,"lease_token",256), _time_text(as_of,"as_of")
        if reason is not None and not isinstance(reason, Mapping): raise ValueError("reason must be a mapping")
        reason = dict(reason or {}); _finite_json(reason, "reason")
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._validate_lease(delivery_id, consumer_id, lease_token, now)
            current = self._fail(row, now, "NACKED", consumer_id, reason)
            self._conn.commit(); return self._result(current)
        except Exception:
            self._conn.rollback(); raise

    def recover_expired(self, *, as_of: str, limit: int = 100) -> list[dict[str, Any]]:
        now, limit = _time_text(as_of,"as_of"), _positive_int(limit,"limit")
        if limit > MAX_LIMIT: raise ValueError(f"limit must be <= {MAX_LIMIT}")
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            rows = self._conn.execute("""SELECT * FROM fabric_deliveries WHERE status='LEASED' AND lease_expires_at IS NOT NULL
                AND lease_expires_at<=? ORDER BY journal_sequence LIMIT ?""", (now,limit)).fetchall()
            result = [self._result(self._fail(row, now, "LEASE_EXPIRED", row["lease_owner"])) for row in rows]
            self._conn.commit(); return result
        except Exception:
            self._conn.rollback(); raise

    def dead_letters(self, *, subscription_id: str | None = None, revision: int | None = None, limit: int = 100) -> list[dict[str, Any]]:
        limit = _positive_int(limit,"limit")
        if limit > MAX_LIMIT: raise ValueError(f"limit must be <= {MAX_LIMIT}")
        clauses, params = ["status='DEAD_LETTERED'"], []
        if subscription_id is not None: clauses.append("subscription_id=?"); params.append(_text(subscription_id,"subscription_id"))
        if revision is not None: clauses.append("revision=?"); params.append(_positive_int(revision,"revision"))
        params.append(limit)
        return [self._result(r) for r in self._conn.execute("SELECT * FROM fabric_deliveries WHERE "+" AND ".join(clauses)+" ORDER BY journal_sequence LIMIT ?",params).fetchall()]

    def requeue_dead_lettered(self, delivery_id: str, *, as_of: str, reason: Mapping[str, Any] | None = None) -> dict[str, Any]:
        delivery_id, now = _text(delivery_id,"delivery_id",128), _time_text(as_of,"as_of")
        if reason is not None and not isinstance(reason, Mapping): raise ValueError("reason must be a mapping")
        reason = dict(reason or {}); _finite_json(reason,"reason")
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._conn.execute("SELECT * FROM fabric_deliveries WHERE delivery_id=?",(delivery_id,)).fetchone()
            if row is None: raise ValueError("unknown delivery")
            if row["status"] != "DEAD_LETTERED": raise ValueError("delivery is not dead-lettered")
            bonus, group = int(row["requeue_bonus"])+1, row["target_id"] if row["target_kind"]=="group" else None
            self._append_receipt("REQUEUED",now,subscription_id=row["subscription_id"],revision=row["revision"],consumer_group=group,
                                 delivery_id=delivery_id,event_id=row["event_id"],attempt=row["attempt"],details=reason)
            self._conn.execute("""UPDATE fabric_deliveries SET status='PENDING',requeue_bonus=?,lease_owner=NULL,lease_token=NULL,
                leased_at=NULL,lease_expires_at=NULL,retry_eligible_at=NULL,updated_at=? WHERE delivery_id=?""",(bonus,now,delivery_id))
            self._append_receipt("PENDING",now,subscription_id=row["subscription_id"],revision=row["revision"],consumer_group=group,
                                 delivery_id=delivery_id,event_id=row["event_id"],attempt=row["attempt"],details={"requeue_bonus":bonus})
            current=self._conn.execute("SELECT * FROM fabric_deliveries WHERE delivery_id=?",(delivery_id,)).fetchone()
            self._conn.commit(); return self._result(current)
        except Exception:
            self._conn.rollback(); raise

    def metrics(self, subscription_id: str, revision: int, *, as_of: str) -> dict[str, Any]:
        now, sub = _time_text(as_of,"as_of"), self._subscription(subscription_id,revision)
        candidates = self._candidates(json.loads(sub["material_json"]),now)
        tail = int(self._conn.execute("SELECT COALESCE(MAX(sequence),0) tail FROM fabric_events").fetchone()["tail"])
        pending, pending_times, active, expired, dead, acked, progress = [], [], 0, 0, 0, 0, []
        for event in candidates:
            did=self._delivery_id(sub["subscription_id"],int(sub["revision"]),sub["target_kind"],sub["target_id"],event["event_id"])
            row=self._conn.execute("SELECT * FROM fabric_deliveries WHERE delivery_id=?",(did,)).fetchone()
            if row is None or row["status"]=="PENDING": pending.append(int(event["sequence"])); pending_times.append(event["received_at"])
            elif row["status"]=="LEASED":
                expired += int(row["lease_expires_at"] is not None and row["lease_expires_at"] <= now)
                active += int(not (row["lease_expires_at"] is not None and row["lease_expires_at"] <= now)); progress.append(int(event["sequence"]))
            elif row["status"]=="DEAD_LETTERED": dead+=1; progress.append(int(event["sequence"]))
            elif row["status"]=="ACKED": acked+=1; progress.append(int(event["sequence"]))
        counts={r["transition"]:int(r["n"]) for r in self._conn.execute("SELECT transition,COUNT(*) n FROM fabric_delivery_receipts WHERE subscription_id=? AND revision=? GROUP BY transition",(sub["subscription_id"],sub["revision"])).fetchall()}
        matching=len(candidates); has=matching>0
        lag=0 if not has else max(0,tail-(max(progress) if progress else max(0,int(sub["start_sequence"])-1)))
        age=None
        if pending_times:
            oldest=min(datetime.fromisoformat(v.replace("Z","+00:00")) for v in pending_times); age=max(0.0,(datetime.fromisoformat(now.replace("Z","+00:00"))-oldest).total_seconds())
        return _authority({"subscription_id":sub["subscription_id"],"revision":int(sub["revision"]),"matching_event_count":matching,
            "pending_count":len(pending),"active_leases":active,"expired_leases":expired,"acked_count":acked,
            "ack_receipt_count":counts.get("ACKED",0),"nack_count":counts.get("NACKED",0),
            "retry_count":counts.get("NACKED",0)+counts.get("LEASE_EXPIRED",0),"dead_letter_count":dead,
            "oldest_pending_sequence":min(pending) if pending else None,"oldest_pending_age_seconds":age,
            "tail_sequence":tail,"sequence_lag":lag,"has_matching_events":has})

    def create_replay_subscription(self, source_subscription_id: str, source_revision: int, replay_subscription_id: str,
                                   start_sequence: int, *, as_of: str) -> dict[str, Any]:
        source_subscription_id, replay_subscription_id = _text(source_subscription_id,"source_subscription_id"), _text(replay_subscription_id,"replay_subscription_id")
        if source_subscription_id == replay_subscription_id: raise ValueError("replay subscription must use a new subscription_id")
        source=self._subscription(source_subscription_id,_positive_int(source_revision,"source_revision")); material=json.loads(source["material_json"])
        return self.create_subscription(SubscriptionSpec(subscription_id=replay_subscription_id,revision=1,mode=material["mode"],
            consumer_id=material.get("consumer_id"),consumer_group=material.get("consumer_group"),start_sequence=_positive_int(start_sequence,"start_sequence"),
            channel=material.get("channel"),event_types=tuple(material.get("event_types") or ()),assets=tuple(material.get("assets") or ()),
            tags=tuple(material.get("tags") or ()),source=material.get("source"),min_severity=material.get("min_severity"),
            max_attempts=int(material["max_attempts"]),retry_delay_seconds=int(material["retry_delay_seconds"])),as_of=as_of)

    def receipts(self, *, delivery_id: str | None = None, subscription_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        limit=_positive_int(limit,"limit")
        if limit>MAX_LIMIT: raise ValueError(f"limit must be <= {MAX_LIMIT}")
        clauses,params=[],[]
        if delivery_id is not None: clauses.append("delivery_id=?"); params.append(_text(delivery_id,"delivery_id",128))
        if subscription_id is not None: clauses.append("subscription_id=?"); params.append(_text(subscription_id,"subscription_id"))
        sql="SELECT * FROM fabric_delivery_receipts"+(" WHERE "+" AND ".join(clauses) if clauses else "")+" ORDER BY receipt_sequence LIMIT ?"; params.append(limit)
        return [_authority({"receipt_sequence":int(r["receipt_sequence"]),"transition":r["transition"],"occurred_at":r["occurred_at"],
            "subscription_id":r["subscription_id"],"revision":r["revision"],"consumer_id":r["consumer_id"],"consumer_group":r["consumer_group"],
            "delivery_id":r["delivery_id"],"event_id":r["event_id"],"attempt":r["attempt"],"details":json.loads(r["details_json"])})
            for r in self._conn.execute(sql,params).fetchall()]

    def close(self) -> None:
        if self._owns_connection: self._conn.close()

    def __enter__(self) -> "IntelligenceDeliveryPlane": return self
    def __exit__(self, exc_type, exc, tb) -> None: self.close()
