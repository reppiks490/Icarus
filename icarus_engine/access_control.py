"""Per-person dashboard access registry and transparent security activity log."""
from __future__ import annotations

import hashlib
import logging
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path


class AccessUnavailable(RuntimeError):
    """Authority could not be read; this is not an invalid credential."""


class AccessRegistry:
    """Store token digests only; added accounts receive read-only dashboard access."""

    def __init__(self, base_dir: str | Path, owner_token: str):
        self.path = Path(base_dir) / "access_registry.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._flush_lock = threading.Lock()
        self._pending = {}
        self._overflow_occurrences = 0
        self._last_flush_at = None
        self._audit_error = None
        self._flushing_requests = 0
        self._stop = threading.Event()
        self._thread = None
        self._closed = False
        with self._db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, label TEXT NOT NULL, role TEXT NOT NULL,
                    token_hash TEXT UNIQUE NOT NULL, active INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL, last_seen REAL, request_count INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL,
                    user_id TEXT, kind TEXT NOT NULL, detail TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS events_at ON events(at DESC);
            """)
            if "occurrences" not in {row[1] for row in db.execute("PRAGMA table_info(events)")}:
                db.execute("ALTER TABLE events ADD COLUMN occurrences INTEGER NOT NULL DEFAULT 1")
            digest = self._digest(owner_token)
            row = db.execute("SELECT id FROM users WHERE role='owner' LIMIT 1").fetchone()
            if row:
                db.execute("UPDATE users SET token_hash=?, active=1 WHERE id=?", (digest, row[0]))
            else:
                db.execute("INSERT INTO users(id,label,role,token_hash,created_at) VALUES('owner','Owner','owner',?,?)", (digest,time.time()))

    @contextmanager
    def _db(self, *, readonly=False):
        # Authentication must never queue behind activity writers. Read-only
        # connections retain the committed SQLite authority on every request;
        # even an exclusive lock fails closed promptly rather than timing out
        # the entire dashboard or trusting a cached, revoked credential.
        target = self.path.absolute().as_uri() + "?mode=ro" if readonly else self.path
        db = None
        try:
            db = sqlite3.connect(target, timeout=.05, uri=readonly)
            db.row_factory = sqlite3.Row
            yield db
            db.commit()
        except sqlite3.DatabaseError as exc:
            if db is not None:
                db.rollback()
            raise AccessUnavailable("Access registry is temporarily unavailable") from exc
        except BaseException:
            if db is not None:
                db.rollback()
            raise
        finally:
            if db is not None:
                db.close()

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _read_identity(self, token: str) -> dict | None:
        if not token:
            return None
        with self._db(readonly=True) as db:
            row = db.execute("SELECT id,label,role FROM users WHERE token_hash=? AND active=1", (self._digest(token),)).fetchone()
            if not row:
                return None
            if row["role"] not in ("owner", "viewer"):
                raise AccessUnavailable("Access registry role is unavailable")
            identity = {"id":row["id"], "label":row["label"], "role":row["role"]}
        return identity

    def authenticate(self, token: str) -> dict | None:
        identity = self._read_identity(token)
        if identity is not None:
            self._enqueue(identity["id"], "access", "Authenticated dashboard/API requests")
        return identity

    def is_active_token(self, token: str) -> bool:
        """Check a token without changing activity or security-event records."""
        return self._read_identity(token) is not None

    def failed_auth(self, detail="Rejected bearer token"):
        self._enqueue(None, "failed_auth", " ".join(str(detail).split())[:160])

    def _merge_pending(self, user_id, kind, detail, count, at):
        key = (user_id, kind, detail)
        if key not in self._pending and len(self._pending) >= 128:
            key = (None, kind, "Activity coalesced after bounded audit buffer filled")
            if detail != "Activity coalesced after bounded audit buffer filled":
                self._overflow_occurrences += count
        previous = self._pending.get(key, (0, at))
        self._pending[key] = (previous[0] + count, max(previous[1], at))

    def _enqueue(self, user_id, kind, detail):
        with self._lock:
            self._merge_pending(user_id, kind, detail, 1, time.time())

    def flush(self):
        """Persist a bounded activity batch outside request authentication."""
        if not self._flush_lock.acquire(blocking=False):
            return False
        try:
            with self._lock:
                batch, self._pending = self._pending, {}
                self._flushing_requests = sum(value[0] for value in batch.values())
            if not batch:
                return True
            try:
                with self._db() as db:
                    for (user_id, kind, detail), (count, at) in batch.items():
                        if kind == "access" and user_id is not None:
                            db.execute("UPDATE users SET last_seen=MAX(COALESCE(last_seen,0),?),request_count=request_count+? WHERE id=?",
                                       (at,count,user_id))
                        db.execute("INSERT INTO events(at,user_id,kind,detail,occurrences) VALUES(?,?,?,?,?)",
                                   (at,user_id,kind,detail if count == 1 else f"{detail} ({count} requests)",count))
            except AccessUnavailable:
                with self._lock:
                    for key, (count, at) in batch.items():
                        self._merge_pending(*key, count, at)
                    self._flushing_requests = 0
                    self._audit_error = "AUDIT_STORAGE_UNAVAILABLE"
                return False
            with self._lock:
                self._last_flush_at, self._audit_error = time.time(), None
                self._flushing_requests = 0
            return True
        finally:
            self._flush_lock.release()

    def audit_status(self):
        with self._lock:
            return {"pending_groups": len(self._pending),
                    "pending_requests": sum(value[0] for value in self._pending.values()) + self._flushing_requests,
                    "overflow_coalesced_requests": self._overflow_occurrences,
                    "last_flush_at": self._last_flush_at, "error": self._audit_error,
                    "basis": "batched activity counts at batch observation time; overflow loses per-user detail, not total counts"}

    def start(self):
        with self._lock:
            if self._closed or self._thread is not None:
                return
            self._thread = threading.Thread(target=self._run, name="icarus-access-audit", daemon=True)
            self._thread.start()

    def _run(self):
        while not self._stop.wait(.5):
            self.flush()

    def close(self):
        with self._lock:
            self._closed = True
            self._stop.set()
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(.2)
        self.flush()
        if self.audit_status()["pending_requests"]:
            logging.getLogger(__name__).warning("Access activity remains unpersisted; inspect audit storage availability")

    def add(self, label: str) -> dict:
        clean = " ".join(str(label).split())[:80]
        if not clean:
            raise ValueError("label is required")
        token = secrets.token_urlsafe(32)
        user_id = secrets.token_hex(8)
        now = time.time()
        with self._db() as db:
            db.execute("INSERT INTO users(id,label,role,token_hash,created_at) VALUES(?,?,?,?,?)", (user_id,clean,"viewer",self._digest(token),now))
            db.execute("INSERT INTO events(at,user_id,kind,detail) VALUES(?,?,?,?)", (now,user_id,"user_added",f"Viewer account added: {clean}"))
        return {"id":user_id,"label":clean,"role":"viewer","token":token}

    def kick(self, user_id: str) -> bool:
        if user_id == "owner":
            raise ValueError("owner access cannot be revoked here")
        with self._db() as db:
            row = db.execute("SELECT label,active FROM users WHERE id=?", (user_id,)).fetchone()
            if not row:
                return False
            db.execute("UPDATE users SET active=0 WHERE id=?", (user_id,))
            db.execute("INSERT INTO events(at,user_id,kind,detail) VALUES(?,?,?,?)", (time.time(),user_id,"user_kicked",f"Viewer access revoked: {row['label']}"))
            return True

    def snapshot(self) -> dict:
        self.flush()
        with self._db(readonly=True) as db:
            users = [dict(x) for x in db.execute("SELECT id,label,role,active,created_at,last_seen,request_count FROM users ORDER BY role DESC,label COLLATE NOCASE")]
            events = [dict(x) for x in db.execute("SELECT at,user_id,kind,detail,occurrences FROM events ORDER BY id DESC LIMIT 200")]
            since = time.time() - 86400
            counts = {row["kind"]: row["n"] for row in db.execute("SELECT kind,SUM(occurrences) AS n FROM events WHERE at>=? AND kind IN ('access','failed_auth') GROUP BY kind", (since,))}
        active = sum(bool(x["active"]) for x in users)
        return {"users":users,"active_users":active,"total_users":len(users),"events":events,
                "activity_audit": self.audit_status(),
                "activity_summary":{"window_hours":24,"authenticated_requests_24h":counts.get("access",0),
                                    "failed_auth_24h":counts.get("failed_auth",0)},
                "privacy_note":"Cues are recorded security events only (authenticated requests, failed authentication, account changes). No psychological or trading-behavior inference is performed."}
