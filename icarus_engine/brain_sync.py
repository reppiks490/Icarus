"""Verified GitHub -> Adaptive Brain ingest for the five custom ICARUS agents.

Cloud automations cannot directly reach the operator's localhost engine. They persist
material results as immutable repository-native MCP events. This background sync
pulls those events into the local Adaptive Brain journal with Git-blob verification,
source allowlisting, idempotence, and no authority escalation.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Mapping
from urllib.request import Request, urlopen

from .brain import record_brain_event

REMOTE_REPOSITORY = "reppiks490/Icarus-engine"
REMOTE_REF = "main"
REMOTE_ROOT = "automation_intelligence/mcp_interface/events"
_REMOTE_API = f"https://api.github.com/repos/{REMOTE_REPOSITORY}/contents/{REMOTE_ROOT}?ref={REMOTE_REF}"

SOURCE_TO_AGENT = {
    "OMEGA_AUTOMATION": "omega",
    "MACRO_AUTOMATION": "macro",
    "FLOW_AUTOMATION": "flow",
    "AION_AUTOMATION": "aion",
    "DAEDALUS_AUTOMATION": "daedalus",
}

_SUBSYSTEM_ALIASES = {
    "aegis": "aegis",
    "aion": "aion",
    "argus": "argus",
    "ascension": "ascension",
    "athena": "athena",
    "daedalus": "daedalus",
    "helios": "helios-prime",
    "helios_prime": "helios-prime",
    "infrastructure": "infrastructure",
    "janus": "janus",
    "nexus": "nexus",
    "oracle": "oracle",
    "prometheus": "prometheus",
    "supermesh_x": "supermesh-x",
    "supermesh-x": "supermesh-x",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _is_sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(c in "0123456789abcdef" for c in value.lower())


def _state_path(base_dir: str | os.PathLike[str]) -> Path:
    return Path(base_dir) / "audit" / "brain_remote_sync.json"


def _default_state(interval_seconds: int) -> dict[str, Any]:
    return {
        "schema_version": "icarus-brain-remote-sync-v1",
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
        "last_ingested": [],
        "processed_blob_shas": [],
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def _read_state(base_dir: str | os.PathLike[str], interval_seconds: int) -> dict[str, Any]:
    path = _state_path(base_dir)
    state = _default_state(interval_seconds)
    if not path.is_file():
        return state
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state["status"] = "degraded"
        state["last_error"] = "local sync state is unreadable; remote events will be safely replayed idempotently"
        return state
    if not isinstance(raw, dict) or raw.get("execution_authorized") is not False:
        state["status"] = "degraded"
        state["last_error"] = "local sync state failed authority validation"
        return state
    state.update(raw)
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
    raw = json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n"
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=".brain-sync-", delete=False) as fh:
        tmp = Path(fh.name)
        fh.write(raw)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _compact_evidence(payload: Mapping[str, Any], path: str, blob_sha: str) -> list[str]:
    out = [
        f"remote_repository:{REMOTE_REPOSITORY}",
        f"remote_path:{path}",
        f"git_blob_sha:{blob_sha}",
        f"source:{payload.get('source', '')}",
        f"category:{payload.get('category', '')}",
    ]
    evidence = payload.get("evidence")
    if isinstance(evidence, Mapping):
        for key, value in list(evidence.items())[:16]:
            out.append(f"{key}:{str(value)[:620]}")
    elif isinstance(evidence, list):
        for value in evidence[:16]:
            out.append(str(value)[:680])
    elif isinstance(evidence, str) and evidence.strip():
        out.append(evidence[:680])
    return out[:32]


def _event_details(payload: Mapping[str, Any], path: str, blob_sha: str) -> dict[str, Any]:
    keep = (
        "category",
        "event_time_utc",
        "retrieval_time_utc",
        "at_utc",
        "status",
        "severity",
        "surface",
        "regime_implication",
        "next_decisive_check",
        "data_gaps",
        "conflicts",
        "paths",
        "persistence_authority",
    )
    details = {key: payload[key] for key in keep if key in payload}
    details.update(
        {
            "remote_repository": REMOTE_REPOSITORY,
            "remote_ref": REMOTE_REF,
            "remote_path": path,
            "remote_blob_sha": blob_sha,
        }
    )
    return details


def _summary(payload: Mapping[str, Any]) -> str:
    for key in ("net_new_delta", "summary", "finding", "detail"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:2200]
    return "Verified custom-agent repository event ingested; no summary field was supplied."


def _normalize_status(value: Any) -> str:
    status = str(value or "observed").strip().lower()
    aliases = {
        "implemented": "verified",
        "useful": "observed",
        "run_persisted": "active",
        "no_material_delta": "observed",
        "warning": "degraded",
        "error": "blocked",
    }
    status = aliases.get(status, status)
    allowed = {"observed", "active", "verified", "qualified", "rejected", "blocked", "degraded", "retired", "unverified"}
    return status if status in allowed else "observed"


class BrainRemoteSync:
    """Poll repository-native custom-agent events into the local brain journal."""

    def __init__(
        self,
        base_dir: str | os.PathLike[str],
        *,
        interval_seconds: int | None = None,
        fetch_json: Callable[[str], Any] | None = None,
        fetch_bytes: Callable[[str], bytes] | None = None,
    ):
        self.base_dir = Path(base_dir)
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
        self.interval_seconds = int(interval_seconds or (60 if token else 300))
        self.interval_seconds = max(30, min(3600, self.interval_seconds))
        self._token = token
        self._fetch_json = fetch_json or self._default_fetch_json
        self._fetch_bytes = fetch_bytes or self._default_fetch_bytes
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def _request(self, url: str, accept: str) -> bytes:
        headers = {
            "Accept": accept,
            "User-Agent": "icarus-adaptive-brain-sync/1",
        }
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
        return state

    def _record_subsystems(
        self,
        payload: Mapping[str, Any],
        evidence: list[str],
        details: Mapping[str, Any],
    ) -> int:
        count = 0
        for key, subsystem_id in _SUBSYSTEM_ALIASES.items():
            value = payload.get(key)
            if not isinstance(value, Mapping):
                continue
            finding = value.get("finding") or value.get("summary") or value.get("detail")
            if not isinstance(finding, str) or not finding.strip():
                continue
            record_brain_event(
                self.base_dir,
                {
                    "kind": "subsystem",
                    "subject": subsystem_id,
                    "summary": finding.strip()[:2200],
                    "status": _normalize_status(value.get("status")),
                    "evidence": evidence,
                    "details": {
                        **dict(details),
                        "reported_subsystem": subsystem_id,
                        "remote_subsystem_status": value.get("status"),
                    },
                },
            )
            count += 1
        return count

    def sync_once(self) -> dict[str, Any]:
        with self._lock:
            state = _read_state(self.base_dir, self.interval_seconds)
            state["last_attempt_at"] = _utc_now()
            state["status"] = "syncing"
            state["last_error"] = None
            errors: list[str] = []
            ingested_paths: list[str] = []

            try:
                listing = self._fetch_json(_REMOTE_API)
                if not isinstance(listing, list):
                    raise ValueError("GitHub event directory response is not a list")
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

            for _name, path, blob_sha, url in entries:
                if blob_sha in processed:
                    continue
                if not url:
                    errors.append(f"{path}: missing GitHub contents URL")
                    continue
                try:
                    raw = self._fetch_bytes(url)
                    if _git_blob_sha(raw) != blob_sha:
                        raise ValueError("Git blob SHA mismatch")
                    payload = json.loads(raw.decode("utf-8"))
                    if not isinstance(payload, Mapping):
                        raise ValueError("event payload is not an object")
                    if payload.get("execution_authorized") is not False:
                        raise ValueError("event does not explicitly preserve execution_authorized=false")

                    source = str(payload.get("source") or "").strip().upper()
                    agent_id = SOURCE_TO_AGENT.get(source)
                    if agent_id is None:
                        state["ignored_total"] = int(state.get("ignored_total", 0)) + 1
                        processed.add(blob_sha)
                        continue

                    schema = payload.get("schema_version", payload.get("schema"))
                    if schema != "icarus-mcp-event-v1":
                        raise ValueError("unsupported custom-agent event schema")
                    category = str(payload.get("category") or "").strip().upper()
                    if category not in {"REPAIR", "AUDIT", "EVOLUTION", "INTEGRATION"}:
                        raise ValueError("unsupported custom-agent event category")

                    evidence = _compact_evidence(payload, path, blob_sha)
                    details = _event_details(payload, path, blob_sha)
                    record_brain_event(
                        self.base_dir,
                        {
                            "kind": "agent",
                            "subject": agent_id,
                            "summary": _summary(payload),
                            "status": _normalize_status(payload.get("status")),
                            "evidence": evidence,
                            "details": details,
                        },
                    )
                    self._record_subsystems(payload, evidence, details)
                    processed.add(blob_sha)
                    state["ingested_total"] = int(state.get("ingested_total", 0)) + 1
                    ingested_paths.append(path)
                except Exception as ex:
                    errors.append(f"{path}: {type(ex).__name__}: {ex}")
                    state["rejected_total"] = int(state.get("rejected_total", 0)) + 1

            state["processed_blob_shas"] = sorted(processed)[-5000:]
            state["last_ingested"] = ingested_paths[-20:]
            state["last_success_at"] = _utc_now()
            state["last_error"] = " | ".join(errors[-10:])[:3000] if errors else None
            state["status"] = "degraded" if errors else "green"
            _write_state(self.base_dir, state)
            return self.status()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.sync_once()
            except Exception:
                # The trader engine must never crash because the optional remote
                # intelligence plane is unavailable.
                pass
            self._stop.wait(self.interval_seconds)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="icarus-adaptive-brain-remote-sync",
            daemon=True,
        )
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=2.0)
