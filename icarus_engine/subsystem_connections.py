"""Scoped, cached native NEXUS telemetry and AION receipt-time memory.

This adapter observes published runtime metadata. It neither acquires market
data nor turns local monitor sequences, receipt lag, or chain integrity into
provider health, empirical qualification, or execution authority.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import threading
import time
from typing import Any, Mapping

from .native_subsystems._divine.aion.contracts import EvidenceTier, Observation, SourceSpec, digest as _native_digest
from .native_subsystems._divine.aion.store import EventStore
from .native_subsystems._divine.nexus.contracts import VectorEvent
from .native_subsystems._divine.nexus.source_health import SourceHealthPlane, SourceHealthRegistry


SCHEMA_VERSION = "icarus-nexus-aion-v1"
SOURCE_REVISION = "27ae69c593ede3019957100cd401625bd2424f43"
_SOURCE_HEALTH_SHA256 = "84a5f0ea2f1906779c51acc44f7ed67597c2f0780846a3d7fac3b8348f81db77"
_MAX_ASSETS = 128
_TOKEN = re.compile(r"[A-Za-z0-9_.:/=^-]{1,120}\Z")
_AGES = ("poll_age_seconds", "bar_age_seconds", "price_age_seconds")
_CAPTURE_WARNINGS = {"CACHE_UNAVAILABLE", "FUTURE_CACHE_TIME", "INVALID_SOURCE_AGE",
                     "FUTURE_SOURCE_TIME", "ASSET_CAPTURE_LIMIT", "CONFIGURATION_CHANGED_DURING_CAPTURE"}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _token(value, default="unknown"):
    return value if isinstance(value, str) and _TOKEN.fullmatch(value) else default


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _asset_state(row, stale_after=15.0):
    if row["cache_state"] == "UNAVAILABLE":
        return "UNAVAILABLE"
    if row["cache_state"] != "OBSERVED" or row["active_error"] or row["capture_age_seconds"] > stale_after:
        return "DEGRADED"
    return "OBSERVING"


def _metadata(symbol, summary, captured_at_ns, now_ns):
    """Select scalars before copying anything from the large runner summary."""
    row = {"symbol": _token(symbol), "provider": _token(summary.get("feed_provider") or summary.get("feed")),
           "provider_symbol": _token(summary.get("provider_symbol")), "kind": _token(summary.get("kind")),
           "captured_at_ns": captured_at_ns, "capture_age_seconds": None,
           "cache_state": "UNAVAILABLE", "bar_index": None, "last_bar_ts": None,
           "active_error": bool(summary.get("last_error").strip()) if isinstance(summary.get("last_error"), str) else False,
           "warm": summary.get("warm") is True, "rewarming": summary.get("rewarming") is True,
           "paused": summary.get("paused") is True, "provider_slo_known": False,
           "sequence_basis": "adapter_local_monitor_observations"}
    warnings = []
    if type(captured_at_ns) is not int or captured_at_ns < 0:
        warnings.append("CACHE_UNAVAILABLE:" + row["symbol"])
    elif captured_at_ns > now_ns:
        warnings.append("FUTURE_CACHE_TIME:" + row["symbol"])
    else:
        row["capture_age_seconds"] = (now_ns - captured_at_ns) / 1e9
        row["cache_state"] = "OBSERVED"
    for source, target in zip(("poll_age", "bar_age", "price_age"), _AGES):
        value = summary.get(source)
        row[target] = None
        if value is not None:
            if not _number(value) or value < 0:
                row["cache_state"] = "UNAVAILABLE"
                warnings.append("INVALID_SOURCE_AGE:" + row["symbol"])
            elif row["capture_age_seconds"] is not None:
                row[target] = float(value) + row["capture_age_seconds"]
    value = summary.get("bar_index")
    if type(value) is int and value >= -1:
        row["bar_index"] = value
    value = summary.get("last_bar_ts")
    if value is not None:
        if not _number(value) or value < 0 or value * 1e9 > now_ns:
            row["cache_state"] = "UNAVAILABLE"
            warnings.append("FUTURE_SOURCE_TIME:" + row["symbol"])
        else:
            row["last_bar_ts"] = value
    row["state"] = _asset_state(row)
    return row, warnings


def capture_portfolio(portfolio, *, now_ns=None):
    """Read only immutable ``_public_views[0]``; never invoke runner/feed APIs.

    The publisher replaces its whole tuple, so taking one tuple reference keeps
    its summary and capture timestamp paired across concurrent publication.
    """
    now_ns = time.time_ns() if now_ns is None else now_ns
    if type(now_ns) is not int or now_ns < 0:
        raise ValueError("capture requires a nonnegative nanosecond clock")
    workspace = getattr(portfolio, "workspace", None)
    revision = workspace.get("config_revision") if isinstance(workspace, Mapping) else None
    if type(revision) is not int or revision < 0:
        revision = None
    runners = getattr(portfolio, "runners", {})
    if not isinstance(runners, Mapping):
        raise ValueError("published runner mapping unavailable")
    items = tuple(runners.items())
    assets, warnings = [], []
    if len(items) > _MAX_ASSETS:
        warnings.append("ASSET_CAPTURE_LIMIT")
    for symbol, runner in sorted(items, key=lambda item: str(item[0]))[:_MAX_ASSETS]:
        views = getattr(runner, "_public_views", None)
        summary, captured = {}, None
        if isinstance(views, tuple) and views and isinstance(views[0], tuple) and len(views[0]) == 2:
            cached, stamp = views[0]
            if isinstance(cached, Mapping) and _number(stamp) and stamp >= 0:
                summary, captured = cached, int(stamp * 1e9)
        row, issues = _metadata(symbol, summary, captured, now_ns)
        assets.append(row)
        warnings.extend(issues)
    current = getattr(portfolio, "workspace", None)
    if (current is not workspace or getattr(portfolio, "runners", None) is not runners
            or isinstance(current, Mapping) and current.get("config_revision") != revision):
        revision = None
        warnings.append("CONFIGURATION_CHANGED_DURING_CAPTURE")
        for row in assets:
            row.update(state="UNAVAILABLE", cache_state="UNAVAILABLE")
    result = {"observed_at_ns": now_ns, "assets": assets, "warnings": warnings,
              "observed_config_revision": revision}
    if isinstance(workspace, Mapping) and workspace.get("id") in {"main", "cc1", "cc2", "cc3", "cc4"}:
        result["workspace_id"] = workspace["id"]
    return result


class NativeSubsystemConnections:
    """One workspace worker; HTTP readers only copy a bounded cached result."""

    def __init__(self, base_dir, *, workspace_id, snapshot_supplier, interval=5.0, clock_ns=time.time_ns):
        if workspace_id not in {"main", "cc1", "cc2", "cc3", "cc4"}:
            raise ValueError("unknown workspace identity")
        if not callable(snapshot_supplier) or not callable(clock_ns):
            raise TypeError("snapshot supplier and clock must be callable")
        if not _number(interval) or interval <= 0:
            raise ValueError("interval must be finite and positive")
        self.workspace_id = workspace_id
        self.store_path = Path(base_dir) / "audit" / "subsystem_connections" / workspace_id / "aion.sqlite3"
        self._supplier, self._clock, self.interval = snapshot_supplier, clock_ns, float(interval)
        self._stale_after = max(15.0, 3 * self.interval)
        self._cache_lock, self._tick_lock, self._lifecycle_lock = threading.Lock(), threading.Lock(), threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._closed = False
        self._store = None
        self._registry = SourceHealthRegistry()
        self._loaded = False
        self._event_count = self._recovered_count = 0
        self._last_persisted_ns = None
        self._last_signature = None
        self._last_context = None
        self._trusted_fingerprint = None
        self._last_full_verification_ns = None
        self._verified_head, self._last_position = "0" * 64, 0
        self._sequences, self._stream_signatures = {}, {}
        self._source_id = "icarus-runtime-monitor:" + workspace_id + ":v1"
        self._source_spec = SourceSpec(source_id=self._source_id, representation_id=SCHEMA_VERSION,
            symbol=self.workspace_id, capabilities=("context",), max_evidence_tier=EvidenceTier.CANDLE_PROXY,
            source_sha256=_SOURCE_HEALTH_SHA256, origin="icarus_runtime_monitor", sequence_policy="none",
            evidence_reference="divine-providence:" + SOURCE_REVISION + ":nexus/source_health",
            license_reference="local_runtime_metadata_no_market_payload")
        self._source_hash = _native_digest(self._source_spec.to_dict())
        self._cache = self._initial()

    def _initial(self):
        native = {"repository": "reppiks490/divine-providence", "revision": SOURCE_REVISION}
        return {"schema_version": SCHEMA_VERSION, "workspace_id": self.workspace_id, "state": "STARTING",
                "observed_at_ns": None, "observed_config_revision": None, "capture_age_seconds": None,
                "assets": [], "warnings": [], "source_revision": SOURCE_REVISION,
                "nexus": {"state": "STARTING", "plane_hash": None, "stream_count": 0,
                          "unknown_slo_streams": 0, "sequence_basis": "adapter_local_monitor_observations",
                          "native_source": native},
                "aion": {"state": "STARTING", "event_count": 0, "chain_verified": False,
                         "last_persisted_ns": None, "recovered_event_count": 0, "native_source": native},
                "execution_authorized": False, "production_decision_authorized": False}

    def start(self):
        with self._lifecycle_lock:
            if self._closed or self._thread is not None:
                return
            self._thread = threading.Thread(target=self._run, name="icarus-subsystems-" + self.workspace_id, daemon=True)
            self._thread.start()

    def _run(self):
        while not self._stop.is_set():
            self.tick()
            if self._stop.wait(self.interval):
                break

    def close(self):
        with self._lifecycle_lock:
            self._closed = True
            self._stop.set()
            thread = self._thread
        with self._cache_lock:
            self._cache["state"] = "STOPPED"
        if thread is not None and thread is not threading.current_thread():
            thread.join()
        # Manual ticks use the same drain boundary as the worker.
        with self._tick_lock:
            pass

    def snapshot(self):
        with self._cache_lock:
            out = deepcopy(self._cache)
        observed = out["observed_at_ns"]
        if observed is None:
            return out
        now = self._clock()
        if type(now) is not int or now < observed:
            if out["state"] != "STOPPED":
                out["state"] = "UNAVAILABLE"
            out["warnings"] = sorted(set(out["warnings"] + ["MONITOR_CLOCK_REVERSED"]))
            return out
        elapsed = (now - observed) / 1e9
        ages = []
        for row in out["assets"]:
            if row["capture_age_seconds"] is not None:
                row["capture_age_seconds"] += elapsed
                row["cache_age_seconds"] = row["capture_age_seconds"]
                ages.append(row["capture_age_seconds"])
            for key in _AGES:
                if row[key] is not None:
                    row[key] += elapsed
            if row["state"] != "UNAVAILABLE":
                row["state"] = _asset_state(row, self._stale_after)
        out["capture_age_seconds"] = max(ages, default=None)
        if elapsed > self._stale_after and out["state"] not in {"UNAVAILABLE", "STOPPED"}:
            out["state"] = "DEGRADED"
            out["warnings"] = sorted(set(out["warnings"] + ["MONITOR_CACHE_STALE"]))
        return out

    def _publish(self, snapshot):
        with self._cache_lock:
            if not self._closed:
                self._cache = snapshot

    def _check_storage_path(self):
        paths = (self.store_path, *self.store_path.parents,
                 *(Path(str(self.store_path) + suffix) for suffix in ("-journal", "-wal", "-shm")))
        if any(path.is_symlink() for path in paths):
            raise ValueError("native storage must not follow a symlink")

    def _fingerprint(self):
        self._check_storage_path()
        image = []
        for suffix in ("", "-journal", "-wal", "-shm"):
            try:
                info = Path(str(self.store_path) + suffix).stat()
                image.append((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns))
            except FileNotFoundError:
                image.append(None)
        return tuple(image)

    def _load_store(self, now):
        self._check_storage_path()
        if self._store is None:
            self._store = EventStore(self.store_path)
        if self._last_persisted_ns is not None and now < self._last_persisted_ns:
            raise ValueError("monitor clock precedes the last persisted receipt")
        image = self._fingerprint()
        if (self._loaded and image == self._trusted_fingerprint
                and now - self._last_full_verification_ns < 60_000_000_000):
            return
        verified = self._store.verify_chain()
        if self._loaded and (verified["events"] < self._event_count or
                verified["events"] == self._event_count and verified["head_hash"] != self._verified_head):
            raise ValueError("previously verified context history was truncated or rewritten")
        if not self._loaded or verified["events"] != self._event_count:
            rows = self._store.asof(now, symbol=self.workspace_id, plane="research")
            if len(rows) != verified["events"]:
                raise ValueError("context history is outside the current receipt-time boundary")
            if self._loaded and self._event_count and not any(
                    row["position"] == self._last_position and row["event_hash"] == self._verified_head for row in rows):
                raise ValueError("previously verified context prefix was replaced")
            for record in rows:
                event = Observation.from_dict(record["event"])
                payload = event.payload
                plane = SourceHealthPlane.from_dict(payload["nexus_plane"])
                if (record["source"] != self._source_id or record["representation_id"] != SCHEMA_VERSION
                        or event.kind != "context" or event.plane != "research"
                        or event.evidence_tier != EvidenceTier.CANDLE_PROXY
                        or event.availability_basis != "observed_receipt"
                        or payload.get("schema_version") != SCHEMA_VERSION
                        or payload.get("workspace_id") != self.workspace_id
                        or payload.get("source_revision") != SOURCE_REVISION
                        or payload.get("execution_authorized") is not False
                        or payload.get("production_decision_authorized") is not False
                        or payload.get("observed_at_ns") != event.available_ns
                        or plane.decision_ns > event.available_ns or not plane.verify()):
                    raise ValueError("native context identity, time or plane is invalid")
            if rows:
                latest = rows[-1]["event"]
                payload = latest["payload"]
                self._last_context = payload
                self._last_signature = payload["observation_signature"]
                self._last_persisted_ns = latest["available_ns"]
                self._sequences = dict(payload.get("local_sequences", {}))
                self._last_position = rows[-1]["position"]
            if not self._loaded:
                self._recovered_count = verified["events"]
            self._event_count = verified["events"]
        if not self._loaded:
            if self._store.register(self._source_spec) != self._source_hash:
                raise ValueError("native source registration hash mismatch")
            self._loaded = True
        self._verified_head = verified["head_hash"]
        self._last_full_verification_ns = now
        self._trusted_fingerprint = self._fingerprint()

    def _normalize(self, sample, now):
        if not isinstance(sample, Mapping) or not isinstance(sample.get("assets"), list):
            raise ValueError("bounded published metadata is required")
        if sample.get("workspace_id", self.workspace_id) != self.workspace_id:
            raise ValueError("foreign workspace capture")
        captured_now = sample.get("observed_at_ns", now)
        if type(captured_now) is not int or captured_now < 0 or captured_now > now:
            raise ValueError("capture observation clock is invalid")
        delta = (now - captured_now) / 1e9
        assets, warnings, symbols = [], [], set()
        for original in sample["assets"][:_MAX_ASSETS]:
            if not isinstance(original, Mapping):
                raise ValueError("asset metadata must be an object")
            symbol = _token(original.get("symbol"), "")
            if not symbol or symbol in symbols:
                raise ValueError("invalid or duplicate asset identity")
            symbols.add(symbol)
            # Re-admit the allowlist even if a caller supplies a custom sampler.
            summary = {"feed_provider": original.get("provider"), "provider_symbol": original.get("provider_symbol"),
                       "kind": original.get("kind"), "bar_index": original.get("bar_index"),
                       "last_bar_ts": original.get("last_bar_ts"), "warm": original.get("warm"),
                       "rewarming": original.get("rewarming"), "paused": original.get("paused"),
                       "last_error": "reported" if original.get("active_error") is True else ""}
            row, issues = _metadata(symbol, summary, original.get("captured_at_ns"), now)
            for key in _AGES:
                value = original.get(key)
                if value is not None:
                    if not _number(value) or value < 0:
                        row["cache_state"] = "UNAVAILABLE"
                        issues.append("INVALID_SOURCE_AGE:" + symbol)
                    else:
                        row[key] = float(value) + delta
            if original.get("cache_state") == "UNAVAILABLE":
                row["cache_state"] = "UNAVAILABLE"
            row["state"] = _asset_state(row, self._stale_after)
            row["cache_age_seconds"] = row["capture_age_seconds"]
            row["reported_error"] = row["active_error"]
            assets.append(row)
            warnings.extend(issues)
        if len(sample["assets"]) > _MAX_ASSETS:
            warnings.append("ASSET_CAPTURE_LIMIT")
        # Only adapter-generated warning codes are admitted, never source error text.
        for code in sample.get("warnings", [])[:2 * _MAX_ASSETS]:
            if (isinstance(code, str) and code.split(":", 1)[0] in _CAPTURE_WARNINGS
                    and re.fullmatch(r"[A-Z_]+(?::[A-Za-z0-9_.:/=^-]{1,120})?", code)):
                warnings.append(code)
        revision = sample.get("observed_config_revision")
        if revision is not None and (type(revision) is not int or revision < 0):
            raise ValueError("invalid observed configuration revision")
        return sorted(assets, key=lambda row: row["symbol"]), sorted(set(warnings)), revision

    @staticmethod
    def _stable_asset(row):
        return {key: row[key] for key in ("symbol", "provider", "provider_symbol", "kind", "bar_index",
                "last_bar_ts", "active_error", "warm", "rewarming", "paused", "state", "cache_state")}

    def tick(self):
        if self._closed or not self._tick_lock.acquire(blocking=False):
            return self.snapshot()
        stage = "AION_STORAGE_UNAVAILABLE"
        out = self._initial()
        try:
            if self._closed:
                return self.snapshot()
            now = self._clock()
            if type(now) is not int or now < 0:
                raise ValueError("invalid monitor clock")
            if self._store is None:
                self._check_storage_path()
                self._store = EventStore(self.store_path)
            stage = "AION_INTEGRITY_UNAVAILABLE"
            self._load_store(now)
            stage = "CAPTURE_UNAVAILABLE"
            capture_failed = False
            try:
                sample = self._supplier()
                now = self._clock()  # Local receipt follows the metadata read.
                assets, warnings, revision = self._normalize(sample, now)
            except Exception:
                capture_failed = True
                if self._last_context:
                    assets, warnings, revision = self._normalize(self._last_context, now)
                    for row in assets:
                        if row["state"] != "UNAVAILABLE":
                            row.update(state="DEGRADED", cache_state="RECOVERED")
                    warnings.append("RECOVERED_CONTEXT_NOT_CURRENT")
                else:
                    assets, warnings, revision = [], [], None
                warnings.append("CAPTURE_UNAVAILABLE")
            out.update(observed_at_ns=now, assets=assets, observed_config_revision=revision)
            warnings.append("PROVIDER_SLO_UNKNOWN")
            valid = [row for row in assets if row["state"] != "UNAVAILABLE"]
            live_ids = {row["symbol"] for row in valid}
            if live_ids != set(self._stream_signatures):
                self._registry = SourceHealthRegistry()
                self._stream_signatures = {}
                self._sequences = {key: value for key, value in self._sequences.items() if key in live_ids}
            stage = "NEXUS_PLANE_INVALID"
            for row in valid:
                identity = _hash(self._stable_asset(row))
                symbol = row["symbol"]
                if self._stream_signatures.get(symbol) == identity:
                    continue
                sequence = self._sequences.get(symbol, 0) + 1
                self._registry.observe(VectorEvent(stream_id=self.workspace_id + ":" + symbol,
                    event_ns=now, available_ns=now, source_timestamp_ns=row["captured_at_ns"],
                    source_sequence=sequence, source_path="icarus_runtime_monitor:published_summary",
                    fields=(("cache_age_seconds", row["capture_age_seconds"]), ("reported_error", float(row["active_error"]))),
                    data_plane="research", quality_flags=("adapter_local_sequence", "provider_slo_unknown"),
                    availability_basis="observed_receipt"), received_ns=now,
                    connected=row["cache_state"] == "OBSERVED")
                self._sequences[symbol] = sequence
                self._stream_signatures[symbol] = identity
            plane = self._registry.snapshot(now)
            if not plane.verify():
                raise ValueError("native health plane failed verification")
            signature = _hash({"assets": [self._stable_asset(row) for row in assets],
                               "warnings": sorted(set(warnings)), "observed_config_revision": revision})
            payload = {"schema_version": SCHEMA_VERSION, "workspace_id": self.workspace_id,
                       "source_revision": SOURCE_REVISION, "observed_at_ns": now, "assets": assets,
                       "warnings": sorted(set(warnings)), "observed_config_revision": revision,
                       "observation_signature": signature, "nexus_plane": plane.to_dict(),
                       "local_sequences": dict(self._sequences), "execution_authorized": False,
                       "production_decision_authorized": False}
            stage = "AION_STORAGE_UNAVAILABLE"
            # A sampler may have taken time; verify any externally changed
            # image before extending the last authenticated native prefix.
            self._load_store(now)
            if signature != self._last_signature:
                observation = Observation(source_id=self._source_id,
                    source_event_id="context-" + str(self._event_count + 1), revision=1, kind="context",
                    event_ns=now, available_ns=now, ingested_ns=now, evidence_tier=EvidenceTier.CANDLE_PROXY,
                    payload=payload, plane="research", availability_basis="observed_receipt",
                    quality_flags=("runtime_metadata_only", "adapter_local_sequence", "provider_slo_unknown"))
                receipt = self._store.append(observation)
                stage = "AION_INTEGRITY_UNAVAILABLE"
                expected = _native_digest({"previous": self._verified_head, "source_hash": self._source_hash,
                                           "event": observation.to_dict()})
                if (receipt["event_hash"] != expected or receipt["position"] != self._last_position + 1
                        or receipt["idempotent"] is not False):
                    raise ValueError("native append did not extend the verified prefix")
                self._event_count += 1
                self._last_position, self._verified_head = receipt["position"], receipt["event_hash"]
                self._last_persisted_ns, self._last_signature, self._last_context = now, signature, payload
                self._trusted_fingerprint = self._fingerprint()
            out["warnings"] = sorted(set(warnings))
            out["capture_age_seconds"] = max((row["capture_age_seconds"] for row in assets if row["capture_age_seconds"] is not None), default=None)
            out["state"] = ("UNAVAILABLE" if not valid else "DEGRADED"
                            if capture_failed or any(row["state"] != "OBSERVING" for row in assets) else "OBSERVING")
            out["nexus"].update(state="UNKNOWN_SLO" if valid else "UNAVAILABLE", plane_hash=plane.plane_hash,
                                stream_count=plane.stream_count, unknown_slo_streams=len(plane.unknown_slo_streams))
            out["aion"].update(state="VERIFIED", event_count=self._event_count, chain_verified=True,
                               last_persisted_ns=self._last_persisted_ns, recovered_event_count=self._recovered_count,
                               last_full_verification_ns=self._last_full_verification_ns)
            self._publish(out)
        except Exception:
            with self._cache_lock:
                out = deepcopy(self._cache)
            out["state"] = "UNAVAILABLE"
            out["warnings"] = sorted(set(out["warnings"] + [stage]))
            if stage.startswith("AION_"):
                out["aion"].update(state="UNAVAILABLE", chain_verified=False)
            if stage == "NEXUS_PLANE_INVALID":
                out["nexus"]["state"] = "UNAVAILABLE"
            self._publish(out)
        finally:
            self._tick_lock.release()
        return self.snapshot()
