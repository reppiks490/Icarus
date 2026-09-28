# Claude (Opus 5.5) — 2026-09-27. Holdout-consumption ledger. A terminal interval one study has scored cannot
# be presented as untouched evidence for a different study. Any doubt fails closed.
from __future__ import annotations
import os, sqlite3
from datetime import datetime, timezone
from pathlib import Path
NEW, REPLAY, OVERLAP = "NEW", "REPLAY", "OVERLAP_SAME_STUDY"
REUSE, UNAVAILABLE = "BLOCKED_HOLDOUT_REUSE", "LEDGER_UNAVAILABLE"
SCORED = (NEW, REPLAY, OVERLAP)      # the holdout may be scored; only NEW and REPLAY can qualify

# slot: each model slot answers its own question, so slots keep separate claims on the same interval.
_SCHEMA = """CREATE TABLE IF NOT EXISTS holdout (
    slot TEXT NOT NULL, symbol TEXT NOT NULL, family TEXT NOT NULL, hold_start REAL NOT NULL,
    hold_end REAL NOT NULL, rows_sha256 TEXT NOT NULL, study_sha256 TEXT NOT NULL, n_hold INTEGER NOT NULL,
    first_seen_utc TEXT NOT NULL,
    PRIMARY KEY (slot, symbol, family, hold_start, hold_end, rows_sha256, study_sha256))"""

def canonical() -> Path:
    """The one ledger every trainer claims in and every validator trusts: $ICARUS_LEDGER, else
    ~/.icarus/holdout_ledger.sqlite3. A path relative to the working directory let a run from another folder or
    worktree start a fresh ledger and call a spent holdout NEW."""
    env = os.environ.get("ICARUS_LEDGER", "").strip()
    return (Path(env) if env else Path.home() / ".icarus" / "holdout_ledger.sqlite3").resolve()

def claim_holdout(path, symbol, family, start, end, rows_sha256, study_sha256, n_hold, slot="xgb"):
    """Record the claim before the holdout is scored. Returns NEW, REPLAY, OVERLAP_SAME_STUDY,
    BLOCKED_HOLDOUT_REUSE (a different study already scored an overlapping interval) or LEDGER_UNAVAILABLE."""
    start, end = float(start), float(end)
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(str(path), timeout=30, isolation_level=None)
        try:
            db.execute(_SCHEMA)
            db.execute("BEGIN IMMEDIATE")      # read-decide-write under one write lock: concurrent claims serialize
            try:
                seen = db.execute(
                    "SELECT hold_start, hold_end, rows_sha256, study_sha256 FROM holdout "
                    "WHERE slot = ? AND symbol = ? AND family = ? AND hold_start <= ? AND ? <= hold_end",
                    (slot, symbol, family, end, start)).fetchall()
                if any(row[3] != study_sha256 for row in seen):
                    status = REUSE
                elif (start, end, rows_sha256, study_sha256) in seen:
                    status = REPLAY
                else:
                    db.execute("INSERT INTO holdout VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                               (slot, symbol, family, start, end, rows_sha256, study_sha256, int(n_hold),
                                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")))
                    status = OVERLAP if seen else NEW
                db.execute("COMMIT")
                return status
            except BaseException:
                db.execute("ROLLBACK")
                raise
        finally:
            db.close()
    except (sqlite3.Error, OSError):
        return UNAVAILABLE

def holdout_recorded(path, symbol, family, start, end, rows_sha256, study_sha256, slot="xgb"):
    """True if exactly this claim is in the ledger, False if not, None if the ledger cannot be read."""
    try:
        path = Path(path)
        if not path.is_file():
            return None
        db = sqlite3.connect(str(path))      # a file: URI breaks on UNC shares; query_only keeps it read-only
        try:
            db.execute("PRAGMA query_only = ON")
            row = db.execute(
                "SELECT 1 FROM holdout WHERE slot = ? AND symbol = ? AND family = ? AND hold_start = ? "
                "AND hold_end = ? AND rows_sha256 = ? AND study_sha256 = ?",
                (slot, symbol, family, float(start), float(end), rows_sha256, study_sha256)).fetchone()
        finally:
            db.close()
    except (sqlite3.Error, OSError, ValueError, TypeError):
        return None
    return row is not None
