# Grok (xAI) — 2026-09-20. Whole file. Offline doctor. No network, no broker, no paid feed.
"""Offline health checks. No network, no broker, no paid feed."""
from __future__ import annotations

import os
from datetime import date
from typing import Any, Dict, List

from .assets import REGISTRY
from .calendar import holiday_coverage
from .feeds.bars import find_history


def _check(items: List[Dict[str, Any]], name: str, ok: bool, detail: str, *, level: str = "ok") -> None:
    if ok:
        sev = "ok"
    elif level == "warn":
        sev = "warn"
    else:
        sev = "fail"
    items.append({"name": name, "ok": bool(ok), "level": sev, "detail": detail})


def inspect(base_dir: str | None = None, *, today: date | None = None) -> Dict[str, Any]:
    root = os.path.abspath(base_dir or os.getcwd())
    today = today or date.today()
    items: List[Dict[str, Any]] = []

    cov = holiday_coverage("equity")
    days_left = (cov - today).days if cov else None
    if cov is None:
        hol_detail = "holiday table empty"
    else:
        hol_detail = (
            f"last dated entry {cov.isoformat()} ({days_left} days ahead) — "
            "verify on cmegroup.com ~2 weeks before each holiday"
        )
    _check(items, "CME equity holiday table",
           days_left is not None and days_left >= 90,
           hol_detail,
           level="warn")
    _check(items, "CME metals holiday table",
           holiday_coverage("metals") == cov,
           f"metals coverage {holiday_coverage('metals')}",
           level="warn")

    found = []
    for spec in REGISTRY.values():
        path, minutes = find_history(root, spec.symbol, 20)
        if path:
            found.append(f"{spec.symbol}_{minutes}m")
    _check(items, "TradingView chart dumps in history/",
           bool(found),
           (", ".join(found) + " — engine will warm from these instead of delayed Yahoo") if found
           else "none yet. Supercharts → Export chart data → `icarus-engine ingest-bars FILE --symbol NQ`",
           level="warn")

    env_path = os.path.join(root, ".env")
    _check(items, ".env present", os.path.isfile(env_path),
           env_path if os.path.isfile(env_path) else "copy icarus_bridge/.env.example — required only for the Alpaca bridge",
           level="warn")

    secrets: Dict[str, str] = {}
    if os.path.isfile(env_path):
        with open(env_path, encoding="utf-8") as fh:
            for line in fh:
                if "=" in line and not line.strip().startswith("#"):
                    k, _, v = line.partition("=")
                    secrets[k.strip()] = v.strip().strip('"')
        _check(items, "WEBHOOK_SECRET", secrets.get("WEBHOOK_SECRET", "change-me") not in ("", "change-me"),
               "still the default — anyone who hits /webhook can place paper orders",
               level="fail")
        _check(items, "ADMIN_TOKEN", secrets.get("ADMIN_TOKEN", "change-me-too") not in ("", "change-me-too"),
               "still the default",
               level="fail")

    bak = [n for n in ("icarus_engine/runtime_v1.py.bak", "icarus_engine/cli_v1.py.bak") if os.path.isfile(os.path.join(root, n))]
    _check(items, "editor leftovers (.bak)", not bak,
           "none in tree" if not bak else ", ".join(bak) + " — local copies only, do not commit",
           level="warn")

    pine = os.path.join(root, "pine", "ALERT_TEMPLATE.json")
    _check(items, "TradingView alert template", os.path.isfile(pine),
           pine if os.path.isfile(pine) else "missing pine/ALERT_TEMPLATE.json",
           level="warn")

    fails = sum(1 for i in items if not i["ok"] and i["level"] == "fail")
    warns = sum(1 for i in items if not i["ok"] and i["level"] == "warn")
    return {
        "root": root,
        "today": today.isoformat(),
        "holiday_coverage": cov.isoformat() if cov else None,
        "holiday_days_left": days_left,
        "history_dir": os.path.join(root, "history"),
        "items": items,
        "fails": fails,
        "warns": warns,
        "ok": fails == 0,
        "notes": [
            "Yahoo NQ=F is ~10 minutes delayed. A TradingView CME pack does not feed this process.",
            "Export NQ1! 1-minute (or chart-TF) bars from TradingView and ingest them for free parity warm-up.",
            "Live NQ fills require a futures broker; the bridge maps NQ1! → QQQ on Alpaca.",
        ],
    }
