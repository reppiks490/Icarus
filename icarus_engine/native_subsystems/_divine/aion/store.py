"""Append-only, source-aware market ledger with verified historical as-of reads."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import json
import math
import sqlite3
import time

from .contracts import Observation, SourceSpec, canonical, digest, validate_source_event


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY, body TEXT NOT NULL, source_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    position INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    source_event_id TEXT NOT NULL, revision INTEGER NOT NULL,
    kind TEXT NOT NULL, symbol TEXT NOT NULL, representation_id TEXT NOT NULL,
    event_ns INTEGER NOT NULL, available_ns INTEGER NOT NULL, ingested_ns INTEGER NOT NULL,
    sequence INTEGER, plane TEXT NOT NULL, body TEXT NOT NULL,
    previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL UNIQUE,
    UNIQUE(source_id, source_event_id, revision)
);
CREATE INDEX IF NOT EXISTS events_asof ON events(available_ns, symbol, position);
CREATE TABLE IF NOT EXISTS source_gaps (
    source_id TEXT PRIMARY KEY REFERENCES sources(source_id),
    previous_sequence INTEGER NOT NULL, observed_sequence INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS source_gap_history (
    position INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    available_ns INTEGER NOT NULL, state TEXT NOT NULL CHECK(state IN ('gap','recovered')),
    previous_sequence INTEGER NOT NULL, observed_sequence INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS gap_history_asof ON source_gap_history(available_ns, position);
CREATE TABLE IF NOT EXISTS predictions (
    prediction_id TEXT PRIMARY KEY, decision_ns INTEGER NOT NULL,
    horizon_ns INTEGER NOT NULL, body TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settlements (
    prediction_id TEXT PRIMARY KEY REFERENCES predictions(prediction_id),
    outcome_ns INTEGER NOT NULL, body TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'immutable event'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'immutable event'); END;
CREATE TRIGGER IF NOT EXISTS gap_history_no_update BEFORE UPDATE ON source_gap_history BEGIN SELECT RAISE(ABORT, 'immutable gap transition'); END;
CREATE TRIGGER IF NOT EXISTS gap_history_no_delete BEFORE DELETE ON source_gap_history BEGIN SELECT RAISE(ABORT, 'immutable gap transition'); END;
CREATE TRIGGER IF NOT EXISTS sources_no_update BEFORE UPDATE ON sources BEGIN SELECT RAISE(ABORT, 'immutable source'); END;
CREATE TRIGGER IF NOT EXISTS sources_no_delete BEFORE DELETE ON sources BEGIN SELECT RAISE(ABORT, 'immutable source'); END;
CREATE TRIGGER IF NOT EXISTS predictions_no_update BEFORE UPDATE ON predictions BEGIN SELECT RAISE(ABORT, 'immutable prediction'); END;
CREATE TRIGGER IF NOT EXISTS predictions_no_delete BEFORE DELETE ON predictions BEGIN SELECT RAISE(ABORT, 'immutable prediction'); END;
CREATE TRIGGER IF NOT EXISTS settlements_no_update BEFORE UPDATE ON settlements BEGIN SELECT RAISE(ABORT, 'immutable settlement'); END;
CREATE TRIGGER IF NOT EXISTS settlements_no_delete BEFORE DELETE ON settlements BEGIN SELECT RAISE(ABORT, 'immutable settlement'); END;
"""


class GapError(ValueError):
    pass


class EventStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as con:
            con.executescript(SCHEMA)

    @contextmanager
    def _db(self):
        con = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA busy_timeout=30000")
        try:
            yield con
        finally:
            con.close()

    def register(self, source: SourceSpec) -> str:
        body = canonical(source.to_dict())
        source_hash = digest(source.to_dict())
        with self._db() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT body FROM sources WHERE source_id=?", (source.source_id,)).fetchone()
            if row and row["body"] != body:
                con.rollback()
                raise ValueError("source identity is immutable; register a versioned source_id")
            con.execute("INSERT OR IGNORE INTO sources VALUES (?,?,?)", (source.source_id, body, source_hash))
            con.commit()
        return source_hash

    def source(self, source_id: str) -> SourceSpec:
        with self._db() as con:
            row = con.execute("SELECT body FROM sources WHERE source_id=?", (source_id,)).fetchone()
        if not row:
            raise ValueError(f"unknown source {source_id}")
        return SourceSpec.from_dict(json.loads(row["body"]))

    def sources(self) -> list[dict]:
        with self._db() as con:
            return [json.loads(r["body"]) for r in con.execute("SELECT body FROM sources ORDER BY source_id")]

    def append(self, event: Observation) -> dict:
        source = self.source(event.source_id)
        validate_source_event(source, event)
        body = canonical(event.to_dict())
        recovery = event.kind == "book_snapshot" and "provider_recovery" in event.quality_flags
        with self._db() as con:
            con.execute("BEGIN IMMEDIATE")
            old = con.execute("SELECT body,event_hash,position FROM events WHERE source_id=? AND source_event_id=? AND revision=?",
                              (event.source_id, event.source_event_id, event.revision)).fetchone()
            if old:
                if old["body"] != body:
                    raise ValueError("conflicting immutable source event")
                con.commit()
                return {"position": old["position"], "event_hash": old["event_hash"], "idempotent": True}
            latest_revision = con.execute("SELECT revision,available_ns,body FROM events WHERE source_id=? AND source_event_id=? ORDER BY revision DESC LIMIT 1",
                                          (event.source_id, event.source_event_id)).fetchone()
            if latest_revision is not None:
                if event.revision <= latest_revision["revision"] or event.available_ns <= latest_revision["available_ns"]:
                    raise ValueError("revision and its availability must increase")
                if source.sequence_policy != "none":
                    raise ValueError("sequenced-stream corrections require a reviewed provider adapter")
                prior_event = json.loads(latest_revision["body"])
                if any(prior_event[key] != getattr(event, key) for key in ("kind", "event_ns", "plane")):
                    raise ValueError("revision cannot change fact identity")
            last = con.execute("SELECT sequence,available_ns FROM events WHERE source_id=? AND sequence IS NOT NULL ORDER BY position DESC LIMIT 1",
                               (event.source_id,)).fetchone()
            gap = con.execute("SELECT * FROM source_gaps WHERE source_id=?", (event.source_id,)).fetchone()
            if gap and not recovery:
                raise GapError("source gap unresolved; authenticated recovery snapshot required")
            if gap and recovery:
                gap_transition = con.execute(
                    "SELECT available_ns FROM source_gap_history WHERE source_id=? AND state='gap' ORDER BY position DESC LIMIT 1",
                    (event.source_id,),
                ).fetchone()
                if (not gap_transition or event.available_ns <= gap_transition["available_ns"]
                        or event.sequence < gap["observed_sequence"]):
                    raise GapError("recovery must follow the observed gap in time and sequence")
            if source.sequence_policy != "none" and last and event.available_ns < last["available_ns"]:
                raise ValueError("sequenced source availability reversed")
            if source.sequence_policy != "none" and last and event.sequence <= last["sequence"]:
                raise ValueError("source sequence reversed or repeated")
            if source.sequence_policy == "contiguous" and last and event.sequence != last["sequence"] + 1 and not recovery:
                con.execute("INSERT OR REPLACE INTO source_gaps VALUES (?,?,?)",
                            (event.source_id, last["sequence"], event.sequence))
                con.execute("INSERT INTO source_gap_history(source_id,available_ns,state,previous_sequence,observed_sequence) VALUES (?,?,?,?,?)",
                            (event.source_id, event.available_ns, "gap", last["sequence"], event.sequence))
                con.commit()
                raise GapError("source sequence gap persisted; replay invalidated")
            tail = con.execute("SELECT event_hash FROM events ORDER BY position DESC LIMIT 1").fetchone()
            previous = tail["event_hash"] if tail else "0" * 64
            event_hash = digest({"previous": previous, "source_hash": digest(source.to_dict()), "event": event.to_dict()})
            cursor = con.execute("""INSERT INTO events(source_id,source_event_id,revision,kind,symbol,representation_id,
                                  event_ns,available_ns,ingested_ns,sequence,plane,body,previous_hash,event_hash)
                                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                                 (event.source_id, event.source_event_id, event.revision, event.kind,
                                  source.symbol, source.representation_id, event.event_ns, event.available_ns,
                                  event.ingested_ns, event.sequence, event.plane, body, previous, event_hash))
            if recovery:
                if gap:
                    con.execute("INSERT INTO source_gap_history(source_id,available_ns,state,previous_sequence,observed_sequence) VALUES (?,?,?,?,?)",
                                (event.source_id, event.available_ns, "recovered", last["sequence"] if last else 0, event.sequence))
                con.execute("DELETE FROM source_gaps WHERE source_id=?", (event.source_id,))
            con.commit()
            return {"position": cursor.lastrowid, "event_hash": event_hash, "idempotent": False}

    def asof(self, timestamp_ns: int, *, symbol: str | None = None, plane: str | None = None,
             include_revisions: bool = False, max_position: int | None = None) -> list[dict]:
        if type(timestamp_ns) is not int or timestamp_ns < 0:
            raise ValueError("as-of time must be nonnegative integer nanoseconds")
        if max_position is not None and (type(max_position) is not int or max_position < 0):
            raise ValueError("invalid event ledger cutoff")
        sql = "SELECT * FROM events WHERE available_ns<=?"
        args: list = [timestamp_ns]
        if max_position is not None:
            sql += " AND position<=?"; args.append(max_position)
        if symbol is not None:
            sql += " AND symbol=?"; args.append(symbol)
        if plane is not None:
            sql += " AND plane=?"; args.append(plane)
        sql += " ORDER BY available_ns,position"
        with self._db() as con:
            rows = con.execute(sql, args).fetchall()
        if not include_revisions:
            latest = {}
            for row in rows:
                key = (row["source_id"], row["source_event_id"])
                if key not in latest or row["revision"] > latest[key]["revision"]:
                    latest[key] = row
            rows = sorted(latest.values(), key=lambda row: (row["available_ns"], row["position"]))
        return [{"event": json.loads(row["body"]), "source": row["source_id"], "symbol": row["symbol"],
                 "representation_id": row["representation_id"], "event_hash": row["event_hash"],
                 "position": row["position"]} for row in rows]

    def timeline(self, *, limit: int = 1000) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= 10000:
            raise ValueError("invalid timeline limit")
        with self._db() as con:
            rows = con.execute("SELECT available_ns,kind,symbol,representation_id,event_hash,position FROM events ORDER BY position DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in reversed(rows)]

    def gaps(self) -> list[dict]:
        with self._db() as con:
            return [dict(row) for row in con.execute("SELECT * FROM source_gaps ORDER BY source_id")]

    def gaps_asof(self, timestamp_ns: int, *, max_position: int | None = None) -> list[dict]:
        if type(timestamp_ns) is not int or timestamp_ns < 0:
            raise ValueError("as-of time must be nonnegative integer nanoseconds")
        if max_position is not None and (type(max_position) is not int or max_position < 0):
            raise ValueError("invalid gap ledger cutoff")
        sql = "SELECT * FROM source_gap_history WHERE available_ns<=?"
        args: list[int] = [timestamp_ns]
        if max_position is not None:
            sql += " AND position<=?"; args.append(max_position)
        sql += " ORDER BY available_ns,position"
        with self._db() as con:
            rows = con.execute(sql, args).fetchall()
        latest = {row["source_id"]: row for row in rows}
        return [dict(row) for source_id, row in sorted(latest.items()) if row["state"] == "gap"]

    def verify_chain(self) -> dict:
        previous = "0" * 64
        count = 0
        with self._db() as con:
            sources = {}
            for r in con.execute("SELECT source_id,body,source_hash FROM sources"):
                body = json.loads(r["body"])
                if r["source_hash"] != digest(body) or r["source_id"] != body["source_id"]:
                    raise ValueError(f"source manifest integrity mismatch: {r['source_id']}")
                sources[r["source_id"]] = body
            for row in con.execute("SELECT * FROM events ORDER BY position"):
                body = json.loads(row["body"])
                source = sources[row["source_id"]]
                if (row["source_event_id"] != body["source_event_id"] or row["revision"] != body["revision"]
                        or row["kind"] != body["kind"] or row["event_ns"] != body["event_ns"]
                        or row["available_ns"] != body["available_ns"] or row["ingested_ns"] != body["ingested_ns"]
                        or row["sequence"] != body["sequence"] or row["plane"] != body["plane"]
                        or row["symbol"] != source["symbol"] or row["representation_id"] != source["representation_id"]
                        or row["source_id"] != body["source_id"]):
                    raise ValueError(f"ledger indexed-column mismatch at position {row['position']}")
                expected = digest({"previous": previous, "source_hash": digest(sources[row["source_id"]]), "event": body})
                if row["previous_hash"] != previous or row["event_hash"] != expected:
                    raise ValueError(f"ledger hash-chain mismatch at position {row['position']}")
                previous = expected
                count += 1
        return {"events": count, "head_hash": previous, "verified": True}

    def predict(self, *, decision_ns: int, horizon_ns: int, model_id: str, symbol: str,
                forecast: float | None, confidence: float | None, abstain: bool,
                reason_codes: list[str], evidence_hashes: list[str], frame_hash: str,
                plane: str = "shadow") -> dict:
        if plane not in ("research", "shadow") or type(decision_ns) is not int or decision_ns < 0 or type(horizon_ns) is not int or horizon_ns <= decision_ns:
            raise ValueError("invalid prediction time or plane")
        if (not isinstance(model_id, str) or not model_id or not isinstance(symbol, str) or not symbol
                or type(abstain) is not bool or not isinstance(reason_codes, list) or not reason_codes
                or any(not isinstance(code, str) or not code for code in reason_codes)):
            raise ValueError("model, symbol, abstain and reasons required")
        if confidence is not None and (isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not math.isfinite(confidence) or not 0 <= confidence <= 1):
            raise ValueError("confidence must be in [0,1]")
        if abstain and forecast is not None:
            raise ValueError("abstention cannot carry a directional forecast")
        if not abstain and (not isinstance(forecast, (int, float)) or isinstance(forecast, bool) or not math.isfinite(forecast)):
            raise ValueError("forecast required unless abstaining")
        if (not isinstance(evidence_hashes, list) or not evidence_hashes
                or any(not isinstance(h, str) or len(h) != 64 or any(c not in "0123456789abcdef" for c in h) for h in evidence_hashes)
                or len(evidence_hashes) != len(set(evidence_hashes))):
            raise ValueError("a nonempty unique evidence set is required")
        with self._db() as con:
            con.execute("BEGIN IMMEDIATE")
            recorded_ns = time.time_ns()
            event_cutoff = con.execute("SELECT COALESCE(MAX(position),0) FROM events").fetchone()[0]
            gap_cutoff = con.execute("SELECT COALESCE(MAX(position),0) FROM source_gap_history").fetchone()[0]
            placeholders = ",".join("?" for _ in evidence_hashes)
            rows = con.execute(f"SELECT event_hash,available_ns,ingested_ns FROM events WHERE event_hash IN ({placeholders})", evidence_hashes).fetchall()
            if len(rows) != len(evidence_hashes) or any(r["available_ns"] > decision_ns for r in rows):
                raise ValueError("prediction references unknown or future evidence")
            from .replay import frame
            actual_frame = frame(self, decision_ns, max_event_position=event_cutoff,
                                 max_gap_position=gap_cutoff)
            if frame_hash != actual_frame["frame_hash"] or not set(evidence_hashes).issubset(actual_frame["evidence_hashes"]):
                raise ValueError("prediction frame differs from decision-time evidence")
            issuance_class = ("prospective_local_unattested"
                              if decision_ns <= recorded_ns < horizon_ns
                              and all(r["ingested_ns"] <= decision_ns for r in rows)
                              else "retrospective_replay")
            core = {"schema": 2, "decision_ns": decision_ns, "horizon_ns": horizon_ns,
                    "model_id": model_id, "symbol": symbol, "forecast": forecast,
                    "confidence": confidence, "abstain": abstain,
                    "frame_hash": frame_hash,
                    "reason_codes": reason_codes, "evidence_hashes": sorted(evidence_hashes),
                    "event_ledger_cutoff": event_cutoff, "gap_ledger_cutoff": gap_cutoff,
                    "plane": plane, "execution_authorized": False, "performance_eligible": False}
            prediction_id = digest(core)
            body = {**core, "recorded_ns": recorded_ns, "issuance_class": issuance_class}
            con.execute("INSERT OR IGNORE INTO predictions VALUES (?,?,?,?)",
                        (prediction_id, decision_ns, horizon_ns, canonical(body)))
            stored = con.execute("SELECT body FROM predictions WHERE prediction_id=?", (prediction_id,)).fetchone()
            con.commit()
        return {"prediction_id": prediction_id, **json.loads(stored["body"])}

    def frozen_frame(self, prediction_id: str) -> dict:
        with self._db() as con:
            row = con.execute("SELECT body FROM predictions WHERE prediction_id=?", (prediction_id,)).fetchone()
        if not row:
            raise ValueError("unknown prediction")
        prediction = json.loads(row["body"])
        if prediction.get("schema") != 2:
            raise ValueError("legacy prediction has no reconstructible ledger cutoff")
        from .replay import frame
        result = frame(self, prediction["decision_ns"],
                       max_event_position=prediction["event_ledger_cutoff"],
                       max_gap_position=prediction["gap_ledger_cutoff"])
        if result["frame_hash"] != prediction["frame_hash"]:
            raise ValueError("frozen prediction frame integrity mismatch")
        return result

    def settle(self, prediction_id: str, *, outcome_ns: int, realized_move: float,
               costs: float | None = None, slippage: float | None = None,
               outcome_reference: str) -> dict:
        if type(outcome_ns) is not int or not outcome_reference:
            raise ValueError("outcome time and reference required")
        from math import isfinite
        if not isinstance(realized_move, (int, float)) or isinstance(realized_move, bool) or not isfinite(realized_move):
            raise ValueError("finite realized move required")
        if any(value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool)
                                      or not isfinite(value) or value < 0) for value in (costs, slippage)):
            raise ValueError("costs and slippage must be nonnegative or unknown")
        with self._db() as con:
            con.execute("BEGIN IMMEDIATE")
            prior = con.execute("SELECT horizon_ns,body FROM predictions WHERE prediction_id=?", (prediction_id,)).fetchone()
            if not prior or outcome_ns < prior["horizon_ns"]:
                raise ValueError("prediction missing or horizon incomplete")
            body = {"prediction_id": prediction_id, "outcome_ns": outcome_ns,
                    "realized_move": realized_move, "costs": costs, "slippage": slippage,
                    "outcome_reference": outcome_reference, "outcome_verified": False,
                    "performance_eligible": False, "execution_authorized": False}
            encoded = canonical(body)
            old = con.execute("SELECT body FROM settlements WHERE prediction_id=?", (prediction_id,)).fetchone()
            if old and old["body"] != encoded:
                raise ValueError("settlement is immutable")
            con.execute("INSERT OR IGNORE INTO settlements VALUES (?,?,?)", (prediction_id, outcome_ns, encoded))
            con.commit()
        return body

    def predictions(self) -> list[dict]:
        with self._db() as con:
            rows = con.execute("""SELECT p.prediction_id,p.body,s.body AS outcome
                                  FROM predictions p LEFT JOIN settlements s USING(prediction_id)
                                  ORDER BY p.decision_ns,p.prediction_id""").fetchall()
        return [{"prediction_id": r["prediction_id"], "prediction": json.loads(r["body"]),
                 "settlement": json.loads(r["outcome"]) if r["outcome"] else None} for r in rows]
