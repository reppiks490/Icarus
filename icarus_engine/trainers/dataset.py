# Grok (xAI) — 2026-09-22. Whole file.
from __future__ import annotations
import csv, math
from pathlib import Path

def _num(v):
    if v is None or v == "":
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None

def load_ohlc(path: Path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError(f"empty csv {path}")
    keys = {k.strip(): k for k in rows[0]}
    def col(*names):
        for n in names:
            if n in keys:
                return keys[n]
            for k in keys:
                if k.lower() == n.lower():
                    return keys[k]
        return None
    t_k, o_k, h_k, l_k, c_k = col("time", "ts"), col("open"), col("high"), col("low"), col("close")
    v_k = col("volume", "Volume")
    tide_l, tide_s = col("TIDE Long"), col("TIDE Short")
    if not t_k or not c_k:
        raise ValueError(f"need time+close in {path}")
    out = []
    for row in rows:
        t = _num(row[t_k]); c = _num(row[c_k])
        if t is None or c is None:
            continue
        if t > 10_000_000_000:
            t /= 1000.0
        out.append({"ts": t, "open": _num(row[o_k]) if o_k else c, "high": _num(row[h_k]) if h_k else c,
                    "low": _num(row[l_k]) if l_k else c, "close": c,
                    "volume": _num(row[v_k]) if v_k else None,
                    "tide_long": _num(row[tide_l]) if tide_l else 0.0,
                    "tide_short": _num(row[tide_s]) if tide_s else 0.0})
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

def attach_labels(bars, family: str):
    from icarus_engine.events.calendar import event_features
    evs = _events()
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
        ev = event_features(b["ts"], evs)
        labeled.append({"ts": b["ts"], "y": y, "family": family, "x": {
            "ret_1": (b["close"] - bars[i - 1]["close"]) if i else 0.0,
            "ret_3": (b["close"] - bars[max(0, i - 3)]["close"]),
            "body": b["close"] - o, "range": rng if rng else 0.0,
            "close_loc": ((b["close"] - lo) / rng) if rng else 0.5,
            "tide": (b.get("tide_long") or 0) - (b.get("tide_short") or 0),
            "run": float(run),
            "fomc": float(ev["fomc"]),
            "any_macro": float(ev["any_macro"]),
        }})
    return labeled

def walk_slices(n: int, train_frac=0.6, valid_frac=0.2):
    if n < 40:
        raise ValueError("not enough labeled rows for a walk-forward")
    a = int(n * train_frac); b = int(n * (train_frac + valid_frac))
    if a < 20 or b - a < 10 or n - b < 10:
        raise ValueError("walk-forward slices too small")
    return (0, a), (a, b), (b, n)
