"""Proof-carrying belief ledger for ICARUS APEX Ω."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any, Callable, Mapping, Sequence

from .ancestry import EvidenceAncestry
from .contracts import authority_flags, parse_utc
from .store import ApexStore

BELIEF_STATES = frozenset({"proposed", "supported", "strongly_supported", "contradicted", "invalid", "quarantined"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _text(value: Any, field: str, *, max_len: int = 1200) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    out = value.strip()
    if len(out) > max_len:
        raise ValueError(f"{field} exceeds {max_len} characters")
    return out


def _list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return [_text(x, f"{field} item", max_len=700) for x in value]


def _unit(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number")
    x = float(value)
    if not math.isfinite(x) or not 0.0 <= x <= 1.0:
        raise ValueError(f"{field} must be in [0, 1]")
    return x


def _json_obj(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    out = dict(value)
    try:
        json.dumps(out, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{field} must be finite JSON") from ex
    return out


def _hash(value: Mapping[str, Any]) -> str:
    raw = json.dumps(dict(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


class BeliefLedger:
    def __init__(self, store: ApexStore, *, ancestry: EvidenceAncestry | None = None, clock: Callable[[], str] | None = None):
        self.store = store
        self.ancestry = ancestry or EvidenceAncestry()
        self.clock = clock or _now

    def _normalize(self, body: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(body, Mapping):
            raise ValueError("belief must be an object")
        revision = _text(body.get("source_revision"), "source_revision", max_len=40).lower()
        if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
            raise ValueError("source_revision must be an exact 40-character Git SHA")
        return {
            "schema_version": "icarus-apex-belief-v1",
            "claim": _text(body.get("claim"), "claim", max_len=4000),
            "scope": _json_obj(body.get("scope", {}), "scope"),
            "source_revision": revision,
            "assumptions": _list(body.get("assumptions", []), "assumptions"),
            "contradictions": _list(body.get("contradictions", []), "contradictions"),
            "falsifiers": _list(body.get("falsifiers", []), "falsifiers"),
            "nominal_confidence": _unit(body.get("nominal_confidence"), "nominal_confidence"),
            "epistemic_uncertainty": _unit(body.get("epistemic_uncertainty"), "epistemic_uncertainty"),
            "aleatoric_uncertainty": _unit(body.get("aleatoric_uncertainty"), "aleatoric_uncertainty"),
            **authority_flags(),
        }

    def propose(self, body: Mapping[str, Any]) -> dict[str, Any]:
        semantic = self._normalize(body)
        bid = _hash(semantic)
        created_at = self.clock()
        created_ts = parse_utc(created_at, "created_at").timestamp()
        raw = json.dumps(semantic, sort_keys=True, separators=(",", ":"), allow_nan=False)
        event_sem = {"belief_id": bid, "state": "proposed", "evidence_ids": [], "reason": "proposed", "event_at": created_at}
        event_id = _hash(event_sem)
        with self.store._lock, self.store._conn:
            cur = self.store._conn.execute(
                "INSERT OR IGNORE INTO beliefs(belief_id, semantic_json, created_at, created_ts) VALUES(?,?,?,?)",
                (bid, raw, created_at, created_ts),
            )
            self.store._conn.execute(
                "INSERT OR IGNORE INTO belief_events(event_id, belief_id, state, evidence_json, reason, event_at, event_ts, semantic_json) VALUES(?,?,?,?,?,?,?,?)",
                (event_id, bid, "proposed", "[]", "proposed", created_at, created_ts, json.dumps(event_sem, sort_keys=True, separators=(",", ":"))),
            )
        belief = dict(semantic)
        belief.update({"belief_id": bid, "state": "proposed", "created_at": created_at})
        return {"ok": True, "idempotent": cur.rowcount == 0, "belief": belief, **authority_flags()}

    def _belief_row(self, belief_id: str):
        row = self.store._conn.execute("SELECT * FROM beliefs WHERE belief_id=?", (belief_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown belief {belief_id}")
        semantic = json.loads(row["semantic_json"])
        if not isinstance(semantic, dict):
            raise ValueError("stored belief is corrupt")
        return row, semantic

    def transition(self, belief_id: str, state: str, *, evidence_ids: Sequence[str], reason: str) -> dict[str, Any]:
        bid = _text(belief_id, "belief_id", max_len=64)
        state = _text(state, "state", max_len=32).lower()
        if state not in BELIEF_STATES - {"proposed"}:
            raise ValueError("unsupported belief transition state")
        reason = _text(reason, "reason", max_len=1200)
        ids = [_text(x, "evidence_id", max_len=64) for x in evidence_ids]
        if len(set(ids)) != len(ids):
            raise ValueError("evidence_ids must be unique")
        row, belief = self._belief_row(bid)
        event_at = self.clock()
        event_ts = parse_utc(event_at, "event_at").timestamp()
        if event_ts < float(row["created_ts"]):
            raise ValueError("belief event cannot predate proposal")
        available = {x["evidence_id"] for x in self.store.evidence_as_of(event_at)}
        if any(eid not in available for eid in ids):
            raise ValueError("belief transition references evidence unavailable at event time")
        support = self.ancestry.effective_support(ids)
        if state in {"supported", "strongly_supported"}:
            if not belief.get("falsifiers"):
                raise ValueError("supported belief requires at least one falsifier")
            if not ids or not support.get("integrity_ok") or support.get("effective_independent_families", 0) < 1:
                raise ValueError("supported belief requires complete evidence ancestry")
        event_sem = {"belief_id": bid, "state": state, "evidence_ids": ids, "reason": reason, "event_at": event_at}
        event_id = _hash(event_sem)
        raw = json.dumps(event_sem, sort_keys=True, separators=(",", ":"), allow_nan=False)
        with self.store._lock, self.store._conn:
            cur = self.store._conn.execute(
                "INSERT OR IGNORE INTO belief_events(event_id, belief_id, state, evidence_json, reason, event_at, event_ts, semantic_json) VALUES(?,?,?,?,?,?,?,?)",
                (event_id, bid, state, json.dumps(ids, separators=(",", ":")), reason, event_at, event_ts, raw),
            )
        return {"ok": True, "idempotent": cur.rowcount == 0, "belief_id": bid, "state": state, "effective_support": support, **authority_flags()}

    def _state_as_of(self, belief_id: str, boundary_ts: float):
        return self.store._conn.execute(
            "SELECT * FROM belief_events WHERE belief_id=? AND event_ts<=? ORDER BY event_ts DESC, rowid DESC LIMIT 1",
            (belief_id, boundary_ts),
        ).fetchone()

    def as_of(self, as_of: str) -> list[dict[str, Any]]:
        boundary = parse_utc(as_of, "as_of").timestamp()
        rows = self.store._conn.execute("SELECT * FROM beliefs WHERE created_ts<=? ORDER BY created_ts, belief_id", (boundary,)).fetchall()
        out = []
        for row in rows:
            event = self._state_as_of(row["belief_id"], boundary)
            if event is None:
                continue
            semantic = json.loads(row["semantic_json"])
            semantic.update({"belief_id": row["belief_id"], "created_at": row["created_at"], "state": event["state"], "state_at": event["event_at"]})
            out.append(semantic)
        return out

    def proof_packet(self, belief_id: str, *, as_of: str | None = None) -> dict[str, Any]:
        bid = _text(belief_id, "belief_id", max_len=64)
        boundary_text = as_of or self.clock()
        boundary = parse_utc(boundary_text, "as_of").timestamp()
        row, semantic = self._belief_row(bid)
        if float(row["created_ts"]) > boundary:
            raise ValueError("belief did not exist at requested as_of")
        event = self._state_as_of(bid, boundary)
        if event is None:
            raise ValueError("belief has no state at requested as_of")
        ids = json.loads(event["evidence_json"])
        support = self.ancestry.effective_support(ids)
        return {
            "schema_version": "icarus-apex-proof-packet-v1",
            "belief_id": bid,
            "claim": semantic["claim"],
            "scope": semantic["scope"],
            "state": event["state"],
            "as_of": boundary_text,
            "source_revision": semantic["source_revision"],
            "assumptions": semantic["assumptions"],
            "contradictions": semantic["contradictions"],
            "falsifiers": semantic["falsifiers"],
            "evidence_ids": ids,
            "effective_support": support,
            "nominal_confidence": semantic["nominal_confidence"],
            "epistemic_uncertainty": semantic["epistemic_uncertainty"],
            "aleatoric_uncertainty": semantic["aleatoric_uncertainty"],
            **authority_flags(),
        }
