"""Phase 11: exact-tick historical competing-risk first-passage laboratory.

The prime-successor concept generalizes to earliest satisfying event:
time-to-upper, time-to-lower, simultaneous OHLC-bar ambiguity, or censoring.

All labels are retrospective, require full lookahead horizon, and NEVER
represent a live forecast. Integer ticks protect price comparisons from
floating-point rounding and prevent fictitious sub-tick precision.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any, Mapping

from .contracts import identity, utc

_ASSET = re.compile(r"^[A-Z0-9._-]{1,24}$")
_ALLOWED = {"asset", "source_commit", "bars"}
_REQUIRED_BAR = {"record_id", "observed_at", "received_at",
                 "open_ticks", "high_ticks", "low_ticks", "close_ticks"}
_AUTHORITY = {"research_only": True, "execution_authorized": False,
              "production_decision_authorized": False, "auto_promote": False}


def _tick(x: Any, name: str) -> int:
    if type(x) is not int or not 1 <= x <= 10**12:
        raise ValueError(f"{name} requires exact positive integer ticks")
    return x


def normalize_tape(tape: Mapping[str, Any]) -> dict:
    if not isinstance(tape, Mapping) or set(tape) != _ALLOWED:
        raise ValueError("invalid event tape schema")
    asset = tape["asset"]
    commit = tape["source_commit"]
    if not isinstance(asset, str) or not _ASSET.fullmatch(asset):
        raise ValueError("invalid asset")
    if (not isinstance(commit, str) or len(commit) != 40
            or any(c not in "0123456789abcdef" for c in commit)):
        raise ValueError("source commit must be a lowercase Git SHA")
    raw = tape["bars"]
    if not isinstance(raw, list) or not 5 <= len(raw) <= 50000:
        raise ValueError("5–50000 observed bars required")
    prev_received = None
    seen = set()
    rows = []
    for bar in raw:
        if not isinstance(bar, Mapping) or set(bar) != _REQUIRED_BAR:
            raise ValueError("invalid bar schema")
        rid = bar["record_id"]
        if not isinstance(rid, str) or not 1 <= len(rid) <= 128 or rid in seen:
            raise ValueError("missing/duplicate event ID")
        seen.add(rid)
        observed = utc(bar["observed_at"])
        received = utc(bar["received_at"])
        if observed > received:
            raise ValueError("future bar observation")
        if prev_received is not None and received <= prev_received:
            raise ValueError("bar receipt time must strictly increase")
        prev_received = received
        o,h,l,c = (_tick(bar[key], key) for key in
                   ("open_ticks", "high_ticks", "low_ticks", "close_ticks"))
        if not l <= o <= h or not l <= c <= h:
            raise ValueError("inconsistent OHLC ticks")
        rows.append({"record_id":rid,"observed_at":observed.isoformat(),
                     "received_at":received.isoformat(),
                     "open_ticks":o,"high_ticks":h,
                     "low_ticks":l,"close_ticks":c})
    return {"asset":asset,"source_commit":commit,"bars":rows}


def label_first_passage(tape: Mapping[str, Any], *,
                        upper_distance_ticks: int,
                        lower_distance_ticks: int,
                        horizon_bars: int,
                        stride: int | None = None) -> dict:
    """Retrospective event labeling with explicit AMBIGUOUS and CENSORED rows.

    A labeled decision at bar i considers bars i+1 ... i+H.
    The bar whose high & low both cross boundaries cannot establish order.
    No labels for incomplete horizons; no data leak into as-of features.
    Non-overlap default stride=H minimizes overlapping episodes.
    """
    data=normalize_tape(tape)
    up=_tick(upper_distance_ticks,"upper_distance_ticks")
    down=_tick(lower_distance_ticks,"lower_distance_ticks")
    if type(horizon_bars) is not int or not 1 <= horizon_bars <= 500:
        raise ValueError("horizon_bars must be integer [1, 500]")
    if stride is None:
        stride=horizon_bars
    if type(stride) is not int or not horizon_bars <= stride <= 50000:
        raise ValueError("stride must be >= horizon, to prevent overlapping labels")
    bars=data["bars"]
    labels=[]
    pending=0
    for i in range(0,len(bars),stride):
        first=bars[i]
        if i+horizon_bars >= len(bars):
            pending+=1
            continue
        upper=first["close_ticks"]+up
        lower=first["close_ticks"]-down
        if lower <= 0 or upper > 10**12:
            raise ValueError("first-passage boundaries outside tick domain")
        event="CENSORED"
        offset=horizon_bars+1
        resolved=bars[i+horizon_bars]["received_at"]
        for j in range(1,horizon_bars+1):
            row=bars[i+j]
            hit_up=row["high_ticks"]>=upper
            hit_down=row["low_ticks"]<=lower
            if hit_up and hit_down:
                event="AMBIGUOUS_BOTH"
            elif hit_up:
                event="UPPER"
            elif hit_down:
                event="LOWER"
            else:
                continue
            offset=j
            resolved=row["received_at"]
            break
        labels.append({
            "decision_record_id":first["record_id"],
            "decision_at":first["received_at"],
            "source_record_id":first["record_id"],
            "label_resolved_at":resolved,
            "first_event_offset_bars":offset,
            "event":event,
            "upper_ticks":upper,
            "lower_ticks":lower,
            "label_is_ambiguous":event=="AMBIGUOUS_BOTH",
            "label_is_censored":event=="CENSORED",
        })
    counts=Counter(row["event"] for row in labels)
    report={
        "schema_version":"icarus-omnigenesis-first-passage-v1",
        "asset":data["asset"],
        "source_commit":data["source_commit"],
        "evidence_kind":"DERIVED_FROM_OBSERVED_TAPE",
        "tape_sha256":identity(data),
        "authority":dict(_AUTHORITY),
        "setup":{"upper_distance_ticks":up,"lower_distance_ticks":down,
                 "horizon_bars":horizon_bars,"stride":stride},
        "label_count":len(labels),
        "pending_count":pending,
        "counts":{key:counts[key] for key in
                  ("UPPER","LOWER","AMBIGUOUS_BOTH","CENSORED")},
        "limitations":[
            "OHLC cannot resolve intrabar high/low ordering",
            "not an execution model: spreads, fees, fills, latency excluded",
            "labels use future observed bars and cannot enter live signals",
            "censoring and ambiguous episodes must not be treated as negatives",
        ],
        "labels":labels,
    }
    report["report_id"]=identity(report)
    return report
