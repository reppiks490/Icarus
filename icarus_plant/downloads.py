# Grok (xAI) — 2026-09-20. Whole file. Pull Supercharts CSVs the owner already downloaded.
"""Scan Downloads/Desktop for TradingView chart CSVs. Copy is not scrape.

Does not contact TradingView. Does not invent ticks. Only files that parse
as OHLCV and map to a registry symbol (NQ, ES, …) are ingested. The original
in Downloads is left in place; a seen-log prevents double-merging the same
bytes every poll.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from icarus_engine.assets import REGISTRY

from .drop import infer_symbol, ingest_file
from .layout import ensure, plant_root


def download_dirs() -> List[str]:
    home = os.path.expanduser("~")
    profile = os.environ.get("USERPROFILE") or home
    cands = [
        os.path.join(profile, "Downloads"),
        os.path.join(home, "Downloads"),
        os.path.join(profile, "Desktop"),
        os.path.join(home, "Desktop"),
        os.path.join(profile, "OneDrive", "Downloads"),
        os.path.join(home, "OneDrive", "Downloads"),
    ]
    out: List[str] = []
    seen = set()
    for p in cands:
        ap = os.path.abspath(p)
        if ap in seen or not os.path.isdir(ap):
            continue
        seen.add(ap)
        out.append(ap)
    return out


def _seen_path(root: str) -> str:
    return os.path.join(root, "run", "downloads-seen.json")


def _load_seen(root: str) -> set:
    path = _seen_path(root)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return set(data) if isinstance(data, list) else set()
    except (OSError, ValueError):
        return set()


def _save_seen(root: str, seen: set) -> None:
    os.makedirs(os.path.join(root, "run"), exist_ok=True)
    with open(_seen_path(root), "w", encoding="utf-8") as fh:
        json.dump(sorted(seen), fh)


def _key(path: str) -> str:
    st = os.stat(path)
    return f"{os.path.abspath(path)}|{int(st.st_mtime)}|{st.st_size}"


def ingest_downloads(root: Optional[str] = None, *, dirs: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Ingest new chart CSVs from Downloads/Desktop into the plant history."""
    root = plant_root(root)
    ensure(root)
    seen = _load_seen(root)
    out: List[Dict[str, Any]] = []
    for folder in (dirs if dirs is not None else download_dirs()):
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for name in sorted(names):
            if not name.lower().endswith(".csv"):
                continue
            src = os.path.join(folder, name)
            if not os.path.isfile(src):
                continue
            key = _key(src)
            if key in seen:
                continue
            try:
                sym = infer_symbol(src)
            except ValueError:
                seen.add(key)
                continue
            if sym not in REGISTRY:
                seen.add(key)
                continue
            try:
                rec = ingest_file(src, root=root, symbol=sym)
            except (ValueError, OSError):
                seen.add(key)
                continue
            rec["from_downloads"] = src
            seen.add(key)
            out.append(rec)
    _save_seen(root, seen)
    return out
