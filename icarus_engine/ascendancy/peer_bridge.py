"""ASCENDANCY peer-repository bridge.

Foreign ICARUS repositories can exchange provenance-bound research/operational
packets without merging authority.  Imported state remains foreign evidence.
Durability-only receipts can inform systems-health reasoning but are ineligible
as substantive Candidate Foundry evidence.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "icarus-peer-intelligence-packet-v1"
BRIDGE_SCHEMA_VERSION = "icarus-ascendancy-peer-bridge-v1"
SELF_REPOSITORY = "reppiks490/Icarus"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_EVIDENCE = {
    "DURABILITY_ONLY",
    "REMOTE_PEER_UNREAD",
    "PERSISTED_WORKER_EVIDENCE",
    "PERSISTED_UNCLASSIFIED",
    "UNAVAILABLE",
    "INCOMPLETE_OR_UNVERIFIED",
    "UNMEASURED",
}
_ALLOWED_HISTORICAL_EVIDENCE = {
    "HISTORICAL_RESEARCH_EVIDENCE",
    "HISTORICAL_COLLECTION_EVIDENCE",
    "HISTORICAL_STATE_ONLY",
    "HISTORICAL_UNVERIFIED",
}
_LOCK = threading.RLock()


def _canonical(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as ex:
        raise ValueError("peer packet must be finite JSON") from ex


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _text(value: Any, name: str, limit: int = 1000) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    out = value.strip()
    if not out:
        raise ValueError(f"{name} is required")
    if len(out) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return out


def _sha(value: Any, name: str, size: int) -> str:
    out = _text(value, name, size).lower()
    pattern = _SHA40 if size == 40 else _SHA64
    if not pattern.fullmatch(out):
        if size == 40:
            raise ValueError(f"{name} must be an exact 40-character Git SHA")
        raise ValueError(f"{name} must be a 64-character hash")
    return out


def _time(value: Any, name: str = "observed_at") -> str:
    raw = _text(value, name, 80)
    probe = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        dt = datetime.fromisoformat(probe)
    except ValueError as ex:
        raise ValueError(f"{name} must be timezone-aware ISO-8601") from ex
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware ISO-8601")
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _assert_research_only(body: Mapping[str, Any], label: str) -> None:
    for key in (
        "execution_authorized",
        "production_decision_authorized",
        "peer_write_authorized",
        "trading_execution_authorized",
    ):
        if body.get(key) is True:
            raise ValueError(f"{label} authority escalation is forbidden")


def _normalize_lane(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("peer lane must be an object")
    _assert_research_only(value, "peer lane")
    status = _text(value.get("evidence_status"), "evidence_status", 64).upper()
    if status not in _ALLOWED_EVIDENCE:
        raise ValueError(f"unsupported evidence_status: {status}")

    substantive = value.get("substantive_research_evidence") is True
    worker_observed = value.get("worker_execution_observed")
    if worker_observed not in (True, False, None):
        raise ValueError("worker_execution_observed must be true, false, or null")

    # Foreign evidence can seed research only when the exporter explicitly
    # observed a worker-produced, persisted result.  Durability/accounting state
    # is never promoted merely because a scheduler receipt exists.
    eligible = (
        status == "PERSISTED_WORKER_EVIDENCE"
        and substantive
        and worker_observed is True
    )
    if status != "PERSISTED_WORKER_EVIDENCE" and substantive:
        raise ValueError("substantive_research_evidence conflicts with evidence_status")

    final_sha = value.get("finalization_commit_sha")
    if final_sha is not None:
        final_sha = _sha(final_sha, "finalization_commit_sha", 40)

    return {
        "name": _text(value.get("name"), "lane name", 160),
        "title": value.get("title"),
        "minute": value.get("minute"),
        "scheduler_id": value.get("scheduler_id"),
        "run_prefix": value.get("run_prefix"),
        "worker_repository": _text(value.get("worker_repository"), "worker_repository", 240),
        "worker_root": value.get("worker_root"),
        "run_id": value.get("run_id"),
        "run_status": value.get("run_status"),
        "finalization_commit_sha": final_sha,
        "completion_semantics": value.get("completion_semantics"),
        "worker_execution_observed": worker_observed,
        "evidence_status": status,
        "substantive_research_evidence": substantive,
        "candidate_evidence_eligible": eligible,
        "execution_authorized": False,
    }


def _optional_sha(value: Any, name: str, size: int) -> str | None:
    if value in (None, ""):
        return None
    return _sha(value, name, size)


def _normalize_historical_artifact(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("historical peer artifact must be an object")
    _assert_research_only(value, "historical peer artifact")

    if value.get("candidate_evidence_eligible") is not False:
        raise ValueError(
            "historical peer artifact candidate_evidence_eligible must remain false"
        )
    status = _text(
        value.get("evidence_status"), "historical evidence_status", 64
    ).upper()
    if status not in _ALLOWED_HISTORICAL_EVIDENCE:
        raise ValueError(f"unsupported historical evidence_status: {status}")

    research_eligible = value.get("research_context_eligible")
    if not isinstance(research_eligible, bool):
        raise ValueError("research_context_eligible must be boolean")
    expected_research = status in {
        "HISTORICAL_RESEARCH_EVIDENCE",
        "HISTORICAL_COLLECTION_EVIDENCE",
    }
    if research_eligible is not expected_research:
        raise ValueError(
            "research_context_eligible conflicts with historical evidence_status"
        )

    artifact_kind = _text(value.get("artifact_kind"), "artifact_kind", 80).upper()
    if artifact_kind != "HISTORICAL_LATEST":
        raise ValueError("unsupported historical artifact_kind")

    summary = value.get("summary")
    if not isinstance(summary, Mapping):
        raise ValueError("historical artifact summary must be an object")
    summary = dict(summary)
    _canonical(summary)

    lineage_value = value.get("lineage")
    if not isinstance(lineage_value, Mapping):
        raise ValueError("historical artifact lineage must be an object")
    lineage = dict(lineage_value)
    for key in ("base_main_sha", "final_main_sha", "history_blob_sha", "ledger_blob_sha"):
        lineage[key] = _optional_sha(lineage.get(key), key, 40)
    lineage["run_core_sha256"] = _optional_sha(
        lineage.get("run_core_sha256"), "run_core_sha256", 64
    )

    artifact_id = _sha(value.get("artifact_id"), "artifact_id", 64)
    unsigned = {k: v for k, v in value.items() if k != "artifact_id"}
    if artifact_id != _hash(unsigned):
        raise ValueError("artifact_id integrity mismatch")

    return {
        "artifact_id": artifact_id,
        "lane": _text(value.get("lane"), "historical lane", 160),
        "artifact_kind": artifact_kind,
        "path": _text(value.get("path"), "historical artifact path", 500),
        "run_id": value.get("run_id"),
        "run_status": value.get("run_status"),
        "evidence_status": status,
        "research_context_eligible": research_eligible,
        "candidate_evidence_eligible": False,
        "summary": summary,
        "lineage": lineage,
        "foreign_evidence_only": True,
        "requires_foundry_and_evaluator": True,
        "execution_authorized": False,
    }


def normalize_peer_packet(body: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one packet emitted by a peer ICARUS repository."""
    if not isinstance(body, Mapping):
        raise ValueError("peer packet must be an object")
    if body.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported peer packet schema_version")
    _assert_research_only(body, "peer packet")

    source_repository = _text(body.get("source_repository"), "source_repository", 240)
    if source_repository == SELF_REPOSITORY:
        raise ValueError("self-source peer packet is forbidden")
    source_commit = _sha(body.get("source_commit"), "source_commit", 40)
    observed_at = _time(body.get("observed_at"))

    packet_id = _sha(body.get("packet_id"), "packet_id", 64)
    unsigned = {k: v for k, v in body.items() if k != "packet_id"}
    expected = _hash(unsigned)
    if packet_id != expected:
        raise ValueError("packet_id integrity mismatch")

    contracts = body.get("source_contracts")
    if not isinstance(contracts, Mapping):
        raise ValueError("source_contracts must be an object")
    contracts = dict(contracts)

    control = body.get("control_plane")
    if not isinstance(control, Mapping):
        raise ValueError("control_plane must be an object")
    control = dict(control)

    raw_lanes = body.get("lanes")
    if not isinstance(raw_lanes, Sequence) or isinstance(raw_lanes, (str, bytes)):
        raise ValueError("lanes must be a list")
    lanes = [_normalize_lane(x) for x in raw_lanes]
    names = [x["name"] for x in lanes]
    if len(names) != len(set(names)):
        raise ValueError("duplicate peer lane name")
    lanes.sort(key=lambda row: row["name"])

    raw_historical = body.get("historical_artifacts") or []
    if (
        not isinstance(raw_historical, Sequence)
        or isinstance(raw_historical, (str, bytes))
    ):
        raise ValueError("historical_artifacts must be a list")
    historical_artifacts = [
        _normalize_historical_artifact(x) for x in raw_historical
    ]
    artifact_ids = [x["artifact_id"] for x in historical_artifacts]
    if len(artifact_ids) != len(set(artifact_ids)):
        raise ValueError("duplicate historical artifact_id")
    historical_artifacts.sort(
        key=lambda row: (row["lane"], str(row.get("run_id") or ""), row["artifact_id"])
    )

    mcp = body.get("mcp_interface")
    if not isinstance(mcp, Mapping):
        raise ValueError("mcp_interface must be an object")
    _assert_research_only(mcp, "peer MCP interface")
    mcp = dict(mcp)
    mcp["trading_execution_authorized"] = False

    truth = body.get("truth_contract")
    if not isinstance(truth, Mapping):
        raise ValueError("truth_contract must be an object")
    required_truths = (
        "foreign_repository_state_is_evidence_not_native_truth",
        "durability_receipt_is_not_substantive_worker_evidence",
        "remote_sibling_state_is_never_inferred",
        "exact_source_commit_required",
        "execution_authority_never_transfers_between_repositories",
    )
    for key in required_truths:
        if truth.get(key) is not True:
            raise ValueError(f"peer truth contract must affirm {key}")
    if historical_artifacts and truth.get(
        "historical_context_never_bypasses_foundry_or_evaluator"
    ) is not True:
        raise ValueError(
            "peer truth contract must affirm historical_context_never_bypasses_foundry_or_evaluator"
        )

    normalized = {
        "schema_version": SCHEMA_VERSION,
        "packet_id": packet_id,
        "source_repository": source_repository,
        "source_commit": source_commit,
        "observed_at": observed_at,
        "source_contracts": contracts,
        "control_plane": control,
        "lanes": lanes,
        "historical_artifacts": historical_artifacts,
        "mcp_interface": mcp,
        "truth_contract": dict(truth),
        "execution_authorized": False,
        "production_decision_authorized": False,
        "peer_write_authorized": False,
    }
    return normalized


class PeerRepositoryBridge:
    """Append-only store for foreign-repository intelligence packets."""

    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.path = self.base_dir / "research" / "ascendancy_peer_repositories.sqlite3"
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
                CREATE TABLE IF NOT EXISTS peer_packets (
                    packet_id TEXT PRIMARY KEY,
                    source_repository TEXT NOT NULL,
                    source_commit TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    semantic_json TEXT NOT NULL,
                    ingested_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_peer_source_time
                    ON peer_packets(source_repository, observed_at, packet_id);
                """
            )

    def close(self) -> None:
        return None

    def ingest(self, body: Mapping[str, Any]) -> dict[str, Any]:
        packet = normalize_peer_packet(body)
        raw = _canonical(packet)
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with _LOCK, self._connect() as con:
            existing = con.execute(
                "SELECT semantic_json FROM peer_packets WHERE packet_id=?",
                (packet["packet_id"],),
            ).fetchone()
            if existing is not None:
                if str(existing["semantic_json"]) != raw:
                    raise RuntimeError("peer packet identity integrity failure")
                return {
                    "idempotent": True,
                    "packet": packet,
                    "execution_authorized": False,
                    "production_decision_authorized": False,
                }
            con.execute(
                """INSERT INTO peer_packets(
                    packet_id,source_repository,source_commit,observed_at,
                    semantic_json,ingested_at
                ) VALUES(?,?,?,?,?,?)""",
                (
                    packet["packet_id"],
                    packet["source_repository"],
                    packet["source_commit"],
                    packet["observed_at"],
                    raw,
                    now,
                ),
            )
        return {
            "idempotent": False,
            "packet": packet,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        try:
            packet = json.loads(row["semantic_json"])
        except (TypeError, json.JSONDecodeError) as ex:
            raise RuntimeError("peer bridge semantic corruption") from ex
        if not isinstance(packet, dict):
            raise RuntimeError("peer bridge semantic corruption")
        packet["ingested_at"] = str(row["ingested_at"])
        return packet

    @staticmethod
    def _summarize(packet: Mapping[str, Any]) -> dict[str, Any]:
        lanes = list(packet.get("lanes") or [])
        eligible = sorted(
            str(x["name"])
            for x in lanes
            if isinstance(x, Mapping) and x.get("candidate_evidence_eligible") is True
        )
        durability = sorted(
            str(x["name"])
            for x in lanes
            if isinstance(x, Mapping) and x.get("evidence_status") == "DURABILITY_ONLY"
        )
        historical = [
            dict(x)
            for x in (packet.get("historical_artifacts") or [])
            if isinstance(x, Mapping)
        ]
        historical_context = [
            x for x in historical if x.get("research_context_eligible") is True
        ]
        historical_candidate = [
            x for x in historical if x.get("candidate_evidence_eligible") is True
        ]
        historical_lanes = sorted({
            str(x.get("lane") or "")
            for x in historical_context
            if str(x.get("lane") or "")
        })
        return {
            **dict(packet),
            "lane_count": len(lanes),
            "substantive_lane_count": len(eligible),
            "durability_only_lane_count": len(durability),
            "candidate_evidence_eligible_lanes": eligible,
            "durability_only_lanes": durability,
            "historical_artifact_count": len(historical),
            "historical_research_context_count": len(historical_context),
            "historical_candidate_evidence_count": len(historical_candidate),
            "historical_research_lanes": historical_lanes,
            "historical_artifacts": historical,
            "foreign_evidence_only": True,
        }

    def snapshot(self) -> dict[str, Any]:
        with _LOCK, self._connect() as con:
            rows = con.execute(
                "SELECT * FROM peer_packets ORDER BY observed_at,packet_id"
            ).fetchall()
        packets = [self._decode(row) for row in rows]

        latest: dict[str, dict[str, Any]] = {}
        for packet in packets:
            source = str(packet["source_repository"])
            prior = latest.get(source)
            if prior is None or (
                packet["observed_at"], packet["packet_id"]
            ) > (
                prior["observed_at"], prior["packet_id"]
            ):
                latest[source] = packet

        latest_rows = [
            self._summarize(latest[source])
            for source in sorted(latest)
        ]

        return {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "packet_count": len(packets),
            "source_count": len(latest_rows),
            "packets": packets,
            "latest_by_source": latest_rows,
            "truth_contract": {
                "peer_state_is_foreign_evidence_only": True,
                "durability_only_never_enters_candidate_evidence": True,
                "substantive_worker_evidence_still_requires_normal_foundry_and_evaluator_gates": True,
                "historical_context_never_bypasses_foundry_or_evaluator": True,
                "historical_artifacts_never_become_candidate_evidence_directly": True,
                "peer_repository_authority_never_transfers": True,
                "historical_packets_are_append_only": True,
            },
            "execution_authorized": False,
            "production_decision_authorized": False,
        }
