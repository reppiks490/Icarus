# Grok (xAI) — 2026-09-20. Whole file. Dummy-proof next-step text + open the drop folder.
"""What to do next. Printed by `icarus-plant setup` and the Windows launcher."""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Dict, List, Optional

from icarus_engine.feeds.bars import find_history

from .layout import ensure, plant_root, repo_root


def preflight(root: Optional[str] = None) -> List[Dict[str, str]]:
    """History presence. No network."""
    root = plant_root(root)
    paths = ensure(root)
    items: List[Dict[str, str]] = []
    path, minutes = find_history(root, "NQ", 20)
    drop = paths["history/drop"]
    if not path:
        items.append({
            "name": "NQ history", "ok": False, "level": "warn",
            "detail": f"none yet — export 1-minute NQ1! from TradingView and copy the CSV into {drop}",
        })
    elif int(minutes or 0) != 1:
        items.append({
            "name": "NQ history", "ok": True, "level": "warn",
            "detail": f"{os.path.basename(path)} warms the strategy; live FileFeed still needs a 1-minute export in {drop}",
        })
    else:
        items.append({
            "name": "NQ history", "ok": True, "level": "ok",
            "detail": path,
        })
    return items


def open_drop(root: Optional[str] = None) -> str:
    """Open history/drop/ in the OS file manager (Explorer on Windows)."""
    drop = ensure(root)["history/drop"]
    try:
        if sys.platform.startswith("win"):
            os.startfile(drop)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", drop])
        else:
            subprocess.Popen(["xdg-open", drop])
    except OSError:
        pass
    return drop


def steps(root: Optional[str] = None) -> str:
    """Numbered instructions. Windows paths when on Windows."""
    root = plant_root(root)
    paths = ensure(root)
    drop = paths["history/drop"]
    if sys.platform.startswith("win"):
        drop_show = drop.replace("/", "\\")
        start_cmd = "start-plant.ps1     (or: icarus-plant start --assets NQ --offline)"
    else:
        drop_show = drop
        start_cmd = "icarus-plant start --assets NQ --offline"
    py = sys.executable
    return f"""Icarus plant setup  (Grok/xAI)
plant root: {root}
repo:       {repo_root()}

1. You are already in the Icarus folder. Python is {py}

2. TradingView (Essential is enough — you do NOT need Plus/Premium for the CSV)
   a. Supercharts → symbol CME_MINI:NQ1!
   b. Timeframe: 1 minute
   c. Scroll the chart LEFT so more history loads
   d. Top toolbar dropdown → Download chart data… → Download

3. Copy that CSV into this folder (File Explorer / Finder):
   {drop_show}

4. Start the plant (leave the window open):
   {start_cmd}

5. On THIS computer, open a browser:
   http://127.0.0.1:8791/
   token: icarus

Each new export MERGE into history/NQ_1m.csv (does not wipe older bars).
This is Brain B. Pine alerts / Alpaca QQQ are Brain A — different path.
A CME pack does not stream into this process.
"""


def write_next_txt(root: Optional[str] = None) -> str:
    root = plant_root(root)
    ensure(root)
    path = os.path.join(root, "NEXT.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(steps(root))
    return path
