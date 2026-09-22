# Grok (xAI) — 2026-09-22. Whole file.
from __future__ import annotations
import json
from pathlib import Path
from icarus_engine.events.calendar import event_features
from icarus_engine.ignore_trade import ignored_symbol
from icarus_engine.spec import SWAP_YES, artifact

def _sign(x):
    if x is None or x == 0:
        return 0
    return 1 if x > 0 else -1

def _sorted(bars):
    return sorted(bars, key=lambda b: b["ts"])

def _asof(exec_ts, cand):
    lo, hi, hit = 0, len(cand) - 1, None
    while lo <= hi:
        mid = (lo + hi) // 2
        if cand[mid]["ts"] <= exec_ts:
            hit = cand[mid]; lo = mid + 1
        else:
            hi = mid - 1
    return hit

def score_pair(exec_bars, cand_bars, events, asset, future, require_xgb=False, xgb_path=None, family="clock_minutes"):
    if ignored_symbol(future):
        return {"status": "ignored", "reason": "execution symbol is not traded",
                "execution": future, "candidate": asset, "swap_recommend": False, "execution_authorized": False}
    if ignored_symbol(asset):
        return {"status": "ignored", "reason": "candidate name is on the do-not-trade list",
                "execution": future, "candidate": asset, "swap_recommend": False, "execution_authorized": False}
    xgb = Path(xgb_path) if xgb_path else Path(artifact(future, family, "xgb"))
    if require_xgb and not xgb.is_file():
        return {"status": "blocked", "reason": f"missing XGB {xgb}",
                "execution": future, "candidate": asset, "swap_recommend": False, "execution_authorized": False}
    exec_bars = _sorted(exec_bars)
    cand_bars = _sorted(cand_bars)
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
        and xgb.is_file()
    )
    return {
        "status": status, "reason": reason, "execution": future, "candidate": asset,
        "family": family, "overlap": hits, "sign_agree": sign_agree,
        "tide_agree": (tide_agree / tide_n) if tide_n else None,
        "tide_n": tide_n, "macro_overlap": ev_n, "macro_agree": macro_agree,
        "xgb_artifact": str(xgb), "swap_recommend": swap, "execution_authorized": False,
    }

def write_audit(report, dest):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, allow_nan=False))
    return dest
