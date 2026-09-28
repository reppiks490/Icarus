# Grok (xAI) — 2026-09-22. Whole file.
from __future__ import annotations
import json
from pathlib import Path
from icarus_engine.events.calendar import event_features_asof
from icarus_engine.ignore_trade import ignored_symbol
from icarus_engine.model_log import log_action
from icarus_engine.spec import SWAP_YES, artifact
from icarus_engine.trainers.dataset import attach_labels
from icarus_engine.trainers.qualify import VALID, qualify_xgb

def _sign(x):
    if x is None or x == 0:
        return 0
    return 1 if x > 0 else -1

def _sorted(bars):
    return sorted(bars, key=lambda b: b["ts"])

_CONTIGUOUS = ("renko", "range", "tick")   # a bar closes exactly when the next one opens

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

def _decision_times(exec_bars, family):
    """dec[i]: when the call on execution move i (bar i-1 close -> bar i close) is made, i.e. bar i-1's close.
    Contiguous bars close when the next opens. After a session gap the true close is not in the data, so only
    bar i-1's open is certain."""
    dec = [None] + [b["ts"] for b in exec_bars[1:]]
    if family in _CONTIGUOUS or len(exec_bars) < 3:
        return dec
    diffs = sorted(exec_bars[i]["ts"] - exec_bars[i - 1]["ts"] for i in range(1, len(exec_bars)))
    step = diffs[len(diffs) // 2]
    for i in range(1, len(exec_bars)):
        if exec_bars[i]["ts"] - exec_bars[i - 1]["ts"] > step:
            dec[i] = exec_bars[i - 1]["ts"]
    return dec

def score_pair(exec_bars, cand_bars, events, asset, future, require_xgb=False, xgb_path=None, family="clock_minutes",
               exec_sha256=None):
    if ignored_symbol(future):
        return {"status": "ignored", "reason": "execution symbol is not traded",
                "execution": future, "candidate": asset, "swap_recommend": False, "execution_authorized": False}
    if ignored_symbol(asset):
        return {"status": "ignored", "reason": "candidate name is on the do-not-trade list",
                "execution": future, "candidate": asset, "swap_recommend": False, "execution_authorized": False}
    exec_bars = _sorted(exec_bars)
    cand_bars = _sorted(cand_bars)
    xgb = Path(xgb_path) if xgb_path else Path(artifact(future, family, "xgb"))
    # The execution bars vouch for the artifact: the validator replays its holdout from these rows.
    labeled = attach_labels(exec_bars, family) if xgb.is_file() else None
    xgb_state, xgb_reason = qualify_xgb(xgb, future, family, dataset_sha256=exec_sha256, labeled=labeled)
    if require_xgb and xgb_state != VALID:
        return {"status": "blocked", "reason": f"XGB {xgb} {xgb_state}: {xgb_reason}", "xgb_state": xgb_state,
                "execution": future, "candidate": asset, "swap_recommend": False, "execution_authorized": False}
    # Strict lead: each candidate move is scored once, against the first execution move decided after the
    # candidate bar closed. Same-interval agreement is correlation, not prediction (EMPIRICAL CAN-01).
    hits = agree = tide_agree = tide_n = ev_agree = ev_n = 0
    dec = _decision_times(exec_bars, family)
    used = None
    for i, b in enumerate(exec_bars[1:], start=1):
        prev = exec_bars[i - 1]
        k = completed_before(cand_bars, dec[i])
        if k is None or k == 0 or k == used:
            continue
        used = k
        c, cp = cand_bars[k], cand_bars[k - 1]
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
        ev = event_features_asof(dec[i], events, future)     # only events released by the decision
        if ev["any_macro"] or ev["earnings"]:
            ev_n += 1
            if x == y:
                ev_agree += 1
    sign_agree = (agree / hits) if hits else None
    macro_agree = (ev_agree / ev_n) if ev_n else None
    status, reason = "eligible", ""
    if hits < SWAP_YES["min_overlap"]:
        status, reason = "reject", f"overlap {hits} < {SWAP_YES['min_overlap']}"
        if ev_n and macro_agree is not None and macro_agree >= SWAP_YES["min_macro_agree"]:
            status, reason = "eligible_macro_exceeds", "quiet fail, macro window beats spec"
    swap = (
        status in ("eligible", "eligible_macro_exceeds")
        and hits >= SWAP_YES["min_overlap"]
        and sign_agree is not None and sign_agree >= SWAP_YES["min_sign_agree"]
        and xgb_state == VALID
    )
    return {
        "status": status, "reason": reason, "execution": future, "candidate": asset,
        "family": family, "lead": "strict", "overlap": hits, "sign_agree": sign_agree,
        "tide_agree": (tide_agree / tide_n) if tide_n else None,
        "tide_n": tide_n, "macro_overlap": ev_n, "macro_agree": macro_agree,
        "xgb_artifact": str(xgb), "xgb_state": xgb_state, "xgb_reason": xgb_reason,
        "swap_recommend": swap, "execution_authorized": False,
    }

def write_audit(report, dest):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, allow_nan=False))
    log_action("audit", f"wrote {dest}", json.dumps({
        "status": report.get("status"), "execution": report.get("execution"),
        "candidate": report.get("candidate"), "swap_recommend": report.get("swap_recommend"),
    }, default=str))
    return dest
