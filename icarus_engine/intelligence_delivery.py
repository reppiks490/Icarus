"""Durable delivery-state plane layered over the ICARUS intelligence journal.

Phase 2 owns routing/delivery state only. It cannot authorize execution or
production decisions.
"""
from __future__ import annotations

import hashlib
import json
import math
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

MAX_TEXT = 240
MAX_FILTER_ITEMS = 64
MAX_REASON_BYTES = 32768
MAX_LIMIT = 1000


def _text(value: Any, name: str, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    out = value.strip()
    if not out:
        raise ValueError(f"{name} is required")
    if len(out) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return out


def _optional_text(value: Any, name: str, limit: int = MAX_TEXT) -> str | None:
    return None if value is None else _text(value, name, limit)


def _positive_int(value: Any, name: str, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _time_text(value: Any, name: str) -> str:
    text = _text(value, name, 80)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as ex:
        raise ValueError(f"{name} must be ISO-8601") from ex
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _items(values: Any, name: str, *, lower: bool = False) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must be a collection")
    try:
        materialized = tuple(values)
    except TypeError as ex:
        raise ValueError(f"{name} must be a collection") from ex
    if len(materialized) > MAX_FILTER_ITEMS:
        raise ValueError(f"{name} exceeds {MAX_FILTER_ITEMS} items")
    normalized = []
    for item in materialized:
        text = _text(item, f"{name} item", 80)
        normalized.append(text.lower() if lower else text)
    return tuple(sorted(set(normalized)))


def _finite_json(value: Any, name: str, *, max_bytes: int = MAX_REASON_BYTES) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{name} must be finite JSON") from ex
    if len(raw.encode("utf-8")) > max_bytes:
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
    subscription_id = _text(spec.subscription_id, "subscription_id")
    revision = _positive_int(spec.revision, "revision")
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
    start_sequence = _positive_int(spec.start_sequence, "start_sequence")
    max_attempts = _positive_int(spec.max_attempts, "max_attempts")
    retry_delay_seconds = _nonnegative_int(spec.retry_delay_seconds, "retry_delay_seconds")
    min_severity = spec.min_severity
    if min_severity is not None:
        if isinstance(min_severity, bool) or not isinstance(min_severity, int) or not 0 <= min_severity <= 5:
            raise ValueError("min_severity must be an integer in [0, 5]")
    return {
        "subscription_id": subscription_id,
        "revision": revision,
        "mode": mode,
        "consumer_id": consumer_id,
        "consumer_group": consumer_group,
        "target_kind": target_kind,
        "target_id": target_id,
        "start_sequence": start_sequence,
        "channel": _optional_text(spec.channel, "channel", 80),
        "event_types": list(_items(spec.event_types, "event_types", lower=True)),
        "assets": list(_items(spec.assets, "assets")),
        "tags": list(_items(spec.tags, "tags")),
        "source": _optional_text(spec.source, "source", 160),
        "min_severity": min_severity,
        "max_attempts": max_attempts,
        "retry_delay_seconds": retry_delay_seconds,
    }


class IntelligenceDeliveryPlane:
    def __init__(
        self,
        path_or_connection: str | sqlite3.Connection = ":memory:",
        *,
        busy_timeout_ms: int = 5000,
        token_factory: Callable[[], str] | None = None,
    ) -> None:
        if isinstance(busy_timeout_ms, bool) or not isinstance(busy_timeout_ms, int) or busy_timeout_ms < 0 or busy_timeout_ms > 60000:
            raise ValueError("busy_timeout_ms must be an integer in [0, 60000]")
        if isinstance(path_or_connection, sqlite3.Connection):
            self._conn = path_or_connection
            self._owns_connection = False
            self._file_backed = False
        elif isinstance(path_or_connection, str):
            self._conn = sqlite3.connect(path_or_connection)
            self._owns_connection = True
            self._file_backed = path_or_connection != ":memory:"
        else:
            raise ValueError("path_or_connection must be a SQLite path or connection")
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute(f"PRAGMA busy_timeout = {busy_timeout_ms}")
        if self._file_backed:
            self._conn.execute("PRAGMA journal_mode = WAL")
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(24))
        self._create_schema()

    def _create_schema(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS fabric_consumers (
                    consumer_id TEXT PRIMARY KEY,
                    registered_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS fabric_consumer_groups (
                    consumer_id TEXT NOT NULL,
                    consumer_group TEXT NOT NULL,
                    enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(consumer_id, consumer_group),
                    FOREIGN KEY(consumer_id) REFERENCES fabric_consumers(consumer_id)
                );
                CREATE TABLE IF NOT EXISTS fabric_subscriptions (
                    subscription_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    mode TEXT NOT NULL,
                    target_kind TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    start_sequence INTEGER NOT NULL,
                    max_attempts INTEGER NOT NULL,
                    retry_delay_seconds INTEGER NOT NULL,
                    material_json TEXT NOT NULL,
                    material_hash TEXT NOT NULL,
                    enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(subscription_id, revision)
                );
                CREATE TABLE IF NOT EXISTS fabric_deliveries (
                    delivery_id TEXT PRIMARY KEY,
                    subscription_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    target_kind TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    journal_sequence INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    attempt INTEGER NOT NULL DEFAULT 0,
                    lease_owner TEXT,
                    lease_token TEXT,
                    leased_at TEXT,
                    lease_expires_at TEXT,
                    retry_eligible_at TEXT,
                    requeue_bonus INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    UNIQUE(subscription_id, revision, target_kind, target_id, event_id),
                    FOREIGN KEY(subscription_id, revision) REFERENCES fabric_subscriptions(subscription_id, revision)
                );
                CREATE TABLE IF NOT EXISTS fabric_delivery_receipts (
                    receipt_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    transition TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    subscription_id TEXT,
                    revision INTEGER,
                    consumer_id TEXT,
                    consumer_group TEXT,
                    delivery_id TEXT,
                    event_id TEXT,
                    attempt INTEGER,
                    details_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_delivery_receipts_subscription
                    ON fabric_delivery_receipts(subscription_id, revision, receipt_sequence);
                CREATE INDEX IF NOT EXISTS idx_deliveries_subscription
                    ON fabric_deliveries(subscription_id, revision, journal_sequence);
                """
            )

    def _append_receipt(
        self,
        transition: str,
        occurred_at: str,
        *,
        subscription_id: str | None = None,
        revision: int | None = None,
        consumer_id: str | None = None,
        consumer_group: str | None = None,
        delivery_id: str | None = None,
        event_id: str | None = None,
        attempt: int | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        raw = _finite_json(dict(details or {}), "receipt details")
        self._conn.execute(
            """INSERT INTO fabric_delivery_receipts(
                transition, occurred_at, subscription_id, revision, consumer_id,
                consumer_group, delivery_id, event_id, attempt, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (transition, occurred_at, subscription_id, revision, consumer_id, consumer_group, delivery_id, event_id, attempt, raw),
        )

    def register_consumer(self, consumer_id: str, *, as_of: str) -> dict[str, Any]:
        consumer_id = _text(consumer_id, "consumer_id")
        occurred_at = _time_text(as_of, "as_of")
        with self._conn:
            row = self._conn.execute("SELECT consumer_id, registered_at FROM fabric_consumers WHERE consumer_id = ?", (consumer_id,)).fetchone()
            idempotent = row is not None
            if not idempotent:
                self._conn.execute("INSERT INTO fabric_consumers(consumer_id, registered_at) VALUES (?, ?)", (consumer_id, occurred_at))
                self._append_receipt("CONSUMER_REGISTERED", occurred_at, consumer_id=consumer_id)
        return _authority({"consumer_id": consumer_id, "registered_at": row["registered_at"] if row else occurred_at, "idempotent": idempotent})

    def set_group_membership(self, consumer_id: str, consumer_group: str, enabled: bool, *, as_of: str) -> dict[str, Any]:
        consumer_id = _text(consumer_id, "consumer_id")
        consumer_group = _text(consumer_group, "consumer_group")
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be boolean")
        occurred_at = _time_text(as_of, "as_of")
        with self._conn:
            exists = self._conn.execute("SELECT 1 FROM fabric_consumers WHERE consumer_id = ?", (consumer_id,)).fetchone()
            if exists is None:
                raise ValueError("consumer must be registered before group membership")
            row = self._conn.execute("SELECT enabled FROM fabric_consumer_groups WHERE consumer_id = ? AND consumer_group = ?", (consumer_id, consumer_group)).fetchone()
            idempotent = row is not None and bool(row["enabled"]) is enabled
            if not idempotent:
                self._conn.execute(
                    """INSERT INTO fabric_consumer_groups(consumer_id, consumer_group, enabled, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(consumer_id, consumer_group) DO UPDATE SET enabled=excluded.enabled, updated_at=excluded.updated_at""",
                    (consumer_id, consumer_group, int(enabled), occurred_at),
                )
                self._append_receipt("GROUP_MEMBERSHIP_ENABLED" if enabled else "GROUP_MEMBERSHIP_DISABLED", occurred_at, consumer_id=consumer_id, consumer_group=consumer_group)
        return _authority({"consumer_id": consumer_id, "consumer_group": consumer_group, "enabled": enabled, "idempotent": idempotent})

    def create_subscription(self, spec: SubscriptionSpec, *, as_of: str) -> dict[str, Any]:
        normalized = _normalize_spec(spec)
        occurred_at = _time_text(as_of, "as_of")
        material_json = _finite_json(normalized, "subscription material")
        material_hash = hashlib.sha256(material_json.encode("utf-8")).hexdigest()
        key = (normalized["subscription_id"], normalized["revision"])
        with self._conn:
            row = self._conn.execute(
                "SELECT material_json, material_hash, enabled, created_at, updated_at FROM fabric_subscriptions WHERE subscription_id = ? AND revision = ?",
                key,
            ).fetchone()
            if row is not None:
                if row["material_hash"] != material_hash or row["material_json"] != material_json:
                    raise ValueError("subscription revision conflict")
                return _authority({
                    "subscription_id": key[0], "revision": key[1], "material_hash": material_hash,
                    "enabled": bool(row["enabled"]), "idempotent": True,
                    "created_at": row["created_at"], "updated_at": row["updated_at"],
                })
            self._conn.execute(
                """INSERT INTO fabric_subscriptions(
                    subscription_id, revision, mode, target_kind, target_id,
                    start_sequence, max_attempts, retry_delay_seconds,
                    material_json, material_hash, enabled, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                (
                    key[0], key[1], normalized["mode"], normalized["target_kind"], normalized["target_id"],
                    normalized["start_sequence"], normalized["max_attempts"], normalized["retry_delay_seconds"],
                    material_json, material_hash, occurred_at, occurred_at,
                ),
            )
            self._append_receipt("SUBSCRIPTION_CREATED", occurred_at, subscription_id=key[0], revision=key[1], consumer_id=normalized["consumer_id"], consumer_group=normalized["consumer_group"])
        return _authority({"subscription_id": key[0], "revision": key[1], "material_hash": material_hash, "enabled": True, "idempotent": False, "created_at": occurred_at, "updated_at": occurred_at})

    def set_subscription_enabled(self, subscription_id: str, revision: int, enabled: bool, *, as_of: str) -> dict[str, Any]:
        subscription_id = _text(subscription_id, "subscription_id")
        revision = _positive_int(revision, "revision")
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be boolean")
        occurred_at = _time_text(as_of, "as_of")
        with self._conn:
            row = self._conn.execute("SELECT material_hash, enabled FROM fabric_subscriptions WHERE subscription_id = ? AND revision = ?", (subscription_id, revision)).fetchone()
            if row is None:
                raise ValueError("unknown subscription revision")
            idempotent = bool(row["enabled"]) is enabled
            if not idempotent:
                self._conn.execute("UPDATE fabric_subscriptions SET enabled = ?, updated_at = ? WHERE subscription_id = ? AND revision = ?", (int(enabled), occurred_at, subscription_id, revision))
                self._append_receipt("SUBSCRIPTION_ENABLED" if enabled else "SUBSCRIPTION_DISABLED", occurred_at, subscription_id=subscription_id, revision=revision)
        return _authority({"subscription_id": subscription_id, "revision": revision, "material_hash": row["material_hash"], "enabled": enabled, "idempotent": idempotent})

    def receipts(self, *, delivery_id: str | None = None, subscription_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        limit = _positive_int(limit, "limit")
        if limit > MAX_LIMIT:
            raise ValueError(f"limit must be <= {MAX_LIMIT}")
        clauses: list[str] = []
        params: list[Any] = []
        if delivery_id is not None:
            clauses.append("delivery_id = ?")
            params.append(_text(delivery_id, "delivery_id", 128))
        if subscription_id is not None:
            clauses.append("subscription_id = ?")
            params.append(_text(subscription_id, "subscription_id"))
        sql = "SELECT * FROM fabric_delivery_receipts"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY receipt_sequence ASC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        result = []
        for row in rows:
            result.append(_authority({
                "receipt_sequence": int(row["receipt_sequence"]),
                "transition": str(row["transition"]),
                "occurred_at": str(row["occurred_at"]),
                "subscription_id": row["subscription_id"],
                "revision": row["revision"],
                "consumer_id": row["consumer_id"],
                "consumer_group": row["consumer_group"],
                "delivery_id": row["delivery_id"],
                "event_id": row["event_id"],
                "attempt": row["attempt"],
                "details": json.loads(row["details_json"]),
            }))
        return result

    def close(self) -> None:
        if self._owns_connection:
            self._conn.close()

    def __enter__(self) -> "IntelligenceDeliveryPlane":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
