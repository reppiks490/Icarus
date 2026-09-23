# Grok (xAI) — 2026-09-22. Whole file.
from __future__ import annotations
import csv, math
from collections import deque
from datetime import datetime
from pathlib import Path

def _num(v):
    if v is None or v == "":
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None

def _timestamp(value):
    t = _num(value)
    if t is None:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                raise ValueError("ISO timestamps must include a timezone")
            t = dt.timestamp()
        except (ValueError, TypeError):
            return None
    return t / 1000.0 if t > 10_000_000_000 else t


def load_ohlc(path: Path, *, strict=False, family=None):
    """CA: training is strict and never reorders or repairs the owner's bars."""
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
    if strict and not all((o_k, h_k, l_k)):
        raise ValueError(f"OHLC required; close-only data has no trainer: {path}")
    out = []
    for row_index, row in enumerate(rows):
        t = _timestamp(row[t_k]); c = _num(row[c_k])
        if t is None or c is None:
            if strict:
                raise ValueError(f"invalid timestamp/close on CSV row {row_index + 2}")
            continue
        bar = {"ts": t, "open": _num(row[o_k]) if o_k else c, "high": _num(row[h_k]) if h_k else c,
                    "low": _num(row[l_k]) if l_k else c, "close": c,
                    "volume": _num(row[v_k]) if v_k else None,
                    "tide_long": _num(row[tide_l]) if tide_l else 0.0,
                    "tide_short": _num(row[tide_s]) if tide_s else 0.0,
                    "row_index": row_index}
        if strict:
            o, h, lo = bar["open"], bar["high"], bar["low"]
            if any(v is None for v in (o, h, lo)) or lo > min(o, c) or h < max(o, c) or lo > h:
                raise ValueError(f"invalid OHLC on CSV row {row_index + 2}")
            if out and (t < out[-1]["ts"] or (t == out[-1]["ts"] and (family or '').startswith('clock_'))):
                raise ValueError(f"non-increasing clock or reversed event index on CSV row {row_index + 2}")
        out.append(bar)
    if len(out) < 8:
        raise ValueError(f"too few parseable rows in {path}")
    if not strict:
        out.sort(key=lambda b: b["ts"])
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

def attach_labels(bars, family: str, *, events=None, asset="", sensors=None):
    """CA: one-step targets with original index and causal feature provenance.

    Sensor rows must explicitly carry available_ts, not just a bar-open time.
    No zero-fill for missing sensors and no inferred profile/order-book data.
    """
    from icarus_engine.events.calendar import event_features
    evs = _events() if events is None else events
    labeled = []
    trailing = deque(maxlen=20)
    run = 0
    sensor_positions = {k: -1 for k in (sensors or {})}
    for name, series in (sensors or {}).items():
        if name not in ("vix_z", "tnx_z", "dxy_z"):
            raise ValueError(f"unsupported sensor {name}")
        if any(not math.isfinite(float(r['available_ts'])) for r in series):
            raise ValueError("sensor available_ts must be finite")
        if any(a['available_ts'] > b['available_ts'] for a, b in zip(series, series[1:])):
            raise ValueError("sensor rows must be ordered by availability")
    for i, b in enumerate(bars[:-1]):
        delta = b["close"] - bars[i - 1]["close"] if i else 0.0
        trailing.append(delta)
        d = _sign(delta)
        if d:
            run = run + d if _sign(run) == d else d
        y = _sign(bars[i + 1]["close"] - b["close"])
        if y == 0:
            continue
        o = b["open"] if b["open"] is not None else b["close"]
        h = b["high"] if b["high"] is not None else b["close"]
        lo = b["low"] if b["low"] is not None else b["close"]
        rng = h - lo
        ev = event_features(b["ts"], evs, asset)
        mean = sum(trailing) / len(trailing)
        x = {
            "ret_1": delta,
            "ret_3": (b["close"] - bars[max(0, i - 3)]["close"]),
            "body": b["close"] - o, "range": rng if rng else 0.0,
            "close_loc": ((b["close"] - lo) / rng) if rng else 0.5,
            "tide": (b.get("tide_long") or 0) - (b.get("tide_short") or 0),
            "run": float(run),
            "fomc": float(ev["fomc"]),
            "any_macro": float(ev["any_macro"]),
            "cpi": float(ev["cpi"]), "nfp": float(ev["nfp"]),
            "earnings": float(ev["earnings"]),
            "vol_20": math.sqrt(sum((v - mean) ** 2 for v in trailing) / len(trailing)),
        }
        for name, series in (sensors or {}).items():
            j = sensor_positions[name]
            while j + 1 < len(series) and series[j + 1]['available_ts'] <= b['ts']:
                j += 1
            sensor_positions[name] = j
            x[name] = series[j]['value'] if j >= 0 else None
        labeled.append({"ts": b["ts"], "label_ts": bars[i + 1]["ts"],
                        "row_index": b.get("row_index", i),
                        "label_index": bars[i + 1].get("row_index", i + 1),
                        "y": y, "family": family, "asset": asset, "x": x})
    return labeled

def walk_slices(n: int, train_frac=0.6, valid_frac=0.2):
    if n < 40:
        raise ValueError("not enough labeled rows for a walk-forward")
    a = int(n * train_frac); b = int(n * (train_frac + valid_frac))
    if a < 20 or b - a < 10 or n - b < 10:
        raise ValueError("walk-forward slices too small")
    return (0, a), (a, b), (b, n)
