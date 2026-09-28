# Claude (Opus 5.5) — 2026-09-27. Strict-lead pairing shared by the candidate audit and the Slot 2 ranker.
# A candidate move is used once, against the first execution move decided after the candidate bar closed.
from __future__ import annotations
from icarus_engine.events.calendar import event_features_asof

CONTIGUOUS = ("renko", "range", "tick")   # a bar closes exactly when the next one opens

def _sign(x):
    if x is None or x == 0:
        return 0
    return 1 if x > 0 else -1

def completed_before(cand, decision_ts):
    """Index of the last candidate bar that had closed by decision_ts, or None. A bar is known to be closed once
    the next bar has opened; the final bar has no visible close and is never used."""
    lo, hi, hit = 0, len(cand) - 2, None
    while lo <= hi:
        mid = (lo + hi) // 2
        if cand[mid + 1]["ts"] <= decision_ts:
            hit = mid; lo = mid + 1
        else:
            hi = mid - 1
    return hit

def decision_times(exec_bars, family):
    """dec[i]: when the call on execution move i (bar i-1 close -> bar i close) is made, i.e. bar i-1's close.
    Contiguous bars close when the next opens. After a session gap the true close is not in the data, so only
    bar i-1's open is certain."""
    dec = [None] + [b["ts"] for b in exec_bars[1:]]
    if family in CONTIGUOUS or len(exec_bars) < 3:
        return dec
    diffs = sorted(exec_bars[i]["ts"] - exec_bars[i - 1]["ts"] for i in range(1, len(exec_bars)))
    step = diffs[len(diffs) // 2]
    for i in range(1, len(exec_bars)):
        if exec_bars[i]["ts"] - exec_bars[i - 1]["ts"] > step:
            dec[i] = exec_bars[i - 1]["ts"]
    return dec

def pairs(exec_bars, cand_bars, events, future="", family="clock_minutes"):
    """Time-sorted bars in. One dict per scored pair: decision ts, label_ts (the execution bar whose close the
    outcome reads), candidate sign x, execution sign y, candidate tide sign, macro flag (events released by the
    decision). Pairs with a flat move are consumed but not returned."""
    out, used = [], None
    dec = decision_times(exec_bars, family)
    for i in range(1, len(exec_bars)):
        k = completed_before(cand_bars, dec[i])
        if k is None or k == 0 or k == used:
            continue
        used = k
        b, prev, c, cp = exec_bars[i], exec_bars[i - 1], cand_bars[k], cand_bars[k - 1]
        x, y = _sign(c["close"] - cp["close"]), _sign(b["close"] - prev["close"])
        if x == 0 or y == 0:
            continue
        ev = event_features_asof(dec[i], events, future)
        out.append({"ts": dec[i], "label_ts": b["ts"], "x": x, "y": y,
                    "tide": _sign((c.get("tide_long") or 0) - (c.get("tide_short") or 0)),
                    "macro": bool(ev["any_macro"] or ev["earnings"])})
    return out
