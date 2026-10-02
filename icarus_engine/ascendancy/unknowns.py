"""ASCENDANCY Unknown-Unknown laboratory.

APEX unknown_force, PANTHEON NULLSPACE/EX_NIHILO, reality-gap monitors and other
subsystems can emit local diagnostics.  This module does something different:
it durably aggregates those diagnostics across engines and independent episodes,
tracks whether residual structure replicates, preserves failed explanations, and
links unexplained phenomena to research candidates.

A repeated residual is not automatically a cause.  Raw events and discovered
phenomena keep cause=None.  The lab has no execution or production authority.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import statistics
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "icarus-ascendancy-unknown-event-v1"
LAB_SCHEMA_VERSION = "icarus-ascendancy-unknown-lab-v1"

EVIDENCE_CLASSES = {"observed", "derived", "reconstructed", "inferred", "unavailable"}
SOURCE_KINDS = {"native", "foreign_lens", "generated", "human", "experiment", "hybrid"}
EXPLANATION_STATUSES = {"FAILED", "INCONCLUSIVE", "SUPPORTED_RESEARCH"}
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_LOCK = threading.RLock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _text(value: Any, name: str, limit: int = 1000) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    out = value.strip()
    if not out:
        raise ValueError(f"{name} is required")
    if len(out) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return out


def _canonical(value: Any, name: str = "value", *, max_bytes: int = 131072) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{name} must be finite JSON") from ex
    if len(raw.encode("utf-8")) > max_bytes:
        raise ValueError(f"{name} exceeds {max_bytes} bytes")
    return raw


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value, "hash input").encode("utf-8")).hexdigest()


def _git_sha(value: Any) -> str:
    out = _text(value, "source_commit", 40).lower()
    if not _SHA40.fullmatch(out):
        raise ValueError("source_commit must be an exact 40-character Git SHA")
    return out


def _hash_id(value: Any, name: str) -> str:
    out = _text(value, name, 64).lower()
    if not _SHA64.fullmatch(out):
        raise ValueError(f"{name} must be a 64-character hash")
    return out


def _iso(value: Any, name: str) -> tuple[str, float]:
    text = _text(value, name, 80)
    probe = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        dt = datetime.fromisoformat(probe)
    except ValueError as ex:
        raise ValueError(f"{name} must be ISO-8601") from ex
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")
    dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z"), dt.timestamp()


def _nonnegative(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be finite")
    out = float(value)
    if not math.isfinite(out) or out < 0.0:
        raise ValueError(f"{name} must be finite and non-negative")
    return out


def _positive_int(value: Any, name: str, maximum: int = 31_536_000) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < 1 or value > maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")
    return value


def _string_list(value: Any, name: str, *, required: bool = False, limit: int = 500) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{name} must be a list")
    out = sorted({_text(item, f"{name} item", limit) for item in value})
    if required and not out:
        raise ValueError(f"{name} must not be empty")
    return out


def normalize_unknown_event(body: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one unexplained-residual event and derive stable identities."""
    if not isinstance(body, Mapping):
        raise ValueError("unknown event must be an object")
    if body.get("cause") is not None:
        raise ValueError("cause must remain null for an unexplained event")
    if body.get("execution_authorized") not in (None, False):
        raise ValueError("unknown event cannot authorize execution")
    if body.get("production_decision_authorized") not in (None, False):
        raise ValueError("unknown event cannot authorize production decisions")

    source_engine = _text(body.get("source_engine"), "source_engine", 160)
    source_kind = _text(body.get("source_kind"), "source_kind", 40).lower()
    if source_kind not in SOURCE_KINDS:
        raise ValueError("unsupported source_kind")
    source_repo = _text(body.get("source_repo"), "source_repo", 180)
    source_commit = _git_sha(body.get("source_commit"))

    asset = _text(body.get("asset"), "asset", 64).upper()
    horizon_seconds = _positive_int(body.get("horizon_seconds"), "horizon_seconds")
    observed_at, observed_ts = _iso(body.get("observed_at"), "observed_at")
    received_at, received_ts = _iso(body.get("received_at"), "received_at")
    if received_ts < observed_ts:
        raise ValueError("received_at cannot precede observed_at")

    episode_id = _text(body.get("episode_id"), "episode_id", 240)
    regime = _text(body.get("regime"), "regime", 160)
    residual_family = _text(body.get("residual_family"), "residual_family", 240)
    residual_magnitude = _nonnegative(body.get("residual_magnitude"), "residual_magnitude")

    evidence_class = _text(body.get("evidence_class"), "evidence_class", 40).lower()
    if evidence_class not in EVIDENCE_CLASSES:
        raise ValueError("unsupported evidence_class")
    evidence_ids = _string_list(body.get("evidence_ids", []), "evidence_ids")
    if evidence_class != "unavailable" and not evidence_ids:
        raise ValueError("confirming unknown event requires evidence_ids")

    failed_systems = _string_list(
        body.get("failed_systems", []),
        "failed_systems",
        required=True,
        limit=160,
    )

    descriptors_value = body.get("phenomenon_descriptors")
    if not isinstance(descriptors_value, Mapping) or not descriptors_value:
        raise ValueError("phenomenon_descriptors must be a non-empty object")
    phenomenon_descriptors = dict(descriptors_value)
    _canonical(phenomenon_descriptors, "phenomenon_descriptors", max_bytes=32768)

    context_value = body.get("context") or {}
    if not isinstance(context_value, Mapping):
        raise ValueError("context must be an object")
    context = dict(context_value)
    _canonical(context, "context", max_bytes=65536)

    # Source identity, episode identity, raw magnitude, timestamps and evidence
    # are intentionally excluded.  This lets independent engines/episodes
    # identify the same *kind* of unexplained state without forcing a match on
    # implementation details.
    phenomenon_semantic = {
        "asset": asset,
        "horizon_seconds": horizon_seconds,
        "regime": regime,
        "residual_family": residual_family,
        "failed_systems": failed_systems,
        "phenomenon_descriptors": phenomenon_descriptors,
    }
    phenomenon_signature = _hash(phenomenon_semantic)

    semantic = {
        "schema_version": SCHEMA_VERSION,
        "source_engine": source_engine,
        "source_kind": source_kind,
        "source_repo": source_repo,
        "source_commit": source_commit,
        "asset": asset,
        "horizon_seconds": horizon_seconds,
        "observed_at": observed_at,
        "received_at": received_at,
        "episode_id": episode_id,
        "regime": regime,
        "residual_family": residual_family,
        "residual_magnitude": residual_magnitude,
        "evidence_class": evidence_class,
        "evidence_ids": evidence_ids,
        "failed_systems": failed_systems,
        "phenomenon_descriptors": phenomenon_descriptors,
        "context": context,
        "phenomenon_signature": phenomenon_signature,
        "usable_for_confirmation": evidence_class != "unavailable",
        "cause": None,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
    semantic["event_id"] = _hash(semantic)
    return semantic


class UnknownUnknownLab:
    """Durable cross-engine unexplained-phenomenon memory."""

    def __init__(self, base_dir: str | os.PathLike[str]):
        self.base_dir = Path(base_dir)
        self.path = self.base_dir / "research" / "ascendancy_unknowns.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path), timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        return con

    @property
    def journal_mode(self) -> str:
        with self._connect() as con:
            return str(con.execute("PRAGMA journal_mode").fetchone()[0]).lower()

    def _init(self) -> None:
        with _LOCK, self._connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    phenomenon_signature TEXT NOT NULL,
                    episode_id TEXT NOT NULL,
                    source_engine TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    observed_ts REAL NOT NULL,
                    received_at TEXT NOT NULL,
                    received_ts REAL NOT NULL,
                    evidence_class TEXT NOT NULL,
                    semantic_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_asc_unknown_signature
                    ON events(phenomenon_signature, observed_ts, event_id);
                CREATE INDEX IF NOT EXISTS idx_asc_unknown_episode
                    ON events(phenomenon_signature, episode_id);

                CREATE TABLE IF NOT EXISTS explanation_tests (
                    explanation_id TEXT PRIMARY KEY,
                    phenomenon_signature TEXT NOT NULL,
                    explanation TEXT NOT NULL,
                    status TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    source_repo TEXT NOT NULL,
                    source_commit TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_asc_unknown_explanations
                    ON explanation_tests(phenomenon_signature, recorded_at);

                CREATE TABLE IF NOT EXISTS candidate_links (
                    link_id TEXT PRIMARY KEY,
                    phenomenon_signature TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    UNIQUE(phenomenon_signature, candidate_id)
                );
                CREATE INDEX IF NOT EXISTS idx_asc_unknown_candidates
                    ON candidate_links(phenomenon_signature, candidate_id);
                """
            )

    def close(self) -> None:
        return None

    def record_event(self, body: Mapping[str, Any]) -> dict[str, Any]:
        event = normalize_unknown_event(body)
        now = _utc_now()
        raw = _canonical(event, "unknown event")
        with _LOCK, self._connect() as con:
            cur = con.execute(
                """INSERT OR IGNORE INTO events(
                    event_id,phenomenon_signature,episode_id,source_engine,
                    observed_at,observed_ts,received_at,received_ts,
                    evidence_class,semantic_json,recorded_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    event["event_id"],
                    event["phenomenon_signature"],
                    event["episode_id"],
                    event["source_engine"],
                    event["observed_at"],
                    _iso(event["observed_at"], "observed_at")[1],
                    event["received_at"],
                    _iso(event["received_at"], "received_at")[1],
                    event["evidence_class"],
                    raw,
                    now,
                ),
            )
        return {
            "idempotent": cur.rowcount == 0,
            "event": event,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def _known_signature(self, signature: str) -> str:
        sig = _hash_id(signature, "phenomenon_signature")
        with self._connect() as con:
            row = con.execute(
                "SELECT 1 FROM events WHERE phenomenon_signature=? LIMIT 1",
                (sig,),
            ).fetchone()
        if row is None:
            raise ValueError("unknown phenomenon_signature")
        return sig

    def record_explanation_test(self, body: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(body, Mapping):
            raise ValueError("explanation test must be an object")
        signature = self._known_signature(body.get("phenomenon_signature"))
        explanation = _text(body.get("explanation"), "explanation", 4000)
        status = _text(body.get("status"), "explanation status", 64).upper()
        if status not in EXPLANATION_STATUSES:
            raise ValueError("unsupported explanation status")
        evidence = _string_list(body.get("evidence", []), "explanation evidence", required=True)
        source_repo = _text(body.get("source_repo"), "source_repo", 180)
        source_commit = _git_sha(body.get("source_commit"))
        semantic = {
            "phenomenon_signature": signature,
            "explanation": explanation,
            "status": status,
            "evidence": evidence,
            "source_repo": source_repo,
            "source_commit": source_commit,
            "cause": None,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }
        explanation_id = _hash(semantic)
        now = _utc_now()
        with _LOCK, self._connect() as con:
            cur = con.execute(
                """INSERT OR IGNORE INTO explanation_tests(
                    explanation_id,phenomenon_signature,explanation,status,
                    evidence_json,source_repo,source_commit,recorded_at
                ) VALUES(?,?,?,?,?,?,?,?)""",
                (
                    explanation_id,
                    signature,
                    explanation,
                    status,
                    _canonical(evidence, "explanation evidence"),
                    source_repo,
                    source_commit,
                    now,
                ),
            )
        return {
            "idempotent": cur.rowcount == 0,
            "explanation_test": {
                **semantic,
                "explanation_id": explanation_id,
                "recorded_at": now,
            },
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def link_candidate(self, phenomenon_signature: str, candidate_id: str, rationale: str) -> dict[str, Any]:
        signature = self._known_signature(phenomenon_signature)
        cid = _hash_id(candidate_id, "candidate_id")
        rationale = _text(rationale, "candidate link rationale", 2000)
        semantic = {
            "phenomenon_signature": signature,
            "candidate_id": cid,
            "rationale": rationale,
        }
        link_id = _hash(semantic)
        now = _utc_now()
        with _LOCK, self._connect() as con:
            cur = con.execute(
                """INSERT OR IGNORE INTO candidate_links(
                    link_id,phenomenon_signature,candidate_id,rationale,recorded_at
                ) VALUES(?,?,?,?,?)""",
                (link_id, signature, cid, rationale, now),
            )
        return {
            "idempotent": cur.rowcount == 0,
            "link_id": link_id,
            "phenomenon_signature": signature,
            "candidate_id": cid,
            "rationale": rationale,
            "cause": None,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    @staticmethod
    def _decode_event(row: sqlite3.Row) -> dict[str, Any]:
        try:
            item = json.loads(row["semantic_json"])
        except (TypeError, json.JSONDecodeError) as ex:
            raise RuntimeError("unknown-event semantic corruption") from ex
        if not isinstance(item, dict):
            raise RuntimeError("unknown-event semantic corruption")
        if item.get("cause") is not None:
            raise RuntimeError("unknown-event cause integrity failure")
        if item.get("execution_authorized") is not False or item.get("production_decision_authorized") is not False:
            raise RuntimeError("unknown-event authority integrity failure")
        return item

    def snapshot(self, *, min_independent_episodes: int = 3) -> dict[str, Any]:
        threshold = _positive_int(
            min_independent_episodes,
            "min_independent_episodes",
            maximum=10000,
        )
        with _LOCK, self._connect() as con:
            event_rows = con.execute(
                "SELECT * FROM events ORDER BY observed_ts,event_id"
            ).fetchall()
            explanation_rows = con.execute(
                """SELECT * FROM explanation_tests
                   ORDER BY recorded_at,explanation_id"""
            ).fetchall()
            link_rows = con.execute(
                """SELECT * FROM candidate_links
                   ORDER BY recorded_at,link_id"""
            ).fetchall()

        events = [self._decode_event(row) for row in event_rows]
        by_signature: dict[str, list[dict[str, Any]]] = {}
        for event in events:
            by_signature.setdefault(str(event["phenomenon_signature"]), []).append(event)

        explanations: dict[str, list[dict[str, Any]]] = {}
        for row in explanation_rows:
            try:
                evidence = json.loads(row["evidence_json"])
            except (TypeError, json.JSONDecodeError):
                evidence = []
            explanations.setdefault(str(row["phenomenon_signature"]), []).append({
                "explanation_id": str(row["explanation_id"]),
                "explanation": str(row["explanation"]),
                "status": str(row["status"]),
                "evidence": evidence if isinstance(evidence, list) else [],
                "source_repo": str(row["source_repo"]),
                "source_commit": str(row["source_commit"]),
                "recorded_at": str(row["recorded_at"]),
            })

        links: dict[str, list[dict[str, Any]]] = {}
        for row in link_rows:
            links.setdefault(str(row["phenomenon_signature"]), []).append({
                "link_id": str(row["link_id"]),
                "candidate_id": str(row["candidate_id"]),
                "rationale": str(row["rationale"]),
                "recorded_at": str(row["recorded_at"]),
            })

        phenomena: list[dict[str, Any]] = []
        for signature in sorted(by_signature):
            rows = by_signature[signature]
            confirming = [row for row in rows if row.get("usable_for_confirmation") is True]
            episodes = sorted({str(row["episode_id"]) for row in confirming})
            magnitudes = sorted(float(row["residual_magnitude"]) for row in confirming)
            independent_episode_count = len(episodes)

            if not confirming:
                status = "UNMEASURED"
            elif independent_episode_count >= threshold:
                status = "REPLICATED"
            elif independent_episode_count >= 2:
                status = "STRUCTURED_CANDIDATE"
            else:
                status = "EARLY"

            observed = sorted(
                (str(row["observed_at"]) for row in rows),
                key=lambda value: _iso(value, "observed_at")[1],
            )
            explanation_items = explanations.get(signature, [])
            candidate_items = links.get(signature, [])
            prototype = rows[0]

            phenomena.append({
                "phenomenon_id": "u-" + signature[:20],
                "phenomenon_signature": signature,
                "status": status,
                "cause": None,
                "event_count": len(rows),
                "confirming_event_count": len(confirming),
                "independent_episode_count": independent_episode_count,
                "independent_episode_threshold": threshold,
                "first_seen": observed[0] if observed else None,
                "last_seen": observed[-1] if observed else None,
                "assets": sorted({str(row["asset"]) for row in rows}),
                "regimes": sorted({str(row["regime"]) for row in rows}),
                "horizons_seconds": sorted({int(row["horizon_seconds"]) for row in rows}),
                "residual_families": sorted({str(row["residual_family"]) for row in rows}),
                "source_engines": sorted({str(row["source_engine"]) for row in rows}),
                "failed_systems": sorted({
                    str(system)
                    for row in rows
                    for system in (row.get("failed_systems") or [])
                }),
                "phenomenon_descriptors": prototype.get("phenomenon_descriptors", {}),
                "evidence_ids": sorted({
                    str(evidence_id)
                    for row in confirming
                    for evidence_id in (row.get("evidence_ids") or [])
                }),
                "mean_residual_magnitude": (
                    sum(magnitudes) / len(magnitudes) if magnitudes else None
                ),
                "median_residual_magnitude": (
                    statistics.median(magnitudes) if magnitudes else None
                ),
                "explanation_tests": explanation_items,
                "failed_explanations": sorted({
                    str(item["explanation"])
                    for item in explanation_items
                    if item["status"] == "FAILED"
                }),
                "candidate_links": candidate_items,
                "candidate_ids": sorted({
                    str(item["candidate_id"]) for item in candidate_items
                }),
                "next_stage": (
                    "GENERATE_OR_TEST_EXPLANATIONS"
                    if status in {"STRUCTURED_CANDIDATE", "REPLICATED"}
                    else "COLLECT_INDEPENDENT_EPISODES"
                    if status == "EARLY"
                    else "ACQUIRE_CONFIRMING_EVIDENCE"
                ),
                "structured_vs_noise_status": status,
                "execution_authorized": False,
                "production_decision_authorized": False,
            })

        return {
            "schema_version": LAB_SCHEMA_VERSION,
            "journal_mode": self.journal_mode,
            "event_count": len(events),
            "phenomenon_count": len(phenomena),
            "replicated_count": sum(1 for row in phenomena if row["status"] == "REPLICATED"),
            "structured_candidate_count": sum(
                1 for row in phenomena if row["status"] == "STRUCTURED_CANDIDATE"
            ),
            "unmeasured_count": sum(1 for row in phenomena if row["status"] == "UNMEASURED"),
            "phenomena": phenomena,
            "contracts": {
                "independent_episodes_required_for_replication": True,
                "unavailable_evidence_cannot_confirm": True,
                "cause_remains_null_until_separate_validation": True,
                "failed_explanations_are_preserved": True,
                "candidate_link_is_not_candidate_qualification": True,
            },
            "execution_authorized": False,
            "production_decision_authorized": False,
        }
