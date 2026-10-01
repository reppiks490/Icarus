"""Durable causal evidence store for ICARUS APEX Ω."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import threading
from typing import Any, Mapping

from .contracts import authority_flags, evidence_id, normalize_evidence, parse_utc


class ApexStore:
    """SQLite-WAL store for immutable APEX evidence."""

    def __init__(self, base_dir: str | os.PathLike[str]):
        self.base_dir = Path(base_dir)
        self.path = self.base_dir / "research" / "apex.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, timeout=10.0, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self.journal_mode = str(self._conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]).lower()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS evidence (
                    evidence_id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    calculated_at TEXT NOT NULL,
                    observed_ts REAL NOT NULL,
                    received_ts REAL NOT NULL,
                    local_received_ts REAL,
                    semantic_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_apex_evidence_asof
                    ON evidence(observed_ts, received_ts);
                CREATE INDEX IF NOT EXISTS idx_apex_evidence_subject_asof
                    ON evidence(subject, observed_ts, received_ts);
                CREATE TABLE IF NOT EXISTS beliefs (
                    belief_id TEXT PRIMARY KEY,
                    semantic_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_ts REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS belief_events (
                    event_id TEXT PRIMARY KEY,
                    belief_id TEXT NOT NULL REFERENCES beliefs(belief_id),
                    state TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    event_at TEXT NOT NULL,
                    event_ts REAL NOT NULL,
                    semantic_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_apex_belief_events_asof
                    ON belief_events(belief_id, event_ts);
                CREATE TABLE IF NOT EXISTS participant_states (
                    state_id TEXT PRIMARY KEY,
                    asset TEXT NOT NULL,
                    as_of TEXT NOT NULL,
                    as_of_ts REAL NOT NULL,
                    semantic_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_apex_participant_states_asof
                    ON participant_states(as_of_ts, asset);
                CREATE TABLE IF NOT EXISTS force_fields (
                    field_id TEXT PRIMARY KEY,
                    asset TEXT NOT NULL,
                    as_of TEXT NOT NULL,
                    as_of_ts REAL NOT NULL,
                    semantic_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_apex_force_fields_asof
                    ON force_fields(as_of_ts, asset);
                CREATE TABLE IF NOT EXISTS causal_edges (
                    edge_id TEXT PRIMARY KEY,
                    horizon_seconds INTEGER NOT NULL,
                    observed_ts REAL NOT NULL,
                    received_ts REAL NOT NULL,
                    semantic_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_apex_causal_edges_asof
                    ON causal_edges(received_ts, horizon_seconds);
                CREATE TABLE IF NOT EXISTS cascade_edges (
                    edge_id TEXT PRIMARY KEY,
                    as_of TEXT NOT NULL,
                    as_of_ts REAL NOT NULL,
                    semantic_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_apex_cascade_edges_asof
                    ON cascade_edges(as_of_ts);
                CREATE TABLE IF NOT EXISTS world_states (
                    world_record_id TEXT PRIMARY KEY,
                    world_id TEXT NOT NULL,
                    as_of TEXT NOT NULL,
                    as_of_ts REAL NOT NULL,
                    semantic_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_apex_world_states_asof
                    ON world_states(as_of_ts, world_id);
                CREATE TABLE IF NOT EXISTS unknown_force_events (
                    event_id TEXT PRIMARY KEY,
                    as_of TEXT NOT NULL,
                    as_of_ts REAL NOT NULL,
                    semantic_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_apex_unknown_force_asof
                    ON unknown_force_events(as_of_ts);
                CREATE TABLE IF NOT EXISTS theory_records (
                    theory_id TEXT PRIMARY KEY,
                    semantic_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_ts REAL NOT NULL,
                    valid_from_ts REAL NOT NULL,
                    valid_until_ts REAL
                );
                CREATE TABLE IF NOT EXISTS theory_events (
                    event_id TEXT PRIMARY KEY,
                    theory_id TEXT NOT NULL REFERENCES theory_records(theory_id),
                    state TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    event_at TEXT NOT NULL,
                    event_ts REAL NOT NULL,
                    semantic_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_apex_theory_events_asof
                    ON theory_events(theory_id, event_ts);
                CREATE TABLE IF NOT EXISTS model_credibility (
                    record_id TEXT PRIMARY KEY,
                    model_id TEXT NOT NULL,
                    as_of TEXT NOT NULL,
                    as_of_ts REAL NOT NULL,
                    semantic_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_apex_model_credibility_asof
                    ON model_credibility(as_of_ts, model_id);
                CREATE TABLE IF NOT EXISTS reality_gap (
                    record_id TEXT PRIMARY KEY,
                    model_id TEXT NOT NULL,
                    as_of TEXT NOT NULL,
                    as_of_ts REAL NOT NULL,
                    semantic_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_apex_reality_gap_asof
                    ON reality_gap(as_of_ts, model_id);
                CREATE TABLE IF NOT EXISTS conscience_verdicts (
                    record_id TEXT PRIMARY KEY,
                    belief_id TEXT NOT NULL,
                    as_of TEXT NOT NULL,
                    as_of_ts REAL NOT NULL,
                    semantic_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_apex_conscience_asof
                    ON conscience_verdicts(as_of_ts, belief_id);
                """
            )
            evidence_columns = {
                str(row["name"]) for row in self._conn.execute("PRAGMA table_info(evidence)").fetchall()
            }
            if "local_received_ts" not in evidence_columns:
                self._conn.execute("ALTER TABLE evidence ADD COLUMN local_received_ts REAL")
            self._conn.execute(
                "UPDATE evidence SET local_received_ts=received_ts WHERE local_received_ts IS NULL"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_apex_evidence_local_asof "
                "ON evidence(observed_ts, received_ts, local_received_ts)"
            )

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _decode_row(self, row: sqlite3.Row) -> dict[str, Any]:
        try:
            semantic = json.loads(row["semantic_json"])
        except (TypeError, json.JSONDecodeError) as ex:
            raise ValueError("stored evidence semantic_json is invalid") from ex
        if not isinstance(semantic, dict):
            raise ValueError("stored evidence semantic_json must be an object")
        if semantic.get("execution_authorized") is not False or semantic.get("production_decision_authorized") is not False:
            raise ValueError("stored evidence cannot authorize execution or production")
        if evidence_id(semantic) != row["evidence_id"]:
            raise ValueError("stored evidence identity mismatch")
        out = dict(semantic)
        out["evidence_id"] = row["evidence_id"]
        out["recorded_at"] = row["recorded_at"]
        local_received_ts = row["local_received_ts"]
        out["local_received_at"] = (
            None
            if local_received_ts is None
            else datetime.fromtimestamp(float(local_received_ts), timezone.utc).isoformat().replace("+00:00", "Z")
        )
        return out

    def record_evidence(
        self,
        body: Mapping[str, Any],
        *,
        local_received_at: str | None = None,
    ) -> dict[str, Any]:
        semantic = normalize_evidence(body)
        eid = evidence_id(semantic)
        observed_ts = parse_utc(semantic["observed_at"], "observed_at").timestamp()
        received_ts = parse_utc(semantic["received_at"], "received_at").timestamp()
        if local_received_at is None:
            local_received_ts = received_ts
            recorded_at = self._utc_now()
        else:
            local_received_dt = parse_utc(local_received_at, "local_received_at")
            local_received_ts = local_received_dt.timestamp()
            recorded_at = local_received_dt.isoformat().replace("+00:00", "Z")
        raw = json.dumps(semantic, sort_keys=True, separators=(",", ":"), allow_nan=False)

        with self._lock, self._conn:
            cur = self._conn.execute(
                """
                INSERT OR IGNORE INTO evidence(
                    evidence_id, subject, kind, observed_at, received_at,
                    calculated_at, observed_ts, received_ts, local_received_ts,
                    semantic_json, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (eid, semantic["subject"], semantic["kind"], semantic["observed_at"],
                 semantic["received_at"], semantic["calculated_at"], observed_ts,
                 received_ts, local_received_ts, raw, recorded_at),
            )
            row = self._conn.execute("SELECT * FROM evidence WHERE evidence_id = ?", (eid,)).fetchone()
        if row is None:
            raise RuntimeError("evidence write did not persist")
        evidence = self._decode_row(row)
        return {"ok": True, "idempotent": cur.rowcount == 0, "evidence": evidence, **authority_flags()}

    def evidence_as_of(self, as_of: str, *, subject: str | None = None) -> list[dict[str, Any]]:
        boundary = parse_utc(as_of, "as_of").timestamp()
        sql = (
            "SELECT * FROM evidence WHERE observed_ts <= ? AND received_ts <= ? "
            "AND COALESCE(local_received_ts, received_ts) <= ?"
        )
        params: list[Any] = [boundary, boundary, boundary]
        if subject is not None:
            if not isinstance(subject, str) or not subject.strip():
                raise ValueError("subject filter must be a non-empty string")
            sql += " AND subject = ?"
            params.append(subject.strip())
        sql += " ORDER BY observed_ts, received_ts, evidence_id"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                out.append(self._decode_row(row))
            except ValueError:
                continue
        return out

    def integrity_status(self) -> dict[str, Any]:
        with self._lock:
            quick = str(self._conn.execute("PRAGMA quick_check").fetchone()[0])
            rows = self._conn.execute("SELECT * FROM evidence ORDER BY evidence_id").fetchall()
        corrupt: list[str] = []
        for row in rows:
            try:
                self._decode_row(row)
            except ValueError:
                corrupt.append(str(row["evidence_id"]))
        sqlite_ok = quick.lower() == "ok"
        return {
            "schema_version": "icarus-apex-store-v1",
            "journal_mode": self.journal_mode,
            "sqlite_ok": sqlite_ok,
            "integrity_ok": sqlite_ok and not corrupt,
            "evidence_rows": len(rows),
            "corrupt_rows": len(corrupt),
            "quarantined_evidence_ids": corrupt,
            **authority_flags(),
        }

    @staticmethod
    def _research_state_semantic(body: Mapping[str, Any], *, id_field: str) -> tuple[dict[str, Any], str, str, float]:
        if not isinstance(body, Mapping):
            raise ValueError("research state must be an object")
        semantic = dict(body)
        semantic.pop(id_field, None)
        semantic.pop("recorded_at", None)
        if semantic.get("execution_authorized") is not False or semantic.get("production_decision_authorized") is not False:
            raise ValueError("research state cannot authorize execution or production")
        asset = semantic.get("asset")
        if not isinstance(asset, str) or not asset.strip():
            raise ValueError("research state asset is required")
        asset = asset.strip().upper()
        semantic["asset"] = asset
        as_of = semantic.get("as_of")
        if not isinstance(as_of, str):
            raise ValueError("research state as_of is required")
        as_of_ts = parse_utc(as_of, "as_of").timestamp()
        try:
            raw = json.dumps(semantic, sort_keys=True, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as ex:
            raise ValueError("research state must be finite JSON") from ex
        import hashlib
        state_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return semantic, state_id, raw, as_of_ts

    def _record_research_state(self, table: str, id_field: str, body: Mapping[str, Any]) -> dict[str, Any]:
        if table not in {"participant_states", "force_fields"}:
            raise ValueError("unsupported research state table")
        semantic, state_id, raw, as_of_ts = self._research_state_semantic(body, id_field=id_field)
        recorded_at = self._utc_now()
        sql = f"INSERT OR IGNORE INTO {table}({id_field}, asset, as_of, as_of_ts, semantic_json, recorded_at) VALUES(?,?,?,?,?,?)"
        with self._lock, self._conn:
            cur = self._conn.execute(sql, (state_id, semantic["asset"], semantic["as_of"], as_of_ts, raw, recorded_at))
        return {"ok": True, "idempotent": cur.rowcount == 0, id_field: state_id, **authority_flags()}

    def _research_states_as_of(self, table: str, id_field: str, as_of: str, *, asset: str | None = None) -> list[dict[str, Any]]:
        if table not in {"participant_states", "force_fields"}:
            raise ValueError("unsupported research state table")
        boundary = parse_utc(as_of, "as_of").timestamp()
        sql = f"SELECT * FROM {table} WHERE as_of_ts <= ?"
        params: list[Any] = [boundary]
        if asset is not None:
            if not isinstance(asset, str) or not asset.strip():
                raise ValueError("asset filter must be non-empty")
            sql += " AND asset = ?"
            params.append(asset.strip().upper())
        sql += f" ORDER BY as_of_ts, {id_field}"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                semantic = json.loads(row["semantic_json"])
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(semantic, dict):
                continue
            if semantic.get("execution_authorized") is not False or semantic.get("production_decision_authorized") is not False:
                continue
            item = dict(semantic)
            item[id_field] = row[id_field]
            item["recorded_at"] = row["recorded_at"]
            out.append(item)
        return out

    def record_participant_state(self, state: Mapping[str, Any]) -> dict[str, Any]:
        return self._record_research_state("participant_states", "state_id", state)

    def participant_states_as_of(self, as_of: str, *, asset: str | None = None) -> list[dict[str, Any]]:
        return self._research_states_as_of("participant_states", "state_id", as_of, asset=asset)

    def record_force_field(self, field: Mapping[str, Any]) -> dict[str, Any]:
        return self._record_research_state("force_fields", "field_id", field)

    def force_fields_as_of(self, as_of: str, *, asset: str | None = None) -> list[dict[str, Any]]:
        return self._research_states_as_of("force_fields", "field_id", as_of, asset=asset)


    @staticmethod
    def _validate_research_authority(body: Mapping[str, Any]) -> None:
        if body.get("execution_authorized") is not False or body.get("production_decision_authorized") is not False:
            raise ValueError("research authority escalation is forbidden")

    def record_causal_edge(self, edge: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(edge, Mapping):
            raise ValueError("causal edge must be an object")
        semantic = dict(edge)
        self._validate_research_authority(semantic)
        eid = semantic.get("edge_id")
        if not isinstance(eid, str) or not eid.strip():
            raise ValueError("causal edge_id is required")
        horizon = semantic.get("horizon_seconds")
        if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon <= 0:
            raise ValueError("horizon_seconds must be a positive integer")
        observed_ts = parse_utc(str(semantic.get("observed_at") or ""), "observed_at").timestamp()
        received_ts = parse_utc(str(semantic.get("received_at") or ""), "received_at").timestamp()
        if received_ts < observed_ts:
            raise ValueError("received_at cannot precede observed_at")
        raw = json.dumps(semantic, sort_keys=True, separators=(",", ":"), allow_nan=False)
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO causal_edges(edge_id,horizon_seconds,observed_ts,received_ts,semantic_json,recorded_at) VALUES(?,?,?,?,?,?)",
                (eid.strip(), horizon, observed_ts, received_ts, raw, self._utc_now()),
            )
        return {"ok": True, "idempotent": cur.rowcount == 0, "edge_id": eid.strip(), **authority_flags()}

    def causal_edges_as_of(self, as_of: str, *, horizon_seconds: int | None = None) -> list[dict[str, Any]]:
        boundary = parse_utc(as_of, "as_of").timestamp()
        sql = "SELECT * FROM causal_edges WHERE observed_ts<=? AND received_ts<=?"
        params: list[Any] = [boundary, boundary]
        if horizon_seconds is not None:
            sql += " AND horizon_seconds=?"
            params.append(horizon_seconds)
        sql += " ORDER BY received_ts, edge_id"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        out=[]
        for row in rows:
            try:
                semantic=json.loads(row["semantic_json"])
            except (TypeError,json.JSONDecodeError):
                continue
            if not isinstance(semantic,dict):
                continue
            try:
                self._validate_research_authority(semantic)
            except ValueError:
                continue
            out.append(semantic)
        return out

    def record_cascade_edge(self, edge: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(edge, Mapping):
            raise ValueError("cascade edge must be an object")
        semantic = dict(edge)
        self._validate_research_authority(semantic)
        eid = semantic.get("edge_id")
        if not isinstance(eid, str) or not eid.strip():
            raise ValueError("cascade edge_id is required")
        as_of = semantic.get("as_of")
        if not isinstance(as_of, str):
            raise ValueError("cascade as_of is required")
        as_of_ts=parse_utc(as_of,"as_of").timestamp()
        raw=json.dumps(semantic,sort_keys=True,separators=(",",":"),allow_nan=False)
        with self._lock,self._conn:
            cur=self._conn.execute(
                "INSERT OR IGNORE INTO cascade_edges(edge_id,as_of,as_of_ts,semantic_json,recorded_at) VALUES(?,?,?,?,?)",
                (eid.strip(),as_of,as_of_ts,raw,self._utc_now()),
            )
        return {"ok":True,"idempotent":cur.rowcount==0,"edge_id":eid.strip(),**authority_flags()}

    def cascade_edges_as_of(self, as_of: str) -> list[dict[str, Any]]:
        boundary=parse_utc(as_of,"as_of").timestamp()
        with self._lock:
            rows=self._conn.execute("SELECT * FROM cascade_edges WHERE as_of_ts<=? ORDER BY as_of_ts,edge_id",(boundary,)).fetchall()
        out=[]
        for row in rows:
            try:
                semantic=json.loads(row["semantic_json"])
            except (TypeError,json.JSONDecodeError):
                continue
            if not isinstance(semantic,dict):
                continue
            try:
                self._validate_research_authority(semantic)
            except ValueError:
                continue
            out.append(semantic)
        return out


    def record_world_state(self, world: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(world, Mapping):
            raise ValueError("world state must be an object")
        semantic=dict(world)
        self._validate_research_authority(semantic)
        world_id=semantic.get("world_id")
        if not isinstance(world_id,str) or not world_id.strip():
            raise ValueError("world_id is required")
        as_of=semantic.get("as_of")
        if not isinstance(as_of,str):
            raise ValueError("world as_of is required")
        as_of_ts=parse_utc(as_of,"as_of").timestamp()
        try:
            raw=json.dumps(semantic,sort_keys=True,separators=(",",":"),allow_nan=False)
        except (TypeError,ValueError) as ex:
            raise ValueError("world state must be finite JSON") from ex
        import hashlib
        rid=hashlib.sha256(raw.encode("utf-8")).hexdigest()
        with self._lock,self._conn:
            cur=self._conn.execute(
                "INSERT OR IGNORE INTO world_states(world_record_id,world_id,as_of,as_of_ts,semantic_json,recorded_at) VALUES(?,?,?,?,?,?)",
                (rid,world_id.strip(),as_of,as_of_ts,raw,self._utc_now()),
            )
        return {"ok":True,"idempotent":cur.rowcount==0,"world_record_id":rid,**authority_flags()}

    def world_states_as_of(self, as_of: str) -> list[dict[str, Any]]:
        boundary=parse_utc(as_of,"as_of").timestamp()
        with self._lock:
            rows=self._conn.execute("SELECT * FROM world_states WHERE as_of_ts<=? ORDER BY as_of_ts,world_record_id",(boundary,)).fetchall()
        out=[]
        for row in rows:
            try:
                semantic=json.loads(row["semantic_json"])
            except (TypeError,json.JSONDecodeError):
                continue
            if not isinstance(semantic,dict):
                continue
            try:
                self._validate_research_authority(semantic)
            except ValueError:
                continue
            item=dict(semantic); item["world_record_id"]=row["world_record_id"]; item["recorded_at"]=row["recorded_at"]; out.append(item)
        return out

    def record_unknown_force(self, event: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(event, Mapping):
            raise ValueError("unknown-force event must be an object")
        semantic=dict(event)
        self._validate_research_authority(semantic)
        eid=semantic.get("event_id")
        if not isinstance(eid,str) or not eid.strip():
            raise ValueError("event_id is required")
        as_of=semantic.get("as_of")
        if not isinstance(as_of,str):
            raise ValueError("unknown-force as_of is required")
        as_of_ts=parse_utc(as_of,"as_of").timestamp()
        raw=json.dumps(semantic,sort_keys=True,separators=(",",":"),allow_nan=False)
        with self._lock,self._conn:
            cur=self._conn.execute(
                "INSERT OR IGNORE INTO unknown_force_events(event_id,as_of,as_of_ts,semantic_json,recorded_at) VALUES(?,?,?,?,?)",
                (eid.strip(),as_of,as_of_ts,raw,self._utc_now()),
            )
        return {"ok":True,"idempotent":cur.rowcount==0,"event_id":eid.strip(),**authority_flags()}

    def unknown_force_events_as_of(self, as_of: str) -> list[dict[str, Any]]:
        boundary=parse_utc(as_of,"as_of").timestamp()
        with self._lock:
            rows=self._conn.execute("SELECT * FROM unknown_force_events WHERE as_of_ts<=? ORDER BY as_of_ts,event_id",(boundary,)).fetchall()
        out=[]
        for row in rows:
            try:
                semantic=json.loads(row["semantic_json"])
            except (TypeError,json.JSONDecodeError):
                continue
            if not isinstance(semantic,dict):
                continue
            try:
                self._validate_research_authority(semantic)
            except ValueError:
                continue
            item=dict(semantic); item["recorded_at"]=row["recorded_at"]; out.append(item)
        return out


    def _record_temporal_state(self, table: str, subject_field: str, body: Mapping[str, Any]) -> dict[str, Any]:
        allowed={"model_credibility":"model_id","reality_gap":"model_id","conscience_verdicts":"belief_id"}
        if allowed.get(table) != subject_field:
            raise ValueError("unsupported temporal state table")
        if not isinstance(body, Mapping):
            raise ValueError("temporal state must be an object")
        semantic=dict(body)
        self._validate_research_authority(semantic)
        subject=semantic.get(subject_field)
        if not isinstance(subject,str) or not subject.strip():
            raise ValueError(f"{subject_field} is required")
        as_of=semantic.get("as_of")
        if not isinstance(as_of,str):
            raise ValueError("as_of is required")
        as_of_ts=parse_utc(as_of,"as_of").timestamp()
        try:
            raw=json.dumps(semantic,sort_keys=True,separators=(",",":"),allow_nan=False)
        except (TypeError,ValueError) as ex:
            raise ValueError("temporal state must be finite JSON") from ex
        import hashlib
        rid=hashlib.sha256(raw.encode("utf-8")).hexdigest()
        with self._lock,self._conn:
            cur=self._conn.execute(
                f"INSERT OR IGNORE INTO {table}(record_id,{subject_field},as_of,as_of_ts,semantic_json,recorded_at) VALUES(?,?,?,?,?,?)",
                (rid,subject.strip(),as_of,as_of_ts,raw,self._utc_now()),
            )
        return {"ok":True,"idempotent":cur.rowcount==0,"record_id":rid,**authority_flags()}

    def _temporal_states_as_of(self, table: str, subject_field: str, as_of: str) -> list[dict[str, Any]]:
        allowed={"model_credibility":"model_id","reality_gap":"model_id","conscience_verdicts":"belief_id"}
        if allowed.get(table) != subject_field:
            raise ValueError("unsupported temporal state table")
        boundary=parse_utc(as_of,"as_of").timestamp()
        with self._lock:
            rows=self._conn.execute(
                f"SELECT * FROM {table} WHERE as_of_ts<=? ORDER BY as_of_ts,record_id",
                (boundary,),
            ).fetchall()
        out=[]
        for row in rows:
            try:
                semantic=json.loads(row["semantic_json"])
            except (TypeError,json.JSONDecodeError):
                continue
            if not isinstance(semantic,dict):
                continue
            try:
                self._validate_research_authority(semantic)
            except ValueError:
                continue
            item=dict(semantic); item["record_id"]=row["record_id"]; item["recorded_at"]=row["recorded_at"]; out.append(item)
        return out

    def record_model_credibility(self, state: Mapping[str, Any]) -> dict[str, Any]:
        return self._record_temporal_state("model_credibility","model_id",state)

    def model_credibility_as_of(self, as_of: str) -> list[dict[str, Any]]:
        return self._temporal_states_as_of("model_credibility","model_id",as_of)

    def record_reality_gap(self, state: Mapping[str, Any]) -> dict[str, Any]:
        return self._record_temporal_state("reality_gap","model_id",state)

    def reality_gap_as_of(self, as_of: str) -> list[dict[str, Any]]:
        return self._temporal_states_as_of("reality_gap","model_id",as_of)

    def record_conscience_verdict(self, state: Mapping[str, Any]) -> dict[str, Any]:
        return self._record_temporal_state("conscience_verdicts","belief_id",state)

    def conscience_verdicts_as_of(self, as_of: str) -> list[dict[str, Any]]:
        return self._temporal_states_as_of("conscience_verdicts","belief_id",as_of)
