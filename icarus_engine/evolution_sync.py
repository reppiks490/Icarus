"""Repository-native MCP evolution feed -> local ICARUS trader observability.

Cloud MCP agents cannot call the operator's localhost trader directly. They publish
small immutable JSON receipts into this repository. This background synchronizer
verifies each Git blob, validates a fail-closed schema, mirrors the event into the
existing System Intelligence and Adaptive Brain journals, and exposes a local
read-only snapshot for the dashboard.

This plane never grants production or execution authority.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Mapping
from urllib.request import Request, urlopen

from .brain import SUBSYSTEMS as BRAIN_SUBSYSTEMS, record_brain_event
from .system_audit import append_system_event

REMOTE_REPOSITORY = "reppiks490/Icarus"
REMOTE_REF = "main"
REMOTE_ROOT = "automation_intelligence/mcp_interface/events"
REMOTE_API = f"https://api.github.com/repos/{REMOTE_REPOSITORY}/contents/{REMOTE_ROOT}?ref={REMOTE_REF}"

SCHEMA_VERSION = "icarus-interface-event-v1"
# Bump whenever deterministic interface validation semantics change. Persisted
# rejected blobs are retried under a new validator revision while historical
# rejection identity remains deduplicated by Git blob SHA.
VALIDATOR_REVISION = "icarus-interface-validator-v2"
# Other receipt families intentionally share REMOTE_ROOT. They are not owned by
# EvolutionRemoteSync, but they are known repository contracts and should be
# skipped without degrading this interface-specific feed.
_IGNORED_SCHEMA_VERSIONS = {
    "icarus-mcp-event-v1",
    "icarus-apex-integration-receipt-v1",
}
_ALLOWED_CATEGORIES = {"REPAIR", "AUDIT", "EVOLUTION", "INTEGRATION", "FINDING"}
_ALLOWED_SEVERITIES = {"info", "success", "warn", "error"}
_ALLOWED_STATUSES = {
    "observed", "active", "staged", "verified", "qualified", "rejected",
    "blocked", "degraded", "retired", "unverified",
}
# Interface receipts are repository-native contracts shared by ICARUS and the
# subsystem repos that publish into automation_intelligence/mcp_interface/events.
# Reuse the Adaptive Brain's canonical subsystem registry instead of maintaining
# a second stale copy here. Research-facet tags are allowed separately because
# they describe evidence dimensions rather than standalone Brain subsystems.
_REGISTERED_SUBSYSTEMS = {
    str(row["id"]).strip().lower().replace("_", "-")
    for row in BRAIN_SUBSYSTEMS
}
_RESEARCH_FACET_SUBSYSTEMS = {
    "calibration",
    "cluster-bootstrap",
    "execution-research",
    "liquidity-load",
    "order-blocks",
    "prospective-validation",
    "research-validation",
    "tail-validation",
    "transfer-validation",
    "ui",
    "uncertainty",
}
_ALLOWED_SUBSYSTEMS = _REGISTERED_SUBSYSTEMS | _RESEARCH_FACET_SUBSYSTEMS


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _git_blob_sha(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw).hexdigest()


def git_blob_sha(raw: bytes) -> str:
    """Public Git-blob digest helper for repository-native event verification."""
    return _git_blob_sha(raw)


def _is_sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(
        c in "0123456789abcdef" for c in value.lower()
    )


def _state_path(base_dir: str | os.PathLike[str]) -> Path:
    return Path(base_dir) / "audit" / "mcp_evolution_sync.json"


def _default_state(interval_seconds: int) -> dict[str, Any]:
    return {
        "schema_version": "icarus-mcp-evolution-sync-v1",
        "validator_revision": VALIDATOR_REVISION,
        "enabled": True,
        "repository": REMOTE_REPOSITORY,
        "ref": REMOTE_REF,
        "root": REMOTE_ROOT,
        "interval_seconds": interval_seconds,
        "status": "not_started",
        "last_attempt_at": None,
        "last_success_at": None,
        "last_error": None,
        "ingested_total": 0,
        "ignored_total": 0,
        "rejected_total": 0,
        "current_rejected_count": 0,
        "processed_blob_shas": [],
        "rejected_blob_shas": [],
        "rejected_blob_errors": {},
        "rejected_history_blob_shas": [],
        "event_id_bindings": {},
        "events": [],
        "subsystems": {},
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def _read_state(base_dir: str | os.PathLike[str], interval_seconds: int) -> dict[str, Any]:
    state = _default_state(interval_seconds)
    path = _state_path(base_dir)
    if not path.is_file():
        return state
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state["status"] = "degraded"
        state["last_error"] = "local MCP evolution sync state is unreadable"
        return state
    if not isinstance(raw, dict):
        state["status"] = "degraded"
        state["last_error"] = "local MCP evolution sync state is not an object"
        return state
    if raw.get("execution_authorized") is not False or raw.get("production_decision_authorized") is not False:
        state["status"] = "degraded"
        state["last_error"] = "local MCP evolution sync state failed authority validation"
        return state
    state.update(raw)

    raw_current_rejected = raw.get("rejected_blob_shas")
    if not isinstance(raw_current_rejected, list):
        raw_current_rejected = []
    raw_rejected_history = raw.get("rejected_history_blob_shas")
    if not isinstance(raw_rejected_history, list):
        raw_rejected_history = []

    current_rejected = {
        str(x).lower()
        for x in raw_current_rejected
        if _is_sha(str(x).lower())
    }
    rejected_history = {
        str(x).lower()
        for x in raw_rejected_history
        if _is_sha(str(x).lower())
    }
    # Migration safety: any blob currently known rejected is historical too.
    rejected_history.update(current_rejected)
    state["rejected_history_blob_shas"] = sorted(rejected_history)[-5000:]

    if raw.get("validator_revision") != VALIDATOR_REVISION:
        state["rejected_blob_shas"] = []
        state["rejected_blob_errors"] = {}
        state["current_rejected_count"] = 0
    state["validator_revision"] = VALIDATOR_REVISION

    state["interval_seconds"] = interval_seconds
    state["execution_authorized"] = False
    state["production_decision_authorized"] = False
    return state


def _write_state(base_dir: str | os.PathLike[str], state: Mapping[str, Any]) -> None:
    path = _state_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(state)
    payload["execution_authorized"] = False
    payload["production_decision_authorized"] = False
    raw = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=".mcp-evolution-", delete=False) as fh:
        tmp = Path(fh.name)
        fh.write(raw)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _text(value: Any, limit: int, field: str) -> str:
    out = str(value or "").strip()
    if not out:
        raise ValueError(f"{field} is required")
    return out[:limit]


def _normalize_event(payload: Mapping[str, Any], *, remote_path: str, blob_sha: str) -> dict[str, Any]:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported MCP interface event schema")
    if payload.get("execution_authorized") is not False:
        raise ValueError("execution_authorized must be false")
    if payload.get("production_decision_authorized") is not False:
        raise ValueError("production_decision_authorized must be false")

    event_id = _text(payload.get("event_id"), 180, "event_id")
    category = _text(payload.get("category"), 32, "category").upper()
    if category not in _ALLOWED_CATEGORIES:
        raise ValueError("unsupported MCP interface event category")
    severity = str(payload.get("severity") or "info").strip().lower()
    if severity not in _ALLOWED_SEVERITIES:
        raise ValueError("unsupported MCP interface event severity")
    status = str(payload.get("status") or "observed").strip().lower()
    if status not in _ALLOWED_STATUSES:
        raise ValueError("unsupported MCP interface event status")

    raw_subsystems = payload.get("subsystems")
    if not isinstance(raw_subsystems, list) or not raw_subsystems:
        raise ValueError("subsystems must be a non-empty array")
    subsystems = []
    for raw in raw_subsystems:
        name = str(raw or "").strip().lower().replace("_", "-")
        if name not in _ALLOWED_SUBSYSTEMS:
            raise ValueError(f"unsupported subsystem {name!r}")
        if name not in subsystems:
            subsystems.append(name)

    source_repository = _text(payload.get("source_repository"), 180, "source_repository")
    source_ref = _text(payload.get("source_ref"), 240, "source_ref")
    source_commit = str(payload.get("source_commit") or "").strip().lower()
    if not _is_sha(source_commit):
        raise ValueError("source_commit must be a 40-character Git SHA")

    recorded_at = _text(payload.get("recorded_at"), 80, "recorded_at")
    try:
        recorded_dt = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
    except ValueError as ex:
        raise ValueError("recorded_at must be RFC3339/ISO-8601") from ex
    if recorded_dt.tzinfo is None or recorded_dt.utcoffset() is None:
        raise ValueError("recorded_at must include a timezone")
    title = _text(payload.get("title"), 220, "title")
    summary = _text(payload.get("summary"), 2400, "summary")

    evidence_raw = payload.get("evidence", [])
    if not isinstance(evidence_raw, list):
        raise ValueError("evidence must be an array")
    evidence = [str(x)[:700] for x in evidence_raw[:32] if str(x).strip()]

    return {
        "event_id": event_id,
        "category": category,
        "severity": severity,
        "status": status,
        "subsystems": subsystems,
        "recorded_at": recorded_at,
        "title": title,
        "summary": summary,
        "source_repository": source_repository,
        "source_ref": source_ref,
        "source_commit": source_commit,
        "evidence": evidence,
        "remote_repository": REMOTE_REPOSITORY,
        "remote_ref": REMOTE_REF,
        "remote_path": remote_path,
        "remote_blob_sha": blob_sha,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def normalize_interface_event(
    payload: Mapping[str, Any], *, source_path: str, blob_sha: str
) -> dict[str, Any]:
    """Public fail-closed validator shared by remote sync and local UI projection."""
    return _normalize_event(payload, remote_path=source_path, blob_sha=blob_sha)


_BRAIN_COMPATIBLE_STATUSES = {
    "observed", "active", "verified", "qualified", "rejected",
    "blocked", "degraded", "retired", "unverified",
}


def _brain_status(status: str) -> str:
    # Interface lifecycle is slightly richer than Adaptive Brain lifecycle.
    # Preserve the interface event's own status in the Evolution feed, but map
    # interface-only states (currently "staged") to a non-escalating brain
    # observation rather than causing ingestion failure.
    return status if status in _BRAIN_COMPATIBLE_STATUSES else "observed"


class EvolutionRemoteSync:
    """Poll immutable repository receipts into the local trader observability plane."""

    def __init__(
        self,
        base_dir: str | os.PathLike[str],
        *,
        interval_seconds: int | None = None,
        fetch_json: Callable[[str], Any] | None = None,
        fetch_bytes: Callable[[str], bytes] | None = None,
        enabled: bool | None = None,
    ):
        self.base_dir = Path(base_dir)
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
        raw_interval = interval_seconds if interval_seconds is not None else (60 if token else 300)
        self.interval_seconds = max(30, min(3600, int(raw_interval)))
        if enabled is None:
            enabled = str(os.environ.get("ICARUS_MCP_EVOLUTION_SYNC", "1")).strip().lower() not in {
                "0", "false", "off", "no",
            }
        self.enabled = bool(enabled)
        self._token = token
        self._fetch_json = fetch_json or self._default_fetch_json
        self._fetch_bytes = fetch_bytes or self._default_fetch_bytes
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def _request(self, url: str, accept: str) -> bytes:
        headers = {"Accept": accept, "User-Agent": "icarus-mcp-evolution-sync/1"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        req = Request(url, headers=headers)
        with urlopen(req, timeout=15) as resp:
            return resp.read()

    def _default_fetch_json(self, url: str) -> Any:
        return json.loads(self._request(url, "application/vnd.github+json").decode("utf-8"))

    def _default_fetch_bytes(self, url: str) -> bytes:
        return self._request(url, "application/vnd.github.raw+json")

    def status(self) -> dict[str, Any]:
        state = _read_state(self.base_dir, self.interval_seconds)
        state.pop("processed_blob_shas", None)
        state.pop("rejected_blob_shas", None)
        state.pop("rejected_blob_errors", None)
        state.pop("rejected_history_blob_shas", None)
        state.pop("event_id_bindings", None)
        return state

    def sync_once(self) -> dict[str, Any]:
        with self._lock:
            state = _read_state(self.base_dir, self.interval_seconds)
            state["enabled"] = self.enabled
            state["last_attempt_at"] = _utc_now()
            state["status"] = "syncing"
            state["last_error"] = None
            if not self.enabled:
                state["status"] = "disabled"
                _write_state(self.base_dir, state)
                return self.status()

            try:
                listing = self._fetch_json(REMOTE_API)
                if not isinstance(listing, list):
                    raise ValueError("GitHub MCP interface event listing is not an array")
            except Exception as ex:
                state["status"] = "degraded"
                state["last_error"] = f"{type(ex).__name__}: {ex}"[:1000]
                _write_state(self.base_dir, state)
                return self.status()

            processed = {
                str(x).lower()
                for x in state.get("processed_blob_shas", [])
                if _is_sha(x)
            }
            rejected = {
                str(x).lower()
                for x in state.get("rejected_blob_shas", [])
                if _is_sha(x)
            }
            rejected_history = {
                str(x).lower()
                for x in state.get("rejected_history_blob_shas", [])
                if _is_sha(x)
            }
            raw_rejected_errors = state.get("rejected_blob_errors")
            if not isinstance(raw_rejected_errors, Mapping):
                raw_rejected_errors = {}
            rejected_errors = {
                str(sha).lower(): str(message)
                for sha, message in raw_rejected_errors.items()
                if _is_sha(str(sha).lower())
            }
            events_by_id = {
                str(x.get("event_id")): x
                for x in state.get("events", [])
                if isinstance(x, dict) and x.get("event_id")
            }
            raw_bindings = state.get("event_id_bindings")
            if not isinstance(raw_bindings, Mapping):
                raw_bindings = {}
            event_id_bindings = {
                str(event_id): str(bound_sha).lower()
                for event_id, bound_sha in raw_bindings.items()
                if str(event_id).strip()
                and _is_sha(str(bound_sha).lower())
            }
            # Backfill bindings from visible legacy state during rollout.
            for event_id, prior in events_by_id.items():
                prior_sha = (
                    str(prior.get("remote_blob_sha") or "").lower()
                    if isinstance(prior, Mapping)
                    else ""
                )
                if _is_sha(prior_sha):
                    event_id_bindings.setdefault(event_id, prior_sha)
            subsystems = dict(state.get("subsystems") or {})
            errors: list[str] = []

            entries = []
            for item in listing[:1000]:
                if not isinstance(item, Mapping):
                    continue
                name = item.get("name")
                path = item.get("path")
                sha = str(item.get("sha") or "").lower()
                if (
                    item.get("type") == "file"
                    and isinstance(name, str)
                    and name.endswith(".json")
                    and isinstance(path, str)
                    and path.startswith(REMOTE_ROOT + "/")
                    and _is_sha(sha)
                ):
                    entries.append((name, path, sha, str(item.get("url") or "")))
            entries.sort(key=lambda x: x[0])
            current_blob_shas = {entry[2] for entry in entries}
            rejected.intersection_update(current_blob_shas)
            rejected_errors = {
                sha: message
                for sha, message in rejected_errors.items()
                if sha in rejected
            }

            for _name, path, blob_sha, url in entries:
                if blob_sha in processed:
                    continue
                if blob_sha in rejected:
                    errors.append(
                        rejected_errors.get(
                            blob_sha,
                            f"{path}: previously rejected receipt version",
                        )
                    )
                    continue

                # Transport/integrity failures are retryable. They do not prove
                # the immutable receipt content is invalid and must never make
                # a blob permanently rejected.
                try:
                    if not url:
                        raise ValueError("missing GitHub contents URL")
                    raw = self._fetch_bytes(url)
                    if _git_blob_sha(raw) != blob_sha:
                        raise ValueError("Git blob SHA mismatch")
                except Exception as ex:
                    errors.append(
                        f"{path}: fetch/integrity {type(ex).__name__}: {ex}"
                    )
                    continue

                # Once Git content identity is proven, deterministic decoding or
                # contract failures belong to this immutable blob version and
                # can be deduplicated safely across later polls.
                try:
                    payload = json.loads(raw.decode("utf-8"))
                    if not isinstance(payload, Mapping):
                        raise ValueError("event payload is not an object")
                    # This repository directory intentionally carries several
                    # event families. The Evolution sync owns only
                    # icarus-interface-event-v1. Known foreign receipt schemas
                    # are ignored, while missing/unknown declarations still
                    # fail closed as contract errors.
                    declared_schema = payload.get("schema_version")
                    if declared_schema is None:
                        declared_schema = payload.get("schema")
                    if declared_schema == SCHEMA_VERSION:
                        event = _normalize_event(
                            payload,
                            remote_path=path,
                            blob_sha=blob_sha,
                        )
                        bound_sha = event_id_bindings.get(
                            event["event_id"]
                        )
                        if bound_sha is not None and bound_sha != blob_sha:
                            raise ValueError(
                                "event_id is already bound to a different "
                                "immutable Git blob"
                            )
                    elif declared_schema in _IGNORED_SCHEMA_VERSIONS:
                        processed.add(blob_sha)
                        state["ignored_total"] = int(
                            state.get("ignored_total", 0)
                        ) + 1
                        continue
                    else:
                        raise ValueError(
                            "unsupported MCP event schema declaration"
                        )
                except (
                    UnicodeDecodeError,
                    json.JSONDecodeError,
                    TypeError,
                    ValueError,
                ) as ex:
                    message = f"{path}: {type(ex).__name__}: {ex}"
                    errors.append(message)
                    rejected.add(blob_sha)
                    rejected_errors[blob_sha] = message
                    if blob_sha not in rejected_history:
                        rejected_history.add(blob_sha)
                        state["rejected_total"] = int(
                            state.get("rejected_total", 0)
                        ) + 1
                    continue
                except Exception as ex:
                    errors.append(
                        f"{path}: validation {type(ex).__name__}: {ex}"
                    )
                    continue

                # Local projection is also retryable. A disk/journal failure
                # must not convert otherwise valid source bytes into a
                # permanently rejected receipt version.
                try:
                    append_system_event(
                        self.base_dir,
                        {
                            "id": f"mcp:{event['event_id']}",
                            "kind": event["category"].lower(),
                            "severity": event["severity"],
                            "title": event["title"],
                            "detail": event["summary"],
                            "recorded_at": event["recorded_at"],
                            "repository": event["source_repository"],
                            "ref": event["source_commit"] or event["source_ref"],
                        },
                    )

                    evidence = [
                        f"remote_repository:{REMOTE_REPOSITORY}",
                        f"remote_path:{path}",
                        f"git_blob_sha:{blob_sha}",
                        f"source_repository:{event['source_repository']}",
                        f"source_ref:{event['source_ref']}",
                        *event["evidence"],
                    ][:32]
                    projected_subsystems: dict[str, dict[str, Any]] = {}
                    for subsystem in event["subsystems"]:
                        record_brain_event(
                            self.base_dir,
                            {
                                "kind": "subsystem",
                                "subject": subsystem,
                                "summary": event["summary"],
                                "status": _brain_status(event["status"]),
                                "evidence": evidence,
                                "details": {
                                    "category": event["category"],
                                    "severity": event["severity"],
                                    "event_id": event["event_id"],
                                    "source_repository": event["source_repository"],
                                    "source_ref": event["source_ref"],
                                    "source_commit": event["source_commit"],
                                    "remote_path": path,
                                    "remote_blob_sha": blob_sha,
                                },
                            },
                        )
                        projected_subsystems[subsystem] = {
                            "status": event["status"],
                            "severity": event["severity"],
                            "title": event["title"],
                            "summary": event["summary"],
                            "recorded_at": event["recorded_at"],
                            "source_repository": event["source_repository"],
                            "source_ref": event["source_ref"],
                            "source_commit": event["source_commit"],
                            "event_id": event["event_id"],
                        }
                except Exception as ex:
                    errors.append(
                        f"{path}: projection {type(ex).__name__}: {ex}"
                    )
                    continue

                subsystems.update(projected_subsystems)
                events_by_id[event["event_id"]] = event
                event_id_bindings[event["event_id"]] = blob_sha
                processed.add(blob_sha)
                state["ingested_total"] = int(
                    state.get("ingested_total", 0)
                ) + 1

            ordered = sorted(
                events_by_id.values(),
                key=lambda x: (str(x.get("recorded_at") or ""), str(x.get("event_id") or "")),
                reverse=True,
            )[:200]
            state["processed_blob_shas"] = sorted(processed)[-5000:]
            state["rejected_blob_shas"] = sorted(rejected)[-5000:]
            state["rejected_blob_errors"] = {
                sha: rejected_errors[sha]
                for sha in state["rejected_blob_shas"]
                if sha in rejected_errors
            }
            state["rejected_history_blob_shas"] = sorted(
                rejected_history
            )[-5000:]
            state["current_rejected_count"] = len(
                state["rejected_blob_shas"]
            )
            state["event_id_bindings"] = event_id_bindings
            state["events"] = ordered
            state["subsystems"] = subsystems
            state["last_error"] = " | ".join(errors[-10:])[:3000] if errors else None
            state["status"] = "degraded" if errors else "green"
            if not errors:
                state["last_success_at"] = _utc_now()
            _write_state(self.base_dir, state)
            return self.status()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.sync_once()
            except Exception:
                pass
            self._stop.wait(self.interval_seconds)

    def start(self) -> None:
        if not self.enabled or (self._thread and self._thread.is_alive()):
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="icarus-mcp-evolution-sync",
            daemon=True,
        )
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=2.0)
