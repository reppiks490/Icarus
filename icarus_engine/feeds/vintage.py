"""Append-only market-data observation provenance.

The canonical history CSV remains the latest captured view for compatibility.
This ledger preserves what ICARUS observed before later imports revise that view.

A first capture is not claimed to be the venue's original publication. It means only
"first version captured by this ICARUS ledger".
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Iterable

from ..pine.timeframe import Bar


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonical_hash(value) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return _sha256_bytes(raw)


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def ledger_path(root: str) -> str:
    return os.path.join(os.path.abspath(root), "history", "vintage.sqlite3")


class MarketDataVintageLedger:
    """Append-only provenance ledger for owner-observed OHLCV source batches."""

    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self.path = ledger_path(self.root)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=10)
        con.execute("PRAGMA foreign_keys=ON")
        return con

    def _init(self) -> None:
        with self._connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS ingest_batches (
                    batch_id TEXT PRIMARY KEY,
                    observed_ns INTEGER NOT NULL,
                    source_sha256 TEXT NOT NULL,
                    source_kind TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    minutes INTEGER NOT NULL,
                    row_count INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS bar_observations (
                    observation_id TEXT PRIMARY KEY,
                    batch_id TEXT NOT NULL REFERENCES ingest_batches(batch_id),
                    symbol TEXT NOT NULL,
                    minutes INTEGER NOT NULL,
                    event_ts INTEGER NOT NULL,
                    observed_ns INTEGER NOT NULL,
                    disposition TEXT NOT NULL,
                    value_sha256 TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    supersedes_observation_id TEXT,
                    UNIQUE(batch_id, event_ts)
                );

                CREATE INDEX IF NOT EXISTS idx_bar_observations_asof
                    ON bar_observations(symbol, minutes, event_ts, observed_ns);

                CREATE TRIGGER IF NOT EXISTS ingest_batches_no_update
                    BEFORE UPDATE ON ingest_batches
                    BEGIN SELECT RAISE(ABORT, 'immutable ingest batch'); END;
                CREATE TRIGGER IF NOT EXISTS ingest_batches_no_delete
                    BEFORE DELETE ON ingest_batches
                    BEGIN SELECT RAISE(ABORT, 'immutable ingest batch'); END;
                CREATE TRIGGER IF NOT EXISTS bar_observations_no_update
                    BEFORE UPDATE ON bar_observations
                    BEGIN SELECT RAISE(ABORT, 'immutable bar observation'); END;
                CREATE TRIGGER IF NOT EXISTS bar_observations_no_delete
                    BEFORE DELETE ON bar_observations
                    BEGIN SELECT RAISE(ABORT, 'immutable bar observation'); END;
                """
            )

    @staticmethod
    def _value_hash(bar: Bar) -> str:
        return _canonical_hash(
            {
                "ts": int(bar.ts),
                "open": float(bar.o),
                "high": float(bar.h),
                "low": float(bar.l),
                "close": float(bar.c),
                "volume": float(bar.v),
            }
        )

    def record_source(
        self,
        source_path: str,
        *,
        symbol: str,
        minutes: int,
        bars: Iterable[Bar],
        source_kind: str = "OWNER_CSV",
        observed_ns: int | None = None,
    ) -> dict:
        """Record an observed source batch before canonical-history mutation.

        The batch identity excludes path and arrival time so re-processing the exact
        same bytes for the same stream/source kind is idempotent.
        """
        rows = list(bars)
        source_hash = file_sha256(source_path)
        batch_id = _canonical_hash(
            {
                "source_sha256": source_hash,
                "source_kind": source_kind,
                "symbol": str(symbol).upper(),
                "minutes": int(minutes),
            }
        )
        seen_ns = int(time.time_ns() if observed_ns is None else observed_ns)
        source_abs = os.path.abspath(source_path)
        inserted = 0

        with self._connect() as con:
            exists = con.execute(
                "SELECT 1 FROM ingest_batches WHERE batch_id=?",
                (batch_id,),
            ).fetchone()
            if exists:
                return {
                    "batch_id": batch_id,
                    "source_sha256": source_hash,
                    "observations_inserted": 0,
                    "duplicate_batch": True,
                }

            con.execute(
                """
                INSERT INTO ingest_batches(
                    batch_id, observed_ns, source_sha256, source_kind,
                    source_path, symbol, minutes, row_count
                ) VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    batch_id,
                    seen_ns,
                    source_hash,
                    source_kind,
                    source_abs,
                    str(symbol).upper(),
                    int(minutes),
                    len(rows),
                ),
            )

            for bar in rows:
                value_hash = self._value_hash(bar)
                prior = con.execute(
                    """
                    SELECT observation_id, value_sha256
                    FROM bar_observations
                    WHERE symbol=? AND minutes=? AND event_ts=?
                    ORDER BY observed_ns DESC, observation_id DESC
                    LIMIT 1
                    """,
                    (str(symbol).upper(), int(minutes), int(bar.ts)),
                ).fetchone()
                if prior is None:
                    disposition = "FIRST_CAPTURED"
                    supersedes = None
                elif prior[1] == value_hash:
                    disposition = "SAME_AS_PRIOR"
                    supersedes = prior[0]
                else:
                    disposition = "REVISION"
                    supersedes = prior[0]

                observation_id = _canonical_hash(
                    {
                        "batch_id": batch_id,
                        "event_ts": int(bar.ts),
                    }
                )
                con.execute(
                    """
                    INSERT INTO bar_observations(
                        observation_id, batch_id, symbol, minutes, event_ts,
                        observed_ns, disposition, value_sha256,
                        open, high, low, close, volume, supersedes_observation_id
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        observation_id,
                        batch_id,
                        str(symbol).upper(),
                        int(minutes),
                        int(bar.ts),
                        seen_ns,
                        disposition,
                        value_hash,
                        float(bar.o),
                        float(bar.h),
                        float(bar.l),
                        float(bar.c),
                        float(bar.v),
                        supersedes,
                    ),
                )
                inserted += 1

        return {
            "batch_id": batch_id,
            "source_sha256": source_hash,
            "observations_inserted": inserted,
            "duplicate_batch": False,
        }
