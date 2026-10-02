"""Verified Icarus-engine -> canonical ICARUS Adaptive Brain federation.

This consumer mirrors repository-native MCP/Automation event records from the
peer Icarus-engine repository.  It verifies Git blob identity, enforces the
producer and consumer contracts, and records accepted events as research-only
Adaptive Brain evidence.

The federation never imports raw owner data, never promotes a model, and never
transfers execution or production-decision authority.
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

REMOTE_REPOSITORY = "reppiks490/Icarus-engine"
REMOTE_REF = "main"
REMOTE_ROOT = "automation_intelligence/mcp_interface"
PRODUCER_CONTRACT_PATH = f"{REMOTE_ROOT}/contract.json"
CONSUMER_CONTRACT_PATH = f"{REMOTE_ROOT}/icarus_consumer_contract.json"
EVENT_ROOT = f"{REMOTE_ROOT}/events"

_REPO_API = f"https://api.github.com/repos/{REMOTE_REPOSITORY}/contents"
_PRODUCER_API = f"{_REPO_API}/{PRODUCER_CONTRACT_PATH}?ref={REMOTE_REF}"
_CONSUMER_API = f"{_REPO_API}/{CONSUMER_CONTRACT_PATH}?ref={REMOTE_REF}"
_EVENTS_API = f"{_REPO_API}/{EVENT_ROOT}?ref={REMOTE_REF}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _is_sha(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(c in "0123456789abcdef" for c in value.lower())
    )


def _state_path(base_dir: str | os.PathLike[str]) -> Path:
    return Path(base_dir) / "audit" / "engine_federation_sync.json"


def _default_state(interval_seconds: int) -> dict[str, Any]:
    return {
        "schema_version": "icarus-engine-federation-sync-v1",
        "enabled": True,
        "repository": REMOTE_REPOSITORY,
        "ref": REMOTE_REF,
        "event_root": EVENT_ROOT,
        "interval_seconds": interval_seconds,
        "status": "not_started",
        "last_attempt_at": None,
        "last_success_at": None,
        "last_error": None,
        "event_count": 0,
        "accepted_event_count": 0,
        "latest_event_id": None,
        "latest_event_at": None,
        "producer_contract_blob": None,
        "consumer_contract_blob": None,
        "event_blobs": {},
        "seen_event_blobs": [],
        "truth_contract": {
            "federation_schema": None,
            "event_records_are_research_observability_only": True,
            "durability_receipts_are_substantive_evidence": False,
            "raw_owner_data_imported": False,
            "automatic_model_promotion": False,
            "automatic_execution_authority": False,
            "production_decision_authorized": False,
        },
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def _read_state(
    base_dir: str | os.PathLike[str], interval_seconds: int
) -> dict[str, Any]:
    state = _default_state(interval_seconds)
    path = _state_path(base_dir)
    if not path.is_file():
        return state
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state["status"] = "degraded"
        state["last_error"] = "local engine federation state is unreadable"
        return state
    if not isinstance(raw, dict):
        state["status"] = "degraded"
        state["last_error"] = "local engine federation state is not an object"
        return state
    if (
        raw.get("execution_authorized") is not False
        or raw.get("production_decision_authorized") is not False
    ):
        state["status"] = "degraded"
        state["last_error"] = "local engine federation state failed authority validation"
        return state
    state.update(raw)
    state["interval_seconds"] = interval_seconds
    state["execution_authorized"] = False
    state["production_decision_authorized"] = False
    return state


def _write_state(
    base_dir: str | os.PathLike[str], state: Mapping[str, Any]
) -> None:
    path = _state_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(state)
    payload["execution_authorized"] = False
    payload["production_decision_authorized"] = False
    raw = json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n"
    with NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=".engine-federation-",
        delete=False,
    ) as fh:
        tmp = Path(fh.name)
        fh.write(raw)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _normalize_contracts(
    producer: Mapping[str, Any],
    consumer: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(producer, Mapping) or not isinstance(consumer, Mapping):
        raise ValueError("federation contracts must be objects")

    if producer.get("schema_version") != "icarus-mcp-interface-contract-v1":
        raise ValueError("unsupported Icarus-engine producer contract")
    if producer.get("event_schema") != "icarus-mcp-event-v1":
        raise ValueError("unsupported producer event schema")
    if producer.get("event_root") != EVENT_ROOT:
        raise ValueError("producer event_root mismatch")
    if producer.get("trading_execution_authorized") is not False:
        raise ValueError("producer contract attempts authority escalation")

    if consumer.get("schema_version") != "icarus-engine-brain-federation-v1":
        raise ValueError("unsupported Icarus-engine Brain federation contract")
    if consumer.get("producer_repository") != REMOTE_REPOSITORY:
        raise ValueError("federation producer repository mismatch")
    if consumer.get("producer_ref") != REMOTE_REF:
        raise ValueError("federation producer ref mismatch")
    if consumer.get("consumer_repository") != "reppiks490/Icarus":
        raise ValueError("federation consumer repository mismatch")
    if consumer.get("producer_contract") != PRODUCER_CONTRACT_PATH:
        raise ValueError("federation producer contract path mismatch")
    if (
        consumer.get("producer_contract_schema")
        != producer.get("schema_version")
    ):
        raise ValueError("federation producer contract schema mismatch")
    if consumer.get("event_root") != producer.get("event_root"):
        raise ValueError("federation event_root mismatch")
    if consumer.get("event_schema") != producer.get("event_schema"):
        raise ValueError("federation event schema mismatch")
    if (
        consumer.get("execution_authorized") is not False
        or consumer.get("production_decision_authorized") is not False
    ):
        raise ValueError("consumer contract attempts authority escalation")

    semantics = consumer.get("semantics")
    if not isinstance(semantics, Mapping):
        raise ValueError("federation semantics are missing")
    if semantics.get("event_records") != "RESEARCH_OBSERVABILITY_ONLY":
        raise ValueError("federation event semantics are not research-only")
    false_semantics = (
        "durability_receipts_are_substantive_evidence",
        "remote_status_is_production_decision",
        "raw_owner_data_transfer",
        "automatic_model_promotion",
        "production_decision_authorized",
        "automatic_execution_authority",
    )
    if any(semantics.get(key) is not False for key in false_semantics):
        raise ValueError("federation semantics attempt authority or evidence escalation")

    required_fields = producer.get("required_fields")
    if not isinstance(required_fields, list) or not required_fields:
        raise ValueError("producer required_fields are missing")
    required_fields = [str(x) for x in required_fields]

    producer_categories = {
        str(x).strip().upper()
        for x in (producer.get("required_categories") or [])
        if str(x).strip()
    }
    accepted_categories = {
        str(x).strip().upper()
        for x in (consumer.get("accepted_categories") or [])
        if str(x).strip()
    }
    if not accepted_categories or not accepted_categories.issubset(producer_categories):
        raise ValueError("consumer accepted categories exceed producer contract")

    accepted_sources = sorted({
        str(x).strip().upper()
        for x in (consumer.get("accepted_sources") or [])
        if str(x).strip()
    })
    if not accepted_sources:
        raise ValueError("consumer accepted_sources are missing")

    validation = consumer.get("event_validation")
    if not isinstance(validation, Mapping):
        raise ValueError("federation event_validation is missing")
    if (
        validation.get("required_fields_source")
        != f"{PRODUCER_CONTRACT_PATH}#required_fields"
    ):
        raise ValueError("federation required_fields source mismatch")
    if validation.get("strict_v1_required_fields") is not True:
        raise ValueError("federation must strictly enforce v1 required fields")

    legacy = validation.get("legacy_relaxed_blob_shas")
    if not isinstance(legacy, list):
        raise ValueError("legacy_relaxed_blob_shas must be a list")
    legacy_shas = [str(x).lower() for x in legacy]
    if len(legacy_shas) != len(set(legacy_shas)) or not all(
        _is_sha(x) for x in legacy_shas
    ):
        raise ValueError("legacy federation blob exceptions must be unique Git SHAs")
    legacy_rule = str(validation.get("legacy_rule") or "")
    if "No future blob inherits this exception" not in legacy_rule:
        raise ValueError("legacy federation exception rule is not fail-closed")

    return {
        "producer_repository": REMOTE_REPOSITORY,
        "producer_ref": REMOTE_REF,
        "consumer_repository": "reppiks490/Icarus",
        "producer_contract_schema": producer["schema_version"],
        "event_root": EVENT_ROOT,
        "event_schema": producer["event_schema"],
        "required_fields": required_fields,
        "accepted_sources": accepted_sources,
        "accepted_categories": sorted(accepted_categories),
        "legacy_relaxed_blob_shas": sorted(legacy_shas),
        "truth_contract": {
            "event_records_are_research_observability_only": True,
            "durability_receipts_are_substantive_evidence": False,
            "remote_status_is_production_decision": False,
            "raw_owner_data_imported": False,
            "automatic_model_promotion": False,
            "automatic_execution_authority": False,
            "production_decision_authorized": False,
        },
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def _normalize_event(
    event: Mapping[str, Any],
    blob_sha: str,
    contracts: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(event, Mapping):
        raise ValueError("federated event must be an object")
    sha = str(blob_sha).lower()
    if not _is_sha(sha):
        raise ValueError("federated event blob SHA is invalid")

    schema = event.get("schema_version", event.get("schema"))
    if schema != contracts.get("event_schema"):
        raise ValueError("federated event schema mismatch")
    if event.get("execution_authorized") is not False:
        raise ValueError("federated event execution_authorized must be false")

    source = str(event.get("source") or "").strip().upper()
    if source not in set(contracts.get("accepted_sources") or []):
        raise ValueError(f"federated event source is not an accepted source: {source}")
    category = str(event.get("category") or "").strip().upper()
    if category not in set(contracts.get("accepted_categories") or []):
        raise ValueError(f"federated event category is not accepted: {category}")

    required = set(contracts.get("required_fields") or [])
    missing = sorted(required.difference(event))
    legacy_relaxed = False
    if missing:
        if sha not in set(contracts.get("legacy_relaxed_blob_shas") or []):
            raise ValueError(
                "federated event is missing required fields: " + ", ".join(missing)
            )
        legacy_relaxed = True

    event_id = str(event.get("event_id") or f"legacy:{sha}").strip()
    summary = str(event.get("summary") or "").strip()
    at_utc = str(event.get("at_utc") or "").strip() or None

    return {
        "schema_version": contracts.get("event_schema"),
        "event_id": event_id,
        "at_utc": at_utc,
        "category": category,
        "status": event.get("status"),
        "severity": event.get("severity"),
        "summary": summary,
        "surface": event.get("surface"),
        "source": source,
        "paths": list(event.get("paths") or []),
        "evidence": list(event.get("evidence") or []),
        "remote_blob_sha": sha,
        "legacy_relaxed": legacy_relaxed,
        "foreign_evidence_only": True,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


class EngineFederationRemoteSync:
    """Verify and mirror Icarus-engine's canonical MCP event corpus."""

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
            "User-Agent": "icarus-engine-federation-sync/1",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        req = Request(url, headers=headers)
        with urlopen(req, timeout=15) as resp:
            return resp.read()

    def _default_fetch_json(self, url: str) -> Any:
        return json.loads(
            self._request(url, "application/vnd.github+json").decode("utf-8")
        )

    def _default_fetch_bytes(self, url: str) -> bytes:
        return self._request(url, "application/vnd.github.raw+json")

    def status(self) -> dict[str, Any]:
        return _read_state(self.base_dir, self.interval_seconds)

    def _verified_document(self, meta: Any, name: str) -> tuple[dict[str, Any], str]:
        if not isinstance(meta, Mapping) or meta.get("type") != "file":
            raise ValueError(f"{name} GitHub metadata is not a file")
        sha = str(meta.get("sha") or "").lower()
        url = str(meta.get("url") or "")
        if not _is_sha(sha) or not url:
            raise ValueError(f"{name} has invalid GitHub blob metadata")
        raw = self._fetch_bytes(url)
        if _git_blob_sha(raw) != sha:
            raise ValueError(f"{name} Git blob SHA mismatch")
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, Mapping):
            raise ValueError(f"{name} payload is not an object")
        return dict(value), sha

    def sync_once(self) -> dict[str, Any]:
        with self._lock:
            prior = _read_state(self.base_dir, self.interval_seconds)
            state = dict(prior)
            state["last_attempt_at"] = _utc_now()
            state["status"] = "syncing"
            state["last_error"] = None
            try:
                consumer_meta = self._fetch_json(_CONSUMER_API)
                producer_meta = self._fetch_json(_PRODUCER_API)
                event_listing = self._fetch_json(_EVENTS_API)

                consumer, consumer_sha = self._verified_document(
                    consumer_meta, "icarus_consumer_contract.json"
                )
                producer, producer_sha = self._verified_document(
                    producer_meta, "contract.json"
                )
                contracts = _normalize_contracts(producer, consumer)

                if not isinstance(event_listing, list):
                    raise ValueError("Icarus-engine event directory response is not a list")

                normalized_events: list[dict[str, Any]] = []
                event_blobs: dict[str, str] = {}
                accepted_sources = set(contracts["accepted_sources"])
                for item in event_listing:
                    if not isinstance(item, Mapping) or item.get("type") != "file":
                        continue
                    name = str(item.get("name") or "")
                    if not name.endswith(".json"):
                        continue
                    sha = str(item.get("sha") or "").lower()
                    url = str(item.get("url") or "")
                    path = str(item.get("path") or f"{EVENT_ROOT}/{name}")
                    if not _is_sha(sha) or not url:
                        raise ValueError(f"{name} has invalid GitHub blob metadata")
                    raw = self._fetch_bytes(url)
                    if _git_blob_sha(raw) != sha:
                        raise ValueError(f"{name} Git blob SHA mismatch")
                    event = json.loads(raw.decode("utf-8"))
                    if not isinstance(event, Mapping):
                        raise ValueError(f"{name} event payload is not an object")
                    source = str(event.get("source") or "").strip().upper()
                    if source not in accepted_sources:
                        continue
                    normalized = _normalize_event(event, sha, contracts)
                    normalized["remote_path"] = path
                    normalized_events.append(normalized)
                    event_blobs[path] = sha

                normalized_events.sort(
                    key=lambda row: (
                        str(row.get("at_utc") or ""),
                        str(row.get("event_id") or ""),
                        str(row.get("remote_blob_sha") or ""),
                    )
                )

                seen = set(
                    str(x)
                    for x in (prior.get("seen_event_blobs") or [])
                    if _is_sha(str(x))
                )
                for event in normalized_events:
                    blob = str(event["remote_blob_sha"])
                    if blob in seen:
                        continue
                    record_brain_event(
                        self.base_dir,
                        {
                            "kind": "subsystem",
                            "subject": "icarus-engine-federation",
                            "summary": (
                                f"{event['source']} {event['category']} — "
                                f"{event.get('summary') or event['event_id']}"
                            )[:1000],
                            "status": "observed",
                            "evidence": [
                                f"remote_repository:{REMOTE_REPOSITORY}",
                                f"remote_ref:{REMOTE_REF}",
                                f"remote_blob:{blob}",
                                f"remote_path:{event.get('remote_path')}",
                                f"producer_contract_blob:{producer_sha}",
                                f"consumer_contract_blob:{consumer_sha}",
                            ],
                            "details": {
                                "remote_event": event,
                                "truth_contract": contracts["truth_contract"],
                                "rule": (
                                    "Foreign repository event is research observability only; "
                                    "durability is not substantive evidence and authority never transfers."
                                ),
                            },
                        },
                    )
                    seen.add(blob)

                latest = normalized_events[-1] if normalized_events else None
                state.update(
                    {
                        "status": "green",
                        "last_success_at": _utc_now(),
                        "last_error": None,
                        "event_count": len(event_listing),
                        "accepted_event_count": len(normalized_events),
                        "latest_event_id": latest.get("event_id") if latest else None,
                        "latest_event_at": latest.get("at_utc") if latest else None,
                        "producer_contract_blob": producer_sha,
                        "consumer_contract_blob": consumer_sha,
                        "event_blobs": event_blobs,
                        "seen_event_blobs": sorted(seen),
                        "truth_contract": {
                            "federation_schema": consumer.get("schema_version"),
                            **contracts["truth_contract"],
                        },
                        "execution_authorized": False,
                        "production_decision_authorized": False,
                    }
                )
            except Exception as ex:
                state["status"] = "degraded"
                state["last_error"] = f"{type(ex).__name__}: {ex}"[:1600]
                state["execution_authorized"] = False
                state["production_decision_authorized"] = False

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
            name="icarus-engine-federation-sync",
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
