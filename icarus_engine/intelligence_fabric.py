"""Durable machine-native intelligence event fabric for ICARUS.

The fabric is an append-only communication/history plane. It ranks attention,
not trade conviction, and cannot authorize execution or production decisions.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = "icarus-intelligence-fabric-v1"
UNIFIED_INTELLIGENCE_SCHEMA_VERSION = "icarus-unified-intelligence-v1"
UNIFIED_SOURCE_KINDS = {"native", "foreign_lens", "experiment", "human"}
UNIFIED_EVIDENCE_CLASSES = {"observed", "derived", "reconstructed", "inferred", "unavailable"}

EVENT_TYPES = {
    "claim",
    "alert",
    "anomaly",
    "research",
    "risk",
    "system",
    "human_note",
    "agent_note",
    "decision_request",
    "decision_response",
}
SOURCE_KINDS = {
    "native",
    "foreign_lens",
    "experiment",
    "human",
    "agent",
    "system",
}
TYPE_BONUS = {
    "risk": 10.0,
    "anomaly": 6.0,
    "alert": 4.0,
    "decision_request": 4.0,
}
MAX_REPEATED = 64
MAX_PAYLOAD_BYTES = 32768
MAX_LIMIT = 1000


def _text(value: Any, name: str, limit: int, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    out = value.strip()
    if not out and not allow_empty:
        raise ValueError(f"{name} is required")
    if len(out) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return out


def _optional_text(value: Any, name: str, limit: int) -> str | None:
    if value is None:
        return None
    return _text(value, name, limit)


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{name} must be a finite number")
    return out


def _unit(value: Any, name: str) -> float:
    out = _finite(value, name)
    if not 0.0 <= out <= 1.0:
        raise ValueError(f"{name} must be in [0, 1]")
    return out


def _parse_time(value: Any, name: str) -> datetime:
    text = _text(value, name, 80)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as ex:
        raise ValueError(f"{name} must be ISO-8601") from ex
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")
    return dt.astimezone(timezone.utc)


def _time_text(value: Any, name: str) -> str:
    return _parse_time(value, name).isoformat().replace("+00:00", "Z")


def _json_value(value: Any, name: str, *, max_bytes: int = MAX_PAYLOAD_BYTES) -> Any:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{name} must be finite JSON") from ex
    if len(raw.encode("utf-8")) > max_bytes:
        raise ValueError(f"{name} exceeds {max_bytes} bytes")
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _items(values: Any, name: str, item_limit: int) -> tuple[str, ...]:
    if values is None:
        values = ()
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must be a collection")
    try:
        materialized = tuple(values)
    except TypeError as ex:
        raise ValueError(f"{name} must be a collection") from ex
    if len(materialized) > MAX_REPEATED:
        raise ValueError(f"{name} exceeds {MAX_REPEATED} items")
    return tuple(sorted({_text(item, f"{name} item", item_limit) for item in materialized}))


def _severity(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("severity must be an integer")
    if not 0 <= value <= 5:
        raise ValueError("severity must be in [0, 5]")
    return value


def _limit(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_LIMIT:
        raise ValueError(f"limit must be an integer in [1, {MAX_LIMIT}]")
    return value


def _nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


@dataclass(frozen=True)
class IntelligenceEvent:
    event_type: str
    source: str
    source_kind: str
    channel: str
    thread_key: str
    title: str
    body: str
    observed_at: str
    received_at: str
    severity: int = 0
    urgency: float = 0.0
    confidence: float | None = None
    expires_at: str | None = None
    assets: tuple[str, ...] = ()
    correlation_id: str | None = None
    causation_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    payload: Mapping[str, Any] = field(default_factory=dict)

    def normalized(self) -> dict[str, Any]:
        event_type = _text(self.event_type, "event_type", 40).lower()
        if event_type not in EVENT_TYPES:
            raise ValueError("unsupported event_type")
        source_kind = _text(self.source_kind, "source_kind", 40).lower()
        if source_kind not in SOURCE_KINDS:
            raise ValueError("unsupported source_kind")

        observed = _parse_time(self.observed_at, "observed_at")
        received = _parse_time(self.received_at, "received_at")
        if received < observed:
            raise ValueError("received_at cannot precede observed_at")
        expires = _time_text(self.expires_at, "expires_at") if self.expires_at is not None else None

        confidence = None if self.confidence is None else _unit(self.confidence, "confidence")
        if not isinstance(self.payload, Mapping):
            raise ValueError("payload must be a mapping")
        payload = _json_value(dict(self.payload), "payload")

        return {
            "schema_version": SCHEMA_VERSION,
            "event_type": event_type,
            "source": _text(self.source, "source", 160),
            "source_kind": source_kind,
            "channel": _text(self.channel, "channel", 80),
            "thread_key": _text(self.thread_key, "thread_key", 240),
            "title": _text(self.title, "title", 240),
            "body": _text(self.body, "body", 4000),
            "observed_at": observed.isoformat().replace("+00:00", "Z"),
            "received_at": received.isoformat().replace("+00:00", "Z"),
            "severity": _severity(self.severity),
            "urgency": _unit(self.urgency, "urgency"),
            "confidence": confidence,
            "expires_at": expires,
            "assets": list(_items(self.assets, "assets", 80)),
            "correlation_id": _optional_text(self.correlation_id, "correlation_id", 240),
            "causation_ids": list(_items(self.causation_ids, "causation_ids", 240)),
            "evidence_ids": list(_items(self.evidence_ids, "evidence_ids", 240)),
            "tags": list(_items(self.tags, "tags", 80)),
            "payload": payload,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def event_id(self) -> str:
        return _sha256_text(_canonical_json(self.normalized()))


def _event_from_mapping(row: Mapping[str, Any]) -> IntelligenceEvent:
    if not isinstance(row, Mapping):
        raise ValueError("event must be IntelligenceEvent or mapping")
    required = (
        "event_type",
        "source",
        "source_kind",
        "channel",
        "thread_key",
        "title",
        "body",
        "observed_at",
        "received_at",
    )
    missing = [key for key in required if key not in row]
    if missing:
        raise ValueError(f"missing event field: {missing[0]}")
    return IntelligenceEvent(
        event_type=row["event_type"],
        source=row["source"],
        source_kind=row["source_kind"],
        channel=row["channel"],
        thread_key=row["thread_key"],
        title=row["title"],
        body=row["body"],
        observed_at=row["observed_at"],
        received_at=row["received_at"],
        severity=row.get("severity", 0),
        urgency=row.get("urgency", 0.0),
        confidence=row.get("confidence"),
        expires_at=row.get("expires_at"),
        assets=tuple(row.get("assets", ()) or ()),
        correlation_id=row.get("correlation_id"),
        causation_ids=tuple(row.get("causation_ids", ()) or ()),
        evidence_ids=tuple(row.get("evidence_ids", ()) or ()),
        tags=tuple(row.get("tags", ()) or ()),
        payload=row.get("payload", {}) or {},
    )


def attention_score(event: IntelligenceEvent | Mapping[str, Any]) -> float:
    row = event.normalized() if isinstance(event, IntelligenceEvent) else event
    if not isinstance(row, Mapping):
        raise ValueError("event must be IntelligenceEvent or mapping")
    event_type = _text(row.get("event_type"), "event_type", 40).lower()
    if event_type not in EVENT_TYPES:
        raise ValueError("unsupported event_type")
    severity = _severity(row.get("severity", 0))
    urgency = _unit(row.get("urgency", 0.0), "urgency")
    return min(100.0, severity * 12.0 + urgency * 30.0 + TYPE_BONUS.get(event_type, 0.0))


class IntelligenceFabric:
    """Append-only SQLite journal and deterministic projections for intelligence events."""

    def __init__(self, path_or_connection: str | sqlite3.Connection = ":memory:") -> None:
        if isinstance(path_or_connection, sqlite3.Connection):
            self._conn = path_or_connection
            self._owns_connection = False
        elif isinstance(path_or_connection, str):
            self._conn = sqlite3.connect(path_or_connection)
            self._owns_connection = True
        else:
            raise ValueError("path_or_connection must be a SQLite path or connection")
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def _create_schema(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS fabric_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    observed_at TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    thread_key TEXT NOT NULL,
                    severity INTEGER NOT NULL,
                    attention_score REAL NOT NULL,
                    expires_at TEXT,
                    envelope_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_fabric_events_received ON fabric_events(received_at, sequence);
                CREATE INDEX IF NOT EXISTS idx_fabric_events_thread ON fabric_events(thread_key, sequence);
                CREATE INDEX IF NOT EXISTS idx_fabric_events_channel ON fabric_events(channel, sequence);
                CREATE INDEX IF NOT EXISTS idx_fabric_events_type ON fabric_events(event_type, sequence);
                CREATE INDEX IF NOT EXISTS idx_fabric_events_source ON fabric_events(source, sequence);
                CREATE INDEX IF NOT EXISTS idx_fabric_events_attention ON fabric_events(attention_score DESC, received_at DESC, sequence DESC);

                CREATE TABLE IF NOT EXISTS fabric_assets (
                    event_id TEXT NOT NULL,
                    asset TEXT NOT NULL,
                    PRIMARY KEY(event_id, asset),
                    FOREIGN KEY(event_id) REFERENCES fabric_events(event_id)
                );
                CREATE INDEX IF NOT EXISTS idx_fabric_assets_asset ON fabric_assets(asset, event_id);

                CREATE TABLE IF NOT EXISTS fabric_tags (
                    event_id TEXT NOT NULL,
                    tag TEXT NOT NULL,
                    PRIMARY KEY(event_id, tag),
                    FOREIGN KEY(event_id) REFERENCES fabric_events(event_id)
                );
                CREATE INDEX IF NOT EXISTS idx_fabric_tags_tag ON fabric_tags(tag, event_id);

                CREATE TABLE IF NOT EXISTS fabric_causes (
                    child_event_id TEXT NOT NULL,
                    parent_event_id TEXT NOT NULL,
                    PRIMARY KEY(child_event_id, parent_event_id),
                    FOREIGN KEY(child_event_id) REFERENCES fabric_events(event_id)
                );
                CREATE INDEX IF NOT EXISTS idx_fabric_causes_parent ON fabric_causes(parent_event_id, child_event_id);
                """
            )

    def publish(self, event: IntelligenceEvent | Mapping[str, Any]) -> dict[str, Any]:
        obj = event if isinstance(event, IntelligenceEvent) else _event_from_mapping(event)
        normalized = obj.normalized()
        envelope_json = _canonical_json(normalized)
        event_id = _sha256_text(envelope_json)
        score = attention_score(normalized)

        with self._conn:
            cursor = self._conn.execute(
                """
                INSERT OR IGNORE INTO fabric_events(
                    event_id, observed_at, received_at, event_type, source, channel,
                    thread_key, severity, attention_score, expires_at, envelope_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    normalized["observed_at"],
                    normalized["received_at"],
                    normalized["event_type"],
                    normalized["source"],
                    normalized["channel"],
                    normalized["thread_key"],
                    normalized["severity"],
                    score,
                    normalized["expires_at"],
                    envelope_json,
                ),
            )
            inserted = cursor.rowcount == 1
            row = self._conn.execute(
                "SELECT sequence, attention_score FROM fabric_events WHERE event_id = ?", (event_id,)
            ).fetchone()
            if row is None:
                raise RuntimeError("fabric append failed without a durable row")
            if inserted:
                self._conn.executemany(
                    "INSERT INTO fabric_assets(event_id, asset) VALUES (?, ?)",
                    [(event_id, item) for item in normalized["assets"]],
                )
                self._conn.executemany(
                    "INSERT INTO fabric_tags(event_id, tag) VALUES (?, ?)",
                    [(event_id, item) for item in normalized["tags"]],
                )
                self._conn.executemany(
                    "INSERT INTO fabric_causes(child_event_id, parent_event_id) VALUES (?, ?)",
                    [(event_id, item) for item in normalized["causation_ids"]],
                )
        return {
            "sequence": int(row["sequence"]),
            "event_id": event_id,
            "idempotent": not inserted,
            "attention_score": float(row["attention_score"]),
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    @staticmethod
    def _record(row: sqlite3.Row) -> dict[str, Any]:
        envelope = json.loads(str(row["envelope_json"]))
        return {
            "sequence": int(row["sequence"]),
            "event_id": str(row["event_id"]),
            "attention_score": float(row["attention_score"]),
            **envelope,
        }

    def get(self, event_id: str) -> dict[str, Any] | None:
        key = _text(event_id, "event_id", 128)
        row = self._conn.execute("SELECT * FROM fabric_events WHERE event_id = ?", (key,)).fetchone()
        return None if row is None else self._record(row)

    def replay(self, *, after_sequence: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        after_sequence = _nonnegative_int(after_sequence, "after_sequence")
        limit = _limit(limit)
        rows = self._conn.execute(
            "SELECT * FROM fabric_events WHERE sequence > ? ORDER BY sequence ASC LIMIT ?",
            (after_sequence, limit),
        ).fetchall()
        return [self._record(row) for row in rows]

    def query(
        self,
        *,
        channel: str | None = None,
        thread_key: str | None = None,
        assets: Iterable[str] | None = None,
        event_types: Iterable[str] | None = None,
        min_severity: int | None = None,
        source: str | None = None,
        tags: Iterable[str] | None = None,
        after: str | None = None,
        before: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        limit = _limit(limit)
        clauses: list[str] = []
        params: list[Any] = []

        if channel is not None:
            clauses.append("e.channel = ?")
            params.append(_text(channel, "channel", 80))
        if thread_key is not None:
            clauses.append("e.thread_key = ?")
            params.append(_text(thread_key, "thread_key", 240))
        if source is not None:
            clauses.append("e.source = ?")
            params.append(_text(source, "source", 160))
        if min_severity is not None:
            clauses.append("e.severity >= ?")
            params.append(_severity(min_severity))
        if after is not None:
            clauses.append("e.received_at > ?")
            params.append(_time_text(after, "after"))
        if before is not None:
            clauses.append("e.received_at <= ?")
            params.append(_time_text(before, "before"))

        asset_items = _items(assets, "assets", 80) if assets is not None else ()
        if asset_items:
            placeholders = ",".join("?" for _ in asset_items)
            clauses.append(
                f"EXISTS (SELECT 1 FROM fabric_assets a WHERE a.event_id = e.event_id AND a.asset IN ({placeholders}))"
            )
            params.extend(asset_items)

        tag_items = _items(tags, "tags", 80) if tags is not None else ()
        if tag_items:
            placeholders = ",".join("?" for _ in tag_items)
            clauses.append(
                f"EXISTS (SELECT 1 FROM fabric_tags t WHERE t.event_id = e.event_id AND t.tag IN ({placeholders}))"
            )
            params.extend(tag_items)

        type_items = _items(event_types, "event_types", 40) if event_types is not None else ()
        if type_items:
            normalized_types = []
            for item in type_items:
                lowered = item.lower()
                if lowered not in EVENT_TYPES:
                    raise ValueError("unsupported event_type")
                normalized_types.append(lowered)
            placeholders = ",".join("?" for _ in normalized_types)
            clauses.append(f"e.event_type IN ({placeholders})")
            params.extend(normalized_types)

        sql = "SELECT e.* FROM fabric_events e"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY e.sequence ASC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [self._record(row) for row in rows]

    def thread(self, thread_key: str, *, limit: int = 100) -> list[dict[str, Any]]:
        return self.query(thread_key=_text(thread_key, "thread_key", 240), limit=limit)

    def inbox(
        self,
        *,
        as_of: str,
        channel: str | None = None,
        assets: Iterable[str] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        limit = _limit(limit)
        boundary = _time_text(as_of, "as_of")
        clauses = ["e.received_at <= ?", "(e.expires_at IS NULL OR e.expires_at > ?)"]
        params: list[Any] = [boundary, boundary]
        if channel is not None:
            clauses.append("e.channel = ?")
            params.append(_text(channel, "channel", 80))
        asset_items = _items(assets, "assets", 80) if assets is not None else ()
        if asset_items:
            placeholders = ",".join("?" for _ in asset_items)
            clauses.append(
                f"EXISTS (SELECT 1 FROM fabric_assets a WHERE a.event_id = e.event_id AND a.asset IN ({placeholders}))"
            )
            params.extend(asset_items)
        sql = (
            "SELECT e.* FROM fabric_events e WHERE "
            + " AND ".join(clauses)
            + " ORDER BY e.attention_score DESC, e.received_at DESC, e.sequence DESC LIMIT ?"
        )
        params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [self._record(row) for row in rows]

    def close(self) -> None:
        if self._owns_connection:
            self._conn.close()

    def __enter__(self) -> "IntelligenceFabric":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def event_from_intelligence_claim(
    claim: Mapping[str, Any], *, claim_id: str | None = None
) -> IntelligenceEvent:
    if not isinstance(claim, Mapping):
        raise ValueError("claim must be a mapping")
    required = (
        "schema_version",
        "source",
        "source_kind",
        "semantic_key",
        "stance",
        "confidence",
        "evidence_class",
        "observed_at",
        "received_at",
        "regime",
        "horizon_seconds",
        "lineage",
        "falsifiers",
        "details",
        "execution_authorized",
        "production_decision_authorized",
    )
    for key in required:
        if key not in claim:
            raise ValueError(f"missing claim field: {key}")

    schema_version = _text(claim["schema_version"], "schema_version", 80)
    if schema_version != UNIFIED_INTELLIGENCE_SCHEMA_VERSION:
        raise ValueError("unsupported schema_version")
    if claim["execution_authorized"] is not False:
        raise ValueError("execution_authorized must be false for Unified Intelligence claims")
    if claim["production_decision_authorized"] is not False:
        raise ValueError("production_decision_authorized must be false for Unified Intelligence claims")
    source = _text(claim["source"], "source", 160)
    source_kind = _text(claim["source_kind"], "source_kind", 40).lower()
    if source_kind not in UNIFIED_SOURCE_KINDS:
        raise ValueError("unsupported source_kind for Unified Intelligence claim")
    semantic_key = _text(claim["semantic_key"], "semantic_key", 240)
    stance = _finite(claim["stance"], "stance")
    if not -1.0 <= stance <= 1.0:
        raise ValueError("stance must be in [-1, 1]")
    confidence = _unit(claim["confidence"], "confidence")
    evidence_class = _text(claim["evidence_class"], "evidence_class", 40).lower()
    if evidence_class not in UNIFIED_EVIDENCE_CLASSES:
        raise ValueError("unsupported evidence_class")
    if evidence_class == "unavailable" and confidence != 0.0:
        raise ValueError("unavailable evidence must have zero confidence")
    regime = _text(claim["regime"], "regime", 120)
    horizon_seconds = _nonnegative_int(claim["horizon_seconds"], "horizon_seconds")
    lineage = _items(claim.get("lineage", ()), "lineage", 240)
    details = claim["details"]
    if not isinstance(details, Mapping):
        raise ValueError("details must be a mapping")
    full_claim = _json_value(dict(claim), "claim")

    evidence = list(lineage)
    if claim_id is not None:
        evidence.append(_text(claim_id, "claim_id", 240))
    evidence_ids = tuple(sorted(set(evidence)))

    semantic_group = json.dumps(
        [semantic_key, regime, horizon_seconds], separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    thread_key = "ui:" + hashlib.sha256(semantic_group).hexdigest()

    asset = details.get("asset")
    assets = (_text(asset, "details.asset", 80),) if isinstance(asset, str) and asset.strip() else ()
    payload = {
        "bridge": "unified-intelligence-v1",
        "claim_id": claim_id,
        "semantic_key": semantic_key,
        "stance": stance,
        "regime": regime,
        "horizon_seconds": horizon_seconds,
        "evidence_class": evidence_class,
        "unified_intelligence_claim": full_claim,
    }

    event = IntelligenceEvent(
        event_type="claim",
        source=source,
        source_kind=source_kind,
        channel="intelligence",
        thread_key=thread_key,
        title=("Intelligence claim: " + semantic_key)[:240],
        body="Unified Intelligence claim projection; source confidence is preserved, not calibrated by the fabric.",
        observed_at=claim["observed_at"],
        received_at=claim["received_at"],
        severity=2,
        urgency=0.5,
        confidence=confidence,
        assets=assets,
        evidence_ids=evidence_ids,
        tags=("unified-intelligence", evidence_class, ("regime:" + regime)[:80]),
        payload=payload,
    )
    event.normalized()  # Fail closed at the bridge boundary, not at a later consumer.
    return event