# Claude (Opus 5.5) — 2026-09-27. DATA gate for trainer CSVs: canonical timestamps, duplicate and OHLC
# integrity, and a manifest (raw file hash, canonical row hash, counts) that travels with every artifact.
# Conflicting duplicates or impossible OHLC block the file; dropped rows are counted, never silent.
from __future__ import annotations
import csv, hashlib, io, json, math, re, statistics
from datetime import datetime
from pathlib import Path

PARSER = "icarus.trainer.integrity/1"
_OFFSET = re.compile(r"(Z|[+-]\d{2}:?\d{2})$")
_TOL = 1e-9

def _num(v):
    if v is None or v == "":
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None

def canonical_ts(raw):
    """Epoch seconds, or None. Numbers are epoch seconds (milliseconds above 1e10). Text must carry its own
    offset: a naive clock time has no knowable zone, so it is never guessed. Unlike the plant's
    feeds.bars.parse_timestamp this keeps pre-2000 history (long daily exports)."""
    s = (raw or "").strip().strip('"')
    if not s:
        return None
    n = _num(s)
    if n is not None:
        if n <= 0:
            return None
        if n > 10_000_000_000:
            n /= 1000.0
        return n if n < 4_102_444_800 else None          # before 2100
    if not _OFFSET.search(s):
        return None
    s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)     # Python 3.10's fromisoformat needs +HH:MM
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00").replace(" ", "T", 1))
    except ValueError:
        return None
    return float(dt.timestamp()) if dt.tzinfo is not None else None

def _columns(fieldnames):
    keys = {k.strip(): k for k in fieldnames or []}
    def col(*names):
        for n in names:
            if n in keys:
                return keys[n]
            for k in keys:
                if k.lower() == n.lower():
                    return keys[k]
        return None
    return col

def inspect_ohlc(path):
    """(bars, manifest). Bars are sorted, unique by timestamp, in the trainer's dict format."""
    path = Path(path)
    raw = path.read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    rows = list(reader)
    if not rows:
        raise ValueError(f"empty csv {path}")
    col = _columns(reader.fieldnames)
    t_k, o_k, h_k, l_k, c_k = col("time", "ts"), col("open"), col("high"), col("low"), col("close")
    v_k, tl_k, ts_k = col("volume", "Volume"), col("TIDE Long"), col("TIDE Short")
    if not t_k or not c_k:
        raise ValueError(f"need time+close in {path}")

    counts = dict.fromkeys(("unparseable_time", "missing_close", "missing_ohlc", "invalid_ohlc",
                            "out_of_order", "duplicate_exact", "duplicate_conflict"), 0)
    by_ts, prev = {}, None
    for row in rows:
        t = canonical_ts(row.get(t_k))
        if t is None:
            counts["unparseable_time"] += 1
            continue
        c = _num(row.get(c_k))
        if c is None:
            counts["missing_close"] += 1
            continue
        if prev is not None and t < prev:
            counts["out_of_order"] += 1
        prev = t
        o = _num(row.get(o_k)) if o_k else c
        h = _num(row.get(h_k)) if h_k else c
        lo = _num(row.get(l_k)) if l_k else c
        if None in (o, h, lo):
            counts["missing_ohlc"] += 1
        known = [v for v in (o, c) if v is not None]
        if h is not None and lo is not None and (h < lo - _TOL or any(v > h + _TOL or v < lo - _TOL for v in known)):
            counts["invalid_ohlc"] += 1
        bar = {"ts": t, "open": o, "high": h, "low": lo, "close": c,
               "volume": _num(row.get(v_k)) if v_k else None,
               "tide_long": _num(row.get(tl_k)) if tl_k else 0.0,
               "tide_short": _num(row.get(ts_k)) if ts_k else 0.0}
        seen = by_ts.get(t)
        if seen is None:
            by_ts[t] = bar
        elif seen == bar:
            counts["duplicate_exact"] += 1
        elif not seen.get("_conflict"):
            seen["_conflict"] = True
            counts["duplicate_conflict"] += 1

    bars = [{k: v for k, v in by_ts[t].items() if k != "_conflict"} for t in sorted(by_ts)]
    # An export's last bar may still have been forming when it was saved; nothing in the file says which.
    counts["trailing_dropped"] = 1 if bars else 0
    bars = bars[:-1]
    steps = [b["ts"] - a["ts"] for a, b in zip(bars, bars[1:])]
    blocked = []
    if counts["duplicate_conflict"]:
        blocked.append(f"{counts['duplicate_conflict']} timestamps carry conflicting rows")
    if counts["invalid_ohlc"]:
        blocked.append(f"{counts['invalid_ohlc']} rows have impossible OHLC (high/low do not bound the bar)")
    # missing_ohlc rows are kept (their open/high/low read as the close downstream) but still flag the file
    flagged = counts["unparseable_time"] + counts["missing_close"] + counts["missing_ohlc"] + counts["duplicate_exact"]
    manifest = {
        "parser": PARSER, "path": str(path), "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "rows_total": len(rows), "rows_used": len(bars), **counts,
        "first_ts": bars[0]["ts"] if bars else None, "last_ts": bars[-1]["ts"] if bars else None,
        "median_step": statistics.median(steps) if steps else None,
        "canonical_rows_sha256": hashlib.sha256(json.dumps(
            [[b["ts"], b["open"], b["high"], b["low"], b["close"], b["volume"], b["tide_long"], b["tide_short"]]
             for b in bars], separators=(",", ":"), allow_nan=False).encode()).hexdigest(),
        "status": "blocked" if blocked else ("issues" if flagged else "clean"),
        "reason": "; ".join(blocked),
    }
    return bars, manifest
