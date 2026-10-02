"""ASCENDANCY federated research intake.

This module converts the canonical BrainRemoteSync Icarus-engine historical
context into durable *research prompts*.  A prompt is an investigation target,
not candidate evidence, not a Foundry candidate, and never trading authority.

The boundary is intentionally one-way:
foreign verified context -> bounded research question -> explicit Foundry /
Evaluator work later.

It never converts foreign context directly into a validated claim or candidate.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Iterable, Mapping

SCHEMA_VERSION = "icarus-ascendancy-federated-research-prompt-v1"
LEDGER_SCHEMA_VERSION = "icarus-ascendancy-federated-research-intake-v1"
REMOTE_REPOSITORY = "reppiks490/Icarus-engine"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_ALLOWED_EVIDENCE = {
    "HISTORICAL_RESEARCH_EVIDENCE",
    "HISTORICAL_COLLECTION_EVIDENCE",
}
_LOCK = threading.RLock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: Any, name: str = "value", max_bytes: int = 262144) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{name} must be finite JSON") from ex
    if len(raw.encode("utf-8")) > max_bytes:
        raise ValueError(f"{name} exceeds {max_bytes} bytes")
    return raw


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value, "hash input").encode("utf-8")).hexdigest()


def _sha40(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an exact Git source commit/blob SHA")
    out = value.strip().lower()
    if not _SHA40.fullmatch(out):
        raise ValueError(f"{name} must be an exact 40-character Git source commit/blob SHA")
    return out


def _text(value: Any, name: str, limit: int = 4000) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    out = value.strip()
    if not out:
        raise ValueError(f"{name} is required")
    if len(out) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return out


def _authority_false(value: Mapping[str, Any], label: str) -> None:
    for key in (
        "execution_authorized",
        "production_decision_authorized",
        "candidate_evidence_eligible",
    ):
        if value.get(key) is True:
            if key == "candidate_evidence_eligible":
                raise ValueError(f"{label} candidate_evidence_eligible must remain false")
            raise ValueError(f"{label} authority escalation is forbidden")


def _values_for_suffix(summary: Mapping[str, Any], suffix: str) -> Iterable[Any]:
    target = suffix.lower()
    for key, value in sorted(summary.items(), key=lambda item: str(item[0])):
        key_text = str(key).lower()
        if key_text == target or key_text.endswith("." + target):
            if isinstance(value, list):
                for item in value:
                    yield item
            else:
                yield value


def _proposal(
    *,
    source_commit: str,
    packet_id: str,
    row: Mapping[str, Any],
    kind: str,
    claim: Any,
    ordinal: int,
) -> dict[str, Any]:
    if isinstance(claim, (dict, list)):
        claim_text = _canonical(claim, "foreign research context claim", 32768)
    else:
        claim_text = _text(str(claim), "foreign research context claim", 4000)

    kind = _text(kind, "proposal_kind", 96).upper()
    source_id = _text(row.get("id"), "historical source id", 160)
    evidence_status = _text(row.get("evidence_status"), "source evidence status", 80).upper()

    question_prefix = {
        "FINDING_REPLICATION": "Can this foreign finding be independently reproduced by ICARUS",
        "ROBUSTNESS_INVESTIGATION": "Does this reported foreign robustness risk survive controlled ICARUS replay",
        "DISAGREEMENT_INVESTIGATION": "Can ICARUS discriminate between the conflicting foreign interpretations",
        "DATA_GAP_INVESTIGATION": "Does resolving this foreign data gap materially change the research conclusion",
        "OBSERVATION_REPLICATION": "Can ICARUS independently reproduce and condition this foreign observation",
    }.get(kind, "Can ICARUS independently investigate this foreign research context")

    semantic: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source_repository": REMOTE_REPOSITORY,
        "source_commit": source_commit,
        "source_packet_id": packet_id,
        "source_id": source_id,
        "source_path": _text(row.get("path"), "historical source path", 600),
        "source_blob_sha": _sha40(row.get("remote_blob_sha"), "historical source blob"),
        "source_run_id": row.get("run_id"),
        "source_run_status": row.get("run_status"),
        "source_evidence_status": evidence_status,
        "proposal_kind": kind,
        "ordinal": int(ordinal),
        "foreign_context": claim_text,
        "research_question": f"{question_prefix}: {claim_text}",
        "claim_status": "FOREIGN_CONTEXT_UNVERIFIED_LOCALLY",
        "admission_state": "RESEARCH_PROMPT_ONLY",
        "research_context_eligible": True,
        "candidate_evidence_eligible": False,
        "automatic_candidate_creation": False,
        "automatic_model_promotion": False,
        "requires_foundry_and_evaluator": True,
        "required_next_gates": [
            "local_observation_or_reconstruction",
            "explicit_falsifiable_hypothesis",
            "candidate_foundry",
            "evaluator_cascade",
        ],
        "falsification_prompts": [
            "independent local replay does not reproduce the reported context",
            "the effect or risk vanishes after provenance, regime, and timing controls",
            "the proposed explanation adds no protected out-of-sample information",
        ],
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
    semantic["proposal_id"] = _hash(semantic)
    return semantic


def _validate_snapshot(snapshot: Mapping[str, Any]) -> tuple[str, str, list[Mapping[str, Any]]]:
    if not isinstance(snapshot, Mapping):
        raise ValueError("federation snapshot must be an object")
    if snapshot.get("execution_authorized") is not False:
        raise ValueError("federation snapshot execution authority is forbidden")
    if snapshot.get("production_decision_authorized") is not False:
        raise ValueError("federation snapshot production authority is forbidden")
    if snapshot.get("repository") != REMOTE_REPOSITORY:
        raise ValueError("federation snapshot repository identity mismatch")
    if str(snapshot.get("status") or "").lower() != "green":
        raise ValueError("federation snapshot is not green")
    if str(snapshot.get("peer_packet_status") or "").lower() != "green":
        raise ValueError("peer packet is not green")
    if snapshot.get("peer_source_commit_verified") is not True:
        raise ValueError("peer source commit is not verified")
    if snapshot.get("peer_packet_fresh") is not True:
        raise ValueError("peer packet is not fresh")
    if str(snapshot.get("historical_context_status") or "").lower() != "green":
        raise ValueError("historical context is not green")
    if int(snapshot.get("historical_candidate_evidence_count") or 0) != 0:
        raise ValueError("historical candidate evidence must remain zero")

    source_commit = _sha40(snapshot.get("peer_source_commit"), "peer source commit")
    packet_id = _text(snapshot.get("peer_packet_id"), "peer packet id", 64).lower()
    if len(packet_id) != 64 or any(ch not in "0123456789abcdef" for ch in packet_id):
        raise ValueError("peer packet id must be a 64-character hash")

    truth = snapshot.get("truth_contract")
    if not isinstance(truth, Mapping):
        raise ValueError("federation truth contract is missing")
    if truth.get("federation_schema") != "icarus-engine-brain-federation-v1":
        raise ValueError("federation schema mismatch")
    if truth.get("historical_context_mode") != "RESEARCH_CONTEXT_ONLY":
        raise ValueError("historical context mode is not research-only")
    for key in (
        "historical_context_never_bypasses_foundry",
        "historical_context_never_bypasses_evaluator",
        "historical_context_never_grants_shadow_qualification",
        "historical_context_never_grants_execution_authority",
    ):
        if truth.get(key) is not True:
            raise ValueError(f"federation truth contract must affirm {key}")
    for key in (
        "durability_receipts_are_substantive_evidence",
        "automatic_model_promotion",
        "automatic_execution_authority",
        "production_decision_authorized",
    ):
        if truth.get(key) is not False:
            raise ValueError(f"federation truth contract attempts escalation: {key}")

    rows = snapshot.get("historical_context_sources")
    if not isinstance(rows, list):
        raise ValueError("historical_context_sources must be a list")
    declared_count = snapshot.get("historical_context_source_count")
    if declared_count is not None and int(declared_count) != len(rows):
        raise ValueError("historical context source count mismatch")
    return source_commit, packet_id, rows


def derive_federated_proposals(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Derive deterministic research prompts from verified foreign context."""
    source_commit, packet_id, rows = _validate_snapshot(snapshot)
    proposals: list[dict[str, Any]] = []

    for raw in rows:
        if not isinstance(raw, Mapping):
            raise ValueError("historical context source must be an object")
        _authority_false(raw, "historical context source")
        if raw.get("research_context_eligible") is not True:
            raise ValueError("historical context source is not research_context_eligible")
        if raw.get("foreign_evidence_only") is not True:
            raise ValueError("historical context source must remain foreign_evidence_only")
        if raw.get("requires_foundry_and_evaluator") is not True:
            raise ValueError("historical context source must require Foundry and Evaluator")

        evidence_status = _text(
            raw.get("evidence_status"), "historical evidence_status", 80
        ).upper()
        if evidence_status not in _ALLOWED_EVIDENCE:
            raise ValueError("unsupported historical evidence_status")
        _sha40(raw.get("remote_blob_sha"), "historical source blob")

        summary = raw.get("summary")
        if not isinstance(summary, Mapping):
            raise ValueError("historical context summary must be an object")
        _canonical(summary, "historical context summary", 65536)

        specs: list[tuple[str, Any]] = []
        specs.extend(("FINDING_REPLICATION", item) for item in _values_for_suffix(summary, "findings"))
        specs.extend(("ROBUSTNESS_INVESTIGATION", item) for item in _values_for_suffix(summary, "unresolved_risks"))
        specs.extend(("DISAGREEMENT_INVESTIGATION", item) for item in _values_for_suffix(summary, "disagreements_collisions"))
        specs.extend(("DATA_GAP_INVESTIGATION", item) for item in _values_for_suffix(summary, "DATA_GAPS"))

        observations = list(_values_for_suffix(summary, "observations"))
        net_new = list(_values_for_suffix(summary, "NET_NEW_DELTA"))
        for item in observations:
            if isinstance(item, Mapping):
                for key in sorted(item):
                    specs.append(("OBSERVATION_REPLICATION", {str(key): item[key]}))
            else:
                specs.append(("OBSERVATION_REPLICATION", item))
        for item in net_new:
            if isinstance(item, Mapping):
                for key in sorted(item):
                    specs.append(("OBSERVATION_REPLICATION", {str(key): item[key]}))
            else:
                specs.append(("OBSERVATION_REPLICATION", item))

        # De-duplicate identical research questions within one immutable source blob
        # while retaining deterministic ordinals for identity.
        seen_claims: set[tuple[str, str]] = set()
        ordinal = 0
        for kind, claim in specs:
            fingerprint = (kind, _canonical(claim, "proposal claim", 32768))
            if fingerprint in seen_claims:
                continue
            seen_claims.add(fingerprint)
            proposals.append(
                _proposal(
                    source_commit=source_commit,
                    packet_id=packet_id,
                    row=raw,
                    kind=kind,
                    claim=claim,
                    ordinal=ordinal,
                )
            )
            ordinal += 1

    proposals.sort(
        key=lambda row: (
            row["source_id"],
            row["source_blob_sha"],
            row["proposal_kind"],
            row["proposal_id"],
        )
    )
    return proposals


class FederatedResearchIntake:
    """Append-only ledger of foreign-context research prompts."""

    def __init__(self, base_dir: str | os.PathLike[str]):
        self.base_dir = Path(base_dir)
        self.path = self.base_dir / "research" / "ascendancy_federated_intake.sqlite3"
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
                CREATE TABLE IF NOT EXISTS proposals (
                    proposal_id TEXT PRIMARY KEY,
                    source_repository TEXT NOT NULL,
                    source_commit TEXT NOT NULL,
                    source_blob_sha TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    proposal_kind TEXT NOT NULL,
                    semantic_json TEXT NOT NULL,
                    ingested_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_federated_intake_source
                    ON proposals(source_repository, source_commit, source_id);
                CREATE INDEX IF NOT EXISTS idx_federated_intake_kind
                    ON proposals(proposal_kind, source_id);
                """
            )

    def close(self) -> None:
        return None

    def ingest(self, snapshot: Mapping[str, Any]) -> dict[str, Any]:
        proposals = derive_federated_proposals(snapshot)
        now = _utc_now()
        new_count = 0
        with _LOCK, self._connect() as con:
            for proposal in proposals:
                raw = _canonical(proposal, "federated research proposal")
                existing = con.execute(
                    "SELECT semantic_json FROM proposals WHERE proposal_id=?",
                    (proposal["proposal_id"],),
                ).fetchone()
                if existing is not None:
                    if str(existing["semantic_json"]) != raw:
                        raise RuntimeError("federated proposal identity integrity failure")
                    continue
                con.execute(
                    """INSERT INTO proposals(
                        proposal_id,source_repository,source_commit,source_blob_sha,
                        source_id,proposal_kind,semantic_json,ingested_at
                    ) VALUES(?,?,?,?,?,?,?,?)""",
                    (
                        proposal["proposal_id"],
                        proposal["source_repository"],
                        proposal["source_commit"],
                        proposal["source_blob_sha"],
                        proposal["source_id"],
                        proposal["proposal_kind"],
                        raw,
                        now,
                    ),
                )
                new_count += 1

        return {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "new_proposal_count": new_count,
            "proposal_count_in_snapshot": len(proposals),
            "proposals": proposals,
            "candidate_evidence_count": 0,
            "automatic_candidate_creation": False,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        try:
            value = json.loads(row["semantic_json"])
        except (TypeError, json.JSONDecodeError) as ex:
            raise RuntimeError("federated intake semantic corruption") from ex
        if not isinstance(value, dict):
            raise RuntimeError("federated intake semantic corruption")
        value["ingested_at"] = str(row["ingested_at"])
        return value

    def snapshot(self) -> dict[str, Any]:
        with _LOCK, self._connect() as con:
            rows = con.execute(
                "SELECT * FROM proposals ORDER BY source_commit,source_id,proposal_kind,proposal_id"
            ).fetchall()
        proposals = [self._decode(row) for row in rows]
        source_repositories = sorted({row["source_repository"] for row in proposals})
        source_commits = sorted({row["source_commit"] for row in proposals})
        kind_counts: dict[str, int] = {}
        for row in proposals:
            kind = str(row["proposal_kind"])
            kind_counts[kind] = kind_counts.get(kind, 0) + 1

        return {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "proposal_count": len(proposals),
            "source_repository_count": len(source_repositories),
            "source_repositories": source_repositories,
            "source_commits": source_commits,
            "proposal_kind_counts": dict(sorted(kind_counts.items())),
            "proposals": proposals,
            "candidate_evidence_count": sum(
                1 for row in proposals if row.get("candidate_evidence_eligible") is True
            ),
            "automatic_candidate_creation": False,
            "automatic_model_promotion": False,
            "truth_contract": {
                "foreign_context_is_not_local_truth": True,
                "research_prompt_is_not_candidate_evidence": True,
                "research_prompt_is_not_a_foundry_candidate": True,
                "foundry_and_evaluator_are_mandatory_downstream": True,
                "source_commit_and_blob_identity_are_preserved": True,
                "historical_context_never_grants_execution_authority": True,
            },
            "execution_authorized": False,
            "production_decision_authorized": False,
        }



SYNC_SCHEMA_VERSION = "icarus-ascendancy-federated-intake-sync-v1"


def _sync_state_path(base_dir: str | os.PathLike[str]) -> Path:
    return Path(base_dir) / "research" / "ascendancy_federated_intake_sync.json"


def _default_sync_state(interval_seconds: int) -> dict[str, Any]:
    return {
        "schema_version": SYNC_SCHEMA_VERSION,
        "status": "not_started",
        "interval_seconds": interval_seconds,
        "last_attempt_at": None,
        "last_success_at": None,
        "last_error": None,
        "last_peer_packet_id": None,
        "last_peer_source_commit": None,
        "new_proposal_count": 0,
        "proposal_count": 0,
        "candidate_evidence_count": 0,
        "automatic_candidate_creation": False,
        "automatic_model_promotion": False,
        "running": False,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def _read_sync_state(
    base_dir: str | os.PathLike[str],
    interval_seconds: int,
) -> dict[str, Any]:
    state = _default_sync_state(interval_seconds)
    path = _sync_state_path(base_dir)
    if not path.is_file():
        return state
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state["status"] = "degraded"
        state["last_error"] = "local federated intake sync state is unreadable"
        return state
    if not isinstance(raw, dict):
        state["status"] = "degraded"
        state["last_error"] = "local federated intake sync state is not an object"
        return state
    if (
        raw.get("execution_authorized") is not False
        or raw.get("production_decision_authorized") is not False
        or raw.get("automatic_candidate_creation") is not False
    ):
        state["status"] = "degraded"
        state["last_error"] = "local federated intake sync state failed authority validation"
        return state
    state.update(raw)
    state["interval_seconds"] = interval_seconds
    state["execution_authorized"] = False
    state["production_decision_authorized"] = False
    state["automatic_candidate_creation"] = False
    state["automatic_model_promotion"] = False
    return state


def _write_sync_state(
    base_dir: str | os.PathLike[str],
    state: Mapping[str, Any],
) -> None:
    path = _sync_state_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(state)
    payload["execution_authorized"] = False
    payload["production_decision_authorized"] = False
    payload["automatic_candidate_creation"] = False
    payload["automatic_model_promotion"] = False
    payload["running"] = False
    raw = json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n"
    with NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=".federated-intake-sync-",
        delete=False,
    ) as fh:
        tmp = Path(fh.name)
        fh.write(raw)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


class FederatedResearchIntakeSync:
    """Autonomous local projection of canonical federation state into prompts.

    The provider is expected to be BrainRemoteSync.status (or an equivalent
    already-verified local snapshot).  This worker performs no remote fetches,
    creates no candidates, and grants no trading authority.
    """

    def __init__(
        self,
        base_dir: str | os.PathLike[str],
        *,
        intake: FederatedResearchIntake,
        provider: Callable[[], Mapping[str, Any]],
        interval_seconds: int = 60,
    ):
        self.base_dir = Path(base_dir)
        self.intake = intake
        self.provider = provider
        self.interval_seconds = max(30, min(3600, int(interval_seconds)))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def status(self) -> dict[str, Any]:
        state = _read_sync_state(self.base_dir, self.interval_seconds)
        state["running"] = bool(self._thread and self._thread.is_alive())
        state["execution_authorized"] = False
        state["production_decision_authorized"] = False
        state["automatic_candidate_creation"] = False
        state["automatic_model_promotion"] = False
        return state

    def sync_once(self) -> dict[str, Any]:
        with self._lock:
            prior = _read_sync_state(self.base_dir, self.interval_seconds)
            state = dict(prior)
            state["last_attempt_at"] = _utc_now()
            state["status"] = "syncing"
            state["last_error"] = None
            try:
                snapshot = self.provider()
                if not isinstance(snapshot, Mapping):
                    raise ValueError("canonical federation provider did not return an object")
                receipt = self.intake.ingest(snapshot)
                ledger = self.intake.snapshot()
                state.update(
                    {
                        "status": "green",
                        "last_success_at": _utc_now(),
                        "last_error": None,
                        "last_peer_packet_id": snapshot.get("peer_packet_id"),
                        "last_peer_source_commit": snapshot.get("peer_source_commit"),
                        "new_proposal_count": int(receipt.get("new_proposal_count") or 0),
                        "proposal_count": int(ledger.get("proposal_count") or 0),
                        "candidate_evidence_count": int(
                            ledger.get("candidate_evidence_count") or 0
                        ),
                        "automatic_candidate_creation": False,
                        "automatic_model_promotion": False,
                        "execution_authorized": False,
                        "production_decision_authorized": False,
                    }
                )
            except Exception as ex:
                ledger = self.intake.snapshot()
                state["status"] = "degraded"
                state["last_error"] = f"{type(ex).__name__}: {ex}"[:1600]
                state["new_proposal_count"] = 0
                state["proposal_count"] = int(ledger.get("proposal_count") or 0)
                state["candidate_evidence_count"] = int(
                    ledger.get("candidate_evidence_count") or 0
                )
                state["execution_authorized"] = False
                state["production_decision_authorized"] = False
                state["automatic_candidate_creation"] = False
                state["automatic_model_promotion"] = False

            _write_sync_state(self.base_dir, state)
            return self.status()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.sync_once()
            except Exception:
                # sync_once itself persists a degraded truth state.  This guard
                # prevents an unexpected persistence failure from killing the
                # background lifecycle.
                pass
            self._stop.wait(self.interval_seconds)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="ascendancy-federated-intake-sync",
            daemon=True,
        )
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if (
            self._thread
            and self._thread.is_alive()
            and self._thread is not threading.current_thread()
        ):
            self._thread.join(timeout=2.0)
