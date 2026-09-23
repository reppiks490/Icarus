# Grok (xAI) — 2026-09-22. Whole file.
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from icarus_engine.events.calendar import event_features
from icarus_engine.ignore_trade import ignored_symbol

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

def _xgb_evidence(path, execution_source, events, future):
    """CA: bind the gate to a real fitted tree and this exact execution tape."""
    from icarus_engine.trainers.run import file_hash, training_signature
    from icarus_engine.trainers.xgb import validate_artifact
    from icarus_engine.trainers.families import FAMILIES, family_for

    artifact_path = Path(path)
    if not artifact_path.is_file():
        raise ValueError(f"missing XGB artifact: {artifact_path}")
    if execution_source is None:
        raise ValueError("execution CSV path required for XGB provenance check")
    source = Path(execution_source)
    if not source.is_file():
        raise ValueError(f"execution CSV unavailable: {source}")
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    if not validate_artifact(artifact, asset=future):
        raise ValueError("XGB artifact failed native reload or symbol validation")
    provenance = artifact.get("provenance") or {}
    if (artifact.get("training_signature") != training_signature()
            or artifact.get("family") not in FAMILIES
            or family_for(artifact.get("chart_type")) != artifact.get("family")
            or artifact.get("dataset_sha256") != file_hash(source)
            or provenance.get("sha256") != artifact.get("dataset_sha256")
            or provenance.get("asset") != future
            or provenance.get("family") != artifact.get("family")
            or provenance.get("chart_type") != artifact.get("chart_type")
            or provenance.get("interval") is None):
        raise ValueError("XGB source, interval, code, or execution tape differs")
    event_hash = hashlib.sha256(json.dumps(events, sort_keys=True).encode()).hexdigest()
    if artifact.get("event_sha256") != event_hash:
        raise ValueError("event calendar differs from the fitted XGB artifact")
    return {
        "artifact": str(artifact_path.resolve()),
        "artifact_sha256": file_hash(artifact_path),
        "source_sha256": artifact["dataset_sha256"],
        "family": artifact["family"],
        "interval": provenance["interval"],
        "holdout_acc": artifact.get("holdout_acc"),
    }


def score_pair(exec_bars, cand_bars, events, asset, future, require_xgb=False,
               xgb_path=None, execution_source=None):
    if ignored_symbol(future):
        return {"status": "ignored", "reason": "execution symbol is not traded",
                "execution": future, "candidate": asset, "execution_authorized": False}
    if ignored_symbol(asset):
        return {"status": "ignored", "reason": "candidate name is on the do-not-trade list",
                "execution": future, "candidate": asset, "execution_authorized": False}
    evidence = None
    if require_xgb:
        p = Path(xgb_path) if xgb_path else Path("run") / "trainers" / f"{future}_clock_minutes_xgb.json"
        try:
            evidence = _xgb_evidence(p, execution_source, events, future)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            return {"status": "blocked", "reason": str(exc),
                    "execution": future, "candidate": asset, "execution_authorized": False}
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
    return {
        "status": "diagnostic", "reason": "Same-bar concordance only; no trade-level qualification",
        "execution": future, "candidate": asset,
        "overlap": hits,
        "sign_agree": (agree / hits) if hits else None,
        "tide_agree": (tide_agree / tide_n) if tide_n else None,
        "tide_n": tide_n, "macro_overlap": ev_n,
        "macro_agree": (ev_agree / ev_n) if ev_n else None,
        "xgb_evidence": evidence,
        "candidate_qualified": False,
        "execution_authorized": False,
    }

def write_audit(report, dest):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, allow_nan=False))
    return dest
