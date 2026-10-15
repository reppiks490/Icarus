"""Per-person dashboard access registry and transparent security activity log."""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path


class AccessRegistry:
    """Store token digests only; added accounts receive read-only dashboard access."""

    def __init__(self, base_dir: str | Path, owner_token: str):
        self.path = Path(base_dir) / "access_registry.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
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
            digest = self._digest(owner_token)
            row = db.execute("SELECT id FROM users WHERE role='owner' LIMIT 1").fetchone()
            if row:
                db.execute("UPDATE users SET token_hash=?, active=1 WHERE id=?", (digest, row[0]))
            else:
                db.execute("INSERT INTO users(id,label,role,token_hash,created_at) VALUES('owner','Owner','owner',?,?)", (digest,time.time()))

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def authenticate(self, token: str) -> dict | None:
        if not token:
            return None
        now = time.time()
        with self._lock, self._db() as db:
            row = db.execute("SELECT * FROM users WHERE token_hash=? AND active=1", (self._digest(token),)).fetchone()
            if not row:
                return None
            db.execute("UPDATE users SET last_seen=?, request_count=request_count+1 WHERE id=?", (now,row["id"]))
            db.execute("INSERT INTO events(at,user_id,kind,detail) VALUES(?,?,?,?)", (now,row["id"],"access","Authenticated dashboard/API request"))
            return {"id":row["id"], "label":row["label"], "role":row["role"]}

    def is_active_token(self, token: str) -> bool:
        """Check a token without changing activity or security-event records."""
        if not token:
            return False
        with self._lock, self._db() as db:
            return db.execute(
                "SELECT 1 FROM users WHERE token_hash=? AND active=1",
                (self._digest(token),),
            ).fetchone() is not None

    def failed_auth(self, detail="Rejected bearer token"):
        with self._lock, self._db() as db:
            db.execute("INSERT INTO events(at,kind,detail) VALUES(?,?,?)", (time.time(),"failed_auth",detail))

    def add(self, label: str) -> dict:
        clean = " ".join(str(label).split())[:80]
        if not clean:
            raise ValueError("label is required")
        token = secrets.token_urlsafe(32)
        user_id = secrets.token_hex(8)
        now = time.time()
        with self._lock, self._db() as db:
            db.execute("INSERT INTO users(id,label,role,token_hash,created_at) VALUES(?,?,?,?,?)", (user_id,clean,"viewer",self._digest(token),now))
            db.execute("INSERT INTO events(at,user_id,kind,detail) VALUES(?,?,?,?)", (now,user_id,"user_added",f"Viewer account added: {clean}"))
        return {"id":user_id,"label":clean,"role":"viewer","token":token}

    def kick(self, user_id: str) -> bool:
        if user_id == "owner":
            raise ValueError("owner access cannot be revoked here")
        with self._lock, self._db() as db:
            row = db.execute("SELECT label,active FROM users WHERE id=?", (user_id,)).fetchone()
            if not row:
                return False
            db.execute("UPDATE users SET active=0 WHERE id=?", (user_id,))
            db.execute("INSERT INTO events(at,user_id,kind,detail) VALUES(?,?,?,?)", (time.time(),user_id,"user_kicked",f"Viewer access revoked: {row['label']}"))
            return True

    def snapshot(self) -> dict:
        with self._lock, self._db() as db:
            users = [dict(x) for x in db.execute("SELECT id,label,role,active,created_at,last_seen,request_count FROM users ORDER BY role DESC,label COLLATE NOCASE")]
            events = [dict(x) for x in db.execute("SELECT at,user_id,kind,detail FROM events ORDER BY id DESC LIMIT 200")]
            since = time.time() - 86400
            counts = {row["kind"]: row["n"] for row in db.execute("SELECT kind,COUNT(*) AS n FROM events WHERE at>=? AND kind IN ('access','failed_auth') GROUP BY kind", (since,))}
        active = sum(bool(x["active"]) for x in users)
        return {"users":users,"active_users":active,"total_users":len(users),"events":events,
                "activity_summary":{"window_hours":24,"authenticated_requests_24h":counts.get("access",0),
                                    "failed_auth_24h":counts.get("failed_auth",0)},
                "privacy_note":"Cues are recorded security events only (authenticated requests, failed authentication, account changes). No psychological or trading-behavior inference is performed."}
