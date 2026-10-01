"""Temporal theory library preserving negative results and historical knowledge."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib,json
from typing import Any, Callable, Mapping, Sequence
from .contracts import authority_flags, parse_utc
from .store import ApexStore
THEORY_STATES=frozenset({"supported","rejected","conditional","regime_specific","unresolved","obsolete"})
def _now()->str:return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def _text(value:Any,field:str,*,max_len:int=4000)->str:
    if not isinstance(value,str) or not value.strip():raise ValueError(f"{field} must be a non-empty string")
    out=value.strip()
    if len(out)>max_len:raise ValueError(f"{field} exceeds {max_len} characters")
    return out
def _hash(value:Mapping[str,Any])->str:return hashlib.sha256(json.dumps(dict(value),sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
class TheoryLibrary:
    def __init__(self,store:ApexStore,*,clock:Callable[[],str]|None=None):self.store=store;self.clock=clock or _now
    def record(self,body:Mapping[str,Any])->dict[str,Any]:
        if not isinstance(body,Mapping):raise ValueError("theory must be an object")
        revision=_text(body.get("source_revision"),"source_revision",max_len=40).lower()
        if len(revision)!=40 or any(c not in "0123456789abcdef" for c in revision):raise ValueError("source_revision must be an exact 40-character Git SHA")
        valid_from=_text(body.get("valid_from"),"valid_from",max_len=80);from_ts=parse_utc(valid_from,"valid_from").timestamp();raw_until=body.get("valid_until");valid_until=None if raw_until is None else _text(raw_until,"valid_until",max_len=80);until_ts=None if valid_until is None else parse_utc(valid_until,"valid_until").timestamp()
        if until_ts is not None and until_ts<from_ts:raise ValueError("valid_until cannot precede valid_from")
        semantic={"schema_version":"icarus-apex-theory-v1","claim":_text(body.get("claim"),"claim"),"scope":dict(body.get("scope") or {}),"source_revision":revision,"valid_from":valid_from,"valid_until":valid_until,"falsifiers":[_text(x,"falsifier",max_len=800) for x in (body.get("falsifiers") or [])],**authority_flags()}
        if not semantic["falsifiers"]:raise ValueError("theory requires at least one falsifier")
        tid=_hash(semantic);created_at=self.clock();created_ts=parse_utc(created_at,"created_at").timestamp();event_sem={"theory_id":tid,"state":"unresolved","evidence_ids":[],"reason":"recorded","event_at":created_at};event_id=_hash(event_sem);raw=json.dumps(semantic,sort_keys=True,separators=(",",":"),allow_nan=False)
        with self.store._lock,self.store._conn:
            cur=self.store._conn.execute("INSERT OR IGNORE INTO theory_records(theory_id,semantic_json,created_at,created_ts,valid_from_ts,valid_until_ts) VALUES(?,?,?,?,?,?)",(tid,raw,created_at,created_ts,from_ts,until_ts))
            self.store._conn.execute("INSERT OR IGNORE INTO theory_events(event_id,theory_id,state,evidence_json,reason,event_at,event_ts,semantic_json) VALUES(?,?,?,?,?,?,?,?)",(event_id,tid,"unresolved","[]","recorded",created_at,created_ts,json.dumps(event_sem,sort_keys=True,separators=(",",":"))))
        theory=dict(semantic);theory.update({"theory_id":tid,"state":"unresolved","created_at":created_at});return {"ok":True,"idempotent":cur.rowcount==0,"theory":theory,**authority_flags()}
    def transition(self,theory_id:str,state:str,*,evidence_ids:Sequence[str],reason:str)->dict[str,Any]:
        tid=_text(theory_id,"theory_id",max_len=64);state=_text(state,"state",max_len=32).lower()
        if state not in THEORY_STATES-{"unresolved"}:raise ValueError("unsupported theory transition")
        ids=[_text(x,"evidence_id",max_len=128) for x in evidence_ids]
        if len(set(ids))!=len(ids):raise ValueError("evidence_ids must be unique")
        reason=_text(reason,"reason",max_len=1200);row=self.store._conn.execute("SELECT * FROM theory_records WHERE theory_id=?",(tid,)).fetchone()
        if row is None:raise KeyError(f"unknown theory {tid}")
        event_at=self.clock();event_ts=parse_utc(event_at,"event_at").timestamp()
        if event_ts<float(row["created_ts"]):raise ValueError("theory event cannot predate record")
        event_sem={"theory_id":tid,"state":state,"evidence_ids":ids,"reason":reason,"event_at":event_at};event_id=_hash(event_sem)
        with self.store._lock,self.store._conn:
            cur=self.store._conn.execute("INSERT OR IGNORE INTO theory_events(event_id,theory_id,state,evidence_json,reason,event_at,event_ts,semantic_json) VALUES(?,?,?,?,?,?,?,?)",(event_id,tid,state,json.dumps(ids,separators=(",",":")),reason,event_at,event_ts,json.dumps(event_sem,sort_keys=True,separators=(",",":"))))
        return {"ok":True,"idempotent":cur.rowcount==0,"theory_id":tid,"state":state,**authority_flags()}
    def as_of(self,as_of:str)->list[dict[str,Any]]:
        boundary=parse_utc(as_of,"as_of").timestamp();rows=self.store._conn.execute("SELECT * FROM theory_records WHERE created_ts<=? AND valid_from_ts<=? AND (valid_until_ts IS NULL OR valid_until_ts>=?) ORDER BY created_ts,theory_id",(boundary,boundary,boundary)).fetchall();out=[]
        for row in rows:
            event=self.store._conn.execute("SELECT * FROM theory_events WHERE theory_id=? AND event_ts<=? ORDER BY event_ts DESC,rowid DESC LIMIT 1",(row["theory_id"],boundary)).fetchone()
            if event is None:continue
            try:semantic=json.loads(row["semantic_json"])
            except (TypeError,json.JSONDecodeError):continue
            if not isinstance(semantic,dict):continue
            item=dict(semantic);item.update({"theory_id":row["theory_id"],"created_at":row["created_at"],"state":event["state"],"state_at":event["event_at"],"reason":event["reason"],"evidence_ids":json.loads(event["evidence_json"])});out.append(item)
        return out
