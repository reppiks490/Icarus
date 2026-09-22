# Grok (xAI) — 2026-09-22. Whole file.
from __future__ import annotations
from .calendar import event_features, load_events

def csv_micro(bar, prev=None, vix_z=0.0, tnx_z=0.0, dxy_z=0.0):
    tide = (bar.get("tide_long") or 0) - (bar.get("tide_short") or 0)
    rng = (bar.get("high") or bar["close"]) - (bar.get("low") or bar["close"])
    ret = (bar["close"] - prev["close"]) if prev is not None else 0.0
    return {"tide": tide, "range": rng, "ret": ret,
            "vix_z": vix_z, "tnx_z": tnx_z, "dxy_z": dxy_z,
            "stress": int(abs(vix_z) > 2 or abs(tnx_z) > 2 or abs(dxy_z) > 2)}

def annotate_bar(bar, events, asset="", prev=None, vix_z=0.0, tnx_z=0.0, dxy_z=0.0):
    return {**bar,
            "events": event_features(bar["ts"], events, asset),
            "micro": csv_micro(bar, prev, vix_z, tnx_z, dxy_z)}

def plant_events(root):
    return load_events(root)
