# Claude (Opus 5.5) — 2026-09-27. DATA gate for trainer CSVs: canonical timestamps, duplicate and OHLC
# integrity, and a manifest (raw file hash, canonical row hash, counts) that travels with every artifact.
# Conflicting duplicates or impossible OHLC block the file; dropped rows are counted, never silent.
from __future__ import annotations
import csv, hashlib, io, json, math, statistics
from pathlib import Path
from ..evidence.timestamps import PARSER_VERSION as TIMESTAMP_PARSER, normalize_timestamp

PARSER = "icarus.trainer.integrity/3"

def _num(v):
    if v is None or v == "":
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None

def canonical_ts(raw):
    """Shared epoch normalization; trainer wall times require an explicit offset."""
    record = normalize_timestamp(raw)
    return record.epoch_seconds if record else None

def _columns(fieldnames, ambiguous, raw_rows, duplicate_features):
    def col(*names):
        indexes = [i for i, k in enumerate(fieldnames) if k.strip().lower() in {n.lower() for n in names}]
        matches = [fieldnames[i] for i in indexes]
        if len(matches) > 1:
            # Only optional TIDE features may be coalesced. Core price/time/volume
            # aliases stay ambiguous. Compare every physical CSV row before any
            # timestamp, OHLC, duplicate-bar or trailing-bar filtering takes place.
            identical = False
            if names in (("TIDE Long",), ("TIDE Short",)):
                missing = conflicts = 0
                for row in raw_rows:
                    if indexes[-1] >= len(row):
                        missing += 1
                    elif any(row[i] != row[indexes[0]] for i in indexes[1:]):
                        conflicts += 1
                identical = not (missing or conflicts)
                duplicate_features.append({
                    "name": names[0], "column_indexes_zero_based": indexes,
                    "comparison": "EXACT_CSV_CELL_TEXT", "rows_compared": len(raw_rows),
                    "conflicting_rows": conflicts, "missing_rows": missing,
                    "status": "IDENTICAL" if identical else "AMBIGUOUS",
                })
            if not identical:
                ambiguous.append('/'.join(names))
        return matches[0] if matches else None
    return col

def inspect_ohlc(path, *, raw_bytes=None):
    """(bars, manifest). Bars are sorted, unique by timestamp, in the trainer's dict format."""
    path = Path(path)
    raw = path.read_bytes() if raw_bytes is None else raw_bytes
    if not isinstance(raw, bytes):
        raise ValueError("OHLC snapshot must be bytes")
    reader = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    fieldnames = next(reader, [])
    raw_rows = [row for row in reader if row]
    if not raw_rows:
        raise ValueError(f"empty csv {path}")
    ambiguous = []
    duplicate_features = []
    col = _columns(fieldnames, ambiguous, raw_rows, duplicate_features)
    t_k, o_k, h_k, l_k, c_k = col("time", "ts"), col("open"), col("high"), col("low"), col("close")
    v_k, tl_k, ts_k = col("volume", "Volume"), col("TIDE Long"), col("TIDE Short")
    if not t_k or not c_k:
        raise ValueError(f"need time+close in {path}")

    counts = dict.fromkeys(("unparseable_time", "missing_close", "missing_ohlc", "invalid_ohlc", "invalid_volume",
                            "out_of_order", "duplicate_exact", "duplicate_conflict", "timestamp_precision_conflict"), 0)
    by_ts, exact_ts, prev = {}, {}, None
    conflicts, precision_conflicts = set(), set()
    units, bases = {}, {}
    for cells in raw_rows:
        # Duplicate keys are safe only for the selected feature groups proven
        # identical above. Every other selected duplicate still blocks admission.
        row = dict(zip(fieldnames, cells))
        record = normalize_timestamp(row.get(t_k))
        if record is None:
            counts["unparseable_time"] += 1
            continue
        t = record.epoch_seconds
        units[record.detected_unit] = units.get(record.detected_unit, 0) + 1
        bases[record.timezone_basis] = bases.get(record.timezone_basis, 0) + 1
        c = _num(row.get(c_k))
        if c is None:
            counts["missing_close"] += 1
            continue
        if prev is not None and t < prev:
            counts["out_of_order"] += 1
        prev = t
        o = _num(row.get(o_k)) if o_k else None
        h = _num(row.get(h_k)) if h_k else None
        lo = _num(row.get(l_k)) if l_k else None
        if None in (o, h, lo):
            counts["missing_ohlc"] += 1
            continue
        if h < lo or max(o, c) > h or min(o, c) < lo:
            counts["invalid_ohlc"] += 1
            continue
        volume = _num(row.get(v_k)) if v_k else None
        if v_k and row.get(v_k) not in (None, '') and (volume is None or volume < 0):
            counts["invalid_volume"] += 1
            continue
        bar = {"ts": t, "open": o, "high": h, "low": lo, "close": c,
               "volume": volume,
               "tide_long": _num(row.get(tl_k)) if tl_k else 0.0,
               "tide_short": _num(row.get(ts_k)) if ts_k else 0.0}
        seen = by_ts.get(t)
        if seen is None:
            by_ts[t] = bar
            exact_ts[t] = record.epoch_seconds_exact
        elif exact_ts[t] != record.epoch_seconds_exact:
            precision_conflicts.add(t)
        elif seen == bar:
            counts["duplicate_exact"] += 1
        else:
            conflicts.add(t)

    counts["duplicate_conflict"] = len(conflicts)
    counts["timestamp_precision_conflict"] = len(precision_conflicts)
    bars = [by_ts[t] for t in sorted(by_ts)]
    # An export's last bar may still have been forming when it was saved; nothing in the file says which.
    counts["trailing_dropped"] = 1 if bars else 0
    bars = bars[:-1]
    steps = [b["ts"] - a["ts"] for a, b in zip(bars, bars[1:])]
    blocked = []
    if ambiguous:
        blocked.append("ambiguous OHLC/feature columns: " + ', '.join(ambiguous))
    if not all((o_k, h_k, l_k)):
        blocked.append("OHLC requires open/high/low/close columns; missing prices are not inferred")
    if counts["missing_close"] or counts["missing_ohlc"]:
        blocked.append("OHLC rows contain missing or nonfinite prices")
    if counts["duplicate_conflict"]:
        blocked.append(f"{counts['duplicate_conflict']} timestamps carry conflicting rows")
    if counts["invalid_ohlc"]:
        blocked.append(f"{counts['invalid_ohlc']} rows have impossible OHLC (high/low do not bound the bar)")
    if counts["invalid_volume"]:
        blocked.append("OHLC rows contain invalid volume")
    if precision_conflicts:
        blocked.append("distinct exact timestamps lose precision in float-second trainer rows")
    if blocked:
        bars = []
    flagged = counts["unparseable_time"] + counts["missing_close"] + counts["missing_ohlc"] + counts["duplicate_exact"]
    manifest = {
        "parser": PARSER, "timestamp_parser": TIMESTAMP_PARSER,
        "timestamp_unit_counts": units, "timezone_basis_counts": bases,
        "timestamp_unit_policy": "MAGNITUDE_DETECTED_NOT_PROVIDER_ATTESTED",
        "path": str(path), "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "rows_total": len(raw_rows), "rows_used": len(bars), **counts,
        "duplicate_feature_columns": duplicate_features,
        "first_ts": bars[0]["ts"] if bars else None, "last_ts": bars[-1]["ts"] if bars else None,
        "median_step": statistics.median(steps) if steps else None,
        "canonical_rows_sha256": hashlib.sha256(json.dumps(
            [[b["ts"], b["open"], b["high"], b["low"], b["close"], b["volume"], b["tide_long"], b["tide_short"]]
             for b in bars], separators=(",", ":"), allow_nan=False).encode()).hexdigest(),
        "status": "blocked" if blocked else ("issues" if flagged else "clean"),
        "reason": "; ".join(blocked),
    }
    return bars, manifest
