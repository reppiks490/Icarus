"""Verified GitHub -> ICARUS federation sync for the Advanced CSV evidence lane.

The CSV Evidence Lab is an independent research repository. This synchronizer
does not import raw owner data or promote CSV artifacts. It mirrors only the
lane's repository-native status/evidence receipts, verifies each Git blob, and
keeps durability separate from substantive evidence.
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

from .brain import record_brain_event

REMOTE_REPOSITORY = "reppiks490/icarus-csv-evidence-lab"
REMOTE_REF = "main"
REMOTE_ROOT = "automation_intelligence/advanced_csv"
_REMOTE_API = f"https://api.github.com/repos/{REMOTE_REPOSITORY}/contents/{REMOTE_ROOT}?ref={REMOTE_REF}"
_REQUIRED_FILES = ("evidence_state.json", "heartbeat.json", "latest.json", "finalization_state.json")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _is_sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(c in "0123456789abcdef" for c in value.lower())


def _state_path(base_dir: str | os.PathLike[str]) -> Path:
    return Path(base_dir) / "audit" / "evidence_lab_sync.json"


def _default_state(interval_seconds: int) -> dict[str, Any]:
    return {
        "schema_version": "icarus-evidence-lab-sync-v1",
        "enabled": True,
        "repository": REMOTE_REPOSITORY,
        "ref": REMOTE_REF,
        "root": REMOTE_ROOT,
        "interval_seconds": interval_seconds,
        "status": "not_started",
        "last_attempt_at": None,
        "last_success_at": None,
        "last_error": None,
        "scheduler_id": None,
        "current_run_id": None,
        "run_status": None,
        "evidence_run_id": None,
        "evidence_status": None,
        "latest_run_id": None,
        "finalization_status": None,
        "latest_pointer_matches_heartbeat": None,
        "evidence_pointer_matches_heartbeat": None,
        "remote_blobs": {},
        "truth_contract": {
            "run_persisted_is_substantive_evidence": False,
            "evidence_authority": "evidence_state.EVIDENCE_STATUS",
            "raw_owner_data_imported": False,
            "automatic_model_promotion": False,
        },
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
        state["last_error"] = "local evidence-lab sync state is unreadable"
        return state
    if not isinstance(raw, dict) or raw.get("execution_authorized") is not False:
        state["status"] = "degraded"
        state["last_error"] = "local evidence-lab sync state failed authority validation"
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
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=".evidence-lab-", delete=False) as fh:
        tmp = Path(fh.name)
        fh.write(raw)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _normalize_snapshot(documents: Mapping[str, Mapping[str, Any]], blobs: Mapping[str, str]) -> dict[str, Any]:
    evidence = documents["evidence_state.json"]
    heartbeat = documents["heartbeat.json"]
    latest = documents["latest.json"]
    finalization = documents["finalization_state.json"]

    for name, payload in documents.items():
        if payload.get("execution_authorized") is not False:
            raise ValueError(f"{name} does not explicitly preserve execution_authorized=false")

    scheduler_ids = {
        str(payload.get("scheduler_id") or "").strip()
        for payload in (evidence, heartbeat, latest, finalization)
        if str(payload.get("scheduler_id") or "").strip()
    }
    if len(scheduler_ids) > 1:
        raise ValueError("advanced CSV federation receipts disagree on scheduler_id")
    scheduler_id = next(iter(scheduler_ids), None)

    current_run = str(heartbeat.get("RUN_ID") or "").strip() or None
    evidence_run = str(evidence.get("RUN_ID") or "").strip() or None
    latest_run = str(latest.get("RUN_ID") or "").strip() or None
    run_status = str(heartbeat.get("RUN_STATUS") or "").strip() or None
    evidence_status = str(evidence.get("EVIDENCE_STATUS") or "").strip() or None
    finalization_status = (
        str(finalization.get("FINALIZATION_STATUS") or finalization.get("status") or "").strip() or None
    )

    latest_matches = (latest_run == current_run) if (latest_run and current_run) else None
    evidence_matches = (evidence_run == current_run) if (evidence_run and current_run) else None

    return {
        "scheduler_id": scheduler_id,
        "current_run_id": current_run,
        "run_status": run_status,
        "evidence_run_id": evidence_run,
        "evidence_status": evidence_status,
        "latest_run_id": latest_run,
        "finalization_status": finalization_status,
        "latest_pointer_matches_heartbeat": latest_matches,
        "evidence_pointer_matches_heartbeat": evidence_matches,
        "remote_blobs": dict(blobs),
        "truth_contract": {
            "run_persisted_is_substantive_evidence": False,
            "evidence_authority": "evidence_state.EVIDENCE_STATUS",
            "raw_owner_data_imported": False,
            "automatic_model_promotion": False,
        },
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


class EvidenceLabRemoteSync:
    """Mirror the active Advanced CSV lane into ICARUS observability only."""

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
        headers = {"Accept": accept, "User-Agent": "icarus-evidence-lab-sync/1"}
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
        return _read_state(self.base_dir, self.interval_seconds)

    def sync_once(self) -> dict[str, Any]:
        with self._lock:
            state = _read_state(self.base_dir, self.interval_seconds)
            previous_run = state.get("current_run_id")
            state["last_attempt_at"] = _utc_now()
            state["status"] = "syncing"
            state["last_error"] = None
            try:
                listing = self._fetch_json(_REMOTE_API)
                if not isinstance(listing, list):
                    raise ValueError("GitHub Advanced CSV directory response is not a list")
                by_name = {
                    str(item.get("name")): item
                    for item in listing
                    if isinstance(item, Mapping) and item.get("type") == "file"
                }
                missing = [name for name in _REQUIRED_FILES if name not in by_name]
                if missing:
                    raise ValueError("missing required federation receipts: " + ", ".join(missing))

                documents: dict[str, Mapping[str, Any]] = {}
                blobs: dict[str, str] = {}
                for name in _REQUIRED_FILES:
                    item = by_name[name]
                    blob_sha = str(item.get("sha") or "").lower()
                    url = str(item.get("url") or "")
                    if not _is_sha(blob_sha) or not url:
                        raise ValueError(f"{name} has invalid GitHub blob metadata")
                    raw = self._fetch_bytes(url)
                    if _git_blob_sha(raw) != blob_sha:
                        raise ValueError(f"{name} Git blob SHA mismatch")
                    payload = json.loads(raw.decode("utf-8"))
                    if not isinstance(payload, Mapping):
                        raise ValueError(f"{name} payload is not an object")
                    documents[name] = payload
                    blobs[name] = blob_sha

                normalized = _normalize_snapshot(documents, blobs)
                state.update(normalized)
                state["last_success_at"] = _utc_now()

                pointer_warnings = []
                if normalized["latest_pointer_matches_heartbeat"] is False:
                    pointer_warnings.append("latest.json does not match heartbeat RUN_ID")
                if normalized["evidence_pointer_matches_heartbeat"] is False:
                    pointer_warnings.append("evidence_state RUN_ID does not match heartbeat RUN_ID")
                state["status"] = "degraded" if pointer_warnings else "green"
                state["last_error"] = " | ".join(pointer_warnings) if pointer_warnings else None

                current_run = normalized.get("current_run_id")
                if current_run and current_run != previous_run:
                    record_brain_event(
                        self.base_dir,
                        {
                            "kind": "subsystem",
                            "subject": "csv-evidence-lab",
                            "summary": (
                                f"Advanced CSV federation observed {current_run}: "
                                f"{normalized.get('run_status') or 'UNKNOWN'}; "
                                f"evidence={normalized.get('evidence_status') or 'UNKNOWN'}."
                            ),
                            "status": "active" if normalized.get("run_status") == "RUN_PERSISTED" else "observed",
                            "evidence": [
                                f"remote_repository:{REMOTE_REPOSITORY}",
                                f"heartbeat_blob:{blobs['heartbeat.json']}",
                                f"evidence_state_blob:{blobs['evidence_state.json']}",
                                f"latest_blob:{blobs['latest.json']}",
                                f"finalization_blob:{blobs['finalization_state.json']}",
                            ],
                            "details": {
                                **normalized,
                                "rule": "RUN_PERSISTED is durability only; substantive evidence authority remains evidence_state.EVIDENCE_STATUS.",
                            },
                        },
                    )
            except Exception as ex:
                state["status"] = "degraded"
                state["last_error"] = f"{type(ex).__name__}: {ex}"[:1200]

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
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="icarus-evidence-lab-sync",
            daemon=True,
        )
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=2.0)
