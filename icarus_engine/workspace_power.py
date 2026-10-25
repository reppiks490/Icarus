"""Durable, independent paper-workspace lifecycle controls.

HTTP admission takes only nonblocking runtime locks. Feed preparation, worker
joins and selected-panel cleanup run in separate per-workspace daemon workers.
The parent owns all shared feed transports throughout these transitions.
"""
from __future__ import annotations

from contextlib import ExitStack
import json
import os
import threading
import time


SCHEMA = "icarus.workspace-power.v1"
_MAX_REVISION = 2**53 - 1


class WorkspacePowerError(ValueError):
    def __init__(self, status, detail):
        self.status = status
        self.detail = detail
        super().__init__(detail)


def _strict_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate field")
        value[key] = item
    return value


class WorkspacePowerControls:
    def __init__(self, manager, *, on_disabled=None, busy=None, on_enabled=None):
        self.manager = manager
        self._on_disabled = on_disabled or (lambda _id: None)
        self._on_enabled = on_enabled or (lambda _id, _portfolio: None)
        self._busy = busy or (lambda _id: False)
        self._lock = threading.RLock()
        self._persist_lock = threading.Lock()
        self._admission = {key: threading.Lock() for key in manager.profiles}
        self._notifications = {key: threading.Lock() for key in manager.profiles}
        self._cancel = {key: threading.Event() for key in manager.profiles}
        self._workers = {}
        self._pending = {}
        self._explicit = set()
        self._closed = False
        self._invalid = False
        self._path = manager.root / "runtime-power.json"
        self._rows = {key: {"id": key, "desired_enabled": True, "runtime_state": "OFF",
                            "revision": 0, "error": None} for key in manager.profiles}
        self._load()

    def _load(self):
        try:
            if not self._path.exists():
                return
            if self._path.stat().st_size > 16384:
                raise ValueError("oversized control file")
            data = json.loads(self._path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
            if (type(data) is not dict or set(data) != {"schema_version", "workspaces"}
                    or data["schema_version"] != SCHEMA or type(data["workspaces"]) is not list
                    or len(data["workspaces"]) != len(self._rows)):
                raise ValueError("invalid control file")
            seen = set()
            for item in data["workspaces"]:
                if (type(item) is not dict or set(item) != {"id", "desired_enabled", "revision"}
                        or type(item["id"]) is not str or item["id"] not in self._rows
                        or item["id"] in seen or type(item["desired_enabled"]) is not bool
                        or type(item["revision"]) is not int or not 0 <= item["revision"] <= _MAX_REVISION):
                    raise ValueError("invalid workspace power record")
                seen.add(item["id"])
            for item in data["workspaces"]:
                self._rows[item["id"]].update(item)
                if not item["desired_enabled"]:
                    self._explicit.add(item["id"])
        except (OSError, ValueError, TypeError, RecursionError):
            self._invalid = True
            self._explicit.update(self._rows)
            for item in self._rows.values():
                item.update(desired_enabled=False, runtime_state="ERROR",
                            error="Workspace power settings are invalid; repair runtime-power.json before enabling.")

    def _record(self, profile_id):
        item = dict(self._rows[profile_id])
        # start=False fixtures and legacy callers can seed portfolios after
        # construction. An accepted OFF or lifecycle transition takes precedence.
        if (profile_id not in self._explicit and not self._closed
                and item["desired_enabled"] and profile_id in self.manager.portfolios):
            item["runtime_state"] = "ON"
        return item

    def snapshot(self):
        with self._lock:
            rows = [self._record(key) for key in self._rows]
        return {"schema_version": SCHEMA, "workspaces": rows,
                "paper_only": True, "execution_authorized": False}

    def is_on(self, profile_id):
        with self._lock:
            return (type(profile_id) is str and profile_id in self._rows and not self._closed
                    and self._record(profile_id)["runtime_state"] == "ON"
                    and self._rows[profile_id]["desired_enabled"]
                    and profile_id in self.manager.portfolios)

    def _save(self, profile_id, enabled, revision):
        # Caller keeps _persist_lock through publication of the same revision,
        # preventing another profile from saving an older in-memory record.
        tmp = self._path.with_suffix(".json.tmp")
        try:
            with self._lock:
                rows = [{key: row[key] for key in ("id", "desired_enabled", "revision")}
                        for row in self._rows.values()]
            for item in rows:
                if item["id"] == profile_id:
                    item.update(desired_enabled=enabled, revision=revision)
            with tmp.open("w", encoding="utf-8") as handle:
                json.dump({"schema_version": SCHEMA, "workspaces": rows}, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self._path)
        except (OSError, ValueError):
            raise WorkspacePowerError(503, "Workspace power settings could not be saved; runtime unchanged.") from None
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _take(stack, lock):
        if not lock.acquire(blocking=False):
            raise WorkspacePowerError(409, "Workspace is busy; retry after its current operation.")
        stack.callback(lock.release)

    def _guard_off(self, profile_id, portfolio, stack):
        if self._busy(profile_id):
            raise WorkspacePowerError(409, "Workspace has an active job; wait before switching it off.")
        if portfolio is None:
            return []
        self._take(stack, portfolio._workspace_power_activation_lock)
        self._take(stack, portfolio._lock)
        runners = sorted(portfolio.runner_list(), key=lambda item: item.symbol)
        for runner in runners:
            self._take(stack, runner.lock)
            if (runner.rewarming or getattr(runner, "_activation_version_id", None)
                    or getattr(runner, "_activation_quarantine", None)):
                raise WorkspacePowerError(409, "Workspace configuration or activation is busy.")
            primary = runner.em
            emulators = (primary, getattr(primary, "shadow", None))
            if any(em is not None and (em.open or em._pending_entries or em._pending_closes)
                   for em in emulators):
                raise WorkspacePowerError(409, "Workspace has open positions or pending orders; resolve them before switching off.")
        return runners

    @staticmethod
    def _signal_stop(portfolio, runners):
        if portfolio is None:
            return
        portfolio.paused = True
        for runner in runners:
            # Do not call set_paused: it cancels pending intents. Admission has
            # already proved flatness while these same runner locks are held.
            runner.paused = True
            if runner.strat is not None:
                runner.strat.paused = True
            runner._removed = True
        portfolio._stop.set()

    def _launch(self, profile_id, enabled):
        try:
            worker = threading.Thread(target=self._transition, args=(profile_id, enabled),
                                      daemon=True, name=f"workspace-power-{profile_id}")
            self._workers[profile_id] = worker
            worker.start()
        except Exception:
            self._workers.pop(profile_id, None)
            self._rows[profile_id].update(runtime_state="ERROR",
                                         error="Workspace lifecycle worker could not start; retry the request.")
            raise WorkspacePowerError(503, "Workspace lifecycle worker could not start; retry the request.") from None

    def request(self, profile_id, body):
        if type(profile_id) is not str or profile_id not in self._rows:
            raise WorkspacePowerError(404, "Unknown workspace.")
        if (type(body) is not dict or set(body) != {"enabled", "expected_revision"}
                or type(body["enabled"]) is not bool or type(body["expected_revision"]) is not int
                or not 0 <= body["expected_revision"] <= _MAX_REVISION):
            raise WorkspacePowerError(400, "Power request requires enabled boolean and nonnegative expected_revision integer.")
        enabled = body["enabled"]
        with ExitStack() as stack:
            self._take(stack, self._admission[profile_id])
            self._take(stack, self.manager.configuration_lock(profile_id))
            with self._lock:
                if self._closed or self._invalid:
                    raise WorkspacePowerError(503, "Workspace power controls are unavailable.")
                current = self._record(profile_id)
                if current["revision"] != body["expected_revision"]:
                    raise WorkspacePowerError(409, "Workspace power revision changed; reload before editing.")
                if enabled and current["runtime_state"] == "STOPPING":
                    raise WorkspacePowerError(409, "Workspace is still stopping; wait before enabling.")
                if current["desired_enabled"] == enabled and current["runtime_state"] in (
                        ("ON", "STARTING") if enabled else ("OFF", "STOPPING")):
                    return self._response(current)
                portfolio = self.manager.portfolios.get(profile_id) or self._pending.get(profile_id)
                if enabled and portfolio is not None and portfolio._stop.is_set():
                    raise WorkspacePowerError(409, "Workspace cleanup is incomplete; retry switching it off first.")
            runners = self._guard_off(profile_id, portfolio, stack) if not enabled else []
            revision = current["revision"] + 1
            if revision > _MAX_REVISION:
                raise WorkspacePowerError(409, "Workspace power revision limit reached.")
            self._take(stack, self._persist_lock)
            self._save(profile_id, enabled, revision)
            with self._lock:
                self._explicit.add(profile_id)
                item = self._rows[profile_id]
                item.update(desired_enabled=enabled, revision=revision,
                            runtime_state="STARTING" if enabled else "STOPPING", error=None)
                if enabled:
                    self._cancel[profile_id] = threading.Event()
                else:
                    self._cancel[profile_id].set()
                    self._signal_stop(portfolio, runners)
                    # Construction can register an unpublished, gated runtime
                    # while persistence is in flight. Stop that latest object
                    # too, before it can begin another provider preparation.
                    latest = self._pending.get(profile_id)
                    if latest is not None and latest is not portfolio:
                        latest._stop.set()
                result = self._response(dict(item))
                if self._closed:
                    item["runtime_state"] = "STOPPING" if portfolio is not None else "OFF"
                    if portfolio is not None:
                        portfolio._stop.set()
                    result = self._response(dict(item))
                elif profile_id not in self._workers:
                    self._launch(profile_id, enabled)
            return result

    @staticmethod
    def _response(item):
        return {"ok": True, "workspace": item, "paper_only": True, "execution_authorized": False}

    def start(self):
        with self._lock:
            if self._closed or self._invalid:
                return
            for profile_id, item in self._rows.items():
                if (item["desired_enabled"] and profile_id not in self._workers
                        and profile_id not in self.manager.portfolios):
                    self._explicit.add(profile_id)
                    item.update(runtime_state="STARTING", error=None)
                    try:
                        self._launch(profile_id, True)
                    except WorkspacePowerError:
                        # One failed lifecycle thread must not suppress siblings.
                        continue

    def _drain(self, portfolio):
        if portfolio is None:
            return
        portfolio._stop.set()
        stop_failed = False
        try:
            portfolio.stop()
        except Exception:
            stop_failed = True
        threads = list(portfolio._threads.values())
        if portfolio._sampler_thread is not None:
            threads.append(portfolio._sampler_thread)
        for worker in threads:
            if worker is not threading.current_thread() and worker.is_alive():
                worker.join()
        return stop_failed

    def _transition(self, profile_id, starting):
        portfolio = None
        failed = False
        published = False
        try:
            if starting:
                cancel = self._cancel[profile_id]

                def created(value):
                    nonlocal portfolio
                    portfolio = value
                    value._workspace_power_gate = threading.Event()
                    with self._lock:
                        self._pending[profile_id] = value
                        if cancel.is_set() or self._closed:
                            value._stop.set()

                self.manager.create_portfolio(profile_id, cancelled=cancel.is_set, created=created)
                if not cancel.is_set():
                    portfolio.start()
                with self.manager.configuration_lock(profile_id), self._lock:
                    if not cancel.is_set() and not self._closed and self._rows[profile_id]["desired_enabled"]:
                        with self.manager._lock:
                            self.manager.portfolios[profile_id] = portfolio
                        self._pending.pop(profile_id, None)
                        self._rows[profile_id].update(runtime_state="ON", error=None)
                        portfolio._workspace_power_gate.set()
                        # Atomically release lifecycle ownership with ON. An
                        # immediately following OFF must launch its own drain.
                        self._workers.pop(profile_id, None)
                        published = True
                if published:
                    # Serialize enable/disable notifications per profile, with
                    # no controller, manager or configuration lock held. OFF
                    # remains STOPPING until an in-flight callback is retired.
                    try:
                        with self._notifications[profile_id]:
                            with self._lock:
                                active = (not self._closed and not cancel.is_set()
                                          and self.manager.portfolios.get(profile_id) is portfolio)
                            if active:
                                self._on_enabled(profile_id, portfolio)
                    except Exception:
                        with self._lock:
                            if self._rows[profile_id]["runtime_state"] == "ON":
                                self._rows[profile_id]["error"] = "Workspace panels could not start; paper runtime remains on."
                    return
            else:
                with self._lock:
                    portfolio = self.manager.portfolios.get(profile_id) or self._pending.get(profile_id)
        except InterruptedError:
            failed = not self._cancel[profile_id].is_set()
        except Exception:
            failed = True
        finally:
            # Successful publication keeps its workers and journal alive.
            if not published:
                try:
                    with self._notifications[profile_id]:
                        self._on_disabled(profile_id)
                except Exception:
                    failed = True
                try:
                    with self.manager.configuration_lock(profile_id):
                        # A shutdown may race an already accepted edit. Wait for
                        # its complete worker map before collecting/joining it.
                        # New edits reject this stopped portfolio, so draining
                        # can release the selected lock for responsive readers.
                        pass
                    failed = self._drain(portfolio) or failed
                    with self.manager.configuration_lock(profile_id):
                        with self._lock:
                            with self.manager._lock:
                                if self.manager.portfolios.get(profile_id) is portfolio:
                                    self.manager.portfolios.pop(profile_id, None)
                            self._pending.pop(profile_id, None)
                        if portfolio is not None:
                            portfolio.journal.close()
                except Exception:
                    failed = True
                with self._lock:
                    self._rows[profile_id].update(
                        runtime_state="ERROR" if failed else "OFF",
                        error="Workspace lifecycle failed; check local diagnostics before retrying." if failed else None)
                    # Publish completion and release ownership atomically. A
                    # new ON must never observe OFF with an old worker handle.
                    if self._workers.get(profile_id) is threading.current_thread():
                        self._workers.pop(profile_id, None)

    def close(self):
        # Shutdown never rewrites desired state. A subsequent process restores
        # only the user's saved enabled workspaces, even after a slow drain.
        with self._lock:
            if self._closed:
                return
            self._closed = True
            for profile_id, item in self._rows.items():
                self._explicit.add(profile_id)
                self._cancel[profile_id].set()
                portfolio = self.manager.portfolios.get(profile_id) or self._pending.get(profile_id)
                if portfolio is not None:
                    portfolio._stop.set()
                if portfolio is not None or profile_id in self._workers:
                    item["runtime_state"] = "STOPPING"
                    if profile_id not in self._workers:
                        try:
                            self._launch(profile_id, False)
                        except WorkspacePowerError:
                            continue
            workers = list(self._workers.values())
        deadline = time.monotonic() + 0.1
        for worker in workers:
            worker.join(max(0.0, deadline - time.monotonic()))
