# Grok (xAI) — 2026-09-22. Whole file.
from __future__ import annotations
import json
from pathlib import Path
from icarus_engine.events.calendar import event_features, load_events
from icarus_engine.trainers.dataset import load_ohlc

def _sign(x):
    if x is None or x == 0:
        return 0
    return 1 if x > 0 else -1

def _asof(exec_ts, cand):
    lo, hi, hit = 0, len(cand) - 1, None
    while lo <= hi:
        mid = (lo + hi) // 2
        if cand[mid]["ts"] <= exec_ts:
            hit = cand[mid]; lo = mid + 1
        else:
            hi = mid - 1
    return hit

def score_pair(exec_bars, cand_bars, events, asset, future):
    hits = agree = tide_agree = tide_n = ev_agree = ev_n = 0
    for i, b in enumerate(exec_bars[1:], start=1):
        prev = exec_bars[i - 1]
        c = _asof(b["ts"], cand_bars)
        if c is None:
            continue
        cp = _asof(prev["ts"], cand_bars)
        if cp is None or c["ts"] == cp["ts"]:
            continue
        y = _sign(b["close"] - prev["close"])
        x = _sign(c["close"] - cp["close"])
        if y == 0 or x == 0:
            continue
        hits += 1
        if x == y:
            agree += 1
        tide = (c.get("tide_long") or 0) - (c.get("tide_short") or 0)
        if tide:
            tide_n += 1
            if _sign(tide) == y:
                tide_agree += 1
        ev = event_features(b["ts"], events, future)
        if ev["any_macro"] or ev["earnings"]:
            ev_n += 1
            if x == y:
                ev_agree += 1
    status, reason = "eligible", ""
    if hits < 200:
        status, reason = "reject", f"overlap {hits} < 200"
        if ev_n and ev_agree / ev_n >= 0.55:
            status, reason = "eligible_macro_exceeds", "quiet fail, macro window beats 0.55"
    return {
        "status": status, "reason": reason, "execution": future, "candidate": asset,
        "overlap": hits,
        "sign_agree": (agree / hits) if hits else None,
        "tide_agree": (tide_agree / tide_n) if tide_n else None,
        "tide_n": tide_n, "macro_overlap": ev_n,
        "macro_agree": (ev_agree / ev_n) if ev_n else None,
        "execution_authorized": False,
    }

def write_audit(report, dest):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, allow_nan=False))
    return dest
