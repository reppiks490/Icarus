"""Deterministic research evidence; clocks in integer nanoseconds."""
from __future__ import annotations
import hashlib
import json
import math

DOMAINS = frozenset(("synthetic", "historical", "paper"))

def digest(body):
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")).hexdigest()

def integer(x):
    if type(x) is not int or x < 0:
        raise ValueError("expected nonnegative integer")
    return x

def probability(x):
    if type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 1:
        raise ValueError("invalid probability")
    return float(x)

def capsule(rows, decision_ns):
    """Admit only observed prefix; reject malformed clocks or duplicate IDs."""
    integer(decision_ns)
    seen=set(); prefix=[]
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"),str) or not row["id"] or row["id"] in seen:
            raise ValueError("invalid or repeated event identity")
        seen.add(row["id"])
        try:
            clocks=[integer(row[k]) for k in ("event_ns","available_ns","ingested_ns")]
        except KeyError as exc:
            raise ValueError("missing clock") from exc
        if clocks != sorted(clocks):
            raise ValueError("invalid clock ordering")
        if clocks[-1] <= decision_ns:
            prefix.append(json.loads(json.dumps(row,allow_nan=False)))
    prefix.sort(key=lambda x:(x["ingested_ns"],x["available_ns"],x["event_ns"],x["id"]))
    result={"schema":"umbra.capsule.v1","decision_ns":decision_ns,"events":prefix}
    return {**result,"digest":digest(result)}

class Ledger:
    """Append-only in-memory reference ledger; NOT an authenticated persistent store."""
    def __init__(self):
        self.entries=[]
    def _append(self,body):
        prev=self.entries[-1]["hash"] if self.entries else "0"*64
        row={"previous_hash":prev,"body":body}
        self.entries.append({**row,"hash":digest(row)})
    def verify(self):
        prev="0"*64
        try:
            for row in self.entries:
                if row["previous_hash"] != prev or row["hash"] != digest({"previous_hash":prev,"body":row["body"]}):
                    return False
                prev=row["hash"]
            return True
        except (ValueError,TypeError,KeyError):
            return False
    def forecast(self,identity,decision_ns,target_ns,p,domain):
        if not self.verify(): raise ValueError("ledger integrity failure")
        if not isinstance(identity,str) or not identity or domain not in DOMAINS:
            raise ValueError("invalid forecast identity or domain")
        if integer(target_ns)<=integer(decision_ns):
            raise ValueError("target must follow decision")
        if any(r["body"]["id"]==identity for r in self.entries):
            raise ValueError("duplicate forecast")
        self._append({"kind":"forecast","id":identity,"decision_ns":decision_ns,"target_ns":target_ns,"probability":probability(p),"domain":domain})
    def settle(self,identity,available_ns,label,domain):
        if not self.verify(): raise ValueError("ledger integrity failure")
        matching=[r["body"] for r in self.entries if r["body"]["id"]==identity]
        if len(matching)!=1 or matching[0]["kind"]!="forecast":
            raise ValueError("unknown or already settled forecast")
        f=matching[0]
        if domain!=f["domain"] or integer(available_ns)<f["target_ns"] or type(label) is not int or label not in (0,1):
            raise ValueError("invalid settlement")
        self._append({"kind":"settlement","id":identity,"available_ns":available_ns,"label":label,"domain":domain,"forecast_hash":next(r["hash"] for r in self.entries if r["body"]==f)})
