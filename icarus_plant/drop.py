# Grok (xAI) — 2026-09-20. Whole file. history/drop/ → canonical history/{SYM}_{N}m.csv.
"""Ingest TradingView Supercharts CSVs dropped into the plant.

Does not scrape TradingView. Does not invent ticks. Moves each file to
``history/drop/done/`` after a successful write. Unparseable files go to
``history/drop/bad/`` so they cannot block the inbox.
"""
from __future__ import annotations

import os
import re
import shutil
import time
from typing import Any, Dict, List, Optional

from icarus_engine.assets import resolve
from icarus_engine.feeds.bars import detect_granularity, history_path, merge_bars, parse_ohlcv_csv, read_text_csv, write_canonical

from .layout import ensure, plant_root

# TradingView "Download chart data" names look like:
#   CME_MINI_NQ1!, 1.csv
#   NQ1!, 1.csv
#   CBOT_MINI_YM1!, 1.csv
#   CME_MINI_NQ1!, 1 (1).csv   (Windows copy)
_EXCHANGE_PREFIX = re.compile(
    r"^(?:CME_MINI_|CBOT_MINI_|COMEX_|NYMEX_|CME_|CBOT_)",
    re.I,
)
_COPY_SUFFIX = re.compile(r"\s*\(\d+\)\s*$")
_TV_INTERVAL = re.compile(r",\s*\d+[DWHMdmh]?\s*$")
_TF_SUFFIX = re.compile(r"[_-](\d+)m$", re.I)
_SETTLE_SEC = 1.5


def infer_symbol(filename: str) -> str:
    """Map a Supercharts download name (or canonical history name) to a registry symbol."""
    stem = os.path.splitext(os.path.basename(filename))[0]
    stem = stem.replace("CME_MINI:", "").replace("CME:", "").replace("CBOT:", "")
    stem = _COPY_SUFFIX.sub("", stem).strip()
    stem = _EXCHANGE_PREFIX.sub("", stem)
    stem = _TV_INTERVAL.sub("", stem)
    stem = _TF_SUFFIX.sub("", stem)
    stem = _COPY_SUFFIX.sub("", stem).strip(" _-")
    return resolve(stem).symbol


def ingest_file(path: str, *, root: Optional[str] = None, symbol: Optional[str] = None, tz=None) -> Dict[str, Any]:
    root = plant_root(root)
    ensure(root)
    bars = parse_ohlcv_csv(read_text_csv(path), tz=tz)
    if not bars:
        raise ValueError(f"{os.path.basename(path)}: no OHLCV rows")
    sym = symbol or infer_symbol(path)
    minutes = max(1, detect_granularity(bars) // 60)
    dest = history_path(root, sym, minutes)
    merged_from = 0
    if os.path.isfile(dest):
        old = parse_ohlcv_csv(read_text_csv(dest))
        merged_from = len(old)
        bars = merge_bars(old, bars)
    n = write_canonical(dest, bars)
    return {
        "symbol": sym, "minutes": minutes, "bars": n, "merged_from": merged_from,
        "added": max(0, n - merged_from), "dest": dest, "src": os.path.abspath(path),
    }


def _unique_dest(folder: str, name: str) -> str:
    dest = os.path.join(folder, name)
    if not os.path.exists(dest):
        return dest
    stem, ext = os.path.splitext(name)
    k = 1
    while os.path.exists(os.path.join(folder, f"{stem}.{k}{ext}")):
        k += 1
    return os.path.join(folder, f"{stem}.{k}{ext}")


def ingest_drop(root: Optional[str] = None) -> List[Dict[str, Any]]:
    """Process every settled *.csv in history/drop/ (not done/, not bad/)."""
    paths = ensure(root)
    drop = paths["history/drop"]
    done = paths["history/drop/done"]
    bad = paths["history/drop/bad"]
    now = time.time()
    out: List[Dict[str, Any]] = []
    for name in sorted(os.listdir(drop)):
        if not name.lower().endswith(".csv"):
            continue
        src = os.path.join(drop, name)
        if not os.path.isfile(src):
            continue
        try:
            if now - os.path.getmtime(src) < _SETTLE_SEC:
                continue
        except OSError:
            continue
        try:
            rec = ingest_file(src, root=paths["root"])
        except Exception as ex:
            dest_bad = _unique_dest(bad, name)
            try:
                shutil.move(src, dest_bad)
            except OSError:
                continue
            rec = {"symbol": "?", "minutes": 0, "bars": 0, "error": str(ex), "src": src, "bad": dest_bad}
            out.append(rec)
            continue
        dest_done = _unique_dest(done, name)
        shutil.move(src, dest_done)
        rec["done"] = dest_done
        out.append(rec)
    return out
