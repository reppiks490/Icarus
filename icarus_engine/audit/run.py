# Grok (xAI) — 2026-09-22. Whole file.
from __future__ import annotations
import json
from pathlib import Path
from icarus_engine.audit.lead import pairs
from icarus_engine.ignore_trade import ignored_symbol
from icarus_engine.model_log import log_action
from icarus_engine.spec import SWAP_YES, artifact
from icarus_engine.trainers.dataset import attach_labels
from icarus_engine.trainers.qualify import VALID, qualify_xgb

def _sorted(bars):
    return sorted(bars, key=lambda b: b["ts"])

def score_pair(exec_bars, cand_bars, events, asset, future, require_xgb=False, xgb_path=None, family="clock_minutes",
               exec_sha256=None, cand_floored=True, ledger_path=None):
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
    xgb_state, xgb_reason = qualify_xgb(xgb, future, family, dataset_sha256=exec_sha256, labeled=labeled,
                                        ledger_path=ledger_path)
    if require_xgb and xgb_state != VALID:
        return {"status": "blocked", "reason": f"XGB {xgb} {xgb_state}: {xgb_reason}", "xgb_state": xgb_state,
                "execution": future, "candidate": asset, "swap_recommend": False, "execution_authorized": False}
    # Strict lead: each candidate move is scored once, against the first execution move decided after the
    # candidate bar closed. Same-interval agreement is correlation, not prediction (EMPIRICAL CAN-01).
    scored = pairs(exec_bars, cand_bars, events, future, family, floored=cand_floored)
    hits = len(scored)
    agree = sum(1 for q in scored if q["x"] == q["y"])
    tide_n = sum(1 for q in scored if q["tide"])
    tide_agree = sum(1 for q in scored if q["tide"] and q["tide"] == q["y"])
    ev_n = sum(1 for q in scored if q["macro"])
    ev_agree = sum(1 for q in scored if q["macro"] and q["x"] == q["y"])
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
