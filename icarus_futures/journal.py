# CL (Claude, Anthropic) — 2026-10-04 — icarus_futures.journal: crash-safe append-only hash-chained execution journal
"""Every intent, venue event and decision is appended as one JSON line carrying the
SHA-256 of the previous line, then flushed and fsynced. On restart the journal is
replayed: a torn final line (process died mid-write) is reported and ignored; a broken
chain anywhere else is corruption and replay refuses (fail closed)."""
from __future__ import annotations

import hashlib
import json
import os

GENESIS = "0" * 64


class JournalCorrupt(RuntimeError):
    pass


class Journal:
    def __init__(self, path: str):
        self.path = path
        self.last_hash = GENESIS
        self.torn_tail = False
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        if os.path.exists(path):
            for rec in self.replay():
                self.last_hash = rec["hash"]

    def append(self, kind: str, payload: dict) -> dict:
        body = dict(kind=kind, payload=payload, prev=self.last_hash)
        raw = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
        rec = dict(body, hash=hashlib.sha256(raw.encode()).hexdigest())
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, sort_keys=True, separators=(",", ":"), default=str) + "\n")
            f.flush()
            os.fsync(f.fileno())
        self.last_hash = rec["hash"]
        return rec

    def replay(self):
        out, prev = [], GENESIS
        with open(self.path, encoding="utf-8") as f:
            lines = f.read().split("\n")
        if lines and lines[-1] == "":
            lines = lines[:-1]
        for i, line in enumerate(lines):
            try:
                rec = json.loads(line)
            except ValueError:
                if i == len(lines) - 1:
                    self.torn_tail = True  # died mid-write: the last record never committed
                    break
                raise JournalCorrupt(f"unparseable record at line {i + 1}")
            body = {k: rec[k] for k in ("kind", "payload", "prev")}
            raw = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
            if rec.get("prev") != prev or hashlib.sha256(raw.encode()).hexdigest() != rec.get("hash"):
                raise JournalCorrupt(f"hash chain broken at line {i + 1}")
            prev = rec["hash"]
            out.append(rec)
        return out
