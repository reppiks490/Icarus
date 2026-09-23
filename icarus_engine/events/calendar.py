# Grok (xAI) — 2026-09-22. Whole file.
from __future__ import annotations
import csv, os, math
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

# Fallback only if Inputs cannot import. Prefer Inputs().fomc_dates.
SEED_FOMC_FALLBACK = (
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
    "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-09",
    "2027-07-28", "2027-09-15", "2027-10-27", "2027-12-08",
    "2028-01-26",
)
KIND_HOUR_UTC = {
    "fomc": 18, "cpi": 12, "ppi": 12, "nfp": 12, "pce": 12,
    "gdp": 12, "ism": 14, "earnings": 20, "geopol": 12, "other": 12,
}

def _epoch(date_s: str, hour: int) -> int:
    y, m, d = (int(p) for p in date_s.split("-"))
    return int(datetime(y, m, d, hour, 0, tzinfo=timezone.utc).timestamp())

def fomc_days():
    try:
        from icarus_engine.strategy.inputs import Inputs
        return [s.strip() for s in Inputs().fomc_dates.replace("\n", ",").split(",") if s.strip()]
    except Exception:
        return list(SEED_FOMC_FALLBACK)

def seed_events():
    # CA: 14:00 New York is 19:00 UTC in winter, not a fixed 18:00 UTC.
    return [{"ts": int(datetime.fromisoformat(day).replace(hour=14, tzinfo=ZoneInfo("America/New_York")).timestamp()), "name": "FOMC decision", "kind": "fomc",
             "scope": "rates,equity,metals,dollar", "source": "inputs", "surprise": None}
            for day in fomc_days()]

def load_event_csv(path: Path):
    rows = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        for raw in csv.DictReader(fh):
            keys = {k.lower().strip(): k for k in raw}
            def g(*names):
                for n in names:
                    if n in keys:
                        return (raw[keys[n]] or "").strip()
                return ""
            ts_s = g("ts", "time", "timestamp", "date", "ts_or_date")
            if not ts_s:
                continue
            kind = (g("kind", "type") or "other").lower()
            try:
                ts = float(ts_s)
                if ts > 10_000_000_000:
                    ts /= 1000.0
                ts = int(ts)
            except ValueError:
                dt = datetime.fromisoformat(ts_s.replace("Z", "+00:00"))
                if len(ts_s) == 10:
                    # CA: unknown print time is available only after this NY date.
                    dt = dt.replace(hour=23, minute=59, second=59, tzinfo=ZoneInfo("America/New_York"))
                if dt.tzinfo is None:
                    raise ValueError("event datetime must specify its UTC offset")
                ts = int(dt.timestamp())
            surprise = g("surprise", "actual_minus_consensus")
            if surprise and not math.isfinite(float(surprise)):
                raise ValueError("event surprise must be finite")
            rows.append({"ts": ts, "name": g("name", "event") or kind, "kind": kind,
                         "scope": g("scope", "assets") or "all",
                         "source": os.path.basename(path),
                         "surprise": float(surprise) if surprise else None})
    return rows

def load_events(root=None):
    events = seed_events()
    if root is None:
        return events
    folder = Path(root) / "history" / "events"
    if folder.is_dir():
        for p in sorted(folder.glob("*.csv")):
            if p.name.endswith(".example.csv"):
                continue
            events.extend(load_event_csv(p))
    events.sort(key=lambda e: e["ts"])
    return events

def window_hits(ts, events, pre_sec=6*3600, post_sec=20*3600):
    # CA: a future print (especially its surprise) is never a model feature.
    return [e for e in events if ts - post_sec <= e["ts"] <= ts]


def _scope_matches(event, asset):
    scope = {s.strip().upper() for s in event.get("scope", "all").split(",")}
    if not asset or "ALL" in scope or asset.upper() in scope:
        return True
    group = ("EQUITY" if asset.upper() in {"NQ", "ES", "YM"} else
             "METALS" if asset.upper() in {"GC", "SI", "PL", "PA"} else
             "CRYPTO" if asset.upper() in {"BTC", "BTCF"} else "")
    return group in scope

def event_features(ts, events, asset=""):
    hits = [e for e in window_hits(ts, events) if _scope_matches(e, asset)]
    kinds = {e["kind"] for e in hits}
    return {
        "event_n": len(hits),
        "fomc": int("fomc" in kinds),
        "cpi": int("cpi" in kinds),
        "nfp": int("nfp" in kinds),
        "pce": int("pce" in kinds),
        "earnings": int("earnings" in kinds),
        "geopol": int("geopol" in kinds),
        "any_macro": int(bool(kinds & {"fomc","cpi","ppi","nfp","pce","gdp","ism"})),
        "surprise_abs": max((abs(e["surprise"]) for e in hits if e.get("surprise") is not None), default=0.0),
    }
