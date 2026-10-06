"""Verified Icarus-engine economic-event clock -> local ICARUS trader snapshot.

The cloud data fabric publishes compact first-party schedule artifacts into
reppiks490/Icarus-engine.  The local trader cannot assume those files are valid merely
because GitHub returned bytes: this synchronizer verifies Git blob identity, validates
the schema and timing contract, then persists a read-only local snapshot for the
Financial & data UI.

This plane is observability/research context only.  It cannot place orders, alter
strategy inputs, promote a candidate, or grant execution authority.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Mapping
from urllib.request import Request, urlopen

REMOTE_REPOSITORY = "reppiks490/Icarus-engine"
REMOTE_REF = "main"
REMOTE_FILES = {
    "manifest": "automation_intelligence/cl_lab/economic_events_manifest.json",
    "upcoming": "automation_intelligence/cl_lab/economic_events_upcoming.json",
}
_REMOTE_APIS = {
    key: f"https://api.github.com/repos/{REMOTE_REPOSITORY}/contents/{path}?ref={REMOTE_REF}"
    for key, path in REMOTE_FILES.items()
}
SYNC_SCHEMA = "icarus-economic-event-sync-v1"
_ALLOWED_SOURCES = {"BLS", "BEA", "CENSUS", "FOMC"}
_ALLOWED_SOURCE_STATUS = {"ok", "degraded", "error"}
_ALLOWED_IMPACT = {"high", "medium", "low"}
_ALLOWED_CATEGORY = {"macro", "growth", "labor", "inflation", "policy"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()


def _is_sha(value: Any) -> bool:
    s = str(value or "").lower()
    return len(s) == 40 and all(c in "0123456789abcdef" for c in s)


def _iso(value: Any, field: str) -> str:
    s = str(value or "").strip()
    if not s:
        raise ValueError(f"{field} is required")
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError as ex:
        raise ValueError(f"{field} must be ISO-8601") from ex
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return s


def _day(value: Any, field: str) -> str:
    s = str(value or "").strip()
    try:
        date.fromisoformat(s)
    except ValueError as ex:
        raise ValueError(f"{field} must be YYYY-MM-DD") from ex
    return s


def _state_path(base_dir: str | os.PathLike[str]) -> Path:
    return Path(base_dir) / "audit" / "economic_event_clock_sync.json"


def _default_state(interval_seconds: int) -> dict[str, Any]:
    return {
        "schema_version": SYNC_SCHEMA,
        "repository": REMOTE_REPOSITORY,
        "ref": REMOTE_REF,
        "interval_seconds": interval_seconds,
        "status": "not_started",
        "source_health": "unavailable",
        "last_attempt_at": None,
        "last_success_at": None,
        "last_error": None,
        "remote_generated_at": None,
        "remote_blobs": {},
        "sources": {},
        "current_events": 0,
        "schedule_versions": 0,
        "high_impact_current": 0,
        "time_known_current": 0,
        "upcoming_count": 0,
        "events": [],
        "causality": None,
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
        state["last_error"] = "local economic-event sync state is unreadable"
        return state
    if not isinstance(raw, Mapping):
        state["status"] = "degraded"
        state["last_error"] = "local economic-event sync state is not an object"
        return state
    if raw.get("execution_authorized") is not False or raw.get("production_decision_authorized") is not False:
        state["status"] = "degraded"
        state["last_error"] = "local economic-event sync state failed authority validation"
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
    raw = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=".event-clock-", delete=False) as fh:
        tmp = Path(fh.name)
        fh.write(raw)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _normalize(manifest: Mapping[str, Any], upcoming: Mapping[str, Any],
               blobs: Mapping[str, str]) -> dict[str, Any]:
    if manifest.get("schema") != "icarus.economic_events/1":
        raise ValueError("unsupported economic-event manifest schema")
    if upcoming.get("schema") != "icarus.economic_events.upcoming/1":
        raise ValueError("unsupported economic-event upcoming schema")
    generated = _iso(manifest.get("generated_at"), "manifest.generated_at")
    if _iso(upcoming.get("generated_at"), "upcoming.generated_at") != generated:
        raise ValueError("economic-event manifest/upcoming generated_at mismatch")
    if upcoming.get("timezone") != "America/New_York":
        raise ValueError("economic-event timezone must be America/New_York")

    raw_sources = manifest.get("sources")
    if not isinstance(raw_sources, Mapping):
        raise ValueError("economic-event sources must be an object")
    missing = sorted(_ALLOWED_SOURCES - set(raw_sources))
    if missing:
        raise ValueError("economic-event sources missing: " + ", ".join(missing))
    sources: dict[str, dict[str, Any]] = {}
    for source in sorted(_ALLOWED_SOURCES):
        raw = raw_sources.get(source)
        if not isinstance(raw, Mapping):
            raise ValueError(f"{source} source state is not an object")
        status = str(raw.get("status") or "")
        if status not in _ALLOWED_SOURCE_STATUS:
            raise ValueError(f"{source} has unsupported status")
        rows = raw.get("rows")
        if isinstance(rows, bool) or not isinstance(rows, int) or rows < 0:
            raise ValueError(f"{source}.rows must be a non-negative integer")
        sources[source] = {
            k: raw.get(k)
            for k in ("status", "rows", "transport", "snapshot_as_of", "source_url", "error",
                      "history_invalid_rows_removed")
            if raw.get(k) is not None
        }

    counts = {}
    for key in ("current_events", "schedule_versions", "high_impact_current",
                "time_known_current", "upcoming_rows"):
        value = manifest.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{key} must be a non-negative integer")
        counts[key] = value
    if sum(int(s["rows"]) for s in sources.values()) != counts["current_events"]:
        raise ValueError("source row counts do not equal current_events")

    raw_events = upcoming.get("events")
    if not isinstance(raw_events, list) or len(raw_events) > 1000:
        raise ValueError("upcoming.events must be an array of at most 1000 events")
    if len(raw_events) != counts["upcoming_rows"]:
        raise ValueError("upcoming event count does not match manifest")

    events = []
    identities = set()
    for index, raw in enumerate(raw_events):
        if not isinstance(raw, Mapping):
            raise ValueError(f"event {index} is not an object")
        source = str(raw.get("source") or "")
        if source not in _ALLOWED_SOURCES:
            raise ValueError(f"event {index} has unsupported source")
        event_key = str(raw.get("event_key") or "").strip()
        title = str(raw.get("title") or "").strip()
        if not event_key or len(event_key) > 128 or not title or len(title) > 500:
            raise ValueError(f"event {index} has invalid identity/title")
        identity = (source, event_key)
        if identity in identities:
            raise ValueError(f"duplicate upcoming event identity {source}:{event_key}")
        identities.add(identity)
        category = str(raw.get("category") or "")
        impact = str(raw.get("impact") or "")
        if category not in _ALLOWED_CATEGORY or impact not in _ALLOWED_IMPACT:
            raise ValueError(f"event {index} has unsupported category/impact")
        event_date = _day(raw.get("event_date"), f"event[{index}].event_date")
        known = raw.get("time_known")
        if not isinstance(known, bool):
            raise ValueError(f"event {index}.time_known must be boolean")
        scheduled_et = raw.get("scheduled_at_et")
        scheduled_utc = raw.get("scheduled_at_utc")
        if known:
            scheduled_et = _iso(scheduled_et, f"event[{index}].scheduled_at_et")
            scheduled_utc = _iso(scheduled_utc, f"event[{index}].scheduled_at_utc")
        elif scheduled_et is not None or scheduled_utc is not None:
            raise ValueError(f"event {index} cannot expose a timestamp when time_known=false")
        row = {
            "source": source,
            "event_key": event_key,
            "title": title,
            "category": category,
            "impact": impact,
            "reference_period": raw.get("reference_period"),
            "event_date": event_date,
            "scheduled_at_et": scheduled_et,
            "scheduled_at_utc": scheduled_utc,
            "time_known": known,
            "timing_basis": str(raw.get("timing_basis") or "")[:300],
        }
        events.append(row)

    # The remote file is already sorted, but make local presentation deterministic.
    events.sort(key=lambda x: (
        x["scheduled_at_utc"] or f"{x['event_date']}T23:59:59+00:00",
        x["source"], x["title"],
    ))
    health = "ok" if all(s["status"] == "ok" for s in sources.values()) else "degraded"
    causality = str(manifest.get("causality") or "").strip()
    if not causality:
        raise ValueError("economic-event causality statement is required")

    return {
        "schema_version": SYNC_SCHEMA,
        "repository": REMOTE_REPOSITORY,
        "ref": REMOTE_REF,
        "status": "green" if health == "ok" else "degraded",
        "source_health": health,
        "remote_generated_at": generated,
        "remote_blobs": dict(blobs),
        "sources": sources,
        "current_events": counts["current_events"],
        "schedule_versions": counts["schedule_versions"],
        "high_impact_current": counts["high_impact_current"],
        "time_known_current": counts["time_known_current"],
        "upcoming_count": len(events),
        "events": events,
        "causality": causality,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


class EconomicEventClockSync:
    """Poll and verify the compact event-clock artifacts from Icarus-engine."""

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
            enabled = str(os.environ.get("ICARUS_EVENT_CLOCK_SYNC", "1")).strip().lower() not in {
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
        headers = {"Accept": accept, "User-Agent": "icarus-economic-event-sync/1"}
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
            state["last_attempt_at"] = _utc_now()
            state["last_error"] = None
            if not self.enabled:
                state["status"] = "disabled"
                _write_state(self.base_dir, state)
                return self.status()
            try:
                documents: dict[str, Mapping[str, Any]] = {}
                blobs: dict[str, str] = {}
                for key, api_url in _REMOTE_APIS.items():
                    meta = self._fetch_json(api_url)
                    if not isinstance(meta, Mapping):
                        raise ValueError(f"{key} GitHub metadata is not an object")
                    sha = str(meta.get("sha") or "").lower()
                    raw_url = str(meta.get("url") or "")
                    if not _is_sha(sha) or not raw_url:
                        raise ValueError(f"{key} GitHub metadata is invalid")
                    raw = self._fetch_bytes(raw_url)
                    if _git_blob_sha(raw) != sha:
                        raise ValueError(f"{key} Git blob SHA mismatch")
                    payload = json.loads(raw.decode("utf-8"))
                    if not isinstance(payload, Mapping):
                        raise ValueError(f"{key} payload is not an object")
                    documents[key] = payload
                    blobs[key] = sha
                normalized = _normalize(documents["manifest"], documents["upcoming"], blobs)
                normalized["interval_seconds"] = self.interval_seconds
                normalized["last_attempt_at"] = state["last_attempt_at"]
                normalized["last_success_at"] = _utc_now()
                normalized["last_error"] = None
                state = normalized
            except Exception as ex:
                # Preserve the last verified event set while clearly marking it stale/degraded.
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
        if not self.enabled or (self._thread and self._thread.is_alive()):
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="icarus-economic-event-sync", daemon=True,
        )
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
