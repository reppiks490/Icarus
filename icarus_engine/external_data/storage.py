from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from .contracts import EvidenceEnvelope
from .identity import canonical_json_bytes, canonical_sha256, normalize_utc, raw_sha256


class StorageIntegrityError(RuntimeError):
    """Raised when persisted bytes or canonical evidence fail integrity checks."""


@dataclass(frozen=True, slots=True)
class RawArtifactRef:
    provider_id: str
    dataset: str
    sha256: str
    path: Path
    size_bytes: int
    created: bool
    metadata: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class UpsertResult:
    evidence_id: str
    observation_key: str
    inserted: bool
    duplicate: bool
    flags: tuple[str, ...]


def _safe_segment(name: str, value: str) -> str:
    if not isinstance(value, str) or not value or value in {".", ".."}:
        raise ValueError(f"{name} must be a non-empty path-safe string")
    if "/" in value or "\\" in value or "\x00" in value:
        raise ValueError(f"{name} must not contain path separators")
    return value


def _utc_text(value) -> str | None:
    normalized = normalize_utc(value)
    if normalized is None:
        return None
    return normalized.isoformat().replace("+00:00", "Z")


def observation_key(envelope: EvidenceEnvelope) -> str:
    """Stable source-observation identity shared by all later revisions/vintages."""
    payload = {
        "source_id": envelope.source_id,
        "provider_id": envelope.provider_id,
        "dataset": envelope.dataset,
        "instrument": envelope.instrument,
        "venue": envelope.venue,
        "source_event_time": envelope.source_event_time,
    }
    return "obs_" + canonical_sha256(payload)


class RawArtifactStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def put(
        self,
        provider: str,
        dataset: str,
        payload: bytes,
        metadata: Mapping[str, Any] | None = None,
    ) -> RawArtifactRef:
        provider = _safe_segment("provider", provider)
        dataset = _safe_segment("dataset", dataset)
        if not isinstance(payload, bytes):
            raise TypeError("raw artifact payload must be bytes")
        digest = raw_sha256(payload)
        parent = self.root / "raw" / provider / dataset
        parent.mkdir(parents=True, exist_ok=True)
        target = parent / f"{digest}.payload"

        if target.exists():
            existing = target.read_bytes()
            if raw_sha256(existing) != digest or existing != payload:
                raise StorageIntegrityError(f"content-address corruption at {target}")
            return RawArtifactRef(
                provider,
                dataset,
                digest,
                target,
                len(payload),
                False,
                MappingProxyType(dict(metadata or {})),
            )

        fd, temp_name = tempfile.mkstemp(prefix=".tmp-", suffix=".payload", dir=parent)
        temp = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            if target.exists():
                existing = target.read_bytes()
                if raw_sha256(existing) != digest or existing != payload:
                    raise StorageIntegrityError(f"content-address corruption at {target}")
            else:
                os.replace(temp, target)
            if raw_sha256(target.read_bytes()) != digest:
                raise StorageIntegrityError(f"content-address verification failed at {target}")
        finally:
            try:
                temp.unlink()
            except FileNotFoundError:
                pass

        return RawArtifactRef(
            provider,
            dataset,
            digest,
            target,
            len(payload),
            True,
            MappingProxyType(dict(metadata or {})),
        )


class EvidenceCatalog:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence (
                    evidence_id TEXT PRIMARY KEY,
                    observation_key TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    dataset TEXT NOT NULL,
                    source_available_at TEXT,
                    ingested_at TEXT NOT NULL,
                    revision_id TEXT,
                    vintage_id TEXT,
                    raw_artifact_sha256 TEXT NOT NULL,
                    canonical_sha256 TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_evidence_source_observation "
                "ON evidence(source_id, observation_key, source_available_at, ingested_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_evidence_asof "
                "ON evidence(source_available_at, provider_id, dataset)"
            )

    def _before_commit(self, _conn: sqlite3.Connection, _envelope: EvidenceEnvelope) -> None:
        """Fault-injection seam; production implementation intentionally does nothing."""

    def upsert(self, envelope: EvidenceEnvelope) -> UpsertResult:
        key = observation_key(envelope)
        payload_json = canonical_json_bytes(envelope.to_canonical_dict()).decode("utf-8")
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            duplicate = conn.execute(
                "SELECT evidence_id FROM evidence WHERE evidence_id=?",
                (envelope.evidence_id,),
            ).fetchone()
            if duplicate is not None:
                conn.commit()
                return UpsertResult(envelope.evidence_id, key, False, True, ())

            prior = conn.execute(
                "SELECT canonical_sha256 FROM evidence WHERE observation_key=?",
                (key,),
            ).fetchall()
            flags: list[str] = []
            if prior:
                flags.append("REVISION")
                if any(row["canonical_sha256"] != envelope.canonical_sha256 for row in prior):
                    flags.append("CONFLICT")

            conn.execute(
                """
                INSERT INTO evidence (
                    evidence_id, observation_key, source_id, provider_id, dataset,
                    source_available_at, ingested_at, revision_id, vintage_id,
                    raw_artifact_sha256, canonical_sha256, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    envelope.evidence_id,
                    key,
                    envelope.source_id,
                    envelope.provider_id,
                    envelope.dataset,
                    _utc_text(envelope.source_available_at),
                    _utc_text(envelope.ingested_at),
                    envelope.revision_id,
                    envelope.vintage_id,
                    envelope.raw_artifact_sha256,
                    envelope.canonical_sha256,
                    payload_json,
                ),
            )
            self._before_commit(conn, envelope)
            conn.commit()
            return UpsertResult(envelope.evidence_id, key, True, False, tuple(flags))
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _decode(payload_json: str) -> EvidenceEnvelope:
        payload = json.loads(payload_json)
        envelope = EvidenceEnvelope(
            source_id=payload["source_id"],
            provider_id=payload["provider_id"],
            dataset=payload["dataset"],
            instrument=payload["instrument"],
            venue=payload["venue"],
            source_event_time=payload["source_event_time"],
            source_publication_time=payload["source_publication_time"],
            source_available_at=payload["source_available_at"],
            retrieved_at=payload["retrieved_at"],
            ingested_at=payload["ingested_at"],
            revision_id=payload["revision_id"],
            vintage_id=payload["vintage_id"],
            raw_artifact_sha256=payload["raw_artifact_sha256"],
            ingest_batch_id=payload["ingest_batch_id"],
            data=payload.get("data") or {},
            quality_flags=tuple(payload["quality_flags"]),
            lineage_parents=tuple(payload["lineage_parents"]),
        )
        if envelope.evidence_id != payload["evidence_id"]:
            raise StorageIntegrityError("stored evidence_id does not match canonical evidence")
        if envelope.canonical_sha256 != payload["canonical_sha256"]:
            raise StorageIntegrityError("stored canonical_sha256 does not match canonical data")
        return envelope

    def revisions(self, source_id: str, key: str) -> list[EvidenceEnvelope]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload_json FROM evidence
                WHERE source_id=? AND observation_key=?
                ORDER BY source_available_at IS NULL, source_available_at, ingested_at, evidence_id
                """,
                (source_id, key),
            ).fetchall()
        return [self._decode(row["payload_json"]) for row in rows]

    def query_as_of(
        self,
        cutoff,
        *,
        provider_id: str | None = None,
        dataset: str | None = None,
        source_id: str | None = None,
    ) -> list[EvidenceEnvelope]:
        cutoff_text = _utc_text(cutoff)
        if cutoff_text is None:
            raise ValueError("cutoff is required")
        clauses = ["source_available_at IS NOT NULL", "source_available_at <= ?"]
        params: list[Any] = [cutoff_text]
        for column, value in (
            ("provider_id", provider_id),
            ("dataset", dataset),
            ("source_id", source_id),
        ):
            if value is not None:
                clauses.append(f"{column}=?")
                params.append(value)
        sql = (
            "SELECT observation_key, source_available_at, ingested_at, evidence_id, payload_json "
            "FROM evidence WHERE "
            + " AND ".join(clauses)
            + " ORDER BY observation_key, source_available_at, ingested_at, evidence_id"
        )
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        latest: dict[str, tuple[str, list[sqlite3.Row]]] = {}
        for row in rows:
            key = row["observation_key"]
            available = row["source_available_at"]
            if key not in latest or available > latest[key][0]:
                latest[key] = (available, [row])
            elif available == latest[key][0]:
                latest[key][1].append(row)
        selected = [row for key in sorted(latest) for row in latest[key][1]]
        return [self._decode(row["payload_json"]) for row in selected]
