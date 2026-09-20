# Grok (xAI) — 2026-09-20. Whole file. history/drop/ → canonical history/{SYM}_{N}m.csv.
"""Ingest TradingView Supercharts CSVs dropped into the plant.

Does not scrape TradingView. Does not invent ticks. Moves each file to
``history/drop/done/`` after a successful write.
"""
from __future__ import annotations

import os
import re
import shutil
from typing import Any, Dict, List, Optional

from icarus_engine.assets import resolve
from icarus_engine.feeds.bars import detect_granularity, history_path, parse_ohlcv_csv, write_canonical

from .layout import ensure, plant_root

_TF_SUFFIX = re.compile(r"[_-](\d+)m$", re.I)


def infer_symbol(filename: str) -> str:
    stem = os.path.splitext(os.path.basename(filename))[0]
    stem = stem.replace("CME_MINI_", "").replace("CME_MINI:", "").replace("CME:", "")
    stem = _TF_SUFFIX.sub("", stem)
    return resolve(stem).symbol


def ingest_file(path: str, *, root: Optional[str] = None, symbol: Optional[str] = None, tz=None) -> Dict[str, Any]:
    root = plant_root(root)
    ensure(root)
    with open(path, "r", encoding="utf-8-sig") as fh:
        bars = parse_ohlcv_csv(fh.read(), tz=tz)
    if not bars:
        raise ValueError(f"{os.path.basename(path)}: no OHLCV rows")
    sym = symbol or infer_symbol(path)
    minutes = max(1, detect_granularity(bars) // 60)
    dest = history_path(root, sym, minutes)
    n = write_canonical(dest, bars)
    return {"symbol": sym, "minutes": minutes, "bars": n, "dest": dest, "src": os.path.abspath(path)}


def ingest_drop(root: Optional[str] = None) -> List[Dict[str, Any]]:
    """Process every *.csv sitting in history/drop/ (not done/)."""
    paths = ensure(root)
    drop = paths["history/drop"]
    done = paths["history/drop/done"]
    out: List[Dict[str, Any]] = []
    for name in sorted(os.listdir(drop)):
        if not name.lower().endswith(".csv"):
            continue
        src = os.path.join(drop, name)
        if not os.path.isfile(src):
            continue
        rec = ingest_file(src, root=paths["root"])
        shutil.move(src, os.path.join(done, name))
        rec["done"] = os.path.join(done, name)
        out.append(rec)
    return out
