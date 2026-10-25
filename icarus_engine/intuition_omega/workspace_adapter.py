"""Selected-workspace, research-only Learning Fabric bridge.

Status reads are read-only and never initialize either SQLite database. A
Learning Fabric import is explicit, owner-gated by the HTTP layer, and runs in
a background worker so a long private-history scan cannot hold an HTTP request
or dashboard navigation open.
"""
from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
from pathlib import Path
import threading
import time
import uuid

from .calibration import ForecastLedger
from .learning_bridge import import_verified_learning_pairs


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class IntuitionWorkspaceAdapter:
    """Read and explicitly import only one workspace's private Learning state."""

    def __init__(self, root: str | Path, *, workspace_id: str):
        self.root = Path(root)
        self.workspace_id = workspace_id
        self.learning_path = self.root / "research" / "learning.sqlite3"
        self.ledger_dir = self.root / "intuition-omega"
        self.ledger_path = self.ledger_dir / "forecasts.sqlite3"
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._closed = False
        self._thread: threading.Thread | None = None
        self._job = {"status": "NOT_STARTED", "job_id": None, "result": None, "error": None}

    @staticmethod
    def _reject_symlinks(path: Path) -> None:
        # Check only the selected chain; a read must not walk an entire private
        # runtime tree, which can be large on the owner's Windows installation.
        for item in (path, *path.parents):
            if item.is_symlink():
                raise ValueError("selected private state must not use symlinks")

    def _ledger_status(self) -> dict:
        if not self.ledger_path.exists():
            return {"state": "NOT_INITIALIZED", "forecast_count": None,
                    "settled_count": None, "integrity": "NOT_CHECKED"}
        try:
            self._reject_symlinks(self.ledger_path)
            uri = self.ledger_path.resolve().as_uri() + "?mode=ro"
            with sqlite3.connect(uri, uri=True, timeout=0.05) as db:
                db.execute("PRAGMA query_only=ON")
                deadline = time.monotonic() + 0.05
                db.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
                tables = {row[0] for row in db.execute(
                    "SELECT name FROM sqlite_schema WHERE type='table'"
                )}
                if not {"forecasts", "resolutions"} <= tables:
                    return {"state": "INCOMPATIBLE", "forecast_count": None,
                            "settled_count": None, "integrity": "NOT_CHECKED"}
                forecasts = db.execute("SELECT COUNT(*) FROM forecasts").fetchone()[0]
                settled = db.execute("SELECT COUNT(*) FROM resolutions").fetchone()[0]
            return {"state": "AVAILABLE", "forecast_count": forecasts,
                    "settled_count": settled, "integrity": "NOT_CHECKED"}
        except (OSError, sqlite3.Error, ValueError):
            return {"state": "UNAVAILABLE", "forecast_count": None,
                    "settled_count": None, "integrity": "NOT_CHECKED"}

    def snapshot(self) -> dict:
        try:
            self._reject_symlinks(self.root)
            self._reject_symlinks(self.learning_path)
            source_state = "AVAILABLE" if self.learning_path.is_file() else "NOT_INITIALIZED"
        except ValueError:
            source_state = "UNAVAILABLE"
        ledger = self._ledger_status()
        with self._lock:
            job = dict(self._job)
            active = self._thread is not None and self._thread.is_alive()
        if active:
            job["status"] = "RUNNING"
        if active:
            state = "RUNNING"
        elif ledger["state"] == "AVAILABLE":
            state = "RESEARCH_ONLY"
        elif source_state == "AVAILABLE":
            state = "SOURCE_AVAILABLE"
        elif source_state == "UNAVAILABLE" or ledger["state"] in {"UNAVAILABLE", "INCOMPATIBLE"}:
            state = "UNAVAILABLE"
        else:
            state = "NOT_INITIALIZED"
        return {
            "schema_version": "icarus-intuition-workspace.v1",
            "status": state,
            "workspace_id": self.workspace_id,
            "learning_source": {"state": source_state, "adapter": "selected Learning Fabric",
                                "source_mutated": False},
            "ledger": ledger,
            "import_job": job,
            "source_mutated": False,
            "production_decision_authorized": False,
            "execution_authorized": False,
        }

    def start_import(self) -> dict:
        self._reject_symlinks(self.root)
        self._reject_symlinks(self.learning_path)
        if not self.learning_path.is_file():
            raise ValueError("selected workspace Learning Fabric database is unavailable")
        with self._lock:
            if self._closed:
                raise ValueError("selected workspace adapter is closing")
            if self._thread is not None and self._thread.is_alive():
                return {"status": "RUNNING", "job_id": self._job["job_id"],
                        "execution_authorized": False, "production_decision_authorized": False}
            job_id = "intuition-" + uuid.uuid4().hex
            self._stop.clear()
            self._job = {"status": "RUNNING", "job_id": job_id,
                         "accepted_at": _now(), "result": None, "error": None}
            thread = threading.Thread(target=self._run_import, args=(job_id,), daemon=True,
                                      name=f"intuition-learning-import-{self.workspace_id}")
            self._thread = thread
            thread.start()
        return {"status": "RUNNING", "job_id": job_id,
                "execution_authorized": False, "production_decision_authorized": False}

    def _run_import(self, job_id: str) -> None:
        ledger = None
        try:
            if self._stop.is_set():
                raise InterruptedError("selected workspace is stopping")
            self._reject_symlinks(self.root)
            self._reject_symlinks(self.ledger_dir)
            self.ledger_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            self._reject_symlinks(self.ledger_path)
            ledger = ForecastLedger(self.ledger_path)
            result = import_verified_learning_pairs(
                self.learning_path, ledger, as_of=_now(), cancelled=self._stop.is_set,
            )
            status, error = "COMPLETED", None
        except InterruptedError:
            result, status, error = None, "CANCELLED", None
        except Exception as exc:
            if self._stop.is_set():
                result, status, error = None, "CANCELLED", None
            else:
                result, status = None, "FAILED"
                error = f"{type(exc).__name__}: {str(exc)[:240]}"
        finally:
            if ledger is not None:
                ledger.close()
        with self._lock:
            if self._job.get("job_id") == job_id:
                self._job = {**self._job, "status": status, "completed_at": _now(),
                             "result": result, "error": error}

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._stop.set()
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=0.1)
