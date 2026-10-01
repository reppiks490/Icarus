# Grok (xAI) — 2026-09-22. Whole file.
from __future__ import annotations
from pathlib import Path
from icarus_engine.spec import FEATURE_KEYS, WALK
from .integrity import inspect_ohlc

def load_ohlc(path: Path):
    # Claude (Opus 5.5) 2026-09-27: parsing lives in integrity.inspect_ohlc (offset-aware timestamps, duplicate
    # and OHLC checks, a manifest). A file with conflicting duplicates or impossible OHLC is refused.
    out, manifest = inspect_ohlc(path)
    if manifest["status"] == "blocked":
        raise ValueError(f"{path}: {manifest['reason']}")
    if len(out) < 8:
        raise ValueError(f"too few parseable rows in {path}")
    return out

def _sign(x):
    if x is None or x == 0:
        return 0
    return 1 if x > 0 else -1

_EVENTS = None

def _events():
    global _EVENTS
    if _EVENTS is None:
        from icarus_engine.events.calendar import seed_events
        _EVENTS = seed_events()
    return _EVENTS

def attach_labels(bars, family: str, events=None):
    from icarus_engine.events.calendar import event_features_asof
    evs = _events() if events is None else events
    labeled = []
    for i, b in enumerate(bars[:-1]):
        y = _sign(bars[i + 1]["close"] - b["close"])
        if y == 0:
            continue
        o = b["open"] if b["open"] is not None else b["close"]
        h = b["high"] if b["high"] is not None else b["close"]
        lo = b["low"] if b["low"] is not None else b["close"]
        rng = h - lo
        run = 0
        for j in range(i, 0, -1):
            d = _sign(bars[j]["close"] - bars[j - 1]["close"])
            if d == 0:
                continue
            if run == 0:
                run = d
            elif d == _sign(run):
                run += d
            else:
                break
        ev = event_features_asof(b["ts"], evs)
        feats = {
            "ret_1": (b["close"] - bars[i - 1]["close"]) if i else 0.0,
            "ret_3": (b["close"] - bars[max(0, i - 3)]["close"]),
            "body": b["close"] - o,
            "range": rng if rng else 0.0,
            "close_loc": ((b["close"] - lo) / rng) if rng else 0.5,
            "tide": (b.get("tide_long") or 0) - (b.get("tide_short") or 0),
            "run": float(run),
            "fomc": float(ev["fomc"]),
            "any_macro": float(ev["any_macro"]),
        }
        # label_ts: the bar whose close the label reads (Claude (Opus 5.5) 2026-09-27).
        labeled.append({"ts": b["ts"], "y": y, "family": family, "label_ts": bars[i + 1]["ts"],
                        "x": {k: feats[k] for k in FEATURE_KEYS}})
    return labeled

EMBARGO = 1   # rows dropped at the end of train and valid: their labels read the next slice's first close

def walk_slices(n: int, train_frac=None, valid_frac=None):
    train_frac = WALK["train"] if train_frac is None else train_frac
    valid_frac = WALK["valid"] if valid_frac is None else valid_frac
    if WALK["shuffle"]:
        raise ValueError("spec forbids shuffle")
    if n < 40:
        raise ValueError("not enough labeled rows for a walk-forward")
    a = int(n * train_frac); b = int(n * (train_frac + valid_frac))
    if a - EMBARGO < 20 or b - a - EMBARGO < 10 or n - b < 10:
        raise ValueError("walk-forward slices too small")
    return (0, a - EMBARGO), (a, b - EMBARGO), (b, n)

def purged_slices(rows):
    """walk_slices for rows that may share timestamps (pooled candidates). A row stays in train or valid only if
    both its decision and the bar its label reads come before the next slice's first decision."""
    (a0, a1), (b0, b1), (c0, c1) = walk_slices(len(rows))
    hold = rows[c0:c1]
    valid = [r for r in rows[b0:b1] if r["ts"] < hold[0]["ts"] and r["label_ts"] < hold[0]["ts"]]
    if not valid:
        raise ValueError("validation slice empty after purging")
    train = [r for r in rows[a0:a1] if r["ts"] < valid[0]["ts"] and r["label_ts"] < valid[0]["ts"]]
    if len(train) < 20 or len(valid) < 10:
        raise ValueError("walk-forward slices too small after purging")
    return train, valid, hold
